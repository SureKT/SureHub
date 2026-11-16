from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.modules.routines.models import RoutineRun
from app.modules.routines.registry import ROUTINES
from app.modules.routines.service import (
    Outcome, Routine, execute, list_runs, missed_fire, needs_catch_up,
)

TZ = ZoneInfo("Europe/Madrid")


def _routine(run=None, cron="0 19 * * sun", catch_up_hours=14):
    return Routine(key="test", name="Test", description="", cron=cron, timezone="Europe/Madrid",
                   engine="litellm", run=run or (lambda s, ctx: Outcome(output={"ok": 1})),
                   catch_up_hours=catch_up_hours)


def test_weekly_review_registered_sunday_18_madrid():
    r = ROUTINES["weekly_review"]
    fire = r.trigger().get_next_fire_time(None, datetime(2026, 11, 16, 10, tzinfo=TZ))
    assert fire == datetime(2026, 11, 22, 18, tzinfo=TZ)


def test_weekly_plan_has_no_schedule_of_its_own():
    # launched after the review (or skip) and by /plan, never by cron
    assert ROUTINES["weekly_plan"].trigger() is None
    assert missed_fire(ROUTINES["weekly_plan"], datetime(2026, 11, 22, 20, tzinfo=TZ)) is None


def test_trigger_respects_dst():
    # last Sunday of October: CEST → CET, still 19:00 local
    r = _routine()
    fire = r.trigger().get_next_fire_time(None, datetime(2026, 10, 24, tzinfo=TZ))
    assert (fire.hour, fire.utcoffset()) == (19, timedelta(hours=1))


def test_execute_success_persists_output(session):
    run = execute(session, _routine(), "manual", now=datetime(2026, 11, 22, 19, tzinfo=TZ))
    assert run.status == "succeeded"
    assert run.output == '{"ok": 1}'
    assert run.finished_at is not None
    assert run.engine == "litellm"


def test_execute_failure_is_recorded_not_raised(session):
    def boom(s, ctx):
        raise RuntimeError("calendar down")
    run = execute(session, _routine(run=boom), "scheduled")
    assert run.status == "failed"
    assert "calendar down" in run.error


def test_execute_passes_context_and_supersedes_parent(session):
    seen = {}

    def capture(s, ctx):
        seen.update(trigger=ctx.trigger, correction=ctx.correction, parent=ctx.parent.id,
                    engine=ctx.engine)
        return Outcome(status="awaiting_approval")

    parent = execute(session, _routine(lambda s, c: Outcome(status="awaiting_approval")), "manual")
    child = execute(session, _routine(capture), "adjust", parent=parent, correction="menos pádel")

    assert seen == {"trigger": "adjust", "correction": "menos pádel", "parent": parent.id,
                    "engine": "litellm"}
    assert child.parent_run_id == parent.id
    session.refresh(parent)
    assert parent.status == "superseded"


def test_failed_adjust_keeps_parent_pending(session):
    parent = execute(session, _routine(lambda s, c: Outcome(status="awaiting_approval")), "manual")

    def boom(s, ctx):
        raise ValueError("x")
    execute(session, _routine(boom), "adjust", parent=parent, correction="c")
    session.refresh(parent)
    assert parent.status == "awaiting_approval"


def test_list_runs_newest_first_and_filtered(session):
    for key in ("a", "b", "a"):
        session.add(RoutineRun(routine_key=key))
    session.commit()
    runs = list_runs(session, "a")
    assert [r.routine_key for r in runs] == ["a", "a"]
    assert runs[0].id > runs[1].id


@pytest.mark.parametrize("now,expected", [
    (datetime(2026, 11, 22, 20, tzinfo=TZ), datetime(2026, 11, 22, 19, tzinfo=TZ)),  # 1h late
    (datetime(2026, 11, 23, 8, 59, tzinfo=TZ), datetime(2026, 11, 22, 19, tzinfo=TZ)),  # Monday early
    (datetime(2026, 11, 23, 9, 30, tzinfo=TZ), None),   # past the 14h window
    (datetime(2026, 11, 22, 18, tzinfo=TZ), None),      # before the fire
])
def test_missed_fire_window(now, expected):
    assert missed_fire(_routine(), now) == expected


def test_no_catch_up_when_disabled():
    assert missed_fire(_routine(catch_up_hours=0), datetime(2026, 11, 22, 20, tzinfo=TZ)) is None


def test_needs_catch_up_only_without_run_since_fire(session):
    r = _routine()
    now = datetime(2026, 11, 22, 21, tzinfo=TZ)
    assert needs_catch_up(session, r, now) is True

    # a run before the fire (e.g. last week) doesn't count
    session.add(RoutineRun(routine_key="test", started_at=datetime(2026, 11, 22, 17, 0)))  # 18:00 local
    session.commit()
    assert needs_catch_up(session, r, now) is True

    # any run after the fire (manual /plan included) does
    session.add(RoutineRun(routine_key="test", started_at=datetime(2026, 11, 22, 18, 30)))  # 19:30 local
    session.commit()
    assert needs_catch_up(session, r, now) is False


def test_schedule_routines_registers_cron_and_catch_up(monkeypatch, engine):
    import bot.routine_handlers as rh

    monkeypatch.setattr(rh, "engine", engine)
    monkeypatch.setattr(rh, "needs_catch_up", lambda s, r, now: True)
    app = MagicMock()

    rh.schedule_routines(app)

    scheduled = [c.kwargs["data"] for c in app.job_queue.run_custom.call_args_list]
    assert scheduled == [{"key": "weekly_review", "trigger": "scheduled"}]
    caught = [c.kwargs["data"]["key"] for c in app.job_queue.run_once.call_args_list]
    assert "weekly_review" in caught


def test_schedule_routines_no_catch_up_when_not_needed(monkeypatch, engine):
    import bot.routine_handlers as rh

    monkeypatch.setattr(rh, "engine", engine)
    monkeypatch.setattr(rh, "needs_catch_up", lambda s, r, now: False)
    app = MagicMock()
    rh.schedule_routines(app)
    app.job_queue.run_once.assert_not_called()
