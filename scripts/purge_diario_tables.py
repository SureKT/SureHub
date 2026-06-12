"""Drop legacy diario tables after Obsidian migration. Run once against surehub.db."""
import argparse
import sqlite3
import sys
from pathlib import Path

TABLES = ("metriclog", "metricfield", "diaryentry", "diarycollection")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db_path", nargs="?", default="surehub.db")
    parser.add_argument("--dry-run", action="store_true", help="List tables only, do not drop")
    args = parser.parse_args()

    db = Path(args.db_path)
    if not db.exists():
        print(f"DB not found: {db}", file=sys.stderr)
        return 1

    con = sqlite3.connect(db)
    cur = con.cursor()
    existing = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    targets = [t for t in TABLES if t in existing]

    if not targets:
        print("No diario tables found — already purged.")
        con.close()
        return 0

    for t in targets:
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n} rows")

    if args.dry_run:
        print("Dry run — nothing dropped.")
        con.close()
        return 0

    cur.execute("PRAGMA foreign_keys=OFF")
    for t in targets:
        cur.execute(f"DROP TABLE IF EXISTS {t}")
        print(f"Dropped {t}")
    cur.execute("VACUUM")
    con.commit()
    con.close()
    print(f"Purged {len(targets)} tables from {db.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
