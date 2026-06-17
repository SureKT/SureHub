# Inbox Auto-Processing (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify new Obsidian inbox notes with IA and, via a batch-approval Telegram digest, turn them into Obsidian tasks or archive them — never acting on garbage/mistranscribed input without approval.

**Architecture:** New `app/modules/inbox/` module (SQLModel `InboxItem` tracks every seen note + its proposal + status). A bot `/inbox` command and a daily `JobQueue` job scan unseen `inbox/*.md`, classify each (Haiku via `complete_tags`), persist as `pending`, and send a digest. Confident `task`/`note` items batch-apply in one tap; `uncertain` items are handled individually. Actions are reversible `.md` file moves.

**Tech Stack:** FastAPI/SQLModel, python-telegram-bot (CommandHandler, CallbackQueryHandler, JobQueue), Anthropic Haiku (`complete_tags`), pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-06-18-inbox-auto-processing-design.md`

---

## Conventions (read first)

- Run tests from repo root with venv active: `python -m pytest -q`.
- Tests set env vars in `tests/conftest.py`; the `engine`/`session` fixtures give an in-memory DB. Bot tests monkeypatch the module-level `engine` (see `tests/test_bot_handlers.py`).
- Service functions take an explicit `session`. The bot opens `with Session(engine) as session:`.
- Use `safe_reply(update, ...)` for user-facing bot sends (never raw `reply_text`).
- Commit after each task. Pushing to `main` triggers CI → deploy, so each task commits but we push once at the end of the plan (or when you want a deploy).

---

### Task 1: `InboxItem` model

**Files:**
- Create: `app/modules/inbox/__init__.py` (empty)
- Create: `app/modules/inbox/models.py`
- Modify: `app/models.py`
- Test: `tests/test_inbox_service.py`

- [ ] **Step 1: Create the empty package file**

Create `app/modules/inbox/__init__.py` with no content.

- [ ] **Step 2: Write the model**

Create `app/modules/inbox/models.py`:

```python
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class InboxItem(SQLModel, table=True):
    __tablename__ = "inbox_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True, unique=True)  # nombre del .md en inbox/
    excerpt: str = ""                                # primeros ~200 chars
    source: str = ""                                 # telegram | telegram-voice | ...
    category: str = "uncertain"                      # task | note | uncertain
    proposed_text: str = ""
    status: str = "pending"                          # pending | approved | archived | discarded
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
```

- [ ] **Step 3: Register the model for create_db**

Modify `app/models.py` — add the import after the memoria import:

```python
from app.modules.memoria.models import Memory  # noqa: F401
from app.modules.inbox.models import InboxItem  # noqa: F401
```

- [ ] **Step 4: Write a test that the table is created**

Create `tests/test_inbox_service.py`:

```python
from sqlmodel import select

from app.modules.inbox.models import InboxItem


def test_inbox_item_persists(session):
    item = InboxItem(filename="2026-06-18-1000-x.md", category="task", proposed_text="comprar pan")
    session.add(item)
    session.commit()

    rows = session.exec(select(InboxItem)).all()
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].filename == "2026-06-18-1000-x.md"
```

- [ ] **Step 5: Run the test**

Run: `python -m pytest tests/test_inbox_service.py -q`
Expected: PASS (the `engine` fixture calls `SQLModel.metadata.create_all`, which now includes `inbox_items`).

- [ ] **Step 6: Commit**

```bash
git add app/modules/inbox/__init__.py app/modules/inbox/models.py app/models.py tests/test_inbox_service.py
git commit -m "feat(inbox): add InboxItem model"
```

---

### Task 2: Note classification (`classify_note`)

**Files:**
- Create: `app/modules/inbox/service.py`
- Test: `tests/test_inbox_service.py`

- [ ] **Step 1: Write failing tests for classification**

Append to `tests/test_inbox_service.py`:

```python
from app.modules.inbox.service import classify_note


