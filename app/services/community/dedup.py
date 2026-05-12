# app/services/community/dedup.py
# MIT License

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SIMILARITY_TIERS = {
    "exact_recipe": "This exact recipe is already in the community feed.",
    "very_similar": "Very similar recipes already exist (70%+ ingredient overlap).",
    "somewhat_similar": "Somewhat similar recipes exist (35-70% ingredient overlap).",
    "different": "No close matches found.",
}


def _parse_ingredient_names(raw) -> set[str]:
    """Return a normalised set of ingredient name tokens from various stored formats."""
    if raw is None:
        return set()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return set()
    names: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            names.add(item.lower().strip())
        elif isinstance(item, dict):
            name = item.get("name") or item.get("ingredient") or ""
            if name:
                names.add(name.lower().strip())
    return names


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity_tier(jaccard_score: float, exact_recipe: bool) -> str:
    if exact_recipe:
        return "exact_recipe"
    if jaccard_score >= 0.70:
        return "very_similar"
    if jaccard_score >= 0.35:
        return "somewhat_similar"
    return "different"


def fetch_recipe_ingredients(db_path: Path, recipe_id: int | None) -> set[str]:
    """Look up ingredient names for a recipe from the local corpus. Returns empty set on miss."""
    if recipe_id is None:
        return set()
    try:
        from app.db.store import Store
        store = Store(db_path)
        try:
            row = store.get_recipe(recipe_id)
            if row is None:
                return set()
            return _parse_ingredient_names(row.get("ingredient_names"))
        finally:
            store.close()
    except Exception:
        logger.debug("ingredient lookup failed for recipe_id=%s", recipe_id)
        return set()


def build_similar_post_result(
    post,
    incoming_recipe_id: int | None,
    incoming_ingredients: set[str],
    db_path: Path,
) -> dict:
    """Build a similarity result dict for one existing community post."""
    exact = (
        incoming_recipe_id is not None
        and post.recipe_id is not None
        and post.recipe_id == incoming_recipe_id
    )

    j_score = 0.0
    if not exact and incoming_ingredients:
        existing_ingredients = fetch_recipe_ingredients(db_path, post.recipe_id)
        if existing_ingredients:
            j_score = jaccard(incoming_ingredients, existing_ingredients)

    tier = similarity_tier(j_score, exact)

    return {
        "slug": post.slug,
        "title": post.title,
        "recipe_name": post.recipe_name,
        "pseudonym": post.pseudonym,
        "published": (
            post.published.isoformat()
            if hasattr(post.published, "isoformat")
            else str(post.published)
        ),
        "similarity_tier": tier,
        "jaccard_score": round(j_score, 3) if not exact else None,
        "tier_description": _SIMILARITY_TIERS.get(tier, ""),
    }
