from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class DiaryCollection(SQLModel, table=True):
    __tablename__ = "diarycollection"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    type: str = "journal"  # journal | timeline


class MetricField(SQLModel, table=True):
    __tablename__ = "metricfield"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    field_type: str = "number"  # number | text | scale
    active: bool = Field(default=True)
    order: int = Field(default=0)


class DiaryEntry(SQLModel, table=True):
    __tablename__ = "diaryentry"
    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    title: Optional[str] = None
    text: Optional[str] = None
    collection_id: Optional[int] = Field(default=None, foreign_key="diarycollection.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricLog(SQLModel, table=True):
    __tablename__ = "metriclog"
    id: Optional[int] = Field(default=None, primary_key=True)
    entry_id: int = Field(foreign_key="diaryentry.id")
    field_id: int = Field(foreign_key="metricfield.id")
    value: str
