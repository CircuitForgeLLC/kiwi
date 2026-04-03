"""
Estimate macro nutrition for recipes that have no direct data.

For each recipe where sugar_g / carbs_g / fiber_g / calories are NULL,
look up the matched ingredient_profiles and average their per-100g values,
then scale by a rough 150g-per-ingredient portion assumption.

Mark such rows with nutrition_estimated=1 so the UI can display a disclaimer.
Recipes with food.com direct data (nutrition_estimated=0 and values set) are untouched.

Usage:
    conda run -n job-seeker python scripts/pipeline/estimate_recipe_nutrition.py \
        --db /path/to/kiwi.db
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path

# Rough grams per ingredient when no quantity data is available.
_GRAMS_PER_INGREDIENT = 150.0


def estimate(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    # Load ingredient_profiles macro data into memory for fast lookup.
    profile_macros: dict[str, dict[str, float]] = {}
    for row in conn.execute(
        "SELECT name, calories_per_100g, carbs_g_per_100g, fiber_g_per_100g, sugar_g_per_100g "
        "FROM ingredient_profiles"
    ):
        name, cal, carbs, fiber, sugar = row
        if name:
            profile_macros[name] = {
                "calories": float(cal or 0),
                "carbs": float(carbs or 0),
                "fiber": float(fiber or 0),
                "sugar": float(sugar or 0),
            }

    # Select recipes with no direct nutrition data.
    rows = conn.execute(
        "SELECT id, ingredient_names FROM recipes "
        "WHERE sugar_g IS NULL AND carbs_g IS NULL AND fiber_g IS NULL"
    ).fetchall()

    updated = 0
    batch: list[tuple] = []

    for recipe_id, ingredient_names_json in rows:
        try:
            names: list[str] = json.loads(ingredient_names_json or "[]")
        except Exception:
            names = []

        matched = [profile_macros[n] for n in names if n in profile_macros]
        if not matched:
            continue

        # Average per-100g macros across matched ingredients,
        # then multiply by assumed portion weight per ingredient.
        n = len(matched)
        portion_factor = _GRAMS_PER_INGREDIENT / 100.0

        total_cal = sum(m["calories"] for m in matched) / n * portion_factor * n
        total_carbs = sum(m["carbs"] for m in matched) / n * portion_factor * n
        total_fiber = sum(m["fiber"] for m in matched) / n * portion_factor * n
        total_sugar = sum(m["sugar"] for m in matched) / n * portion_factor * n

        batch.append((
            round(total_cal, 1) or None,
            round(total_carbs, 2) or None,
            round(total_fiber, 2) or None,
            round(total_sugar, 2) or None,
            recipe_id,
        ))

        if len(batch) >= 5000:
            conn.executemany(
                "UPDATE recipes SET calories=?, carbs_g=?, fiber_g=?, sugar_g=?, "
                "nutrition_estimated=1 WHERE id=?",
                batch,
            )
            conn.commit()
            updated += len(batch)
            print(f"  {updated} recipes estimated...")
            batch = []

    if batch:
        conn.executemany(
            "UPDATE recipes SET calories=?, carbs_g=?, fiber_g=?, sugar_g=?, "
            "nutrition_estimated=1 WHERE id=?",
            batch,
        )
        conn.commit()
        updated += len(batch)

    conn.close()
    print(f"Total: {updated} recipes received estimated nutrition")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    args = parser.parse_args()
    estimate(args.db)
