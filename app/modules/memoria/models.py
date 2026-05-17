from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class Memoria(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hecho: str
    fecha: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
