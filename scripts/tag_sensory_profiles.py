#!/usr/bin/env python3
"""
Tag recipes with sensory_tags (texture, smell, noise) based on ingredient
names and direction keywords.

Stores results in the sensory_tags JSON column added by migration 035.
Empty "{}" means untagged -- these recipes pass all sensory filters.

Run:
  python scripts/tag_sensory_profiles.py [path/to/kiwi.db]
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

_DEFAULT_PATHS = [
    "/devl/kiwi-cloud-data/local-dev/kiwi.db",
    "/devl/kiwi-data/kiwi.db",
]

BATCH_SIZE = 2_000

TEXTURE_TAGS = ("mushy", "slimy", "crunchy", "chewy", "creamy", "chunky")

_PROFILE_TO_TEXTURE: dict[str, str] = {
    "creamy": "creamy",
    "fatty":  "creamy",
}

_DIR_TEXTURE_PATTERNS: dict[str, list[str]] = {
    "mushy":  ["stew", "braise", "slow.cook", "slow cook", "soften", "mash", "slow-cook"],
    "crunchy": ["fry", "roast", "toast", "bake", "crispy", "raw"],
    "creamy":  ["blend", "puree", "mash smooth"],
    "chunky":  ["chunk", "cube", "dice"],
}

_ING_TEXTURE_PATTERNS: dict[str, list[str]] = {
    "slimy":  ["okra", "seaweed", "natto", "enoki", "oyster mushroom"],
    "chewy":  ["calamari", "squid", "octopus", "jerky", "dried fruit",
               "sourdough", "bagel", "pretzel"],
    "crunchy": ["nuts", "seeds", "breadcrumbs", "crackers", "croutons",
                "granola", "cornflakes"],
}

_SMELL_KEYWORDS: dict[str, list[str]] = {
    "fermented": [
        "fish sauce", "soy sauce", "miso", "kimchi", "natto",
        "blue cheese", "aged cheese", "balsamic",
    ],
    "pungent": [
        "garlic", "curry powder", "garam masala",
        "fish fillet", "fish steak", "fish filet", "liver",
    ],
    "aromatic": [
        "basil", "rosemary", "thyme", "cilantro", "citrus zest",
        "cinnamon", "vanilla", "cardamom",
    ],
}
_SMELL_ORDER = ("fermented", "pungent", "aromatic", "mild")

_NOISE_PATTERNS: dict[str, list[str]] = {
    "very_loud": ["deep fry", "deep-fry", "pressure cook", "instant pot"],
    "loud":      ["sear", "high heat", "wok", "stir-fry", "stir fry"],
    "moderate":  ["saute", "pan-fry", "pan fry", "bake", "roast"],
}
_NOISE_ORDER = ("very_loud", "loud", "moderate", "quiet")


def _classify_textures(
    ingredient_names: list[str],
    directions: list[str],
    profile_textures: set[str],
) -> list[str]:
    """Return list of texture tags that apply to this recipe."""
    dirs_text = " ".join(directions).lower()
    ings_text = " ".join(ingredient_names).lower()
    result: list[str] = []

    for tag in TEXTURE_TAGS:
        fired = False

        if not fired and tag == "creamy" and ("creamy" in profile_textures or "fatty" in profile_textures):
            fired = True

        if not fired and tag in _DIR_TEXTURE_PATTERNS:
            for kw in _DIR_TEXTURE_PATTERNS[tag]:
                if kw in dirs_text:
                    fired = True
                    break

        if not fired and tag in _ING_TEXTURE_PATTERNS:
            for kw in _ING_TEXTURE_PATTERNS[tag]:
                if kw in ings_text:
                    fired = True
                    break

        if fired:
            result.append(tag)

    return result


def _classify_smell(ingredient_names: list[str]) -> str:
    """Return highest smell level present in ingredient list."""
    ings_lower = " ".join(ingredient_names).lower()
    for level in ("fermented", "pungent", "aromatic"):
        for kw in _SMELL_KEYWORDS[level]:
            if kw in ings_lower:
                return level
    return "mild"


def _classify_noise(directions: list[str]) -> str:
    """Return highest noise level present in direction steps."""
    dirs_lower = " ".join(directions).lower()

    for kw in _NOISE_PATTERNS["very_loud"]:
        if kw in dirs_lower:
            return "very_loud"

    for kw in _NOISE_PATTERNS["loud"]:
        if kw in dirs_lower:
            return "loud"
    if re.search(r"\bfry\b", dirs_lower) and "deep" not in dirs_lower:
        return "loud"

    for kw in _NOISE_PATTERNS["moderate"]:
        if kw in dirs_lower:
            return "moderate"

    return "quiet"


def tag_recipes(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    print(f"Total recipes: {total:,}")

    updated = 0
    offset = 0
    texture_counts: dict[str, int] = {t: 0 for t in TEXTURE_TAGS}
    smell_counts: dict[str, int] = {s: 0 for s in _SMELL_ORDER}
    noise_counts: dict[str, int] = {n: 0 for n in _NOISE_ORDER}

    while True:
        rows = conn.execute(
            """SELECT r.id, r.ingredient_names, r.directions
               FROM recipes r
               LIMIT ? OFFSET ?""",
            (BATCH_SIZE, offset),
        ).fetchall()

        if not rows:
            break

        batch: list[tuple[str, int]] = []

        for row in rows:
            recipe_id = row["id"]

            try:
                ingredient_names: list[str] = json.loads(row["ingredient_names"] or "[]")
            except (json.JSONDecodeError, TypeError):
                ingredient_names = []

            try:
                directions: list[str] = json.loads(row["directions"] or "[]")
            except (json.JSONDecodeError, TypeError):
                directions = []

            if ingredient_names:
                placeholders = ",".join("?" * len(ingredient_names))
                profile_rows = conn.execute(
                    f"""SELECT DISTINCT texture_profile
                        FROM ingredient_profiles
                        WHERE LOWER(name) IN ({placeholders})""",
                    [n.lower() for n in ingredient_names],
                ).fetchall()
                profile_textures = {r["texture_profile"] for r in profile_rows if r["texture_profile"]}
            else:
                profile_textures = set()

            textures = _classify_textures(ingredient_names, directions, profile_textures)
            smell = _classify_smell(ingredient_names)
            noise = _classify_noise(directions)

            for t in textures:
                texture_counts[t] = texture_counts.get(t, 0) + 1
            smell_counts[smell] = smell_counts.get(smell, 0) + 1
            noise_counts[noise] = noise_counts.get(noise, 0) + 1

            sensory_tags = json.dumps({
                "textures": textures,
                "smell": smell,
                "noise": noise,
            })
            batch.append((sensory_tags, recipe_id))

        conn.executemany(
            "UPDATE recipes SET sensory_tags = ? WHERE id = ?",
            batch,
        )
        conn.commit()

        updated += len(batch)
        offset += BATCH_SIZE
        print(f"  {updated:,} / {total:,} tagged...", end="\r")

    print(f"\nDone. {updated:,} recipes tagged.\n")

    print("Texture tag distribution:")
    for tag, count in sorted(texture_counts.items(), key=lambda x: -x[1]):
        pct = count / updated * 100 if updated else 0
        print(f"  {tag:12s}  {count:8,}  ({pct:.1f}%)")

    print("\nSmell level distribution:")
    for level in _SMELL_ORDER:
        count = smell_counts.get(level, 0)
        pct = count / updated * 100 if updated else 0
        print(f"  {level:12s}  {count:8,}  ({pct:.1f}%)")

    print("\nNoise level distribution:")
    for level in _NOISE_ORDER:
        count = noise_counts.get(level, 0)
        pct = count / updated * 100 if updated else 0
        print(f"  {level:12s}  {count:8,}  ({pct:.1f}%)")

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = next((p for p in _DEFAULT_PATHS if Path(p).exists()), None)
        if not path:
            print(f"No DB found. Pass path as argument or create one of: {_DEFAULT_PATHS}")
            sys.exit(1)

    print(f"Tagging sensory profiles in: {path}")
    tag_recipes(path)
