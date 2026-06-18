import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from sqlmodel import Session, select

from app.modules.inbox.models import InboxItem

VALID_CATEGORIES = ("task", "note", "uncertain")

CLASSIFY_PROMPT = (
    "Clasifica esta nota personal y extrae el texto accionable.\n"
    "Categorías:\n"
    "- task: algo que hacer sin hora concreta (comprar, llamar, revisar...).\n"
    "- note: información o idea, no accionable.\n"
    "- uncertain: ambigua, muy corta, o con fecha/hora (posible evento).\n"
    'Responde SOLO un JSON: {{"category": "task|note|uncertain", "proposed_text": "<texto>"}}.\n'
    "Para task, proposed_text es la tarea en imperativo breve.\n\n"
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


def scan_inbox(session: Session, vault_path, llm: Callable[[str], str]) -> list[InboxItem]:
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
        item = InboxItem(
            filename=path.name,
            excerpt=body[:200],
            source=source,
            category=category,
            proposed_text=proposed or body[:200],
            status="pending",
        )
        session.add(item)
        created.append(item)
    session.commit()
    for item in created:
        session.refresh(item)
    return created
