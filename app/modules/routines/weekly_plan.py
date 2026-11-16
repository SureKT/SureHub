"""Weekly planning routine: vault + Google Calendar → proposed blocks → approval →
Calendar events + summary note in the vault.

Nothing is written to Calendar or the vault until approve(). Vault access is
read-only except for our own folder (_surehub/), written atomically.

Plan blocks are recognised by a visible convention shared with the Claude mobile
chat (CONVENTIONS_REL in the vault), not by hidden metadata: both planners can
move, edit or delete each other's blocks on equal terms.
"""
import fnmatch
import html
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.modules.routines.engines import run_litellm
from app.modules.routines.models import RoutineRun
from app.modules.routines.service import Outcome, RunContext, load_json
from app.services import calendar as calendar_api
from app.services.calendar import CALENDAR_COLORS

KEY = "weekly_plan"
NOTE_DIR = "_surehub/planificacion"
MAX_FILE_CHARS = 6000
MAX_BLOCK_HOURS = 12
MIN_BLOCK_MINUTES = 30

# (label, glob relative to the vault, mode). Modes: full | open_tasks | active_plan | latest
VAULT_INPUTS = [
    ("Tareas pendientes", "Tareas.md", "open_tasks"),
    ("Plan activo", "planificacion/*.md", "active_plan"),
    ("Última revisión semanal", "planificacion/revisiones/*.md", "latest"),
    ("Proyecto propio", "proyecto-propio/_punto-de-partida.md", "full"),
    ("Búsqueda de empleo", "job-search/_dashboard.md", "full"),
    ("Patrones de eventos", "_surehub/contexto-eventos.md", "full"),
]
REVISION_GLOB = "planificacion/revisiones/*.md"
CONVENTIONS_REL = "_surehub/convenciones-calendario.md"

DEFAULT_CONVENTIONS = """---
tipo: convencion
---

# Convenciones del calendario

Las usan por igual SureHub (rutina de planificación) y el chat de Claude del móvil.
Editar aquí vale para los dos.

## Bloques de plan
- Título: `Área: tarea concreta`. Ej.: `App pádel: emparejamientos rotativos + tests`,
  `Dinero: 3 candidaturas`, `Aprender: WebSockets en FastAPI`.
- Descripción: 1-3 líneas con el detalle concreto (qué hacer, criterio de hecho).
- Sin recurrencia. Mínimo 30 minutos.
- Las citas y compromisos reales NO usan el formato `Área:` (ej. `Médico`,
  `Reunión cliente instituto (chatbot)`), así nadie los mueve.

## Colores (colorId de Google Calendar)
- 3 Grape: coach / terapia
- 4 Flamingo: proyectos, formación, aprender
- 5 Banana: social y ocio
- 8 Graphite: dinero, búsqueda de empleo, revisión, por defecto
- 9 Blueberry: gimnasio
- 10 Basil: pádel, escalada, deporte de club
- 11 Tomato: salud

## Movibles
Eventos sin recurrencia cuyo título encaja con alguno de estos patrones (`*` = cualquier
texto, sin distinguir mayúsculas). Al replanificar se pueden mover, editar o borrar;
todo lo demás (recurrentes incluidos) es fijo.
- `*: *`
- `Gym*`
"""

# Syncthing internals and conflict copies must never be read as content.
_IGNORED_DIRS = {".stfolder", ".stversions", ".obsidian", ".trash"}

THEMES = {
    "coach": "coach o terapia (Grape)",
    "formacion": "proyectos, formación, aprender (Flamingo)",
    "social": "social y ocio (Banana)",
    "padel": "pádel, escalada, deporte de club (Basil)",
    "gimnasio": "gimnasio (Blueberry)",
    "salud": "salud (Tomato)",
    "default": "dinero, búsqueda de empleo, revisión, por defecto (Graphite)",
}
THEME_ICONS = {"coach": "🟣", "formacion": "🩷", "social": "🟡", "padel": "🟢",
               "gimnasio": "🔵", "salud": "🔴", "default": "⚫"}
DAYS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
DAYS_ES_LONG = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

SYSTEM = (
    "Eres el planificador semanal de Gerard. Propones bloques concretos en su calendario. "
    "Respondes SOLO con un objeto JSON válido, sin texto antes ni después."
)