def test_classify_task():
    llm = lambda prompt: '{"category": "task", "proposed_text": "comprar pan"}'
    assert classify_note("tengo que comprar pan", llm) == ("task", "comprar pan")


def test_classify_note_category():
    llm = lambda prompt: 'Claro: {"category": "note", "proposed_text": "idea sobre x"}'
    assert classify_note("una idea sobre x", llm) == ("note", "idea sobre x")


def test_classify_invalid_category_becomes_uncertain():
    llm = lambda prompt: '{"category": "evento", "proposed_text": "cena jueves"}'
    cat, _ = classify_note("cena el jueves", llm)
    assert cat == "uncertain"


def test_classify_llm_failure_is_uncertain():
    def llm(prompt):
        raise RuntimeError("API down")
    cat, text = classify_note("nota cualquiera", llm)
    assert cat == "uncertain"
    assert text == "nota cualquiera"


def test_classify_non_json_is_uncertain():
    llm = lambda prompt: "no soy json"
    assert classify_note("algo", llm)[0] == "uncertain"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_inbox_service.py -q`
Expected: FAIL with `ImportError: cannot import name 'classify_note'`.

- [ ] **Step 3: Implement classification**

Create `app/modules/inbox/service.py`:

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_inbox_service.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/inbox/service.py tests/test_inbox_service.py
git commit -m "feat(inbox): IA note classification with safe uncertain fallback"
```

---

### Task 3: Read note frontmatter + scan inbox

**Files:**
- Modify: `app/modules/inbox/service.py`
- Test: `tests/test_inbox_service.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_inbox_service.py`:

```python
from app.modules.inbox.service import scan_inbox

NOTE = """---
created: 2026-06-18T10:00:00+02:00
tags: [compras]
source: telegram-voice
---

tengo que comprar pan y leche
"""


def _write_note(vault, name, content=NOTE):
    inbox = vault / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / name).write_text(content, encoding="utf-8")


def test_scan_creates_items_for_new_notes(session, tmp_path):
    _write_note(tmp_path, "2026-06-18-1000-pan.md")
    llm = lambda prompt: '{"category": "task", "proposed_text": "comprar pan y leche"}'

    created = scan_inbox(session, tmp_path, llm)

    assert len(created) == 1
    item = created[0]
    assert item.filename == "2026-06-18-1000-pan.md"
    assert item.category == "task"
    assert item.proposed_text == "comprar pan y leche"
    assert item.source == "telegram-voice"
    assert item.status == "pending"


def test_scan_skips_already_seen(session, tmp_path):
    _write_note(tmp_path, "2026-06-18-1000-pan.md")
    llm = lambda prompt: '{"category": "task", "proposed_text": "x"}'

    scan_inbox(session, tmp_path, llm)
    created_again = scan_inbox(session, tmp_path, llm)

    assert created_again == []


def test_scan_no_inbox_dir_returns_empty(session, tmp_path):
    assert scan_inbox(session, tmp_path, lambda p: "{}") == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_inbox_service.py -q`
Expected: FAIL with `ImportError: cannot import name 'scan_inbox'`.

- [ ] **Step 3: Implement `_read_note` and `scan_inbox`**

Append to `app/modules/inbox/service.py`:

```python
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
```

Note: `inbox.glob("*.md")` is non-recursive, so it never descends into `inbox/_descartado/` (Task 4).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_inbox_service.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/inbox/service.py tests/test_inbox_service.py
git commit -m "feat(inbox): scan inbox for unseen notes and persist proposals"
```

---

### Task 4: Apply actions (task / note / discard) + batch

**Files:**
- Modify: `app/modules/inbox/service.py`
- Test: `tests/test_inbox_service.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_inbox_service.py`:

```python
from app.modules.inbox.service import (
    apply_item, apply_suggested, pending_items, get_item,
)


