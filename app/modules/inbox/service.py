import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from sqlmodel import Session, select

from app.modules.inbox.models import InboxItem

VALID_CATEGORIES = ("task", "note", "event", "uncertain")
VALID_THEMES = ("coach", "formacion", "social", "gimnasio", "padel", "default")

CLASSIFY_PROMPT = (
    "Clasifica esta nota personal y extrae el texto accionable.\n"
    "Categorías:\n"
    "- task: algo para hacer o resolver. Incluye: listas de compras, bugs ('falla', 'hay un problema'), "
    "deseos de mejora ('quiero que', 'sería bueno'), investigar, cualquier acción pendiente.\n"
    "- note: información o idea puramente informativa, sin acción implícita.\n"
    "- event: algo con fecha/hora concreta (cita, cena, partido, clase...).\n"
    "- uncertain: ambigua o muy corta.\n"
    'Responde SOLO un JSON: {{"category": "task|note|event|uncertain", "proposed_text": "<texto>"}}.\n'
    "Para task, proposed_text es la tarea en imperativo breve.\n\n"
    "Nota:\n{text}"
)

EVENT_PROMPT = (
    "Extrae el evento de esta nota personal. Hoy es {today}.\n"
    "Responde SOLO un JSON: "
    '{{"summary": "<título breve>", "start": "<ISO>", "end": "<ISO>", '
    '"all_day": true|false, "theme": "<tema>"}}.\n'
    "Reglas:\n"
    "- start/end en hora LOCAL ISO sin zona horaria: 'YYYY-MM-DDTHH:MM:SS'.\n"
    "- Si all_day=true, usa solo fecha 'YYYY-MM-DD' y start==end (el día del evento).\n"
    "- Duración explícita ('2h', '90 min') -> end = start + duración.\n"
    "- Inicio y fin dados ('de 18 a 20') -> úsalos tal cual.\n"
    "- Solo hora de inicio -> end = start + 1 hora.\n"
    "- Sin ninguna hora -> all_day=true.\n"
    "- theme: una de [coach, formacion, social, gimnasio, padel]; si no encaja, 'default'.\n\n"
    "Nota:\n{text}"
)


def _parse_classification(raw: str) -> tuple[str, str]:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return ("uncertain", "")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return ("uncertain", "")
    category = data.get("category", "uncertain")
    if category not in VALID_CATEGORIES:
        category = "uncertain"
    return (category, str(data.get("proposed_text", "")).strip())


def classify_note(text: str, llm: Callable[[str], str]) -> tuple[str, str]:
    """Returns (category, proposed_text). Never raises: on any failure → uncertain
    with the original text, so capture is never lost nor acted on blindly."""
    try:
        category, proposed = _parse_classification(llm(CLASSIFY_PROMPT.format(text=text)))
    except Exception:
        return ("uncertain", text.strip())
    return (category, proposed or text.strip())


def _parse_event(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    summary = str(data.get("summary", "")).strip()
    start = str(data.get("start", "")).strip()
    if not (summary and start):
        return None
    end = str(data.get("end", "")).strip() or start
    theme = data.get("theme", "default")
    if theme not in VALID_THEMES:
        theme = "default"
    return {
        "summary": summary,
        "start": start,
        "end": end,
        "all_day": bool(data.get("all_day", False)),
        "theme": theme,
    }


def extract_event(text: str, today: str, llm: Callable[[str], str]) -> dict | None:
    """Returns {summary,start,end,all_day,theme} or None on any failure
    (caller treats None as 'not a usable event' → stays uncertain)."""
    try:
        return _parse_event(llm(EVENT_PROMPT.format(today=today, text=text)))
    except Exception:
        return None


def _today_str() -> str:
    from zoneinfo import ZoneInfo
    from app.config import settings
    now = datetime.now(ZoneInfo(settings.TIMEZONE))
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return f"{now:%Y-%m-%d} ({dias[now.weekday()]})"


def _read_note(path: Path) -> tuple[str, str]:
    """Returns (body, source) from a note with YAML-ish frontmatter."""
    raw = path.read_text(encoding="utf-8")
    source = ""
    body = raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) == 3:
            front, body = parts[1], parts[2]
            for line in front.splitlines():
                if line.startswith("source:"):
                    source = line.split(":", 1)[1].strip()
    return body.strip(), source


