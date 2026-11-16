import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import Session, select

import bot.handlers as h
import bot.routine_handlers as rh
from app.modules.routines import weekly_review as wr
from app.modules.routines.engines import EngineResult
from app.modules.routines.models import RoutineRun
from app.modules.routines.registry import ROUTINES
from app.modules.routines.service import execute, load_json

TZ = ZoneInfo("Europe/Madrid")
SUNDAY = datetime(2026, 11, 22, 18, tzinfo=TZ)
QUESTIONS = "### Cuerpo\n- ¿Me he movido?\n### Vida\n- ¿He visto a gente?\n\n> **¿Qué cambiaría?**"
STRUCTURED = json.dumps({"body": "### Cuerpo\nPádel 3 días.\n### Vida\nRita el lunes.",
                         "summary": "Deporte bien. Prioridad: candidaturas."})


@pytest.fixture
def vault(tmp_path, monkeypatch):
    (tmp_path / "Personal").mkdir()
    (tmp_path / "Personal" / "Revisión semanal.md").write_text(QUESTIONS, encoding="utf-8")
    monkeypatch.setattr(wr.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


def test_review_asks_questions_from_the_users_note(session, vault):
    run = execute(session, ROUTINES["weekly_review"], "scheduled", now=SUNDAY)
    assert run.status == "awaiting_input"
    out = load_json(run.output)
    assert out == {"date": "2026-11-22", "questions": QUESTIONS}

    text = wr.render_questions(out)
    assert "<b>Cuerpo</b>" in text and "¿Me he movido?" in text
    assert "<i>¿Qué cambiaría?</i>" in text and "**" not in text


def test_review_falls_back_to_default_questions(session, tmp_path, monkeypatch):
    monkeypatch.setattr(wr.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    run = execute(session, ROUTINES["weekly_review"], "scheduled", now=SUNDAY)
    assert "Mente/Futuro" in load_json(run.output)["questions"]


def test_complete_writes_new_note_and_summary(session, vault, monkeypatch):
    run = execute(session, ROUTINES["weekly_review"], "scheduled", now=SUNDAY)
    prompts = []
    monkeypatch.setattr(wr, "run_litellm",
                        lambda p, **k: prompts.append(p) or EngineResult(text=STRUCTURED, cost_usd=0.01))

    out = wr.complete(session, run, "pues he jugado al pádel tres días y vi a Rita", vault)

    assert run.status == "succeeded" and run.cost_usd == 0.01
    assert out["note"] == "planificacion/revisiones/2026-11-22.md"
    note = (vault / out["note"]).read_text(encoding="utf-8")
    assert "tipo: revision" in note and "# Revisión semanal — 22 nov 2026" in note
    assert "Pádel 3 días." in note
    assert out["summary"] == "Deporte bien. Prioridad: candidaturas."
    assert "vi a Rita" in prompts[0] and "¿Me he movido?" in prompts[0]


def test_complete_never_overwrites_an_existing_note(session, vault, monkeypatch):
    existing = vault / "planificacion" / "revisiones" / "2026-11-22.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("mía, hecha a mano", encoding="utf-8")
    run = execute(session, ROUTINES["weekly_review"], "scheduled", now=SUNDAY)
    monkeypatch.setattr(wr, "run_litellm", lambda p, **k: EngineResult(text=STRUCTURED))

    out = wr.complete(session, run, "respuesta", vault)
    assert out["note"] == "planificacion/revisiones/2026-11-22-2.md"
    assert existing.read_text(encoding="utf-8") == "mía, hecha a mano"


def test_llm_failure_still_saves_the_raw_answer(session, vault, monkeypatch):
    run = execute(session, ROUTINES["weekly_review"], "scheduled", now=SUNDAY)

    def down(*a, **k):
        raise RuntimeError("API caída")
    monkeypatch.setattr(wr, "run_litellm", down)

    out = wr.complete(session, run, "mi revisión dictada entera", vault)
    assert "mi revisión dictada entera" in (vault / out["note"]).read_text(encoding="utf-8")
    assert "API caída" in out["structure_error"]
    assert run.status == "succeeded"


# ── Telegram flow ───────────────────────────────────────────────────────────

@pytest.fixture
def world(engine, vault, monkeypatch):
    monkeypatch.setattr(rh, "engine", engine)
    monkeypatch.setattr(wr, "run_litellm", lambda p, **k: EngineResult(text=STRUCTURED))
    return {"engine": engine, "vault": vault}


def _ctx():
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.args = []
    ctx.bot.send_message = AsyncMock(return_value=MagicMock(message_id=777))
    return ctx


def _update(text="", reply_to=None):
    u = MagicMock()
    u.effective_user.id = 111
    u.message.text = text
    u.message.reply_text = AsyncMock()
    u.message.reply_chat_action = AsyncMock()
    u.message.reply_to_message = MagicMock(message_id=reply_to) if reply_to else None
    u.effective_chat.send_message = AsyncMock()
    return u


def _runs(engine):
    with Session(engine) as s:
        return list(s.exec(select(RoutineRun).order_by(RoutineRun.id)))


async def _scheduled_review(ctx):
    ctx.job.data = {"key": "weekly_review", "trigger": "scheduled"}
    await rh.routine_job(ctx)


async def test_scheduled_review_sends_questions_and_stores_message_id(world):
    ctx = _ctx()
    await _scheduled_review(ctx)

    kw = ctx.bot.send_message.call_args.kwargs
    assert "Revisión semanal" in kw["text"]
    run = _runs(world["engine"])[0]
    assert [b.callback_data for b in kw["reply_markup"].inline_keyboard[0]] == [
        f"rt:answer:{run.id}", f"rt:skip:{run.id}"]
    assert load_json(run.result)["message_id"] == 777


async def test_answer_button_then_text_saves_review_and_sends_summary(world):
    ctx = _ctx()
    await _scheduled_review(ctx)
    review_id = _runs(world["engine"])[0].id

    cb = _update()
    cb.callback_query = MagicMock(data=f"rt:answer:{review_id}", answer=AsyncMock(),
                                  edit_message_text=AsyncMock())
    await rh.callback_routine(cb, ctx)
    assert ctx.user_data[rh.REVIEW_KEY] == review_id

    await h.message(_update(text="he hecho pádel 3 días, vi a Rita"), ctx)

    runs = _runs(world["engine"])
    assert [(r.routine_key, r.status) for r in runs] == [("weekly_review", "succeeded")]
    last = ctx.bot.send_message.call_args.kwargs["text"]
    assert "Resumen para el chat de planificación" in last and "<pre>" in last
    assert "Prioridad: candidaturas." in last


async def test_reply_to_the_questions_message_answers_after_restart(world):
    ctx = _ctx()
    await _scheduled_review(ctx)

    fresh = _ctx()   # bot restarted: no user_data, only the reply link
    await h.message(_update(text="mi revisión", reply_to=777), fresh)
    assert _runs(world["engine"])[0].status == "succeeded"


async def test_voice_answer(world, monkeypatch):
    ctx = _ctx()
    await _scheduled_review(ctx)
    ctx.user_data[rh.REVIEW_KEY] = _runs(world["engine"])[0].id
    ctx.bot.get_file = AsyncMock(return_value=MagicMock(download_to_drive=AsyncMock()))
    monkeypatch.setattr(h, "transcribe", lambda p: "revisión por voz")
    monkeypatch.setattr(h, "_save_and_reply_note", AsyncMock(side_effect=AssertionError("not a note")))

    await h.voice_message(_update(), ctx)
    assert load_json(_runs(world["engine"])[0].output)["answer"] == "revisión por voz"


async def test_skip_closes_the_review(world):
    ctx = _ctx()
    await _scheduled_review(ctx)
    review_id = _runs(world["engine"])[0].id
    cb = _update()
    cb.callback_query = MagicMock(data=f"rt:skip:{review_id}", answer=AsyncMock(),
                                  edit_message_text=AsyncMock())
    await rh.callback_routine(cb, ctx)

    runs = _runs(world["engine"])
    assert [(r.routine_key, r.status) for r in runs] == [("weekly_review", "skipped")]


async def test_unrelated_text_is_not_captured_as_review(world, monkeypatch):
    ctx = _ctx()
    await _scheduled_review(ctx)       # pending review, but Responder not pressed
    saved = AsyncMock()
    monkeypatch.setattr(h, "_save_and_reply_note", saved)

    await h.message(_update(text="idea suelta para luego"), _ctx())
    saved.assert_awaited_once()
    assert _runs(world["engine"])[0].status == "awaiting_input"
