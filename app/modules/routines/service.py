import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.modules.routines.models import RoutineRun

logger = logging.getLogger("surehub.routines")


@dataclass
class RunContext:
    now: datetime                        # tz-aware, routine timezone
    trigger: str
    engine: str = "litellm"
    parent: Optional[RoutineRun] = None  # previous run when regenerating (adjust)
    correction: Optional[str] = None
    options: dict = field(default_factory=dict)   # manual-run arguments (e.g. /plan semana)


@dataclass
class Outcome:
    status: str = "succeeded"            # succeeded | awaiting_approval
    output: dict = field(default_factory=dict)
    cost_usd: float = 0.0


@dataclass(frozen=True)
class Routine:
    key: str
    name: str
    description: str
    cron: Optional[str]                  # crontab, 5 fields, in `timezone`; None = only triggered
    timezone: str
    engine: str                          # litellm | claude_code
    run: Callable[[Session, RunContext], Outcome]
    # If the bot was down at fire time (deploy, restart), run on startup as long
    # as we're within this many hours of the missed fire. 0 = no catch-up.
    catch_up_hours: int = 0

    def trigger(self) -> CronTrigger | None:
        if not self.cron:
            return None
        return CronTrigger.from_crontab(self.cron, timezone=ZoneInfo(self.timezone))


def _utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def execute(session: Session, routine: Routine, trigger: str, *, now: datetime | None = None,
            parent: RoutineRun | None = None, correction: str | None = None,
            options: dict | None = None) -> RoutineRun:
    """Run a routine and persist the run. Never raises: failures end as status=failed
    so the caller can alert instead of losing the error in a job thread."""
    now = now or datetime.now(ZoneInfo(routine.timezone))
    run = RoutineRun(routine_key=routine.key, trigger=trigger, engine=routine.engine,
                     parent_run_id=parent.id if parent else None)
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        outcome = routine.run(session, RunContext(now=now, trigger=trigger, engine=routine.engine, parent=parent,
                                                  correction=correction, options=options or {}))
        run.status = outcome.status
        run.output = json.dumps(outcome.output, ensure_ascii=False)
        run.cost_usd = outcome.cost_usd
        if parent is not None:
            parent.status = "superseded"
            session.add(parent)
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
    trigger = routine.trigger()
    if routine.catch_up_hours <= 0 or trigger is None:
        return None
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
