"""
One-time migration: rename Spanish tables/columns to English, update data values.
Run from repo root with venv active: python scripts/migrate_to_english.py
Safe to run multiple times (checks if old names exist before acting).
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "surehub.db"


def tables(cur) -> set[str]:
    return {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def columns(cur, table: str) -> set[str]:
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def main():
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}. Nothing to do.")
        sys.exit(0)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")
    cur.execute("PRAGMA journal_mode = WAL")

    existing = tables(cur)
    print(f"Existing tables: {sorted(existing)}")

    # --- categoria → category ---
    if "categoria" in existing:
        print("Migrating 'categoria' table...")
        cols = columns(cur, "categoria")
        if "nombre" in cols:
            cur.execute("ALTER TABLE categoria RENAME COLUMN nombre TO name")
        if "tipo" in cols:
            cur.execute("ALTER TABLE categoria RENAME COLUMN tipo TO type")
        if "estimacion_mensual" in cols:
            cur.execute("ALTER TABLE categoria RENAME COLUMN estimacion_mensual TO monthly_estimate")
        if "activa" in cols:
            cur.execute("ALTER TABLE categoria RENAME COLUMN activa TO active")
        cur.execute("ALTER TABLE categoria RENAME TO category")
        print("  Done.")
    elif "category" in existing:
        print("'category' already exists, skipping.")

    # --- gastorecurrente → recurringexpense ---
    if "gastorecurrente" in existing:
        print("Migrating 'gastorecurrente' table...")
        cols = columns(cur, "gastorecurrente")
        if "nombre" in cols:
            cur.execute("ALTER TABLE gastorecurrente RENAME COLUMN nombre TO name")
        if "cantidad" in cols:
            cur.execute("ALTER TABLE gastorecurrente RENAME COLUMN cantidad TO amount")
        if "dia" in cols:
            cur.execute("ALTER TABLE gastorecurrente RENAME COLUMN dia TO day")
        if "activo" in cols:
            cur.execute("ALTER TABLE gastorecurrente RENAME COLUMN activo TO active")
        cur.execute("ALTER TABLE gastorecurrente RENAME TO recurringexpense")
        print("  Done.")
    elif "recurringexpense" in existing:
        print("'recurringexpense' already exists, skipping.")

    # --- gasto → expense ---
    if "gasto" in existing:
        print("Migrating 'gasto' table...")
        cols = columns(cur, "gasto")
        if "cantidad" in cols:
            cur.execute("ALTER TABLE gasto RENAME COLUMN cantidad TO amount")
        if "descripcion" in cols:
            cur.execute("ALTER TABLE gasto RENAME COLUMN descripcion TO description")
        if "fecha" in cols:
            cur.execute("ALTER TABLE gasto RENAME COLUMN fecha TO date")
        if "fuente" in cols:
            cur.execute("ALTER TABLE gasto RENAME COLUMN fuente TO source")
        if "categoria_id" in cols:
            cur.execute("ALTER TABLE gasto RENAME COLUMN categoria_id TO category_id")
        if "recurrente_id" in cols:
            cur.execute("ALTER TABLE gasto RENAME COLUMN recurrente_id TO recurring_id")
        cur.execute("ALTER TABLE gasto RENAME TO expense")
        # Update data values
        cur.execute("UPDATE expense SET source = 'import' WHERE source = 'importacion'")
        cur.execute("UPDATE expense SET source = 'recurring' WHERE source = 'recurrente'")
        n = con.total_changes
        print(f"  Updated {n} source values.")
        print("  Done.")
    elif "expense" in existing:
        print("'expense' already exists, skipping.")
        # Still update data values in case they weren't migrated
        cur.execute("UPDATE expense SET source = 'import' WHERE source = 'importacion'")
        cur.execute("UPDATE expense SET source = 'recurring' WHERE source = 'recurrente'")

    # Update category type values (fijo → fixed)
    if "category" in tables(cur):
        cur.execute("UPDATE category SET type = 'fixed' WHERE type = 'fijo'")
        cur.execute("UPDATE category SET type = 'variable' WHERE type = 'variable'")
        n = con.total_changes
        print(f"Updated {n} category type values.")

    # --- memoria → memory ---
    if "memoria" in existing:
        print("Migrating 'memoria' table...")
        cols = columns(cur, "memoria")
        if "hecho" in cols:
            cur.execute("ALTER TABLE memoria RENAME COLUMN hecho TO fact")
        if "fecha" in cols:
            cur.execute("ALTER TABLE memoria RENAME COLUMN fecha TO date")
        cur.execute("ALTER TABLE memoria RENAME TO memory")
        print("  Done.")
    elif "memory" in existing:
        print("'memory' already exists, skipping.")

    cur.execute("PRAGMA foreign_keys = ON")
    con.commit()
    con.close()

    print("\nMigration complete.")
    con2 = sqlite3.connect(DB_PATH)
    print(f"Tables now: {sorted(tables(con2.cursor()))}")
    con2.close()


if __name__ == "__main__":
    main()
