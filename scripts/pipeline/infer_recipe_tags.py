"""
Infer and backfill normalized tags for all recipes.

Reads recipes in batches, cross-references ingredient_profiles and
substitution_pairs, runs tag_inferrer on each recipe, and writes the result
to recipes.inferred_tags. Also rebuilds recipe_browser_fts after the run.

This script is idempotent: pass --force to re-derive tags even if
inferred_tags is already non-empty.

Usage:
    conda run -n cf python scripts/pipeline/infer_recipe_tags.py \\
        [path/to/kiwi.db] [--batch-size 2000] [--force]

Estimated time on 3.1M rows: 10-20 minutes (CPU-bound text matching).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Allow importing from the app package when run from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.recipe.tag_inferrer import infer_tags


# ---------------------------------------------------------------------------
# Substitution constraint label mapping
# Keys are what we store in substitution_pairs.constraint_label.
# ---------------------------------------------------------------------------
_INTERESTING_CONSTRAINTS = {"gluten_free", "low_calorie", "low_carb", "vegan", "dairy_free", "low_sodium"}


def _load_profiles(conn: sqlite3.Connection) -> dict[str, dict]:
    """
    Load ingredient_profiles into a dict keyed by name.
    Values hold only the fields we need for tag inference.
    """
    profiles: dict[str, dict] = {}
    rows = conn.execute("""
        SELECT name, elements, glutamate_mg, is_fermented, ph_estimate
        FROM ingredient_profiles
    """).fetchall()
    for name, elements_json, glutamate_mg, is_fermented, ph_estimate in rows:
        try:
            elements: list[str] = json.loads(elements_json) if elements_json else []
        except Exception:
            elements = []
        profiles[name] = {
            "elements":    elements,
            "glutamate":   float(glutamate_mg or 0),
            "fermented":   bool(is_fermented),
            "ph":          float(ph_estimate) if ph_estimate is not None else None,
        }
    return profiles


def _load_sub_index(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """
    Build a dict of ingredient_name -> set of available constraint labels.
    Only loads constraints we care about.
    """
    index: dict[str, set[str]] = {}
    placeholders = ",".join("?" * len(_INTERESTING_CONSTRAINTS))
    rows = conn.execute(
        f"SELECT original_name, constraint_label FROM substitution_pairs "
        f"WHERE constraint_label IN ({placeholders})",
        list(_INTERESTING_CONSTRAINTS),
    ).fetchall()
    for name, label in rows:
        index.setdefault(name, set()).add(label)
    return index


def _enrich(
    ingredient_names: list[str],
    profile_index: dict[str, dict],
    sub_index: dict[str, set[str]],
) -> dict:
    """
    Cross-reference ingredient_names against our enrichment indices.
    Returns a dict of enriched signals ready for infer_tags().
    """
    fermented_count = 0
    glutamate_total = 0.0
    ph_values: list[float] = []
    element_totals: dict[str, float] = {}
    profiled = 0
    constraint_sets: list[set[str]] = []

    for name in ingredient_names:
        profile = profile_index.get(name)
        if profile:
            profiled += 1
            glutamate_total += profile["glutamate"]
            if profile["fermented"]:
                fermented_count += 1
            if profile["ph"] is not None:
                ph_values.append(profile["ph"])
            for elem in profile["elements"]:
                element_totals[elem] = element_totals.get(elem, 0.0) + 1.0

        subs = sub_index.get(name)
        if subs:
            constraint_sets.append(subs)

    # Element coverage: fraction of profiled ingredients that carry each element
    element_coverage: dict[str, float] = {}
    if profiled > 0:
        element_coverage = {e: round(c / profiled, 3) for e, c in element_totals.items()}

    # Only emit a can_be:* tag if ALL relevant ingredients have the substitution available.
    # (A recipe is gluten_free-achievable only if every gluten source can be swapped.)
    # We use a simpler heuristic: if at least one ingredient has the constraint, flag it.
    # Future improvement: require coverage of all gluten-bearing ingredients.
    available_constraints: list[str] = []
    if constraint_sets:
        union_constraints: set[str] = set()
        for cs in constraint_sets:
            union_constraints.update(cs)
        available_constraints = sorted(union_constraints & _INTERESTING_CONSTRAINTS)

    return {
        "element_coverage":         element_coverage,
        "fermented_count":          fermented_count,
        "glutamate_total":          glutamate_total,
        "ph_min":                   min(ph_values) if ph_values else None,
        "available_sub_constraints": available_constraints,
    }


def run(db_path: Path, batch_size: int = 2000, force: bool = False) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    total = conn.execute("SELECT count(*) FROM recipes").fetchone()[0]
    print(f"Total recipes: {total:,}")
    print("Loading ingredient profiles...")
    profile_index = _load_profiles(conn)
    print(f"  {len(profile_index):,} profiles loaded")
    print("Loading substitution index...")
    sub_index = _load_sub_index(conn)
    print(f"  {len(sub_index):,} substitutable ingredients indexed")

    updated = 0
    skipped = 0
    offset = 0

    where_clause = "" if force else "WHERE inferred_tags = '[]' OR inferred_tags IS NULL"

    eligible = conn.execute(
        f"SELECT count(*) FROM recipes {where_clause}"
    ).fetchone()[0]
    print(f"Recipes to process: {eligible:,} ({'all' if force else 'untagged only'})")

    while True:
        rows = conn.execute(
            f"""
            SELECT id, title, ingredient_names, category, keywords,
                   element_coverage,
                   calories, fat_g, protein_g, carbs_g, servings
            FROM recipes {where_clause}
            ORDER BY id
            LIMIT ? OFFSET ?
            """,
            (batch_size, offset),
        ).fetchall()
        if not rows:
            break

        updates: list[tuple[str, int]] = []
        for (row_id, title, ingr_json, category, kw_json,
             elem_cov_json, calories, fat_g, protein_g, carbs_g, servings) in rows:
            try:
                ingredient_names: list[str] = json.loads(ingr_json) if ingr_json else []
                corpus_keywords: list[str] = json.loads(kw_json) if kw_json else []
                element_coverage: dict[str, float] = (
                    json.loads(elem_cov_json) if elem_cov_json else {}
                )
            except Exception:
                ingredient_names = []
                corpus_keywords = []
                element_coverage = {}

            enriched = _enrich(ingredient_names, profile_index, sub_index)
            # Prefer the pre-computed element_coverage from the recipes table
            # (it was computed over all ingredients at import time, not just the
            # profiled subset). Fall back to what _enrich computed.
            effective_coverage = element_coverage or enriched["element_coverage"]

            tags = infer_tags(
                title=title or "",
                ingredient_names=ingredient_names,
                corpus_keywords=corpus_keywords,
                corpus_category=category or "",
                element_coverage=effective_coverage,
                fermented_count=enriched["fermented_count"],
                glutamate_total=enriched["glutamate_total"],
                ph_min=enriched["ph_min"],
                available_sub_constraints=enriched["available_sub_constraints"],
                calories=calories,
                protein_g=protein_g,
                fat_g=fat_g,
                carbs_g=carbs_g,
                servings=servings,
            )
            updates.append((json.dumps(tags), row_id))

        if updates:
            conn.executemany(
                "UPDATE recipes SET inferred_tags = ? WHERE id = ?", updates
            )
            conn.commit()
            updated += len(updates)
        else:
            skipped += len(rows)

        offset += len(rows)
        pct = min(100, int((offset / eligible) * 100)) if eligible else 100
        print(
            f"  {pct:>3}%  offset {offset:,}  tagged {updated:,}",
            end="\r",
        )

    print(f"\nDone. Tagged {updated:,} recipes, skipped {skipped:,}.")

    if updated > 0:
        print("Rebuilding FTS5 browser index (recipe_browser_fts)...")
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
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--force", action="store_true",
                        help="Re-derive tags even if inferred_tags is already set.")
    args = parser.parse_args()
    if not args.db.exists():
        print(f"DB not found: {args.db}")
        sys.exit(1)
    run(args.db, args.batch_size, args.force)
