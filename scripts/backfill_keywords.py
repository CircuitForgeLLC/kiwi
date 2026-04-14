#!/usr/bin/env python3
"""
Backfill keywords column: repair character-split R-vector data.

The food.com corpus was imported with Keywords stored as a JSON array of
individual characters (e.g. ["c","(","\"","I","t","a","l","i","a","n",...])
instead of the intended keyword list (e.g. ["Italian","Low-Fat","Easy"]).

This script detects the broken pattern (all array elements have length 1),
rejoins them into the original R-vector string, parses quoted tokens, and
writes the corrected JSON back.

Rows that are already correct (empty array, or multi-char strings) are skipped.
FTS5 index is rebuilt after the update so searches reflect the fix.

Usage:
    conda run -n cf python scripts/backfill_keywords.py [path/to/kiwi.db]
    # default: data/kiwi.db

Estimated time on 3.1M rows: 3-8 minutes (mostly the FTS rebuild at the end).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

_QUOTED = re.compile(r'"([^"]*)"')


def _parse_r_vector(s: str) -> list[str]:
    return _QUOTED.findall(s)


def _repair(raw_json: str) -> str | None:
    """Return corrected JSON string, or None if the row is already clean."""
    try:
        val = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(val, list) or not val:
        return None  # empty or non-list — leave as-is

    # Already correct: contains multi-character strings
    if any(isinstance(e, str) and len(e) > 1 for e in val):
        return None

    # Broken: all single characters — rejoin and re-parse
    if all(isinstance(e, str) and len(e) == 1 for e in val):
        rejoined = "".join(val)
        keywords = _parse_r_vector(rejoined)
        return json.dumps(keywords)

    return None


def backfill(db_path: Path, batch_size: int = 5000) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    total = conn.execute("SELECT count(*) FROM recipes").fetchone()[0]
    print(f"Total recipes: {total:,}")

    fixed = 0
    skipped = 0
    offset = 0

    while True:
        rows = conn.execute(
            "SELECT id, keywords FROM recipes LIMIT ? OFFSET ?",
            (batch_size, offset),
        ).fetchall()
        if not rows:
            break

        updates: list[tuple[str, int]] = []
        for row_id, raw_json in rows:
            corrected = _repair(raw_json)
            if corrected is not None:
                updates.append((corrected, row_id))
            else:
                skipped += 1

        if updates:
            conn.executemany(
                "UPDATE recipes SET keywords = ? WHERE id = ?", updates
            )
            conn.commit()
            fixed += len(updates)

        offset += batch_size
        done = offset + len(rows) - (batch_size - len(rows))
        pct = min(100, int((offset / total) * 100))
        print(f"  {pct:>3}%  processed {offset:,}  fixed {fixed:,}  skipped {skipped:,}", end="\r")

    print(f"\nDone. Fixed {fixed:,} rows, skipped {skipped:,} (already correct or empty).")

    if fixed > 0:
        print("Rebuilding FTS5 browser index (recipe_browser_fts)…")
        try:
            conn.execute("INSERT INTO recipe_browser_fts(recipe_browser_fts) VALUES('rebuild')")
            conn.commit()
            print("FTS rebuild complete.")
        except Exception as e:
            print(f"FTS rebuild skipped (table may not exist yet): {e}")

    conn.close()


if __name__ == "__main__":
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/kiwi.db")
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        sys.exit(1)
    backfill(db_path)
