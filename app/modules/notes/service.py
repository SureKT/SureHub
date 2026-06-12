import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Callable

TAG_PROMPT = (
    "Genera entre 2 y 5 tags cortos en minúscula para clasificar esta nota. "
    "Responde SOLO con un array JSON de strings, sin texto adicional. "
    'Ejemplo: ["ideas", "trabajo"]\n\nNota:\n{text}'
)

MAX_TAGS = 5


def _slugify(text: str, max_words: int = 5) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[a-zA-Z0-9]+", ascii_text.lower())[:max_words]
    return "-".join(words) or "nota"


def _parse_tags(raw: str) -> list[str]:
    raw = raw.strip()
    candidates: list[str] = []
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                candidates = [str(t) for t in parsed]
        except json.JSONDecodeError:
            candidates = match.group(0).strip("[]").split(",")
    if not candidates and raw:
        candidates = raw.splitlines()[0].split(",")

    tags: list[str] = []
    for c in candidates:
        tag = re.sub(r"[^a-z0-9/-]+", "-", c.strip().strip("\"'#").lower()).strip("-")
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:MAX_TAGS]


def generate_tags(text: str, llm: Callable[[str], str]) -> list[str]:
    # La captura nunca debe perderse por un fallo del LLM: ante error, sin tags.
    try:
        response = llm(TAG_PROMPT.format(text=text))
        return _parse_tags(response)
    except Exception:
        return []


def create_note(text: str, vault_path: str | Path, llm: Callable[[str], str] | None = None) -> Path:
    tags = generate_tags(text, llm) if llm else []
    now = datetime.now().astimezone()

    inbox = Path(vault_path) / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    base = f"{now.strftime('%Y-%m-%d-%H%M')}-{_slugify(text)}"
    path = inbox / f"{base}.md"
    counter = 2
    while path.exists():
        path = inbox / f"{base}-{counter}.md"
        counter += 1

    content = (
        "---\n"
        f"created: {now.isoformat(timespec='seconds')}\n"
        f"tags: [{', '.join(tags)}]\n"
        "source: telegram\n"
        "---\n\n"
        f"{text}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def extract_tags(path: Path) -> list[str]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("tags:"):
            inner = line.split(":", 1)[1].strip().strip("[]")
            return [t.strip() for t in inner.split(",") if t.strip()]
    return []