def test_apply_task_appends_and_archives(session, tmp_path):
    _write_note(tmp_path, "2026-06-18-1000-pan.md")
    llm = lambda prompt: '{"category": "task", "proposed_text": "comprar pan"}'
    item = scan_inbox(session, tmp_path, llm)[0]

    apply_item(session, item, tmp_path, "task")

    tasks = (tmp_path / "Tareas.md").read_text(encoding="utf-8")
    assert "- [ ] comprar pan" in tasks
    assert "[[2026-06-18-1000-pan]]" in tasks
    assert not (tmp_path / "inbox" / "2026-06-18-1000-pan.md").exists()
    assert (tmp_path / "archivo" / "2026-06-18-1000-pan.md").exists()
    assert item.status == "approved"


def test_apply_task_override_text(session, tmp_path):
    _write_note(tmp_path, "n.md")
    item = scan_inbox(session, tmp_path, lambda p: '{"category":"task","proposed_text":"mal"}')[0]

    apply_item(session, item, tmp_path, "task", override_text="texto corregido")

    assert "- [ ] texto corregido" in (tmp_path / "Tareas.md").read_text(encoding="utf-8")


def test_apply_note_archives(session, tmp_path):
    _write_note(tmp_path, "n.md")
    item = scan_inbox(session, tmp_path, lambda p: '{"category":"note","proposed_text":"idea"}')[0]

    apply_item(session, item, tmp_path, "note")

    assert (tmp_path / "archivo" / "n.md").exists()
    assert not (tmp_path / "Tareas.md").exists()
    assert item.status == "archived"


def test_apply_discard_moves_to_descartado(session, tmp_path):
    _write_note(tmp_path, "n.md")
    item = scan_inbox(session, tmp_path, lambda p: '{"category":"uncertain","proposed_text":"?"}')[0]

    apply_item(session, item, tmp_path, "discard")

    assert (tmp_path / "inbox" / "_descartado" / "n.md").exists()
    assert item.status == "discarded"


def test_apply_suggested_applies_task_and_note_only(session, tmp_path):
    _write_note(tmp_path, "a.md")
    _write_note(tmp_path, "b.md")
    _write_note(tmp_path, "c.md")
    cats = iter([
        '{"category":"task","proposed_text":"t"}',
        '{"category":"note","proposed_text":"n"}',
        '{"category":"uncertain","proposed_text":"?"}',
    ])
    scan_inbox(session, tmp_path, lambda p: next(cats))

    counts = apply_suggested(session, tmp_path)

    assert counts == {"task": 1, "note": 1}
    # the uncertain one stays pending
    assert len(pending_items(session)) == 1
    assert pending_items(session)[0].category == "uncertain"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_inbox_service.py -q`
Expected: FAIL with `ImportError` for `apply_item`.

- [ ] **Step 3: Implement file ops + apply functions**

Append to `app/modules/inbox/service.py`:

```python
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


def apply_suggested(session: Session, vault_path) -> dict:
    counts = {"task": 0, "note": 0}
    for item in pending_items(session):
        if item.category in ("task", "note"):
            apply_item(session, item, vault_path, item.category)
            counts[item.category] += 1
    return counts
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_inbox_service.py -q`
Expected: PASS (all inbox service tests).

- [ ] **Step 5: Commit**

```bash
git add app/modules/inbox/service.py tests/test_inbox_service.py
git commit -m "feat(inbox): reversible apply actions (task/note/discard) + batch"
```

---

### Task 5: Build the digest messages (bot layer)

**Files:**
- Create: `bot/inbox_handlers.py`
- Test: `tests/test_inbox_handlers.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_inbox_handlers.py`:

```python
from telegram import InlineKeyboardMarkup

import bot.inbox_handlers as ih
from app.modules.inbox.service import scan_inbox

NOTE = """---
source: telegram
---

cuerpo de la nota
"""


def _write(vault, name):
    inbox = vault / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / name).write_text(NOTE, encoding="utf-8")


def test_build_digest_empty(session):
    assert ih.build_digest(session) == []