PROMPT = """Planifica {span}: del {start} ({start_day}) al {end} ({end_day}). Zona horaria Europe/Madrid.{not_before}

## Reglas
- Los eventos fijos (incluidos los recurrentes) no se mueven: no los solapes ni los dupliques.
- Los bloques de trabajo de cada día (proyecto, dinero/candidaturas, aprender) los propones tú siguiendo el día tipo del plan activo, pero encajados alrededor de los eventos fijos: si un evento ocupa la franja habitual, mueve o acorta el bloque en vez de perderlo.
- Bloques concretos y accionables: qué proyecto o tarea en cada hueco, según tareas pendientes y prioridades de las notas.
- Sigue al pie de la letra las convenciones del calendario (formato de título, descripción, colores).
- Respeta las prioridades del plan activo y de la última revisión semanal si existen.
- Deja huecos libres: no rellenes cada minuto. NUNCA crees bloques de pausa, comida, descanso, "libre" ni recordatorios: un hueco sin plan se queda vacío. Si la semana ya está bien cubierta, propón pocos bloques.
- Cada bloque dura al menos 30 minutos.
- Títulos cortos en español (máx. 60 caracteres).
- theme decide el color; debe ser una de estas claves:
{themes}

## Convenciones del calendario
{conventions}

## Formato de respuesta (JSON)
{{"summary": "2-4 frases: foco de la semana y por qué", "blocks": [{{"title": "Área: tarea", "start": "YYYY-MM-DDTHH:MM", "end": "YYYY-MM-DDTHH:MM", "theme": "...", "description": "1-3 líneas de detalle"}}]}}

## Eventos fijos en el calendario
{events}
{current}
## Notas del vault
{inputs}
"""

ADJUST = """
## Propuesta anterior
{previous}

## Corrección de Gerard
{correction}

Aplica la corrección cambiando solo lo necesario; conserva el resto de bloques tal cual.
"""

CURRENT_PLAN = """
## Plan vigente (bloques movibles ya en el calendario, de SureHub o del chat)
Mantenlos si siguen encajando, muévelos si algo choca, o quítalos.
`blocks` debe contener TODO lo que quieras que quede: un bloque que mantengas igual
va con el mismo título, inicio y fin exactos (así no se recrea).
{blocks}
"""

SLOT_MINUTES = 30
MIN_REMAINING = timedelta(hours=2)


# ── window ──────────────────────────────────────────────────────────────────

def _next_slot(now: datetime) -> datetime:
    naive = now.replace(tzinfo=None, second=0, microsecond=0)
    extra = (-naive.minute) % SLOT_MINUTES or SLOT_MINUTES
    return naive + timedelta(minutes=extra)


def _label(start: date) -> str:
    year, week, _ = start.isocalendar()
    return f"{year}-W{week:02d}"


def plan_window(now: datetime, scope: str = "rest") -> tuple[date, date, str, datetime]:
    """(start, end, week label, earliest block start).

    rest: from the next 30-min slot until Sunday — replanning works any day, any
          hour. With under MIN_REMAINING left in the week it falls through to next.
    next: the whole next week (Monday→Sunday)."""
    today = now.date()
    if scope == "rest":
        earliest = _next_slot(now)
        end = today + timedelta(days=6 - today.weekday())
        week_over = datetime.combine(end + timedelta(days=1), datetime.min.time())
        if week_over - earliest >= MIN_REMAINING:
            return today, end, _label(today), earliest
    start = today + timedelta(days=7 - today.weekday())
    return start, start + timedelta(days=6), _label(start), datetime.combine(start, datetime.min.time())


def resolve_scope(ctx: RunContext) -> str:
    """Manual runs choose (default: rest of the week). Automatic runs on Sunday (after
    the review) plan the next week; on Monday morning, the week that just started."""
    if ctx.options.get("scope") in ("rest", "next"):
        return ctx.options["scope"]
    if ctx.trigger in ("scheduled", "catch_up", "after_review") and ctx.now.weekday() == 6:
        return "next"
    return "rest"


def _fmt_day(d: date) -> str:
    return f"{DAYS_ES[d.weekday()]} {d.day} {MONTHS_ES[d.month - 1]}"


# ── vault inputs ────────────────────────────────────────────────────────────

def is_ignored(path: Path, vault: Path) -> bool:
    rel = path.relative_to(vault)
    if any(part in _IGNORED_DIRS for part in rel.parts):
        return True
    return ".sync-conflict-" in path.name or path.name.startswith((".syncthing.", "~syncthing~"))


