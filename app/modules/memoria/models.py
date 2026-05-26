from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class Memory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    fact: str
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
