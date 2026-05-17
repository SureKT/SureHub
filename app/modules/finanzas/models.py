from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class Gasto(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    descripcion: str
    cantidad: float
    categoria: Optional[str] = None
    fecha: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fuente: str = "telegram"  # telegram | csv | manual
