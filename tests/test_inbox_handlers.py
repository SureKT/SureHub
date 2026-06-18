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