def test_build_digest_groups_confident_and_uncertain(session, tmp_path):
    _write(tmp_path, "a.md")
    _write(tmp_path, "b.md")
    cats = iter([
        '{"category":"task","proposed_text":"comprar pan"}',
        '{"category":"uncertain","proposed_text":"?"}',
    ])
    scan_inbox(session, tmp_path, lambda p: next(cats))

    messages = ih.build_digest(session)

    # one batch message for confident + one per uncertain
    assert len(messages) == 2
    batch_text, batch_kb = messages[0]
    assert "comprar pan" in batch_text
    assert isinstance(batch_kb, InlineKeyboardMarkup)
    assert batch_kb.inline_keyboard[0][0].callback_data == "inbox:applyall"
    uncertain_text, uncertain_kb = messages[1]
    assert "Dudosa" in uncertain_text
    # has task/note/discard/edit buttons
    datas = [b.callback_data for row in uncertain_kb.inline_keyboard for b in row]
    assert any(d.startswith("inbox:task:") for d in datas)
    assert any(d.startswith("inbox:edit:") for d in datas)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_inbox_handlers.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'bot.inbox_handlers'`.

- [ ] **Step 3: Implement `build_digest`**

Create `bot/inbox_handlers.py` with exactly this content:

```python
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlmodel import Session

from app.config import settings
from app.database import engine
from app.services.llm import complete_tags
from app.modules.inbox.service import (
    scan_inbox, pending_items, apply_item, apply_suggested, get_item,
)
from bot.handlers import allowed, safe_reply


def build_digest(session) -> list[tuple[str, InlineKeyboardMarkup | None]]:
    items = pending_items(session)
    if not items:
        return []
    messages: list[tuple[str, InlineKeyboardMarkup | None]] = []

    confident = [i for i in items if i.category in ("task", "note")]
    if confident:
        lines = ["*Sugeridos* (los aplico en lote):"]
        for i in confident:
            icon = "✅" if i.category == "task" else "📄"
            lines.append(f"{icon} {i.proposed_text}")
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("✓ Aplicar sugeridos", callback_data="inbox:applyall")]]
        )
        messages.append(("\n".join(lines), kb))

    for i in items:
        if i.category != "uncertain":
            continue
        voice = " 🎤" if i.source == "telegram-voice" else ""
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✓ Tarea", callback_data=f"inbox:task:{i.id}"),
                InlineKeyboardButton("📄 Archivar", callback_data=f"inbox:note:{i.id}"),
            ],
            [
                InlineKeyboardButton("✗ Descartar", callback_data=f"inbox:discard:{i.id}"),
                InlineKeyboardButton("✏️ Editar", callback_data=f"inbox:edit:{i.id}"),
            ],
        ])
        messages.append((f"*Dudosa*{voice}:\n{i.excerpt}", kb))

    return messages
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_inbox_handlers.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/inbox_handlers.py tests/test_inbox_handlers.py
git commit -m "feat(inbox): build batched + per-item digest messages"
```

---

### Task 6: `/inbox` command

**Files:**
- Modify: `bot/inbox_handlers.py`
- Test: `tests/test_inbox_handlers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_inbox_handlers.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

ALLOWED_USER_ID = 111


@pytest.fixture(autouse=True)
def inbox_engine(engine, monkeypatch):
    monkeypatch.setattr(ih, "engine", engine)
    return engine


def make_update(user_id=ALLOWED_USER_ID):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    update.message.reply_chat_action = AsyncMock()
    return update


def make_context():
    ctx = MagicMock()
    ctx.args = []
    ctx.user_data = {}
    return ctx


async def test_cmd_inbox_empty_says_clean(monkeypatch, tmp_path):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    update = make_update()

    await ih.cmd_inbox(update, make_context())

    assert "limpia" in update.message.reply_text.call_args.args[0].lower()