def _vault_files(vault: Path, pattern: str) -> list[Path]:
    return sorted(p for p in vault.glob(pattern) if p.is_file() and not is_ignored(p, vault))


def _frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def _open_tasks(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip().startswith("- [ ]"))


def read_inputs(vault: Path) -> list[tuple[str, str, str]]:
    """[(label, relpath, content)] read-only, capped per file."""
    out = []
    for label, pattern, mode in VAULT_INPUTS:
        files = _vault_files(vault, pattern)
        if mode == "latest":
            files = files[-1:]
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            if mode == "active_plan" and _frontmatter(text).get("estado") != "activo":
                continue
            if mode == "open_tasks":
                text = _open_tasks(text)
            if text.strip():
                out.append((label, str(path.relative_to(vault)), text[:MAX_FILE_CHARS]))
    return out


def revision_is_fresh(vault: Path, start: date) -> bool:
    for path in reversed(_vault_files(vault, REVISION_GLOB)):
        try:
            return date.fromisoformat(path.stem[:10]) >= start - timedelta(days=3)
        except ValueError:
            continue
    return False


def ensure_conventions(vault: Path) -> Path:
    """Create the shared conventions note once (our own folder). Never overwritten:
    after the first write it belongs to the user, edited from Obsidian."""
    path = vault / CONVENTIONS_REL
    if not path.exists():
        write_note_atomic(vault, CONVENTIONS_REL, DEFAULT_CONVENTIONS)
    return path


def load_conventions(vault: Path) -> tuple[str, list[str]]:
    """(note text, movable title patterns from its `## Movibles` section)."""
    path = vault / CONVENTIONS_REL
    text = path.read_text(encoding="utf-8") if path.exists() else DEFAULT_CONVENTIONS
    patterns, in_section = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            in_section = line[3:].strip().lower() == "movibles"
            continue
        m = re.match(r"^\s*-\s*`([^`]+)`", line)
        if in_section and m:
            patterns.append(m.group(1))
    return text, patterns


def is_movable_title(title: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(title.lower(), p.lower()) for p in patterns)


# ── prompt / parsing ────────────────────────────────────────────────────────

def _fmt_events(events: list[dict]) -> str:
    if not events:
        return "(ninguno)"
    lines = []
    for ev in events:
        tag = " (recurrente)" if ev.get("recurring") else ""
        if ev["all_day"]:
            lines.append(f"- {ev['start']} (todo el día): {ev['summary']}{tag}")
        else:
            lines.append(f"- {ev['start'][:16]} → {ev['end'][11:16]}: {ev['summary']}{tag}")
    return "\n".join(lines)


def split_events(events: list[dict], earliest: datetime,
                 patterns: list[str]) -> tuple[list[dict], list[dict]]:
    """(fixed, movable). Movable = plan block by the shared convention (title pattern),
    not recurring, timed and not yet started — whoever created it (SureHub or chat)."""
    fixed, movable = [], []
    for ev in events:
        ok = (not ev.get("recurring") and not ev["all_day"]
              and datetime.fromisoformat(ev["start"]) >= earliest
              and is_movable_title(ev["summary"], patterns))
        (movable if ok else fixed).append(ev)
    return fixed, movable


def _fmt_current(movable: list[dict]) -> str:
    if not movable:
        return ""
    lines = []
    for e in movable:
        desc = " — " + " ".join(e["description"].split())[:160] if e.get("description") else ""
        lines.append(f"- {e['start'][:16]} → {e['end'][11:16]}: {e['summary']}{desc}")
    return CURRENT_PLAN.format(blocks="\n".join(lines))


