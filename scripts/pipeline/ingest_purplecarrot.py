"""Ingest Purple Carrot scraped recipes into the Kiwi corpus database.

Reads recipes_purplecarrot_live.parquet (output of scrape_live.py) and
upserts into the shared recipes table, setting source='purplecarrot' and
using the recipe slug as the external_id (prefixed pc_).

Run after each weekly_harvest.sh scrape:

    conda run -n cf python3 scripts/pipeline/ingest_purplecarrot.py \
        [--db /Library/Assets/kiwi/kiwi.db] \
        [--parquet /Library/Assets/kiwi/pipeline/recipes_purplecarrot_live.parquet]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import math
import re

import pandas as pd

# ── Helpers (inlined from build_recipe_index to avoid cross-module import) ─────

_MEASURE_PATTERN = re.compile(
    r"^\d[\d\s/¼½¾⅓⅔]*\s*(cup|tbsp|tsp|oz|lb|g|kg|ml|l|clove|slice|piece|can|pkg|package|bunch|head|stalk|sprig|pinch|dash|to taste|as needed)s?\b",
    re.IGNORECASE,
)
_LEAD_NUMBER = re.compile(r"^\d[\d\s/¼½¾⅓⅔]*\s*")
_TRAILING_QUALIFIER = re.compile(
    r"\s*(to taste|as needed|or more|or less|optional|if desired|if needed)\s*$",
    re.IGNORECASE,
)


def _float_or_none(val: object) -> float | None:
    try:
        v = float(val)  # type: ignore[arg-type]
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _safe_list(val: object) -> list:
    if val is None:
        return []
    if isinstance(val, float) and math.isnan(val):
        return []
    if isinstance(val, list):
        return val
    # Parquet often deserializes list columns as numpy arrays
    try:
        import numpy as np
        if isinstance(val, np.ndarray):
            return val.tolist()
    except ImportError:
        pass
    return []


def _extract_ingredient_names(raw_list: list[str]) -> list[str]:
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


def _compute_element_coverage(profiles: list[dict]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for p in profiles:
        for elem in p.get("elements", []):
            counts[elem] = counts.get(elem, 0) + 1
    if not profiles:
        return {}
    return {e: round(c / len(profiles), 3) for e, c in counts.items()}

# ── Config ─────────────────────────────────────────────────────────────────────

DEFAULT_DB      = Path("/Library/Assets/kiwi/kiwi.db")
DEFAULT_PARQUET = Path("/Library/Assets/kiwi/pipeline/recipes_purplecarrot_live.parquet")


# ── Ingest ─────────────────────────────────────────────────────────────────────

def ingest(db_path: Path, parquet_path: Path) -> None:
    df = pd.read_parquet(parquet_path)

    # Filter to rows with full recipe data
    if "HasFullRecipe" in df.columns:
        df = df[df["HasFullRecipe"] == True].copy()

    if df.empty:
        print("No full recipes found in parquet — nothing to ingest.")
        return

    print(f"Ingesting {len(df)} Purple Carrot recipes into {db_path} …")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")

        # Pre-load ingredient element profiles for coverage calculation
        profile_index: dict[str, list[str]] = {}
        for row in conn.execute("SELECT name, elements FROM ingredient_profiles"):
            try:
                profile_index[row[0]] = json.loads(row[1])
            except Exception:
                pass

        inserted = updated = 0

        for _, row in df.iterrows():
            slug = str(row.get("Slug", "")).strip()
            if not slug:
                continue

            external_id = f"pc_{slug}"
            title = str(row.get("Name", "")).strip()[:500]
            if not title:
                continue

            raw_ingredients = [str(i) for i in _safe_list(row.get("RecipeIngredientParts", []))]
            directions      = [str(d) for d in _safe_list(row.get("RecipeInstructions", []))]

            ingredient_names = _extract_ingredient_names(raw_ingredients)
            profiles = [
                {"elements": profile_index[n]}
                for n in ingredient_names if n in profile_index
            ]
            coverage = _compute_element_coverage(profiles)

            # Keywords: merge scraped tags with allergen info
            kw_raw = _safe_list(row.get("Keywords", []))
            allergens = str(row.get("Allergens", "") or "")
            if allergens:
                kw_raw = list(kw_raw) + [f"allergen:{a.strip()}" for a in allergens.split(",") if a.strip()]
            keywords_json = json.dumps(kw_raw)

            # Check if already present (same external_id)
            existing = conn.execute(
                "SELECT id FROM recipes WHERE external_id = ?", (external_id,)
            ).fetchone()

            params = (
                title,
                json.dumps(raw_ingredients),
                json.dumps(ingredient_names),
                json.dumps(directions),
                "meal-kit",         # category
                keywords_json,
                _float_or_none(row.get("Calories")),
                _float_or_none(row.get("FatContent")),
                _float_or_none(row.get("ProteinContent")),
                None,               # sodium_mg — not scraped
                json.dumps(coverage),
                None,               # sugar_g   — not scraped
                _float_or_none(row.get("CarbohydrateContent")),
                _float_or_none(row.get("FiberContent")),
                2.0,                # servings — PC meal kits are 2-serving by default
                0,                  # nutrition_estimated — PC provides real data
            )

            if existing:
                conn.execute("""
                    UPDATE recipes
                    SET title=?, ingredients=?, ingredient_names=?, directions=?,
                        category=?, keywords=?, calories=?, fat_g=?, protein_g=?,
                        sodium_mg=?, element_coverage=?,
                        sugar_g=?, carbs_g=?, fiber_g=?, servings=?, nutrition_estimated=?
                    WHERE external_id=?
                """, params + (external_id,))
                updated += 1
            else:
                conn.execute("""
                    INSERT INTO recipes
                      (external_id, source, title, ingredients, ingredient_names,
                       directions, category, keywords, calories, fat_g, protein_g,
                       sodium_mg, element_coverage,
                       sugar_g, carbs_g, fiber_g, servings, nutrition_estimated)
                    VALUES (?, 'purplecarrot', ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (external_id,) + params)
                inserted += 1

        conn.commit()
    finally:
        conn.close()

    print(f"Done — {inserted} inserted, {updated} updated")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",      type=Path, default=DEFAULT_DB)
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET)
    args = parser.parse_args()

    if not args.parquet.exists():
        print(f"ERROR: parquet not found at {args.parquet}")
        raise SystemExit(1)

    ingest(args.db, args.parquet)


if __name__ == "__main__":
    main()
