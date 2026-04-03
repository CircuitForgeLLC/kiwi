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
_QUOTED = re.compile(r'"([^"]*)"')


def _float_or_none(val: object) -> float | None:
    """Return float > 0, or None for missing / zero values."""
    try:
        v = float(val)  # type: ignore[arg-type]
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _safe_list(val: object) -> list:
    """Convert a value to a list, handling NaN/float/None gracefully."""
    if val is None:
        return []
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return []
    except Exception:
        pass
    if isinstance(val, list):
        return val
    return []


def _parse_r_vector(s: str) -> list[str]:
    """Parse R character vector format: c("a", "b") -> ["a", "b"]."""
    return _QUOTED.findall(s)


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


def _parse_allrecipes_text(text: str) -> tuple[str, list[str], list[str]]:
    """Parse corbt/all-recipes text format into (title, ingredients, directions)."""
    lines = text.strip().split('\n')
    title = lines[0].strip()
    ingredients: list[str] = []
    directions: list[str] = []
    section: str | None = None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.lower() == 'ingredients:':
            section = 'ingredients'
        elif stripped.lower() in ('directions:', 'steps:', 'instructions:'):
            section = 'directions'
        elif stripped.startswith('- ') and section == 'ingredients':
            ingredients.append(stripped[2:].strip())
        elif stripped.startswith('- ') and section == 'directions':
            directions.append(stripped[2:].strip())
    return title, ingredients, directions


def _row_to_fields(row: pd.Series) -> tuple[str, str, list[str], list[str]]:
    """Extract (external_id, title, raw_ingredients, directions) from a parquet row.

    Handles both corbt/all-recipes (single 'input' text column) and the
    food.com columnar format (RecipeId, Name, RecipeIngredientParts, ...).
    """
    if "input" in row.index and pd.notna(row.get("input")):
        title, raw_ingredients, directions = _parse_allrecipes_text(str(row["input"]))
        external_id = f"ar_{hash(title) & 0xFFFFFFFF}"
    else:
        raw_parts = row.get("RecipeIngredientParts", [])
        if isinstance(raw_parts, str):
            parsed = _parse_r_vector(raw_parts)
            raw_parts = parsed if parsed else [raw_parts]
        raw_ingredients = [str(i) for i in (_safe_list(raw_parts))]

        raw_dirs = row.get("RecipeInstructions", [])
        if isinstance(raw_dirs, str):
            parsed_dirs = _parse_r_vector(raw_dirs)
            directions = parsed_dirs if parsed_dirs else [raw_dirs]
        else:
            directions = [str(d) for d in (_safe_list(raw_dirs))]

        title = str(row.get("Name", ""))[:500]
        external_id = str(row.get("RecipeId", ""))

    return external_id, title, raw_ingredients, directions


def build(db_path: Path, recipes_path: Path, batch_size: int = 10000) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")

        # Pre-load ingredient element profiles to avoid N+1 queries
        profile_index: dict[str, list[str]] = {}
        for row in conn.execute("SELECT name, elements FROM ingredient_profiles"):
            try:
                profile_index[row[0]] = json.loads(row[1])
            except Exception:
                pass

        df = pd.read_parquet(recipes_path)
        inserted = 0
        batch = []

        for _, row in df.iterrows():
            external_id, title, raw_ingredients, directions = _row_to_fields(row)
            if not title:
                continue
            ingredient_names = extract_ingredient_names(raw_ingredients)

            profiles = []
            for name in ingredient_names:
                if name in profile_index:
                    profiles.append({"elements": profile_index[name]})
            coverage = compute_element_coverage(profiles)

            batch.append((
                external_id,
                title,
                json.dumps(raw_ingredients),
                json.dumps(ingredient_names),
                json.dumps(directions),
                str(row.get("RecipeCategory", "") or ""),
                json.dumps(_safe_list(row.get("Keywords"))),
                _float_or_none(row.get("Calories")),
                _float_or_none(row.get("FatContent")),
                _float_or_none(row.get("ProteinContent")),
                _float_or_none(row.get("SodiumContent")),
                json.dumps(coverage),
                # New macro columns (migration 014)
                _float_or_none(row.get("SugarContent")),
                _float_or_none(row.get("CarbohydrateContent")),
                _float_or_none(row.get("FiberContent")),
                _float_or_none(row.get("RecipeServings")),
                0,  # nutrition_estimated — food.com direct data is authoritative
            ))

            if len(batch) >= batch_size:
                before = conn.total_changes
                conn.executemany("""
                    INSERT OR REPLACE INTO recipes
                      (external_id, title, ingredients, ingredient_names, directions,
                       category, keywords, calories, fat_g, protein_g, sodium_mg,
                       element_coverage,
                       sugar_g, carbs_g, fiber_g, servings, nutrition_estimated)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, batch)
                conn.commit()
                inserted += conn.total_changes - before
                print(f"  {inserted} recipes inserted...")
                batch = []

        if batch:
            before = conn.total_changes
            conn.executemany("""
                INSERT OR REPLACE INTO recipes
                  (external_id, title, ingredients, ingredient_names, directions,
                   category, keywords, calories, fat_g, protein_g, sodium_mg,
                   element_coverage,
                   sugar_g, carbs_g, fiber_g, servings, nutrition_estimated)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, batch)
            conn.commit()
            inserted += conn.total_changes - before

        conn.commit()
    finally:
        conn.close()
    print(f"Total: {inserted} recipes inserted")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",         required=True, type=Path)
    parser.add_argument("--recipes",    required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=10000)
    args = parser.parse_args()
    build(args.db, args.recipes, args.batch_size)
