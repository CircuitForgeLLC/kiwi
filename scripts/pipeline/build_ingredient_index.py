"""
Build ingredient_profiles table from USDA FDC (Food Data Central) data.

Usage:
    conda run -n job-seeker python scripts/pipeline/build_ingredient_index.py \
        --db /path/to/kiwi.db \
        --usda-fdc data/usda_fdc_cleaned.parquet \
        --usda-branded data/usda_branded.parquet
"""
from __future__ import annotations
import argparse
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd


# ── Element derivation rules (threshold-based) ────────────────────────────

_ELEMENT_RULES: list[tuple[str, callable]] = [
    ("Richness",  lambda r: r.get("fat_pct", 0)        > 5.0),
    ("Seasoning", lambda r: r.get("sodium_mg_per_100g", 0) > 200),
    ("Depth",     lambda r: r.get("glutamate_mg", 0)   > 1.0),
    ("Structure", lambda r: r.get("starch_pct", 0)     > 10.0 or r.get("binding_score", 0) >= 2),
    ("Texture",   lambda r: r.get("water_activity", 1.0) < 0.6),  # low water = likely crunchy/dry
]

_ACID_KEYWORDS = ["vinegar", "lemon", "lime", "citric", "tartaric", "kombucha", "kefir",
                  "yogurt", "buttermilk", "wine", "tomato"]
_AROMA_KEYWORDS = ["garlic", "onion", "herb", "spice", "basil", "oregano", "cumin",
                   "ginger", "cinnamon", "pepper", "chili", "paprika", "thyme", "rosemary",
                   "cilantro", "parsley", "dill", "fennel", "cardamom", "turmeric"]
_FERMENTED_KEYWORDS = ["miso", "soy sauce", "kimchi", "sauerkraut", "kefir", "yogurt",
                       "kombucha", "tempeh", "natto", "vinegar", "nutritional yeast"]


def normalize_name(raw: str) -> str:
    """Lowercase, strip parentheticals and trailing descriptors."""
    name = raw.lower().strip()
    name = re.sub(r"\(.*?\)", "", name)          # remove (85% lean)
    name = re.sub(r",.*$", "", name)             # remove ,shredded
    name = re.sub(r"\s+", " ", name).strip()
    return name


def derive_elements(row: dict) -> list[str]:
    elements = [elem for elem, check in _ELEMENT_RULES if check(row)]
    name = row.get("name", "").lower()
    if any(k in name for k in _ACID_KEYWORDS):
        elements.append("Brightness")
    if any(k in name for k in _AROMA_KEYWORDS):
        elements.append("Aroma")
    return list(dict.fromkeys(elements))  # dedup, preserve order


def derive_binding_score(row: dict) -> int:
    protein = row.get("protein_pct", 0)
    starch = row.get("starch_pct", 0)
    if starch > 50 or (protein > 10 and starch > 20):
        return 3
    if starch > 20 or protein > 12:
        return 2
    if starch > 5 or protein > 6:
        return 1
    return 0


def build(db_path: Path, usda_fdc_path: Path, usda_branded_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")

    df_fdc = pd.read_parquet(usda_fdc_path)
    df_branded = pd.read_parquet(usda_branded_path)

    # Rename columns to unified schema
    fdc_col_map = {
        "food_item": "name",
        "Total lipid (fat)": "fat_pct",
        "Protein": "protein_pct",
        "Carbohydrate, by difference": "carb_pct",
        "Fiber, total dietary": "fiber_pct",
        "Sodium, Na": "sodium_mg_per_100g",
        "Water": "moisture_pct",
    }
    df = df_fdc.rename(columns={k: v for k, v in fdc_col_map.items() if k in df_fdc.columns})

    inserted = 0
    for _, row in df.iterrows():
        name = normalize_name(str(row.get("name", "")))
        if not name or len(name) < 2:
            continue
        r = {
            "name": name,
            "fat_pct": float(row.get("fat_pct") or 0),
            "protein_pct": float(row.get("protein_pct") or 0),
            "moisture_pct": float(row.get("moisture_pct") or 0),
            "sodium_mg_per_100g": float(row.get("sodium_mg_per_100g") or 0),
            "starch_pct": 0.0,
        }
        r["binding_score"] = derive_binding_score(r)
        r["elements"] = derive_elements(r)
        r["is_fermented"] = int(any(k in name for k in _FERMENTED_KEYWORDS))

        try:
            conn.execute("""
                INSERT OR IGNORE INTO ingredient_profiles
                  (name, elements, fat_pct, fat_saturated_pct, moisture_pct,
                   protein_pct, starch_pct, binding_score, sodium_mg_per_100g,
                   is_fermented, source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                r["name"], json.dumps(r["elements"]),
                r["fat_pct"], 0.0, r["moisture_pct"],
                r["protein_pct"], r["starch_pct"], r["binding_score"],
                r["sodium_mg_per_100g"], r["is_fermented"], "usda_fdc",
            ))
            inserted += conn.execute("SELECT changes()").fetchone()[0]
        except Exception:
            continue

    conn.commit()
    conn.close()
    print(f"Inserted {inserted} ingredient profiles from USDA FDC")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",           required=True, type=Path)
    parser.add_argument("--usda-fdc",     required=True, type=Path)
    parser.add_argument("--usda-branded", required=True, type=Path)
    args = parser.parse_args()
    build(args.db, args.usda_fdc, args.usda_branded)
