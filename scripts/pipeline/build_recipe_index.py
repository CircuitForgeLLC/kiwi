"""
Import food.com recipe corpus into recipes table.

Usage:
    conda run -n job-seeker python scripts/pipeline/build_recipe_index.py \
        --db /path/to/kiwi.db \
        --recipes data/recipes_foodcom.parquet \
        --batch-size 10000
"""
from __future__ import annotations
import argparse
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd

_MEASURE_PATTERN = re.compile(
    r"^\d[\d\s/\u00bc\u00bd\u00be\u2153\u2154]*\s*(cup|tbsp|tsp|oz|lb|g|kg|ml|l|clove|slice|piece|can|pkg|package|bunch|head|stalk|sprig|pinch|dash|to taste|as needed)s?\b",
    re.IGNORECASE,
)
_LEAD_NUMBER = re.compile(r"^\d[\d\s/\u00bc\u00bd\u00be\u2153\u2154]*\s*")
_TRAILING_QUALIFIER = re.compile(
    r"\s*(to taste|as needed|or more|or less|optional|if desired|if needed)\s*$",
    re.IGNORECASE,
)


def extract_ingredient_names(raw_list: list[str]) -> list[str]:
    """Strip quantities and units from ingredient strings -> normalized names."""
    names = []
    for raw in raw_list:
        s = raw.lower().strip()
        s = _MEASURE_PATTERN.sub("", s)
        s = _LEAD_NUMBER.sub("", s)
        s = re.sub(r"\(.*?\)", "", s)
        s = re.sub(r",.*$", "", s)
        s = _TRAILING_QUALIFIER.sub("", s)
        s = s.strip(" -.,")
        if s and len(s) > 1:
            names.append(s)
    return names


def compute_element_coverage(profiles: list[dict]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for p in profiles:
        for elem in p.get("elements", []):
            counts[elem] = counts.get(elem, 0) + 1
    if not profiles:
        return {}
    return {e: round(c / len(profiles), 3) for e, c in counts.items()}


def build(db_path: Path, recipes_path: Path, batch_size: int = 10000) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    df = pd.read_parquet(recipes_path)
    inserted = 0
    batch = []

    for _, row in df.iterrows():
        raw_ingredients = row.get("RecipeIngredientParts", [])
        if isinstance(raw_ingredients, str):
            try:
                raw_ingredients = json.loads(raw_ingredients)
            except Exception:
                raw_ingredients = [raw_ingredients]
        raw_ingredients = [str(i) for i in (raw_ingredients or [])]
        ingredient_names = extract_ingredient_names(raw_ingredients)

        profiles = []
        for name in ingredient_names:
            row_p = conn.execute(
                "SELECT elements FROM ingredient_profiles WHERE name = ?", (name,)
            ).fetchone()
            if row_p:
                profiles.append({"elements": json.loads(row_p[0])})
        coverage = compute_element_coverage(profiles)

        directions = row.get("RecipeInstructions", [])
        if isinstance(directions, str):
            try:
                directions = json.loads(directions)
            except Exception:
                directions = [directions]

        batch.append((
            str(row.get("RecipeId", "")),
            str(row.get("Name", ""))[:500],
            json.dumps(raw_ingredients),
            json.dumps(ingredient_names),
            json.dumps([str(d) for d in (directions or [])]),
            str(row.get("RecipeCategory", "") or ""),
            json.dumps(list(row.get("Keywords", []) or [])),
            float(row.get("Calories") or 0) or None,
            float(row.get("FatContent") or 0) or None,
            float(row.get("ProteinContent") or 0) or None,
            float(row.get("SodiumContent") or 0) or None,
            json.dumps(coverage),
        ))

        if len(batch) >= batch_size:
            conn.executemany("""
                INSERT OR IGNORE INTO recipes
                  (external_id, title, ingredients, ingredient_names, directions,
                   category, keywords, calories, fat_g, protein_g, sodium_mg, element_coverage)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, batch)
            conn.commit()
            inserted += len(batch)
            print(f"  {inserted} recipes inserted...")
            batch = []

    if batch:
        conn.executemany("""
            INSERT OR IGNORE INTO recipes
              (external_id, title, ingredients, ingredient_names, directions,
               category, keywords, calories, fat_g, protein_g, sodium_mg, element_coverage)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, batch)
        conn.commit()
        inserted += len(batch)

    conn.close()
    print(f"Total: {inserted} recipes inserted")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",         required=True, type=Path)
    parser.add_argument("--recipes",    required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=10000)
    args = parser.parse_args()
    build(args.db, args.recipes, args.batch_size)
