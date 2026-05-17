from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class Categoria(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)
    tipo: str  # "variable" | "fijo"
    estimacion_mensual: float = 0.0
    activa: bool = Field(default=True)


class GastoRecurrente(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    cantidad: float
    categoria_id: Optional[int] = Field(default=None, foreign_key="categoria.id")
    dia: int = Field(default=1)  # day of month to generate (1-28)
    activo: bool = Field(default=True)


class Gasto(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    categoria_id: Optional[int] = Field(default=None, foreign_key="categoria.id")
    recurrente_id: Optional[int] = Field(default=None, foreign_key="gastorecurrente.id")
    cantidad: float
    descripcion: Optional[str] = None
    fecha: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fuente: str = "telegram"  # telegram | manual | importacion | recurrente
