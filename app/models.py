from sqlmodel import SQLModel
from app.modules.finanzas.models import Expense, RecurringExpense, Category  # noqa: F401
from app.modules.memoria.models import Memory  # noqa: F401
from app.modules.inbox.models import InboxItem  # noqa: F401
from app.modules.calendar.models import GoogleToken  # noqa: F401
