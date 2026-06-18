from sqlalchemy import create_engine

from app.database import _migrate

NEW_COLS = {"event_start", "event_end", "all_day", "theme", "calendar_event_id"}


def _cols(engine, table):
    with engine.begin() as conn:
        return {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}


def test_migrate_adds_missing_inbox_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE inbox_items (id INTEGER PRIMARY KEY, filename TEXT)")

    _migrate(engine)

    assert NEW_COLS <= _cols(engine, "inbox_items")


def test_migrate_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE inbox_items (id INTEGER PRIMARY KEY, filename TEXT)")

    _migrate(engine)
    _migrate(engine)  # second run must not raise

    assert NEW_COLS <= _cols(engine, "inbox_items")


def test_migrate_skips_when_table_absent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    _migrate(engine)  # no inbox_items table → no error
    assert _cols(engine, "inbox_items") == set()
