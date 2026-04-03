#!/usr/bin/env python3
"""
Backfill texture_profile in ingredient_profiles from existing macro data.

Texture categories and their macro signatures (all values g/100g):
  fatty    - fat > 60                       (oils, lard, pure butter)
  creamy   - fat 15-60                      (cream, cheese, fatty meats, nut butter)
  firm     - protein > 15, fat < 15         (lean meats, fish, legumes, firm tofu)
  starchy  - carbs > 40, fat < 10           (flour, oats, rice, bread, potatoes)
  fibrous  - fiber > 4, carbs < 40          (brassicas, leafy greens, whole grains)
  tender   - protein 2-15, fat < 10,        (soft veg, eggs, soft tofu, cooked beans)
             carbs < 40
  liquid   - calories < 25, fat < 1,        (broth, juice, dilute sauces)
             protein < 3
  neutral  - fallthrough default

Rules are applied in priority order: fatty → creamy → firm → starchy →
fibrous → tender → liquid → neutral.

Run:
  python scripts/backfill_texture_profiles.py [path/to/kiwi.db]

Or inside the container:
  docker exec kiwi-cloud-api-1 python /app/kiwi/scripts/backfill_texture_profiles.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Default DB paths to try
_DEFAULT_PATHS = [
    "/devl/kiwi-cloud-data/local-dev/kiwi.db",
    "/devl/kiwi-data/kiwi.db",
]

BATCH_SIZE = 5_000


def _classify(fat: float, protein: float, carbs: float,
              fiber: float, calories: float) -> str:
    # Cap runaway values — data quality issue in some branded entries
    fat = min(fat or 0.0, 100.0)
    protein = min(protein or 0.0, 100.0)
    carbs = min(carbs or 0.0, 100.0)
    fiber = min(fiber or 0.0, 50.0)
    calories = min(calories or 0.0, 900.0)

    if fat > 60:
        return "fatty"
    if fat > 15:
        return "creamy"
    # Starchy before firm: oats/legumes have high protein AND high carbs — carbs win
    if carbs > 40 and fat < 10:
        return "starchy"
    # Firm: lean proteins with low carbs (meats, fish, hard tofu)
    # Lower protein threshold (>7) catches tofu (9%) and similar plant proteins
    if protein > 7 and fat < 12 and carbs < 20:
        return "firm"
    if fiber > 4 and carbs < 40:
        return "fibrous"
    if 2 < protein <= 15 and fat < 10 and carbs < 40:
        return "tender"
    if calories < 25 and fat < 1 and protein < 3:
        return "liquid"
    return "neutral"


def backfill(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) FROM ingredient_profiles").fetchone()[0]
    print(f"Total rows: {total:,}")

    updated = 0
    offset = 0
    counts: dict[str, int] = {}

    while True:
        rows = conn.execute(
            """SELECT id, fat_pct, protein_pct, carbs_g_per_100g,
                      fiber_g_per_100g, calories_per_100g
               FROM ingredient_profiles
               LIMIT ? OFFSET ?""",
            (BATCH_SIZE, offset),
        ).fetchall()

        if not rows:
            break

        batch: list[tuple[str, int]] = []
        for row in rows:
            texture = _classify(
                row["fat_pct"],
                row["protein_pct"],
                row["carbs_g_per_100g"],
                row["fiber_g_per_100g"],
                row["calories_per_100g"],
            )
            counts[texture] = counts.get(texture, 0) + 1
            batch.append((texture, row["id"]))

        conn.executemany(
            "UPDATE ingredient_profiles SET texture_profile = ? WHERE id = ?",
            batch,
        )
        conn.commit()

        updated += len(batch)
        offset += BATCH_SIZE
        print(f"  {updated:,} / {total:,} updated...", end="\r")

    print(f"\nDone. {updated:,} rows updated.\n")
    print("Texture distribution:")
    for texture, count in sorted(counts.items(), key=lambda x: -x[1]):
        pct = count / updated * 100
        print(f"  {texture:10s}  {count:8,}  ({pct:.1f}%)")

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = next((p for p in _DEFAULT_PATHS if Path(p).exists()), None)
        if not path:
            print(f"No DB found. Pass path as argument or create one of: {_DEFAULT_PATHS}")
            sys.exit(1)

    print(f"Backfilling texture profiles in: {path}")
    backfill(path)
