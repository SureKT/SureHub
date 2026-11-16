from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


class RoutineRun(SQLModel, table=True):
    """One execution of a routine. Routine definitions live in code (registry.py);
    only runs are persisted, so prompts and schedules stay versioned and tested."""

    __tablename__ = "routine_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    routine_key: str = Field(index=True)
    trigger: str = "manual"            # scheduled | manual | catch_up | adjust
    status: str = "running"            # running | succeeded | failed | awaiting_approval |
                                       # approving | approved | discarded | superseded | undone
    engine: str = ""
    parent_run_id: Optional[int] = Field(default=None, foreign_key="routine_runs.id")
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True, sa_type=DateTime)
    finished_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    output: str = ""                   # JSON: what the routine produced (e.g. proposal)
    result: str = ""                   # JSON: side effects applied (event ids, note path)
    error: Optional[str] = None
    cost_usd: float = 0.0
