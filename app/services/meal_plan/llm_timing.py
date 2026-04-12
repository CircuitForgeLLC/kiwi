# app/services/meal_plan/llm_timing.py
# BSL 1.1 — LLM feature
"""Estimate cook times for recipes missing corpus prep/cook time fields.

Used only when tier allows `meal_plan_llm_timing`. Falls back gracefully
when LLMRouter is unavailable.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_TIMING_PROMPT = """\
You are a practical cook. Given a recipe name and its ingredients, estimate:
1. prep_time: minutes of active prep work (chopping, mixing, etc.)
2. cook_time: minutes of cooking (oven, stovetop, etc.)

Respond with ONLY two integers on separate lines:
prep_time
cook_time

If you cannot estimate, respond with:
0
0
"""


def estimate_timing(recipe_name: str, ingredients: list[str], router) -> tuple[int | None, int | None]:
    """Return (prep_minutes, cook_minutes) for a recipe using LLMRouter.

    Returns (None, None) if the router is unavailable or the response is
    unparseable. Never raises.

    Args:
        recipe_name: Name of the recipe.
        ingredients: List of raw ingredient strings from the corpus.
        router: An LLMRouter instance (from circuitforge_core.llm).
    """
    if router is None:
        return None, None

    ingredient_list = "\n".join(f"- {i}" for i in (ingredients or [])[:15])
    prompt = f"Recipe: {recipe_name}\n\nIngredients:\n{ingredient_list}"

    try:
        response = router.complete(
            system=_TIMING_PROMPT,
            user=prompt,
            max_tokens=16,
            temperature=0.0,
        )
        lines = response.strip().splitlines()
        prep = int(lines[0].strip()) if lines else 0
        cook = int(lines[1].strip()) if len(lines) > 1 else 0
        if prep == 0 and cook == 0:
            return None, None
        return prep or None, cook or None
    except Exception as exc:
        logger.debug("LLM timing estimation failed for %r: %s", recipe_name, exc)
        return None, None
