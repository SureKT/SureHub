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
                   run=run or (lambda s, ctx: Outcome(output={"ok": 1})),
                   catch_up_hours=catch_up_hours)


def test_weekly_review_not_scheduled():
    # the Claude scheduled task does the review now; SureHub's is manual only
    r = ROUTINES["weekly_review"]
    assert r.scheduled is False
    assert r.cron == "0 18 * * sun"  # kept so re-enabling is a one-line change


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


def test_execute_failure_is_recorded_not_raised(session):
    def boom(s, ctx):
        raise RuntimeError("calendar down")
    run = execute(session, _routine(run=boom), "scheduled")
    assert run.status == "failed"
    assert "calendar down" in run.error


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

    # any run after the fire (manual included) does
    session.add(RoutineRun(routine_key="test", started_at=datetime(2026, 11, 22, 18, 30)))  # 19:30 local
    session.commit()
    assert needs_catch_up(session, r, now) is False


def test_schedule_routines_registers_cron_and_catch_up(monkeypatch, engine):
    import bot.routine_handlers as rh

    manual = Routine(key="manual", name="M", description="", cron="0 9 * * *",
                     timezone="Europe/Madrid", run=lambda s, ctx: Outcome(), scheduled=False)
    monkeypatch.setattr(rh, "ROUTINES", {"test": _routine(), "manual": manual})
    monkeypatch.setattr(rh, "engine", engine)
    monkeypatch.setattr(rh, "needs_catch_up", lambda s, r, now: True)
    app = MagicMock()

    rh.schedule_routines(app)

    # scheduled=False routines get neither a cron job nor a catch-up
    scheduled = [c.kwargs["data"] for c in app.job_queue.run_custom.call_args_list]
    assert scheduled == [{"key": "test", "trigger": "scheduled"}]
    caught = [c.kwargs["data"]["key"] for c in app.job_queue.run_once.call_args_list]
    assert caught == ["test"]


def test_schedule_routines_no_catch_up_when_not_needed(monkeypatch, engine):
    import bot.routine_handlers as rh

    monkeypatch.setattr(rh, "engine", engine)
    monkeypatch.setattr(rh, "needs_catch_up", lambda s, r, now: False)
    app = MagicMock()
    rh.schedule_routines(app)
    app.job_queue.run_once.assert_not_called()
