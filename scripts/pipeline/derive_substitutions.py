"""
Derive substitution pairs by diffing lishuyang/recipepairs.
GPL-3.0 source -- derived annotations only, raw pairs not shipped.

Usage:
    PYTHONPATH=/path/to/kiwi conda run -n cf python scripts/pipeline/derive_substitutions.py \
        --db /path/to/kiwi.db \
        --recipepairs data/pipeline/recipepairs.parquet \
        --recipepairs-recipes data/pipeline/recipepairs_recipes.parquet
"""
from __future__ import annotations
import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd


def diff_ingredients(base: list[str], target: list[str]) -> tuple[list[str], list[str]]:
    base_set = set(base)
    target_set = set(target)
    removed = list(base_set - target_set)
    added = list(target_set - base_set)
    return removed, added


def _parse_categories(val: object) -> list[str]:
    """Parse categories field which may be a list, str-repr list, or bare string."""
    if isinstance(val, list):
        return [str(v) for v in val]
    if isinstance(val, str):
        val = val.strip()
        if val.startswith("["):
            # parse list repr: ['a', 'b'] — use json after converting single quotes
            try:
                fixed = re.sub(r"'", '"', val)
                return json.loads(fixed)
            except Exception:
                pass
        return [val] if val else []
    return []


def build(db_path: Path, recipepairs_path: Path, recipes_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        # Load ingredient lists from the bundled recipepairs recipe corpus.
        # This is GPL-3.0 data — we only use it for diffing; raw data is not persisted.
        print("Loading recipe ingredient index from recipepairs corpus...")
        recipes_df = pd.read_parquet(recipes_path, columns=["id", "ingredients"])
        recipe_ingredients: dict[str, list[str]] = {}
        for _, r in recipes_df.iterrows():
            ings = r["ingredients"]
            if ings is not None and hasattr(ings, "__iter__") and not isinstance(ings, str):
                recipe_ingredients[str(int(r["id"]))] = [str(i) for i in ings]
        print(f"  {len(recipe_ingredients)} recipes loaded")

        pairs_df = pd.read_parquet(recipepairs_path)
        pair_counts: dict[tuple, dict] = defaultdict(lambda: {"count": 0})

        print("Diffing recipe pairs...")
        for _, row in pairs_df.iterrows():
            base_id = str(int(row["base"]))
            target_id = str(int(row["target"]))
            base_ings = recipe_ingredients.get(base_id, [])
            target_ings = recipe_ingredients.get(target_id, [])
            if not base_ings or not target_ings:
                continue

            removed, added = diff_ingredients(base_ings, target_ings)
            if len(removed) != 1 or len(added) != 1:
                continue

            original = removed[0]
            substitute = added[0]
            constraints = _parse_categories(row.get("categories", []))
            if not constraints:
                continue
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
    parser.add_argument("--db",                  required=True, type=Path)
    parser.add_argument("--recipepairs",         required=True, type=Path,
                        help="pairs.parquet from lishuyang/recipepairs")
    parser.add_argument("--recipepairs-recipes", required=True, type=Path,
                        dest="recipepairs_recipes",
                        help="recipes.parquet from lishuyang/recipepairs (ingredient lookup)")
    args = parser.parse_args()
    build(args.db, args.recipepairs, args.recipepairs_recipes)
