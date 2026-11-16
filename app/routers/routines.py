from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.modules.routines.registry import ROUTINES
from app.modules.routines.service import get_run, last_run, list_runs, load_json

router = APIRouter(prefix="/api/routines", tags=["routines"])


def _run_dict(run) -> dict:
    return {
        "id": run.id,
        "routine_key": run.routine_key,
        "trigger": run.trigger,
        "status": run.status,
        "engine": run.engine,
        "parent_run_id": run.parent_run_id,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "cost_usd": run.cost_usd,
        "error": run.error,
    }


@router.get("")
def routines(session: Session = Depends(get_session)):
    out = []
    for r in ROUTINES.values():
        last = last_run(session, r.key)
        out.append({
            "key": r.key, "name": r.name, "description": r.description, "cron": r.cron,
            "timezone": r.timezone, "engine": r.engine,
            "last_run": _run_dict(last) if last else None,
        })
    return out


@router.get("/runs")
def runs(routine_key: str | None = None, limit: int = 20, session: Session = Depends(get_session)):
    return [_run_dict(r) for r in list_runs(session, routine_key, min(limit, 200))]


@router.get("/runs/{run_id}")
def run_detail(run_id: int, session: Session = Depends(get_session)):
    run = get_run(session, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return {**_run_dict(run), "output": load_json(run.output), "result": load_json(run.result)}