def scan_inbox(session: Session, vault_path, llm: Callable[[str], str],
               event_llm: Callable[[str], str] | None = None) -> list[InboxItem]:
    inbox = Path(vault_path) / "inbox"
    if not inbox.exists():
        return []
    seen = {i.filename for i in session.exec(select(InboxItem)).all()}
    created: list[InboxItem] = []
    for path in sorted(inbox.glob("*.md")):
        if path.name in seen:
            continue
        body, source = _read_note(path)
        category, proposed = classify_note(body, llm)
        event_fields = {}
        if category == "event":
            data = extract_event(body, _today_str(), event_llm) if event_llm else None
            if data:
                proposed = data["summary"]
                event_fields = {
                    "event_start": data["start"],
                    "event_end": data["end"],
                    "all_day": data["all_day"],
                    "theme": data["theme"],
                }
            else:
                category = "uncertain"
        item = InboxItem(
            filename=path.name,
            excerpt=body[:200],
            source=source,
            category=category,
            proposed_text=proposed or body[:200],
            status="pending",
            **event_fields,
        )
        session.add(item)
        created.append(item)
    session.commit()
    for item in created:
        session.refresh(item)
    return created


def _move(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    counter = 2
    while dest.exists():
        dest = dest_dir / f"{src.stem}-{counter}{src.suffix}"
        counter += 1
    src.rename(dest)
    return dest


def _append_task(vault_path, text: str, filename: str) -> None:
    tasks_file = Path(vault_path) / "Tareas.md"
    backlink = Path(filename).stem
    with tasks_file.open("a", encoding="utf-8") as f:
        f.write(f"- [ ] {text}  ([[{backlink}]])\n")


def pending_items(session: Session) -> list[InboxItem]:
    return session.exec(select(InboxItem).where(InboxItem.status == "pending")).all()


def get_item(session: Session, item_id: int) -> InboxItem | None:
    return session.get(InboxItem, item_id)


def apply_item(session: Session, item: InboxItem, vault_path, action: str,
               override_text: str | None = None) -> InboxItem:
    vault = Path(vault_path)
    note_path = vault / "inbox" / item.filename
    if action == "task":
        _append_task(vault_path, override_text or item.proposed_text, item.filename)
        if note_path.exists():
            _move(note_path, vault / "archivo")
        item.status = "approved"
    elif action == "note":
        if note_path.exists():
            _move(note_path, vault / "archivo")
        item.status = "archived"
    elif action == "discard":
        if note_path.exists():
            _move(note_path, vault / "inbox" / "_descartado")
        item.status = "discarded"
    else:
        raise ValueError(f"unknown action: {action}")
    item.resolved_at = datetime.utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def apply_event(session: Session, item: InboxItem, vault_path,
                create_event: Callable[..., tuple[str, str]]) -> tuple[InboxItem, str]:
    """Crea el evento (create_event inyectado, mockeable), archiva la nota y marca
    el item como scheduled. Devuelve (item, html_link)."""
    vault = Path(vault_path)
    note_path = vault / "inbox" / item.filename
    event_id, link = create_event(
        item.proposed_text, item.event_start, item.event_end, item.all_day, item.theme
    )
    if note_path.exists():
        _move(note_path, vault / "archivo")
    item.status = "scheduled"
    item.calendar_event_id = event_id
    item.resolved_at = datetime.utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item, link


def apply_suggested(session: Session, vault_path) -> dict:
    counts = {"task": 0, "note": 0}
    for item in pending_items(session):
        if item.category in ("task", "note"):
            apply_item(session, item, vault_path, item.category)
            counts[item.category] += 1
    return counts
