from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "local",
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)


def _migrate(eng):
    """Apply incremental SQLite column additions without losing data."""
    with eng.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(gasto)"))
        cols = {row[1] for row in result.fetchall()}
        if "recurrente_id" not in cols:
            conn.execute(text(
                "ALTER TABLE gasto ADD COLUMN recurrente_id INTEGER REFERENCES gastorecurrente(id)"
            ))
            conn.commit()


def create_db():
    SQLModel.metadata.create_all(engine)
    if "sqlite" in settings.DATABASE_URL:
        _migrate(engine)


def get_session():
    with Session(engine) as session:
        yield session
