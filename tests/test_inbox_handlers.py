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
