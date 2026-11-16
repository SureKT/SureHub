import json
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import Session

import bot.handlers as h
import bot.routine_handlers as rh
from app.modules.routines import weekly_plan as wp
from app.modules.routines.engines import EngineResult
from app.modules.routines.models import RoutineRun
from app.services import calendar as calendar_api

ALLOWED_USER_ID = 111

# /plan uses the real clock: put the block on the window's last day (Sunday) late
# enough to never be "in the past" whatever time the suite runs.
_DAY = wp.plan_window(datetime.now(ZoneInfo("Europe/Madrid")), "next")[1].isoformat()
PROPOSAL = json.dumps({"summary": "Foco", "blocks": [
    {"title": "App pádel", "start": f"{_DAY}T20:00", "end": f"{_DAY}T21:30", "theme": "formacion"},
]})


@pytest.fixture(autouse=True)
def world(engine, monkeypatch, tmp_path):
    monkeypatch.setattr(rh, "engine", engine)
    monkeypatch.setattr(wp.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setattr(calendar_api, "list_events", lambda s, e: [])
    engine_calls = []

    def fake_engine(prompt, **kw):
        engine_calls.append(prompt)
        return EngineResult(text=PROPOSAL, cost_usd=0.01)

    monkeypatch.setattr(wp, "run_litellm", fake_engine)
    rh._in_flight.clear()
    return {"engine": engine, "vault": tmp_path, "engine_calls": engine_calls}


def make_update(user_id=ALLOWED_USER_ID, text=""):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.reply_chat_action = AsyncMock()
    update.effective_chat.send_message = AsyncMock()
    return update


def make_context():
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot.send_message = AsyncMock()
    return ctx


def make_callback(data):
    update = make_update()
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update, query


def _runs(engine):
    with Session(engine) as s:
        return list(s.exec(__import__("sqlmodel").select(RoutineRun).order_by(RoutineRun.id)))


async def _plan(ctx=None):
    ctx = ctx or make_context()
    ctx.args = ["semana"]   # next week: the fixed proposal date is always inside it
    await rh.cmd_plan(make_update(), ctx)
    return ctx


@pytest.mark.parametrize("args,expected", [
    ([], "rest"), (["semana"], "next"), (["Próxima"], "next"), (["siguiente"], "next"), (["hoy"], "rest"),
])
def test_plan_scope_args(args, expected):
    assert rh.plan_scope(args) == expected


async def test_cmd_plan_sends_proposal_with_approval_buttons(world):
    ctx = await _plan()

    kwargs = ctx.bot.send_message.call_args.kwargs
    assert "App pádel" in kwargs["text"]
    assert kwargs["parse_mode"] == "HTML"
    datas = [b.callback_data for row in kwargs["reply_markup"].inline_keyboard for b in row]
    run_id = _runs(world["engine"])[0].id
    assert datas == [f"rt:approve:{run_id}", f"rt:adjust:{run_id}", f"rt:discard:{run_id}"]


async def test_cmd_plan_unauthorized_ignored(world):
    ctx = make_context()
    await rh.cmd_plan(make_update(user_id=999), ctx)
    ctx.bot.send_message.assert_not_called()
    assert _runs(world["engine"]) == []


async def test_failed_run_sends_alert(world, monkeypatch):
    def down(s, e):
        raise ValueError("token caducado")
    monkeypatch.setattr(calendar_api, "list_events", down)
    ctx = await _plan()

    text = ctx.bot.send_message.call_args.kwargs["text"]
    assert "falló" in text and "token caducado" in text
    assert ctx.bot.send_message.call_args.kwargs["reply_markup"] is None


async def test_scheduled_job_runs_and_delivers(world, monkeypatch):
    monkeypatch.setattr(wp, "resolve_scope", lambda ctx: "next")   # real clock may not be Sunday
    ctx = make_context()
    ctx.job.data = {"key": "weekly_plan", "trigger": "scheduled"}
    await rh.routine_job(ctx)
    assert _runs(world["engine"])[0].trigger == "scheduled"
    assert "App pádel" in ctx.bot.send_message.call_args.kwargs["text"]


async def test_approve_creates_events_and_offers_undo(world, monkeypatch):
    await _plan()
    run_id = _runs(world["engine"])[0].id
    monkeypatch.setattr(calendar_api, "create_event", lambda *a, **k: ("ev1", "l"))

    update, query = make_callback(f"rt:approve:{run_id}")
    await rh.callback_routine(update, make_context())

    text = query.edit_message_text.call_args.args[0]
    assert "1 eventos" in text and "_surehub/planificacion/" in text
    kb = query.edit_message_text.call_args.kwargs["reply_markup"]
    assert kb.inline_keyboard[0][0].callback_data == f"rt:undo:{run_id}"
    assert _runs(world["engine"])[0].status == "approved"


async def test_second_approve_is_rejected(world, monkeypatch):
    await _plan()
    run_id = _runs(world["engine"])[0].id
    created = []
    monkeypatch.setattr(calendar_api, "create_event", lambda *a, **k: created.append(a) or ("ev", "l"))

    for _ in range(2):
        update, query = make_callback(f"rt:approve:{run_id}")
        await rh.callback_routine(update, make_context())

    assert len(created) == 1
    assert "ya no está activa" in query.edit_message_text.call_args.args[0]


async def test_approve_while_in_flight_is_blocked(world, monkeypatch):
    await _plan()
    run_id = _runs(world["engine"])[0].id
    rh._in_flight.add(run_id)
    monkeypatch.setattr(calendar_api, "create_event", lambda *a, **k: pytest.fail("must not create"))

    update, query = make_callback(f"rt:approve:{run_id}")
    await rh.callback_routine(update, make_context())
    assert "espera" in update.effective_chat.send_message.call_args.args[0]


async def test_approve_failure_keeps_retry_possible(world, monkeypatch):
    await _plan()
    run_id = _runs(world["engine"])[0].id

    def boom(*a, **k):
        raise RuntimeError("500")
    monkeypatch.setattr(calendar_api, "create_event", boom)

    update, query = make_callback(f"rt:approve:{run_id}")
    await rh.callback_routine(update, make_context())

    assert "reintentar" in update.effective_chat.send_message.call_args.args[0]
    assert _runs(world["engine"])[0].status == "approving"
    assert run_id not in rh._in_flight


async def test_no_calendar_write_without_approval(world, monkeypatch):
    monkeypatch.setattr(calendar_api, "create_event", lambda *a, **k: pytest.fail("no approval yet"))
    await _plan()
    update, query = make_callback(f"rt:discard:{_runs(world['engine'])[0].id}")
    await rh.callback_routine(update, make_context())
    assert "descartada" in query.edit_message_text.call_args.args[0]
    assert _runs(world["engine"])[0].status == "discarded"


async def test_adjust_by_text_regenerates_through_message_handler(world):
    await _plan()
    parent_id = _runs(world["engine"])[0].id
    ctx = make_context()
    update, _ = make_callback(f"rt:adjust:{parent_id}")
    await rh.callback_routine(update, ctx)
    assert ctx.user_data[rh.ADJUST_KEY] == parent_id

    # next free text is the correction, not a note/expense
    msg = make_update(text="el martes no puedo por la mañana")
    await h.message(msg, ctx)

    runs = _runs(world["engine"])
    assert [r.status for r in runs] == ["superseded", "awaiting_approval"]
    assert runs[1].parent_run_id == parent_id
    assert "el martes no puedo por la mañana" in world["engine_calls"][-1]
    assert rh.ADJUST_KEY not in ctx.user_data


async def test_adjust_by_voice(world, monkeypatch):
    await _plan()
    parent_id = _runs(world["engine"])[0].id
    ctx = make_context()
    ctx.user_data[rh.ADJUST_KEY] = parent_id
    ctx.bot.get_file = AsyncMock(return_value=MagicMock(download_to_drive=AsyncMock()))
    monkeypatch.setattr(h, "transcribe", lambda p: "mueve el gimnasio al jueves")
    monkeypatch.setattr(h, "_save_and_reply_note", AsyncMock(side_effect=AssertionError("not a note")))

    await h.voice_message(make_update(), ctx)

    assert "mueve el gimnasio al jueves" in world["engine_calls"][-1]
    assert _runs(world["engine"])[-1].trigger == "adjust"


async def test_adjust_on_stale_run_falls_back_to_normal_capture(world, monkeypatch):
    await _plan()
    run_id = _runs(world["engine"])[0].id
    rh._set_status(run_id, "discarded")
    ctx = make_context()
    ctx.user_data[rh.ADJUST_KEY] = run_id
    saved = AsyncMock()
    monkeypatch.setattr(h, "_save_and_reply_note", saved)

    await h.message(make_update(text="idea suelta para luego"), ctx)
    saved.assert_awaited_once()


async def test_undo_after_approve(world, monkeypatch):
    await _plan()
    run_id = _runs(world["engine"])[0].id
    monkeypatch.setattr(calendar_api, "create_event", lambda *a, **k: ("ev1", "l"))
    deleted = []
    monkeypatch.setattr(calendar_api, "delete_event", deleted.append)
    update, _ = make_callback(f"rt:approve:{run_id}")
    await rh.callback_routine(update, make_context())

    update, query = make_callback(f"rt:undo:{run_id}")
    await rh.callback_routine(update, make_context())

    assert deleted == ["ev1"]
    assert "1 eventos borrados" in query.edit_message_text.call_args.args[0]


async def test_cmd_routines_lists_runs_and_run_button(world):
    await _plan()
    update = make_update()
    await rh.cmd_routines(update, make_context())
    text = update.message.reply_text.call_args.args[0]
    kb = update.message.reply_text.call_args.kwargs["reply_markup"]
    assert "Planificación semanal" in text and "Revisión semanal" in text and "pendiente" in text
    datas = [row[0].callback_data for row in kb.inline_keyboard]
    assert set(datas) == {"rt:run:weekly_plan", "rt:run:weekly_review"}


async def test_run_button_executes_routine(world):
    update, query = make_callback("rt:run:weekly_plan")
    ctx = make_context()
    await rh.callback_routine(update, ctx)
    assert _runs(world["engine"])[0].trigger == "manual"
    ctx.bot.send_message.assert_awaited()
