from sqlmodel import SQLModel
# Los modelos de cada módulo se importan aquí para que create_db() los registre
from app.modules.finanzas.models import Gasto  # noqa: F401
from app.modules.memoria.models import Memoria  # noqa: F401
