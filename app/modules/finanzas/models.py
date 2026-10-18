from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime
from sqlmodel import SQLModel, Field


class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    type: str  # "variable" | "fixed"
    monthly_estimate: float = 0.0
    active: bool = Field(default=True)


class RecurringExpense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    amount: float
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")
    day: int = Field(default=1)  # day of month to generate (1-28)
    active: bool = Field(default=True)


class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")
    recurring_id: Optional[int] = Field(default=None, foreign_key="recurringexpense.id")
    amount: float
    description: Optional[str] = None
    # sa_type=DateTime (naive) en todos los datetime: sqlmodel>=0.0.45 usaría UTCDateTime,
    # que rechaza naive, devuelve aware y rompe los bounds string de _month_range.
    # Ver tests/test_models_datetime.py.
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime)
    source: str = "telegram"  # telegram | manual | import | recurring
