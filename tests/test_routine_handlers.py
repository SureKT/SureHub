from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import Session, select

import bot.routine_handlers as rh
from app.modules.routines import weekly_review as wr
from app.modules.routines.models import RoutineRun

ALLOWED_USER_ID = 111


@pytest.fixture(autouse=True)
def world(engine, monkeypatch, tmp_path):
    monkeypatch.setattr(rh, "engine", engine)
    monkeypatch.setattr(wr.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    return {"engine": engine}


def make_update(user_id=ALLOWED_USER_ID):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    update.effective_chat.send_message = AsyncMock()
    return update


def make_context():
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    return ctx


def make_callback(data, user_id=ALLOWED_USER_ID):
    update = make_update(user_id)
    query = MagicMock(data=data, answer=AsyncMock(), edit_message_text=AsyncMock())
    update.callback_query = query
    return update, query


def _runs(engine):
    with Session(engine) as s:
        return list(s.exec(select(RoutineRun).order_by(RoutineRun.id)))


async def test_failed_run_sends_alert(world, monkeypatch):
    def down(vault):
        raise ValueError("vault caído")
    monkeypatch.setattr(wr, "load_questions", down)
    ctx = make_context()
    await rh.run_and_deliver(ctx.bot, "weekly_review", "manual")

    kw = ctx.bot.send_message.call_args.kwargs
    assert "falló" in kw["text"] and "vault caído" in kw["text"]
    assert kw["reply_markup"] is None
    assert _runs(world["engine"])[0].status == "failed"


async def test_cmd_routines_lists_runs_and_run_button(world):
    await rh.run_and_deliver(make_context().bot, "weekly_review", "manual")
    update = make_update()
    await rh.cmd_routines(update, make_context())
    text = update.message.reply_text.call_args.args[0]
    kb = update.message.reply_text.call_args.kwargs["reply_markup"]
    assert "Revisión semanal" in text and "esperando respuesta" in text
    assert [row[0].callback_data for row in kb.inline_keyboard] == ["rt:run:weekly_review"]


async def test_cmd_routines_unauthorized_ignored(world):
    update = make_update(user_id=999)
    await rh.cmd_routines(update, make_context())
    update.message.reply_text.assert_not_called()


async def test_run_button_executes_routine(world):
    update, _ = make_callback("rt:run:weekly_review")
    ctx = make_context()
    await rh.callback_routine(update, ctx)
    assert _runs(world["engine"])[0].trigger == "manual"
    ctx.bot.send_message.assert_awaited()


async def test_answer_on_stale_review_is_rejected(world):
    run = await rh.run_and_deliver(make_context().bot, "weekly_review", "manual")
    skip_update, _ = make_callback(f"rt:skip:{run.id}")
    await rh.callback_routine(skip_update, make_context())

    update, query = make_callback(f"rt:answer:{run.id}")
    ctx = make_context()
    await rh.callback_routine(update, ctx)
    assert rh.REVIEW_KEY not in ctx.user_data
    assert "ya no está pendiente" in query.edit_message_text.call_args.args[0]
