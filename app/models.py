from sqlmodel import SQLModel
# Los modelos de cada módulo se importan aquí para que create_db() los registre
# from app.modules.finanzas.models import *
from app.modules.spotify.models import SpotifyToken  # noqa: F401
