"""
RecipeEngine — orchestrates the four creativity levels.

Level 1: corpus lookup ranked by ingredient match + expiry urgency
Level 2: Level 1 + deterministic substitution swaps
Level 3: element scaffold → LLM constrained prompt (see llm_recipe.py)
Level 4: wildcard LLM (see llm_recipe.py)

Amendments:
- max_missing: filter to recipes missing ≤ N pantry items
- hard_day_mode: filter to easy-method recipes only
- grocery_list: aggregated missing ingredients across suggestions
"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.store import Store

from app.models.schemas.recipe import GroceryLink, RecipeRequest, RecipeResult, RecipeSuggestion, SwapCandidate
from app.services.recipe.element_classifier import ElementClassifier
from app.services.recipe.grocery_links import GroceryLinkBuilder
from app.services.recipe.substitution_engine import SubstitutionEngine

_LEFTOVER_DAILY_MAX_FREE = 5

# Method complexity classification patterns
_EASY_METHODS = re.compile(
    r"\b(microwave|mix|stir|blend|toast|assemble|heat)\b", re.IGNORECASE
)
_INVOLVED_METHODS = re.compile(
    r"\b(braise|roast|knead|deep.?fry|fry|sauté|saute|bake|boil)\b", re.IGNORECASE
)


def _classify_method_complexity(
    directions: list[str],
    available_equipment: list[str] | None = None,
) -> str:
    """Classify recipe method complexity from direction strings.

    Returns 'easy', 'moderate', or 'involved'.
    available_equipment can expand the easy set (e.g. ['toaster', 'air fryer']).
    """
    text = " ".join(directions).lower()
    equipment_set = {e.lower() for e in (available_equipment or [])}

    if _INVOLVED_METHODS.search(text):
        return "involved"

    if _EASY_METHODS.search(text):
        return "easy"

    # Check equipment-specific easy methods
    for equip in equipment_set:
        if equip in text:
            return "easy"

    return "moderate"


class RecipeEngine:
    def __init__(self, store: "Store") -> None:
        self._store = store
        self._classifier = ElementClassifier(store)
        self._substitution = SubstitutionEngine(store)

    def suggest(
        self,
        req: RecipeRequest,
        available_equipment: list[str] | None = None,
    ) -> RecipeResult:
        # Rate-limit leftover mode for free tier
        if req.expiry_first and req.tier == "free":
            allowed, count = self._store.check_and_increment_rate_limit(
                "leftover_mode", _LEFTOVER_DAILY_MAX_FREE
            )
            if not allowed:
                return RecipeResult(
                    suggestions=[], element_gaps=[], rate_limited=True, rate_limit_count=count
                )

        profiles = self._classifier.classify_batch(req.pantry_items)
        gaps = self._classifier.identify_gaps(profiles)
        pantry_set = {item.lower().strip() for item in req.pantry_items}

        if req.level >= 3:
            from app.services.recipe.llm_recipe import LLMRecipeGenerator
            gen = LLMRecipeGenerator(self._store)
            return gen.generate(req, profiles, gaps)

        # Level 1 & 2: deterministic path
        rows = self._store.search_recipes_by_ingredients(req.pantry_items, limit=20)
        suggestions = []

        for row in rows:
            ingredient_names: list[str] = row.get("ingredient_names") or []
            if isinstance(ingredient_names, str):
                try:
                    ingredient_names = json.loads(ingredient_names)
                except Exception:
                    ingredient_names = []

            # Compute missing ingredients
            missing = [n for n in ingredient_names if n.lower() not in pantry_set]

            # Filter by max_missing
            if req.max_missing is not None and len(missing) > req.max_missing:
                continue

            # Filter by hard_day_mode
            if req.hard_day_mode:
                directions: list[str] = row.get("directions") or []
                if isinstance(directions, str):
                    try:
                        directions = json.loads(directions)
                    except Exception:
                        directions = [directions]
                complexity = _classify_method_complexity(directions, available_equipment)
                if complexity == "involved":
                    continue

            # Build swap candidates for Level 2
            swap_candidates: list[SwapCandidate] = []
            if req.level == 2 and req.constraints:
                for ing in ingredient_names:
                    for constraint in req.constraints:
                        swaps = self._substitution.find_substitutes(ing, constraint)
                        for swap in swaps[:1]:
                            swap_candidates.append(SwapCandidate(
                                original_name=swap.original_name,
                                substitute_name=swap.substitute_name,
                                constraint_label=swap.constraint_label,
                                explanation=swap.explanation,
                                compensation_hints=swap.compensation_hints,
                            ))

            coverage_raw = row.get("element_coverage") or {}
            if isinstance(coverage_raw, str):
                try:
                    coverage_raw = json.loads(coverage_raw)
                except Exception:
                    coverage_raw = {}

            suggestions.append(RecipeSuggestion(
                id=row["id"],
                title=row["title"],
                match_count=int(row.get("match_count") or 0),
                element_coverage=coverage_raw,
                swap_candidates=swap_candidates,
                missing_ingredients=missing,
                level=req.level,
            ))

        # Build grocery list — deduplicated union of all missing ingredients
        seen: set[str] = set()
        grocery_list: list[str] = []
        for s in suggestions:
            for item in s.missing_ingredients:
                if item not in seen:
                    grocery_list.append(item)
                    seen.add(item)

        # Build grocery links — affiliate deeplinks for each missing ingredient
        link_builder = GroceryLinkBuilder(tier=req.tier, has_byok=req.has_byok)
        grocery_links = link_builder.build_all(grocery_list)

        return RecipeResult(
            suggestions=suggestions,
            element_gaps=gaps,
            grocery_list=grocery_list,
            grocery_links=grocery_links,
        )