def build_prompt(start: date, end: date, label: str, inputs: list[tuple[str, str, str]],
                 events: list[dict], previous: dict | None = None,
                 correction: str | None = None, movable: list[dict] | None = None,
                 earliest: datetime | None = None, conventions: str = DEFAULT_CONVENTIONS) -> str:
    themes = "\n".join(f"  - {k}: {v}" for k, v in THEMES.items())
    notes = "\n\n".join(f"### {lbl} ({rel})\n{content}" for lbl, rel, content in inputs) or "(sin notas)"
    whole_week = start.weekday() == 0 and (earliest is None or earliest.time() == datetime.min.time())
    span = f"la semana {label}" if whole_week else f"el resto de la semana {label}"
    nb = (f"\nAhora son las {earliest:%H:%M} del {earliest:%d/%m}: ningún bloque puede empezar antes."
          if earliest and earliest.time() != datetime.min.time() else "")
    prompt = PROMPT.format(span=span, start=start.isoformat(), end=end.isoformat(),
                           start_day=DAYS_ES_LONG[start.weekday()], end_day=DAYS_ES_LONG[end.weekday()],
                           not_before=nb, themes=themes, conventions=conventions.strip(),
                           events=_fmt_events(events),
                           current=_fmt_current(movable or []), inputs=notes)
    if previous is not None and correction:
        prev = {"summary": previous.get("summary", ""), "blocks": previous.get("blocks", [])}
        prompt += ADJUST.format(previous=json.dumps(prev, ensure_ascii=False, indent=1),
                                correction=correction)
    return prompt


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("La respuesta del modelo no contiene JSON")
    data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise ValueError("JSON del modelo no es un objeto")
    return data


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


def parse_proposal(text: str, start: date, end: date, events: list[dict],
                   earliest: datetime | None = None) -> dict:
    """Validate the model output in code instead of trusting the prompt: drop blocks
    that are malformed, outside the window, too long or overlapping real events."""
    data = _extract_json(text)
    busy = [(datetime.fromisoformat(e["start"]), datetime.fromisoformat(e["end"]))
            for e in events if not e["all_day"]]
    blocks, dropped = [], []
    for raw in data.get("blocks") or []:
        try:
            title = str(raw["title"]).strip()[:80]
            s = datetime.fromisoformat(str(raw["start"]))
            e = datetime.fromisoformat(str(raw["end"]))
        except (KeyError, TypeError, ValueError):
            dropped.append({"title": str(raw.get("title", "?")) if isinstance(raw, dict) else "?",
                            "reason": "formato inválido"})
            continue
        s, e = s.replace(tzinfo=None), e.replace(tzinfo=None)
        reason = None
        if not title:
            reason = "sin título"
        elif e - s < timedelta(minutes=MIN_BLOCK_MINUTES) or e - s > timedelta(hours=MAX_BLOCK_HOURS):
            reason = "duración inválida"
        elif not (start <= s.date() <= end):
            reason = "fuera de la semana"
        elif earliest and s < earliest:
            reason = "en el pasado"
        elif any(_overlaps(s, e, bs, be) for bs, be in busy):
            reason = "se solapa con un evento existente"
        if reason:
            dropped.append({"title": title or "?", "reason": reason})
            continue
        theme = str(raw.get("theme", "default")).strip().lower()
        blocks.append({
            "title": title,
            "start": s.isoformat(timespec="seconds"),
            "end": e.isoformat(timespec="seconds"),
            "theme": theme if theme in CALENDAR_COLORS else "default",
            "description": str(raw.get("description") or raw.get("notes") or "").strip()[:500],
        })
        busy.append((s, e))  # also prevents the model's own blocks from overlapping
    blocks.sort(key=lambda b: b["start"])
    return {"summary": str(data.get("summary") or "").strip(), "blocks": blocks, "dropped": dropped}


# ── routine entry point ─────────────────────────────────────────────────────

def run(session: Session, ctx: RunContext) -> Outcome:
    vault = Path(settings.OBSIDIAN_VAULT_PATH)
    previous = load_json(ctx.parent.output) if ctx.parent else None
    if previous:
        # Adjusting keeps the same window even if the correction arrives later.
        start, end, label = (date.fromisoformat(previous["start"]),
                             date.fromisoformat(previous["end"]), previous["week"])
        earliest = datetime.fromisoformat(previous["not_before"]) if previous.get("not_before") \
            else datetime.combine(start, datetime.min.time())
    else:
        start, end, label, earliest = plan_window(ctx.now, resolve_scope(ctx))

    # Calendar is mandatory: planning blind would propose blocks over real events.
    events = calendar_api.list_events(start, end)
    ensure_conventions(vault)
    conventions, patterns = load_conventions(vault)
    fixed, movable = split_events(events, earliest, patterns)
    inputs = read_inputs(vault)
    warnings = []
    if not revision_is_fresh(vault, start):
        warnings.append("No hay revisión semanal reciente: el plan no la tiene en cuenta.")

    prompt = build_prompt(start, end, label, inputs, fixed, previous, ctx.correction,
                          movable=movable, earliest=earliest, conventions=conventions)
    result = run_litellm(prompt, system=SYSTEM, function=KEY)
    proposal = parse_proposal(result.text, start, end, fixed, earliest)
    if not proposal["blocks"]:
        raise ValueError("El modelo no propuso ningún bloque válido")

    output = {
        "week": label, "start": start.isoformat(), "end": end.isoformat(),
        "not_before": earliest.isoformat(timespec="minutes"),
        "events_considered": len(fixed), "inputs": [rel for _, rel, _ in inputs],
        "warnings": warnings, "correction": ctx.correction,
        "replaces": [{k: ev.get(k) for k in ("id", "summary", "start", "end", "color_id", "description")}
                     for ev in movable],
        **proposal,
    }
    return Outcome(status="awaiting_approval", output=output, cost_usd=result.cost_usd)


