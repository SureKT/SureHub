import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.modules.routines.models import RoutineRun

logger = logging.getLogger("surehub.routines")


@dataclass
class RunContext:
    now: datetime                        # tz-aware, routine timezone
    trigger: str


@dataclass
class Outcome:
    status: str = "succeeded"            # succeeded | awaiting_input
    output: dict = field(default_factory=dict)
    cost_usd: float = 0.0


@dataclass(frozen=True)
class Routine:
    key: str
    name: str
    description: str
    cron: str                            # crontab, 5 fields, in `timezone`
    timezone: str
    run: Callable[[Session, RunContext], Outcome]
    # If the bot was down at fire time (deploy, restart), run on startup as long
    # as we're within this many hours of the missed fire. 0 = no catch-up.
    catch_up_hours: int = 0
    # False = no cron or catch-up; still runnable by hand from /routines.
    scheduled: bool = True

    def trigger(self) -> CronTrigger:
        return CronTrigger.from_crontab(self.cron, timezone=ZoneInfo(self.timezone))


def _utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def execute(session: Session, routine: Routine, trigger: str, *,
            now: datetime | None = None) -> RoutineRun:
    """Run a routine and persist the run. Never raises: failures end as status=failed
    so the caller can alert instead of losing the error in a job thread."""
    now = now or datetime.now(ZoneInfo(routine.timezone))
    run = RoutineRun(routine_key=routine.key, trigger=trigger)
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        outcome = routine.run(session, RunContext(now=now, trigger=trigger))
        run.status = outcome.status
        run.output = json.dumps(outcome.output, ensure_ascii=False)
        run.cost_usd = outcome.cost_usd
    except Exception as e:
        logger.exception("Routine %s failed", routine.key)
        run.status = "failed"
        run.error = f"{type(e).__name__}: {e}"[:2000]

    run.finished_at = datetime.utcnow()
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_run(session: Session, run_id: int) -> RoutineRun | None:
    return session.get(RoutineRun, run_id)


def list_runs(session: Session, routine_key: str | None = None, limit: int = 20) -> list[RoutineRun]:
    stmt = select(RoutineRun).order_by(RoutineRun.started_at.desc(), RoutineRun.id.desc()).limit(limit)
    if routine_key:
        stmt = stmt.where(RoutineRun.routine_key == routine_key)
    return list(session.exec(stmt))


def last_run(session: Session, routine_key: str) -> RoutineRun | None:
    runs = list_runs(session, routine_key, limit=1)
    return runs[0] if runs else None


def missed_fire(routine: Routine, now: datetime) -> datetime | None:
    """Most recent fire time within the catch-up window (≤ now), or None."""
    if routine.catch_up_hours <= 0:
        return None
    trigger = routine.trigger()
    window_start = now - timedelta(hours=routine.catch_up_hours)
    fire = trigger.get_next_fire_time(None, window_start)
    last = None
    while fire is not None and fire <= now:
        last = fire
        fire = trigger.get_next_fire_time(fire, fire + timedelta(seconds=1))
    return last


def needs_catch_up(session: Session, routine: Routine, now: datetime) -> bool:
    fire = missed_fire(routine, now)
    if fire is None:
        return False
    # Any run (manual included) since the missed fire counts: the user already got it.
    stmt = select(RoutineRun).where(RoutineRun.routine_key == routine.key,
                                    RoutineRun.started_at >= _utc_naive(fire))
    return session.exec(stmt).first() is None


def load_json(raw: str) -> Any:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