async def test_cmd_inbox_sends_digest(monkeypatch, tmp_path):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setattr(ih, "complete_tags", lambda p: '{"category":"task","proposed_text":"comprar pan"}')
    _write(tmp_path, "a.md")
    update = make_update()

    await ih.cmd_inbox(update, make_context())

    # at least one digest message sent containing the proposed task
    sent = " ".join(c.args[0] for c in update.message.reply_text.call_args_list)
    assert "comprar pan" in sent


async def test_cmd_inbox_unauthorized_ignored(tmp_path):
    update = make_update(user_id=999)
    await ih.cmd_inbox(update, make_context())
    update.message.reply_text.assert_not_called()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_inbox_handlers.py -q`
Expected: FAIL with `AttributeError: ... has no attribute 'cmd_inbox'`.

- [ ] **Step 3: Implement `_scan_and_digest` and `cmd_inbox`**

Append to `bot/inbox_handlers.py`:

```python
def _scan_and_digest(vault_path) -> list[tuple[str, InlineKeyboardMarkup | None]]:
    """Runs in a worker thread: own session, LLM classification (slow), then
    builds detached (text, keyboard) tuples that outlive the session."""
    with Session(engine) as session:
        scan_inbox(session, vault_path, complete_tags)
        return build_digest(session)


async def cmd_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await update.message.reply_chat_action("typing")
    messages = await asyncio.to_thread(_scan_and_digest, settings.OBSIDIAN_VAULT_PATH)
    if not messages:
        await safe_reply(update, "Inbox limpia ✅")
        return
    for text, kb in messages:
        await safe_reply(update, text, parse_mode="Markdown", reply_markup=kb)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_inbox_handlers.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/inbox_handlers.py tests/test_inbox_handlers.py
git commit -m "feat(inbox): /inbox command scans and sends the digest"
```

---

### Task 7: Digest callbacks (apply-all + per-item)

**Files:**
- Modify: `bot/inbox_handlers.py`
- Test: `tests/test_inbox_handlers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_inbox_handlers.py`:

```python
def make_callback_update(data, user_id=ALLOWED_USER_ID):
    update = make_update(user_id=user_id)
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    update.effective_chat.send_message = AsyncMock()
    return update, query


