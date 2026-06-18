from sqlmodel import SQLModel, create_engine, Session
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "local",
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)


# Idempotent SQLite ADD COLUMN migrations for tables that predate new fields.
# create_all() only creates missing tables, never alters existing ones, so columns
# added to an already-deployed table must be backfilled here at startup.
_COLUMN_MIGRATIONS = {
    "inbox_items": {
        "event_start": "TEXT",
        "event_end": "TEXT",
        "all_day": "BOOLEAN DEFAULT 0",
        "theme": "TEXT DEFAULT ''",
        "calendar_event_id": "TEXT",
    },
}


def _migrate(target_engine=engine):
    if "sqlite" not in str(target_engine.url):
        return
    with target_engine.begin() as conn:
        for table, cols in _COLUMN_MIGRATIONS.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if not existing:
                continue  # table doesn't exist yet → create_all handles it
            for name, ddl in cols.items():
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def create_db():
    SQLModel.metadata.create_all(engine)
    _migrate()


def get_session():
    with Session(engine) as session:
        yield session