def _same(block: dict, ev: dict) -> bool:
    return (block["title"], block["start"], block["end"]) == (ev["summary"], ev["start"], ev["end"])


# ── rendering ───────────────────────────────────────────────────────────────

def _range_label(output: dict) -> str:
    s, e = date.fromisoformat(output["start"]), date.fromisoformat(output["end"])
    return f"{_fmt_day(s)} – {_fmt_day(e)}"


def _by_day(blocks: list[dict]) -> dict[str, list[dict]]:
    days: dict[str, list[dict]] = {}
    for b in blocks:
        days.setdefault(b["start"][:10], []).append(b)
    return days


def render_proposal(output: dict) -> str:
    """Telegram HTML (escaped: titles come from the model)."""
    esc = html.escape
    lines = [f"🗓 <b>Plan {esc(output['week'])}</b> · {esc(_range_label(output))}"]
    if output.get("summary"):
        lines.append(f"<i>{esc(output['summary'])}</i>")
    for day, blocks in _by_day(output["blocks"]).items():
        lines.append(f"\n<b>{esc(_fmt_day(date.fromisoformat(day)))}</b>")
        for b in blocks:
            icon = THEME_ICONS.get(b["theme"], "⚫")
            lines.append(f"{icon} {b['start'][11:16]}–{b['end'][11:16]} {esc(b['title'])}")
    lines.append(f"\n{len(output['blocks'])} bloques · {output.get('events_considered', 0)} eventos fijos respetados")
    replaces = output.get("replaces") or []
    if replaces:
        kept = sum(1 for ev in replaces if any(_same(b, ev) for b in output["blocks"]))
        lines.append(f"♻️ Reajusta el plan vigente: {kept} bloques se mantienen, "
                     f"{len(replaces) - kept} se sustituyen")
    if output.get("dropped"):
        lines.append(f"↪️ {len(output['dropped'])} descartados (solapes o formato)")
    for w in output.get("warnings", []):
        lines.append(f"⚠️ {esc(w)}")
    text = "\n".join(lines)
    return text if len(text) <= 3900 else text[:3890] + "\n…"


def note_relpath(week: str) -> str:
    return f"{NOTE_DIR}/{week}.md"


def _blocks_markdown(blocks: list[dict]) -> list[str]:
    lines = []
    for day, day_blocks in _by_day(blocks).items():
        d = date.fromisoformat(day)
        lines.append(f"## {DAYS_ES_LONG[d.weekday()]} {d.day}")
        for b in day_blocks:
            extra = f" — {' '.join(b['description'].split())}" if b.get("description") else ""
            lines.append(f"- {b['start'][11:16]}–{b['end'][11:16]} · {b['title']} `{b['theme']}`{extra}")
        lines.append("")
    return lines


def replan_section(output: dict, run_id: int) -> str:
    nb = datetime.fromisoformat(output["not_before"])
    lines = ["", f"# Reajuste desde {_fmt_day(nb.date())} {nb:%H:%M} (run {run_id})", ""]
    if output.get("correction"):
        lines += [f"> Corrección: {output['correction']}", ""]
    if output.get("summary"):
        lines += [output["summary"], ""]
    return "\n".join(lines + _blocks_markdown(output["blocks"]))


