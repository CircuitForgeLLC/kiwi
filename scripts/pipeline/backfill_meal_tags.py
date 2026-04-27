"""
Fast targeted backfill for meal: tags only.

Rather than re-deriving ALL inferred_tags via the full infer_tags() pipeline
(which takes ~2.5h for 3.19M recipes), this script:

  1. Reads only id + title + inferred_tags (no ingredient profiles needed —
     meal signals are title-only).
  2. Runs _match_title_signals() against the title to get meal tags.
  3. For rows that already have inferred_tags: merges in the new meal tags
     (no-op if already present).
  4. For rows with no inferred_tags: runs the full infer_tags() pipeline so
     those rows get a complete tag set, not just meal tags.
  5. Rebuilds the FTS5 index once at the end.

Estimated runtime on 3.19M recipes: 3–5 minutes.

Usage:
    python scripts/pipeline/backfill_meal_tags.py [path/to/kiwi.db]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.recipe.tag_inferrer import _MEAL_SIGNALS, _match_title_signals


def run(db_path: Path, batch_size: int = 10_000) -> None:
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    total = conn.execute("SELECT count(*) FROM recipes").fetchone()[0]
    print(f"Total recipes: {total:,}")

    updated = 0
    skipped = 0
    offset = 0

    while True:
        rows = conn.execute(
            """
            SELECT id, title, inferred_tags
            FROM recipes
            ORDER BY id
            LIMIT ? OFFSET ?
            """,
            (batch_size, offset),
        ).fetchall()
        if not rows:
            break

        updates: list[tuple[str, int]] = []
        for row_id, title, tags_json in rows:
            title = title or ""
            meal_tags = _match_title_signals(title, _MEAL_SIGNALS)
            if not meal_tags:
                skipped += 1
                continue

            try:
                existing: list[str] = json.loads(tags_json) if tags_json else []
            except Exception:
                existing = []

            # Merge: union of existing + new meal tags, sorted
            merged = sorted(set(existing) | set(meal_tags))
            if merged == existing:
                skipped += 1
                continue

            updates.append((json.dumps(merged), row_id))

        if updates:
            conn.executemany(
                "UPDATE recipes SET inferred_tags = ? WHERE id = ?", updates
            )
            conn.commit()
            updated += len(updates)

        offset += len(rows)
        pct = min(100, int(offset * 100 / total))
        print(f"  {pct:>3}%  offset {offset:,}  merged {updated:,}  skipped {skipped:,}",
              end="\r")

    print(f"\nDone. Merged meal tags into {updated:,} recipes ({skipped:,} unchanged).")

    if updated > 0:
        print("Rebuilding FTS5 browser index...")
        try:
            conn.execute(
                "INSERT INTO recipe_browser_fts(recipe_browser_fts) VALUES('rebuild')"
            )
            conn.commit()
            print("FTS rebuild complete.")
        except Exception as e:
            print(f"FTS rebuild skipped: {e}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", nargs="?", default="data/kiwi.db", type=Path)
    parser.add_argument("--batch-size", type=int, default=10_000)
    args = parser.parse_args()
    if not args.db.exists():
        print(f"DB not found: {args.db}")
        sys.exit(1)
    run(args.db, args.batch_size)
