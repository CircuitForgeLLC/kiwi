"""
Derive substitution pairs by diffing lishuyang/recipepairs.
GPL-3.0 source -- derived annotations only, raw pairs not shipped.

Usage:
    conda run -n job-seeker python scripts/pipeline/derive_substitutions.py \
        --db /path/to/kiwi.db \
        --recipepairs data/recipepairs.parquet
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd

from scripts.pipeline.build_recipe_index import extract_ingredient_names

CONSTRAINT_COLS = ["vegan", "vegetarian", "dairy_free", "low_calorie",
                   "low_carb", "low_fat", "low_sodium", "gluten_free"]


def diff_ingredients(base: list[str], target: list[str]) -> tuple[list[str], list[str]]:
    base_set = set(base)
    target_set = set(target)
    removed = list(base_set - target_set)
    added = list(target_set - base_set)
    return removed, added


def build(db_path: Path, recipepairs_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        print("Loading recipe ingredient index...")
        recipe_ingredients: dict[str, list[str]] = {}
        for row in conn.execute("SELECT external_id, ingredient_names FROM recipes"):
            recipe_ingredients[str(row[0])] = json.loads(row[1])

        df = pd.read_parquet(recipepairs_path)
        pair_counts: dict[tuple, dict] = defaultdict(lambda: {"count": 0})

        print("Diffing recipe pairs...")
        for _, row in df.iterrows():
            base_id = str(row.get("base", ""))
            target_id = str(row.get("target", ""))
            base_ings = recipe_ingredients.get(base_id, [])
            target_ings = recipe_ingredients.get(target_id, [])
            if not base_ings or not target_ings:
                continue

            removed, added = diff_ingredients(base_ings, target_ings)
            if len(removed) != 1 or len(added) != 1:
                continue

            original = removed[0]
            substitute = added[0]
            constraints = [c for c in CONSTRAINT_COLS if row.get(c, 0)]
            for constraint in constraints:
                key = (original, substitute, constraint)
                pair_counts[key]["count"] += 1

        def get_profile(name: str) -> dict:
            row = conn.execute(
                "SELECT fat_pct, moisture_pct, glutamate_mg, protein_pct "
                "FROM ingredient_profiles WHERE name = ?", (name,)
            ).fetchone()
            if row:
                return {"fat": row[0] or 0, "moisture": row[1] or 0,
                        "glutamate": row[2] or 0, "protein": row[3] or 0}
            return {"fat": 0, "moisture": 0, "glutamate": 0, "protein": 0}

        print("Writing substitution pairs...")
        inserted = 0
        for (original, substitute, constraint), data in pair_counts.items():
            if data["count"] < 3:
                continue
            p_orig = get_profile(original)
            p_sub = get_profile(substitute)
            conn.execute("""
                INSERT OR REPLACE INTO substitution_pairs
                  (original_name, substitute_name, constraint_label,
                   fat_delta, moisture_delta, glutamate_delta, protein_delta,
                   occurrence_count, source)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                original, substitute, constraint,
                round(p_sub["fat"] - p_orig["fat"], 2),
                round(p_sub["moisture"] - p_orig["moisture"], 2),
                round(p_sub["glutamate"] - p_orig["glutamate"], 2),
                round(p_sub["protein"] - p_orig["protein"], 2),
                data["count"], "derived",
            ))
            inserted += 1

        conn.commit()
    finally:
        conn.close()
    print(f"Inserted {inserted} substitution pairs (min 3 occurrences)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",          required=True, type=Path)
    parser.add_argument("--recipepairs", required=True, type=Path)
    args = parser.parse_args()
    build(args.db, args.recipepairs)