def note_markdown(output: dict, run_id: int) -> str:
    lines = [
        "---",
        "tipo: plan-semanal",
        f"semana: {output['week']}",
        f"inicio: {output['start']}",
        f"fin: {output['end']}",
        f"generado: SureHub (rutina {KEY}, run {run_id})",
        "---",
        "",
        f"# Plan {output['week']} · {_range_label(output)}",
        "",
    ]
    if output.get("summary"):
        lines += [output["summary"], ""]
    lines += _blocks_markdown(output["blocks"])
    if output.get("warnings"):
        lines += ["## Avisos", *[f"- {w}" for w in output["warnings"]], ""]
    return "\n".join(lines)


def write_note_atomic(vault: Path, relpath: str, content: str) -> Path:
    """Temp file + os.replace in the same dir. The `.syncthing.*.tmp` name is in
    Syncthing's built-in ignore set, so a half-written file is never synced."""
    target = vault / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".syncthing.{target.name}.tmp"
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, target)
    return target


# ── side effects (only after approval) ──────────────────────────────────────

def _save_result(session: Session, run: RoutineRun, result: dict) -> None:
    run.result = json.dumps(result, ensure_ascii=False)
    session.add(run)
    session.commit()


def _theme_for_color(color_id: str | None) -> str:
    return next((k for k, v in CALENDAR_COLORS.items() if v == color_id), "default")


def approve(session: Session, run: RoutineRun, vault: Path) -> dict:
    """Create the new blocks, then remove the replaced movable ones (create first so a
    failure never leaves the week empty). Every step is persisted as it happens, so a
    retry after a partial failure neither duplicates nor re-deletes anything."""
    output = load_json(run.output)
    result = load_json(run.result) or {}
    created: dict[str, str] = result.setdefault("created", {})
    kept: dict[str, str] = result.setdefault("kept", {})
    removed: list[dict] = result.setdefault("removed", [])
    run.status = "approving"
    _save_result(session, run, result)

    replaces = output.get("replaces") or []
    for i, b in enumerate(output["blocks"]):
        if str(i) in created or str(i) in kept:
            continue
        same = next((ev for ev in replaces if _same(b, ev) and ev["id"] not in kept.values()), None)
        if same:
            kept[str(i)] = same["id"]   # unchanged block: keep the event, no churn
        else:
            event_id, _ = calendar_api.create_event(
                b["title"], b["start"], b["end"], False, b["theme"],
                private={"surehub_run": run.id, "surehub_routine": KEY},
                description=b.get("description", ""),
            )
            created[str(i)] = event_id
        _save_result(session, run, result)

    done = {ev["id"] for ev in removed}
    for ev in replaces:
        if ev["id"] in kept.values() or ev["id"] in done:
            continue
        calendar_api.delete_event(ev["id"])
        removed.append(ev)
        _save_result(session, run, result)

    rel = note_relpath(output["week"])
    if "note" not in result:
        path = vault / rel
        if output.get("replaces") and path.exists():
            previous_note = path.read_text(encoding="utf-8")
            result["note_previous"] = previous_note
            content = previous_note.rstrip("\n") + "\n" + replan_section(output, run.id)
        else:
            content = note_markdown(output, run.id)
        write_note_atomic(vault, rel, content)
        result["note"] = rel
    run.status = "approved"
    _save_result(session, run, result)
    return result


def undo(session: Session, run: RoutineRun, vault: Path) -> int:
    """Back to the state before approving: delete what this run created, recreate what
    it replaced, restore the previous note. Returns how many events were deleted."""
    result = load_json(run.result) or {}
    created: dict[str, str] = result.get("created", {})
    count = result.get("undo_deleted", 0)
    for idx in list(created):
        calendar_api.delete_event(created[idx])
        del created[idx]
        count += 1
        result["undo_deleted"] = count
        _save_result(session, run, result)

    removed: list[dict] = result.get("removed", [])
    while removed:
        ev = removed[0]
        calendar_api.create_event(ev["summary"], ev["start"], ev["end"], False,
                                  _theme_for_color(ev.get("color_id")),
                                  description=ev.get("description") or "")
        removed.pop(0)
        _save_result(session, run, result)

    if result.get("note"):
        if result.get("note_previous") is not None:
            write_note_atomic(vault, result["note"], result["note_previous"])
        else:
            (vault / result["note"]).unlink(missing_ok=True)
    run.status = "undone"
    _save_result(session, run, result)
    return count