async def test_callback_apply_all(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setattr(ih, "complete_tags", lambda p: '{"category":"task","proposed_text":"comprar pan"}')
    _write(tmp_path, "a.md")
    scan_inbox(session, tmp_path, ih.complete_tags)

    update, query = make_callback_update("inbox:applyall")
    await ih.callback_inbox(update, make_context())

    assert "- [ ] comprar pan" in (tmp_path / "Tareas.md").read_text(encoding="utf-8")
    assert "1" in query.edit_message_text.call_args.args[0]


async def test_callback_per_item_task(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    _write(tmp_path, "a.md")
    item = scan_inbox(session, tmp_path, lambda p: '{"category":"uncertain","proposed_text":"comprar pan"}')[0]

    update, query = make_callback_update(f"inbox:task:{item.id}")
    await ih.callback_inbox(update, make_context())

    assert "- [ ] comprar pan" in (tmp_path / "Tareas.md").read_text(encoding="utf-8")


async def test_callback_edit_prompts_for_text(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    _write(tmp_path, "a.md")
    item = scan_inbox(session, tmp_path, lambda p: '{"category":"uncertain","proposed_text":"x"}')[0]

    update, query = make_callback_update(f"inbox:edit:{item.id}")
    context = make_context()
    await ih.callback_inbox(update, context)

    assert context.user_data["inbox_edit_id"] == item.id
    assert "texto" in query.edit_message_text.call_args.args[0].lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_inbox_handlers.py -q`
Expected: FAIL with `AttributeError: ... 'callback_inbox'`.

- [ ] **Step 3: Implement `callback_inbox`**

Append to `bot/inbox_handlers.py`:

```python
async def _edit_or_send(update: Update, query, text: str):
    from telegram.error import BadRequest
    try:
        await query.edit_message_text(text)
    except BadRequest:
        await update.effective_chat.send_message(text)


async def callback_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # inbox:applyall | inbox:<action>:<id>

    if data == "inbox:applyall":
        with Session(engine) as session:
            counts = apply_suggested(session, settings.OBSIDIAN_VAULT_PATH)
        await _edit_or_send(
            update, query,
            f"✓ Aplicados: {counts['task']} tarea(s), {counts['note']} nota(s) archivada(s)."
        )
        return

    _, action, item_id_str = data.split(":")
    item_id = int(item_id_str)

    if action == "edit":
        context.user_data["inbox_edit_id"] = item_id
        await _edit_or_send(update, query, "Envíame el texto corregido de la tarea.")
        return

    with Session(engine) as session:
        item = get_item(session, item_id)
        if not item or item.status != "pending":
            await _edit_or_send(update, query, "Ya resuelta.")
            return
        apply_item(session, item, settings.OBSIDIAN_VAULT_PATH, action)

    labels = {"task": "✓ Tarea creada", "note": "📄 Archivada", "discard": "✗ Descartada"}
    await _edit_or_send(update, query, labels.get(action, "Hecho."))
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_inbox_handlers.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/inbox_handlers.py tests/test_inbox_handlers.py
git commit -m "feat(inbox): digest callbacks (apply-all + per-item actions)"
```

---

### Task 8: Edit flow (apply corrected text as task)

**Files:**
- Modify: `bot/inbox_handlers.py` (add `apply_edited_task`)
- Modify: `bot/handlers.py` (`message` checks `inbox_edit_id` first)
- Test: `tests/test_inbox_handlers.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_inbox_handlers.py`:

```python
async def test_apply_edited_task(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    _write(tmp_path, "a.md")
    item = scan_inbox(session, tmp_path, lambda p: '{"category":"uncertain","proposed_text":"x"}')[0]

    update = make_update()
    handled = await ih.apply_edited_task(update, item.id, "comprar pan corregido")

    assert handled is True
    assert "- [ ] comprar pan corregido" in (tmp_path / "Tareas.md").read_text(encoding="utf-8")


async def test_apply_edited_task_unknown_id(monkeypatch, tmp_path):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    update = make_update()
    assert await ih.apply_edited_task(update, 9999, "x") is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_inbox_handlers.py -q`
Expected: FAIL with `AttributeError: ... 'apply_edited_task'`.

- [ ] **Step 3: Implement `apply_edited_task`**

Append to `bot/inbox_handlers.py`:

```python
async def apply_edited_task(update: Update, item_id: int, text: str) -> bool:
    """Applies `text` as the task for a pending item. Returns False if the item
    no longer exists / isn't pending (caller should fall through to normal handling)."""
    with Session(engine) as session:
        item = get_item(session, item_id)
        if not item or item.status != "pending":
            return False
        apply_item(session, item, settings.OBSIDIAN_VAULT_PATH, "task", override_text=text)
    await safe_reply(update, f"✓ Tarea creada: {text}")
    return True
```

- [ ] **Step 4: Wire it into the main text handler**

Modify `bot/handlers.py` — add this block at the very start of `async def message(...)`, right after the `if not allowed(update): return` line and before `text = update.message.text`:

```python
    edit_id = context.user_data.pop("inbox_edit_id", None)
    if edit_id is not None:
        from bot.inbox_handlers import apply_edited_task
        if await apply_edited_task(update, edit_id, update.message.text.strip()):
            return
```

(The import is local to avoid a circular import: `bot.inbox_handlers` imports from `bot.handlers`.)

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_inbox_handlers.py tests/test_bot_handlers.py -q`
Expected: PASS (inbox edit tests pass; existing bot tests unaffected — `inbox_edit_id` is absent so the new block is a no-op).

- [ ] **Step 6: Commit**

```bash
git add bot/inbox_handlers.py bot/handlers.py tests/test_inbox_handlers.py
git commit -m "feat(inbox): edit flow applies corrected text as task"
```

---

### Task 9: Daily digest job (JobQueue)

**Files:**
- Modify: `bot/inbox_handlers.py` (add `inbox_digest_job`)
- Modify: `app/config.py` (add `INBOX_DIGEST_HOUR`)
- Modify: `.env.example`
- Test: `tests/test_inbox_handlers.py`

- [ ] **Step 1: Add the config setting**

Modify `app/config.py` — add after the `TIMEZONE` line:

```python
    INBOX_DIGEST_HOUR: int = 9  # hora local del digest diario de la inbox
```

- [ ] **Step 2: Document it in `.env.example`**

Modify `.env.example` — add near the other app settings:

```
# Hora (0-23, local) del digest diario de la inbox de Obsidian
INBOX_DIGEST_HOUR=9
```

- [ ] **Step 3: Write failing test**

Append to `tests/test_inbox_handlers.py`:

```python
async def test_inbox_digest_job_sends_to_user(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setattr(ih, "complete_tags", lambda p: '{"category":"task","proposed_text":"comprar pan"}')
    _write(tmp_path, "a.md")

    context = MagicMock()
    context.bot.send_message = AsyncMock()

    await ih.inbox_digest_job(context)

    sent = " ".join(str(c.kwargs.get("text", "")) for c in context.bot.send_message.call_args_list)
    assert "comprar pan" in sent
    # sent to the allowed user id
    assert context.bot.send_message.call_args.kwargs["chat_id"] == ih.settings.allowed_user_ids[0]


async def test_inbox_digest_job_silent_when_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    await ih.inbox_digest_job(context)

    context.bot.send_message.assert_not_called()
```

- [ ] **Step 4: Run to verify it fails**

Run: `python -m pytest tests/test_inbox_handlers.py -q`
Expected: FAIL with `AttributeError: ... 'inbox_digest_job'`.

- [ ] **Step 5: Implement the job**

Append to `bot/inbox_handlers.py`:

```python
async def inbox_digest_job(context: ContextTypes.DEFAULT_TYPE):
    """Daily scheduled scan + digest. Silent when there's nothing pending."""
    messages = await asyncio.to_thread(_scan_and_digest, settings.OBSIDIAN_VAULT_PATH)
    if not messages:
        return
    chat_id = settings.allowed_user_ids[0]
    for text, kb in messages:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text,
                                           parse_mode="Markdown", reply_markup=kb)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
```

- [ ] **Step 6: Run to verify pass**

Run: `python -m pytest tests/test_inbox_handlers.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add bot/inbox_handlers.py app/config.py .env.example tests/test_inbox_handlers.py
git commit -m "feat(inbox): daily digest job + INBOX_DIGEST_HOUR config"
```

---

### Task 10: Register handlers, command menu, schedule job

**Files:**
- Modify: `bot/run.py`
- Modify: `bot/help_text.py`
- Test: manual import smoke test

- [ ] **Step 1: Register command + callback + daily job in `bot/run.py`**

Modify `bot/run.py`:

(a) Add imports near the other handler imports:

```python
from bot.inbox_handlers import cmd_inbox, callback_inbox, inbox_digest_job
from datetime import time as dtime
from zoneinfo import ZoneInfo
```

(b) In `main()`, after the existing `CommandHandler("note", cmd_nota)` registration, add:

```python
    app.add_handler(CommandHandler("inbox", cmd_inbox))
```

(c) After the existing `CallbackQueryHandler(callback_categoria, pattern="^cat:")` line, add:

```python
    app.add_handler(CallbackQueryHandler(callback_inbox, pattern="^inbox:"))
```

(d) In `main()`, after `app.add_error_handler(on_error)`, schedule the daily job:

```python
    app.job_queue.run_daily(
        inbox_digest_job,
        time=dtime(hour=settings.INBOX_DIGEST_HOUR, tzinfo=ZoneInfo(settings.TIMEZONE)),
    )
```

- [ ] **Step 2: Add `/inbox` to help + command menu in `bot/help_text.py`**

Modify `bot/help_text.py`:

(a) In `HELP`, after the `*Notas (Obsidian)*` block (the `/note — alias de /nota\n\n` line), add:

```python
    "*Inbox*\n"
    "/inbox — procesar notas pendientes (digest)\n\n"
```

(b) In `bot_commands()`, add before the closing `]`:

```python
        BotCommand("inbox", "Procesar inbox de notas"),
```

- [ ] **Step 3: Smoke-test imports and JobQueue availability**

Run: `python -c "import bot.run; print('run.py import OK')"`
Expected: `run.py import OK` (no ImportError).

Note: `app.job_queue` requires the `python-telegram-bot[job-queue]` extra. Verify it's present:

Run: `python -c "from telegram.ext import ApplicationBuilder; a=ApplicationBuilder().token('1:x').build(); print('job_queue:', a.job_queue is not None)"`
Expected: `job_queue: True`. If it prints `None` or errors, add `python-telegram-bot[job-queue]>=21.0` to `requirements.txt` (replacing the plain entry) and `pip install -r requirements-dev.txt`, then re-run.

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (all tests, including the existing suite).

- [ ] **Step 5: Commit**

```bash
git add bot/run.py bot/help_text.py requirements.txt
git commit -m "feat(inbox): register /inbox command, callbacks and daily digest job"
```

---

### Task 11: Update BACKLOG

**Files:**
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Move the task-capture/processing item to reflect progress**

Modify `docs/BACKLOG.md` — remove the two seeded inbox lines from `## Pendiente` and add under `## En curso`:

```markdown
## En curso

- [ ] Procesado de inbox **Fase 1** (clasificación + digest + tareas→Obsidian) — en implementación.
  Fase 2 (eventos→Google Calendar) pendiente. Spec: `docs/superpowers/specs/2026-06-18-inbox-auto-processing-design.md`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/BACKLOG.md
git commit -m "docs: mark inbox processing phase 1 in progress"
```

---

## Final verification (after all tasks)

- [ ] Run full suite: `python -m pytest -q` → all green.
- [ ] Import smoke: `python -c "import bot.run, app.main; print('OK')"`.
- [ ] Push to deploy: `git push origin main` → watch CI then deploy in the Actions tab.
- [ ] Live smoke (server): send `/inbox` to the bot → expect a digest of the real 5 inbox notes (or "Inbox limpia ✅"); tap "Aplicar sugeridos"; confirm `Tareas.md` appears in the vault and notes moved to `archivo/`.

---

## Self-Review

**Spec coverage:**
- Classification (task/note/uncertain, LLM-fail→uncertain) → Task 2 ✓
- Seen-tracking via DB, scan unseen → Tasks 1, 3 ✓
- Digest: batch confident + per-item uncertain, voice flag → Task 5 ✓
- `/inbox` on-demand → Task 6 ✓
- Apply actions task/note/discard, reversible moves, Tareas.md backlink → Task 4 ✓
- Edit flow → Tasks 7, 8 ✓
- Daily JobQueue + config → Tasks 9, 10 ✓
- help/menu wiring → Task 10 ✓
- BACKLOG → Task 11 ✓
- Out of scope (events/Calendar) → not present ✓

**Placeholder scan:** No TBD/TODO/placeholder snippets. Every code step shows complete file content.

**Type consistency:** `classify_note`, `scan_inbox(session, vault_path, llm)`, `apply_item(session, item, vault_path, action, override_text=None)`, `apply_suggested`, `pending_items`, `get_item`, `build_digest(session)`, `_scan_and_digest(vault_path)`, `cmd_inbox`, `callback_inbox`, `apply_edited_task(update, item_id, text)`, `inbox_digest_job(context)` — names/signatures consistent across tasks. Callback data scheme `inbox:applyall` / `inbox:<action>:<id>` consistent between Task 5 (buttons) and Task 7 (parser).
