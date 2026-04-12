# app/services/meal_plan/llm_planner.py
# BSL 1.1 — LLM feature
"""LLM-assisted full-week meal plan generation.

Returns suggestions for human review — never writes to the DB directly.
The API endpoint presents the suggestions and waits for user approval
before calling store.upsert_slot().
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_PLAN_SYSTEM = """\
You are a practical meal planning assistant. Given a pantry inventory and
dietary preferences, suggest a week of dinners (or other configured meals).

Prioritise ingredients that are expiring soon. Prefer variety across the week.
Respect all dietary restrictions.

Respond with a JSON array only — no prose, no markdown fences.
Each item: {"day": 0-6, "meal_type": "dinner", "recipe_id": <int or null>, "suggestion": "<recipe name>"}

day 0 = Monday, day 6 = Sunday.
If you cannot match a known recipe_id, set recipe_id to null and provide a suggestion name.
"""


@dataclass(frozen=True)
class PlanSuggestion:
    day: int            # 0 = Monday
    meal_type: str
    recipe_id: int | None
    suggestion: str     # human-readable name


def generate_plan(
    pantry_items: list[str],
    meal_types: list[str],
    dietary_notes: str,
    router,
) -> list[PlanSuggestion]:
    """Return a list of PlanSuggestion for user review.

    Never writes to DB — caller must upsert slots after user approves.
    Returns an empty list if router is None or response is unparseable.
    """
    if router is None:
        return []

    pantry_text = "\n".join(f"- {item}" for item in pantry_items[:50])
    meal_text = ", ".join(meal_types)
    user_msg = (
        f"Meal types: {meal_text}\n"
        f"Dietary notes: {dietary_notes or 'none'}\n\n"
        f"Pantry (partial):\n{pantry_text}"
    )

    try:
        response = router.complete(
            system=_PLAN_SYSTEM,
            user=user_msg,
            max_tokens=512,
            temperature=0.7,
        )
        items = json.loads(response.strip())
        suggestions = []
        for item in items:
            if not isinstance(item, dict):
                continue
            day = item.get("day")
            meal_type = item.get("meal_type", "dinner")
            if not isinstance(day, int) or day < 0 or day > 6:
                continue
            suggestions.append(PlanSuggestion(
                day=day,
                meal_type=meal_type,
                recipe_id=item.get("recipe_id"),
                suggestion=str(item.get("suggestion", "")),
            ))
        return suggestions
    except Exception as exc:
        logger.debug("LLM plan generation failed: %s", exc)
        return []
