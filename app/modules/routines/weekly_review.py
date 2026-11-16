"""Weekly review routine: the server asks the review questions on Sunday (Telegram),
the user answers in one voice/text message whenever they can, and the answers are
saved as a new note in the vault. The weekly plan is launched right after.

The questions are read live from the user's own note (QUESTIONS_REL) so editing
them in Obsidian changes the review without a deploy.
"""
import html
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.modules.routines.engines import run_litellm
from app.modules.routines.models import RoutineRun
from app.modules.routines.service import Outcome, RunContext, load_json
from app.modules.routines.weekly_plan import (
    MONTHS_ES, REVISION_GLOB, _extract_json, _vault_files, write_note_atomic,
)

logger = logging.getLogger("surehub.routines")

KEY = "weekly_review"
QUESTIONS_REL = "Personal/Revisión semanal.md"
REVIEW_DIR = "planificacion/revisiones"
MAX_EXAMPLE_CHARS = 4000

DEFAULT_QUESTIONS = """### 🧭 ¿Estoy viviendo en la dirección que elegí?

### Cuerpo
- ¿Me he movido?
- ¿He hecho deporte?
### Mente/Futuro
- ¿He programado/aprendido?
- ¿He hecho algo por mi futuro?
### Vida
- ¿He visto a gente?
- ¿He disfrutado?
### Entorno
- ¿Estoy cuidando mi espacio?

> **¿Qué cambiaría esta semana para que la próxima sea un poquito mejor?**
"""

SYSTEM = "Ordenas respuestas dictadas por voz. Respondes SOLO con un objeto JSON válido."

PROMPT = """Gerard ha respondido de golpe (probablemente por voz) a su revisión semanal.
Ordena sus respuestas por pregunta.

## Reglas
- Conserva sus palabras y su tono, en primera persona. Solo limpia muletillas y repeticiones del dictado.
- No inventes nada. Si una pregunta no tiene respuesta, pon "(sin respuesta)".
- Si decidió algo concreto (horarios, cambios), destácalo con "→ Decidido: …".
- Usa los mismos encabezados que las preguntas y termina con la pregunta final en cita (>) y su respuesta.
- Sigue el estilo de la revisión anterior si la hay.

## Formato de respuesta (JSON)
{{"body": "markdown de las secciones (sin título ni frontmatter)", "summary": "5-8 líneas en texto plano para dárselas a quien planifique la semana: estado, qué funcionó, qué no, decisiones y prioridades para la semana que viene"}}

## Preguntas
{questions}

## Revisión anterior (estilo)
{example}

## Respuestas de Gerard
{answer}
"""


def load_questions(vault: Path) -> str:
    path = vault / QUESTIONS_REL
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return DEFAULT_QUESTIONS.strip()


def run(session: Session, ctx: RunContext) -> Outcome:
    vault = Path(settings.OBSIDIAN_VAULT_PATH)
    return Outcome(status="awaiting_input",
                   output={"date": ctx.now.date().isoformat(), "questions": load_questions(vault)})


def render_questions(output: dict) -> str:
    """Telegram HTML from the questions note (markdown headings/quotes → bold/italic)."""
    lines = ["🧭 <b>Revisión semanal</b>", ""]
    for raw in output["questions"].splitlines():
        line = raw.strip()
        if not line or line == "---":
            continue
        clean = html.escape(re.sub(r"\*\*(.+?)\*\*", r"\1", line.lstrip("#> ").strip()))
        if line.startswith("#"):
            lines.append(f"\n<b>{clean}</b>")
        elif line.startswith(">"):
            lines.append(f"\n<i>{clean}</i>")
        else:
            lines.append(clean)
    lines.append("\n🎤 Responde todo de golpe con un audio o texto: pulsa <b>Responder</b> "
                 "o contesta a este mensaje. Luego preparo el plan de la semana.")
    return "\n".join(lines)


def _note_path(vault: Path, day: str) -> str:
    """New file always: never overwrite an existing note (Syncthing rule)."""
    rel = f"{REVIEW_DIR}/{day}.md"
    n = 2
    while (vault / rel).exists():
        rel = f"{REVIEW_DIR}/{day}-{n}.md"
        n += 1
    return rel


def _latest_example(vault: Path) -> str:
    files = _vault_files(vault, REVISION_GLOB)
    return files[-1].read_text(encoding="utf-8")[:MAX_EXAMPLE_CHARS] if files else "(no hay)"


def _note(day: str, body: str) -> str:
    d = date.fromisoformat(day)
    return "\n".join([
        "---", "tipo: revision", f"fecha: {day}", "generado: SureHub (rutina weekly_review)", "---", "",
        f"# Revisión semanal — {d.day} {MONTHS_ES[d.month - 1]} {d.year}", "",
        "Respuestas de Gerard (dictado, ordenado por pregunta).", "",
        body.strip(), "",
    ])


def complete(session: Session, run: RoutineRun, answer: str, vault: Path) -> dict:
    """Structure the answer, write the note, mark the run done. If the LLM fails the
    raw answer is saved anyway: a review the user dictated must never be lost."""
    output = load_json(run.output)
    cost = 0.0
    try:
        prompt = PROMPT.format(questions=output["questions"], example=_latest_example(vault),
                               answer=answer)
        res = run_litellm(prompt, system=SYSTEM, function=KEY)
        cost = res.cost_usd
        data = _extract_json(res.text)
        body, summary = str(data["body"]), str(data.get("summary") or "").strip()
    except Exception as e:
        logger.exception("Review structuring failed; saving raw answer")
        output["structure_error"] = f"{type(e).__name__}: {e}"[:500]
        body, summary = f"### Respuestas (sin ordenar)\n\n{answer.strip()}", answer.strip()[:1500]

    rel = _note_path(vault, output["date"])
    write_note_atomic(vault, rel, _note(output["date"], body))
    output.update(answer=answer, note=rel, summary=summary)
    run.output = json.dumps(output, ensure_ascii=False)
    run.cost_usd += cost
    run.status = "succeeded"
    run.finished_at = datetime.utcnow()
    session.add(run)
    session.commit()
    return output


def skip(session: Session, run: RoutineRun) -> None:
    run.status = "skipped"
    run.finished_at = datetime.utcnow()
    session.add(run)
    session.commit()
