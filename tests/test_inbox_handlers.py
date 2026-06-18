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


def test_build_digest_event_card(session, tmp_path):
    _write(tmp_path, "ev.md")
    classify = lambda p: '{"category":"event","proposed_text":"x"}'
    event_llm = lambda p: '{"summary":"Pádel con Marc","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'
    scan_inbox(session, tmp_path, classify, event_llm=event_llm)

    messages = ih.build_digest(session)

    assert len(messages) == 1
    text, kb = messages[0]
    assert "Pádel con Marc" in text
    assert "padel" in text
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert any(d.startswith("inbox:event:") for d in datas)
    assert any(d.startswith("inbox:editdate:") for d in datas)


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


async def test_callback_event_creates_and_replies_link(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    _write(tmp_path, "ev.md")
    classify = lambda p: '{"category":"event","proposed_text":"x"}'
    event_llm = lambda p: '{"summary":"Pádel","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'
    item = scan_inbox(session, tmp_path, classify, event_llm=event_llm)[0]
    monkeypatch.setattr(ih, "cal_create_event", lambda *a, **k: ("evt1", "https://cal/evt1"))

    update, query = make_callback_update(f"inbox:event:{item.id}")
    await ih.callback_inbox(update, make_context())

    assert "https://cal/evt1" in query.edit_message_text.call_args.args[0]
    assert (tmp_path / "archivo" / "ev.md").exists()


async def test_callback_event_create_failure_keeps_pending(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    _write(tmp_path, "ev.md")
    classify = lambda p: '{"category":"event","proposed_text":"x"}'
    event_llm = lambda p: '{"summary":"Pádel","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'
    item = scan_inbox(session, tmp_path, classify, event_llm=event_llm)[0]

    def boom(*a, **k):
        raise FileNotFoundError("no token")
    monkeypatch.setattr(ih, "cal_create_event", boom)

    update, query = make_callback_update(f"inbox:event:{item.id}")
    await ih.callback_inbox(update, make_context())

    assert "No pude crear" in query.edit_message_text.call_args.args[0]
    # la nota no se movió ni cambió de estado
    assert (tmp_path / "inbox" / "ev.md").exists()


async def test_callback_editdate_prompts_and_sets_state(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    _write(tmp_path, "ev.md")
    classify = lambda p: '{"category":"event","proposed_text":"x"}'
    event_llm = lambda p: '{"summary":"Pádel","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'
    item = scan_inbox(session, tmp_path, classify, event_llm=event_llm)[0]

    update, query = make_callback_update(f"inbox:editdate:{item.id}")
    context = make_context()
    await ih.callback_inbox(update, context)

    assert context.user_data["inbox_event_edit_id"] == item.id
    assert "fecha" in query.edit_message_text.call_args.args[0].lower()


async def test_reextract_event_date_updates_and_resends_card(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    _write(tmp_path, "ev.md")
    classify = lambda p: '{"category":"event","proposed_text":"x"}'
    event_llm = lambda p: '{"summary":"Pádel","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'
    item = scan_inbox(session, tmp_path, classify, event_llm=event_llm)[0]
    monkeypatch.setattr(ih, "complete_event",
                        lambda p: '{"summary":"Pádel","start":"2026-06-21T10:00:00","end":"2026-06-21T11:00:00","all_day":false,"theme":"padel"}')

    update = make_update()
    update.effective_chat.send_message = AsyncMock()
    handled = await ih.reextract_event_date(update, item.id, "mejor el sábado a las 10")

    assert handled is True
    sent = update.effective_chat.send_message.call_args
    assert "21/06 10:00" in sent.kwargs.get("text", sent.args[0] if sent.args else "")


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
