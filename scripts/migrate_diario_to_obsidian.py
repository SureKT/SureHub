"""Migrate diary data (diaryentry, metriclog) from the SureHub DB to Obsidian daily notes.

Usage:
    python scripts/migrate_diario_to_obsidian.py [db_path] [--out DIR]

Defaults: db_path=surehub.db, --out ./diario_export/

Output: one YYYY-MM-DD.md per calendar day with at least one entry or metric.
Frontmatter is Dataview-compatible (key: value). Multiple entries on the same
day are concatenated as sections in the body. Days with metrics but no text
produce a note with frontmatter only.

Read-only on the DB. Does not delete anything.
"""
import argparse
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

EXPECTED_TABLES = ("diaryentry", "diarycollection", "metricfield", "metriclog")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "field"


def yaml_value(raw: str):
    """Render a metric value so Dataview sees numbers as numbers."""
    s = raw.strip()
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    if re.fullmatch(r"[\w .,\-áéíóúüñÁÉÍÓÚÜÑ]*", s) and not s.startswith(("-", " ")):
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def day_of(dt_str: str) -> str:
    return dt_str[:10]


def time_of(dt_str: str) -> str:
    return dt_str[11:16] if len(dt_str) >= 16 else ""


def build_note(day: str, entries: list[dict], metrics_by_entry: dict[int, list[dict]]) -> str:
    collections = []
    day_metrics = []  # (slug, value) in field order
    seen_slugs = {}
    for e in entries:
        if e["collection_name"] and e["collection_name"] not in collections:
            collections.append(e["collection_name"])
        for m in metrics_by_entry.get(e["id"], []):
            slug = slugify(m["field_name"])
            if slug in seen_slugs:
                seen_slugs[slug] += 1
                slug = f"{slug}_{seen_slugs[slug]}"
            else:
                seen_slugs[slug] = 1
            day_metrics.append((m["field_order"], slug, yaml_value(m["value"])))
    day_metrics.sort(key=lambda t: (t[0], t[1]))

    lines = ["---", f"date: {day}"]
    if collections:
        lines.append("collections: [" + ", ".join(collections) + "]")
    for _, slug, value in day_metrics:
        lines.append(f"{slug}: {value}")
    lines.append("---")

    content_entries = [e for e in entries if e["title"] or e["text"]]
    body = []
    for e in content_entries:
        heading = e["title"] or time_of(e["date"]) or "Entry"
        if len(content_entries) > 1 or e["title"]:
            body.append(f"## {heading}")
        if e["text"]:
            body.append(e["text"].strip())

    note = "\n".join(lines) + "\n"
    if body:
        note += "\n" + "\n\n".join(body) + "\n"
    return note


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("db_path", nargs="?", default="surehub.db", help="SQLite DB path (default: surehub.db)")
    parser.add_argument("--out", "-o", default="./diario_export", help="Output folder (default: ./diario_export)")
    args = parser.parse_args()

    db = Path(args.db_path)
    if not db.exists():
        print(f"DB not found: {db}", file=sys.stderr)
        return 1

    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    existing = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = [t for t in EXPECTED_TABLES if t not in existing]
    if missing:
        print(f"Missing diary tables in {db}: {', '.join(missing)}", file=sys.stderr)
        return 1

    entries = [dict(r) for r in cur.execute(
        """SELECT e.id, e.date, e.title, e.text, c.name AS collection_name
           FROM diaryentry e
           LEFT JOIN diarycollection c ON c.id = e.collection_id
           ORDER BY e.date, e.created_at"""
    )]
    metrics_by_entry: dict[int, list[dict]] = defaultdict(list)
    for r in cur.execute(
        """SELECT l.entry_id, f.name AS field_name, f."order" AS field_order, l.value
           FROM metriclog l
           JOIN metricfield f ON f.id = l.field_id
           ORDER BY f."order", f.name, l.id"""
    ):
        metrics_by_entry[r["entry_id"]].append(dict(r))
    con.close()

    by_day: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_day[day_of(e["date"])].append(e)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for day in sorted(by_day):
        note = build_note(day, by_day[day], metrics_by_entry)
        (out_dir / f"{day}.md").write_text(note, encoding="utf-8")

    n_metrics = sum(len(v) for v in metrics_by_entry.values())
    print(f"Exported {len(entries)} entries ({n_metrics} metric logs) into {len(by_day)} daily notes -> {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
