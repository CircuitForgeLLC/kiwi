# app/services/leftovers_predictor.py
"""Cooked-leftovers shelf-life predictor.

Fast path: deterministic lookup anchored to FDA/USDA safe food handling.
Fallback: LLM for unclassifiable edge cases (same gate as expiry_llm_matching).

Design notes:
  - shortest-component-wins for proteins: a fish taco is bounded by the fish.
  - category/keyword signals override ingredient signals for assembled dishes
    (soup, stew, casserole) where the cooking method matters more than the
    dominant protein.
  - no urgency/panic framing — see feedback_kiwi_no_panic.md.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LeftoversResult:
    fridge_days: int
    freeze_days: int | None        # None = "not recommended"
    freeze_by_day: int | None      # day number from cook date to freeze by; None = no need
    storage_advice: str


# ---------------------------------------------------------------------------
# Protein priority table — shorter shelf life wins when multiple match.
# Values: (fridge_days, freeze_days).  All fridge values are conservative.
# Sources: USDA FoodKeeper, FDA Safe Food Handling.
# ---------------------------------------------------------------------------
_PROTEIN_SIGNALS: list[tuple[list[str], int, int | None]] = [
    # (keyword_list, fridge_days, freeze_days)
    (["fish", "salmon", "tuna", "cod", "tilapia", "halibut", "trout", "bass",
      "mahi", "snapper", "flounder", "catfish", "swordfish", "sardine", "anchovy"],
     2, 90),
    (["shrimp", "prawn", "scallop", "crab", "lobster", "clam", "mussel",
      "oyster", "squid", "octopus", "seafood"],
     2, 90),
    (["ground beef", "ground turkey", "ground pork", "ground chicken",
      "ground meat", "hamburger", "mince"],
     3, 90),
    (["chicken", "turkey", "poultry", "duck", "hen"],
     3, 90),
    (["pork", "ham", "bacon", "sausage", "chorizo", "bratwurst", "kielbasa",
      "salami", "pepperoni"],
     4, 120),
    (["beef", "steak", "brisket", "roast", "lamb", "veal", "venison"],
     4, 180),
    (["egg", "eggs", "frittata", "quiche", "omelette"],
     3, None),
    (["tofu", "tempeh", "seitan"],
     4, 90),
]

# ---------------------------------------------------------------------------
# Dish-type signals — override protein signal when a structural match fires.
# Ordered from most-perishable to least.
# ---------------------------------------------------------------------------
_DISH_SIGNALS: list[tuple[list[str], int, int | None, str]] = [
    # (keywords, fridge_days, freeze_days, storage_advice_fragment)

    # Ceviche: acid denatures proteins but does not kill pathogens.
    # FDA/USDA classify it as raw seafood — 2-day fridge max, do not freeze.
    (["ceviche", "tiradito", "leche de tigre"],
     2, None,
     "Acid marination is not the same as heat cooking — treat as raw seafood. "
     "Best eaten the day it's made; 2 days maximum in the fridge."),

    # Fermented / salt-cured dishes — preservation extends shelf life significantly.
    # This matches dish names, not just presence of the ingredient (lardo in a pasta
    # follows normal pasta rules, not this entry).
    (["kimchi", "sauerkraut", "preserved lemon"],
     14, None,
     "Fermented and salt-preserved dishes keep well. Store submerged in their brine."),

    (["confit", "gravlax", "gravad lax", "lardo"],
     7, 60,
     "Store covered in its fat or cure. Keep cold and away from strong-smelling foods."),

    (["soup", "stew", "broth", "chowder", "bisque", "gumbo", "chili"],
     4, 120,
     "Soups and stews keep well in the fridge. Cool to room temperature before covering."),
    (["curry"],
     4, 90,
     "Store curry in an airtight container. The flavours deepen overnight."),
    (["casserole", "bake", "gratin", "lasagna", "lasagne", "moussaka",
      "shepherd's pie", "pot pie"],
     5, 90,
     "Cover tightly. Reheat individual portions rather than the whole dish."),
    (["pasta", "noodle", "spaghetti", "penne", "linguine", "fettuccine",
      "macaroni", "risotto"],
     4, 60,
     "Store pasta and sauce separately if possible to prevent sogginess."),
    (["rice", "fried rice", "pilaf", "biryani"],
     3, 90,
     "Cool rice quickly — spread on a tray if needed. Don't leave at room temperature for more than 1 hour."),
    (["salad"],
     2, None,
     "Keep dressing separate. Once dressed, best eaten the same day."),
    (["stir fry", "stir-fry"],
     3, 60,
     "Reheat in a hot pan or wok rather than a microwave to keep texture."),
    (["sandwich", "wrap", "taco", "burrito"],
     2, None,
     "Assemble fresh when possible. Fillings keep better stored separately."),
    (["pizza"],
     4, 60,
     "Reheat in a dry skillet for a crisp base rather than a microwave."),
    (["muffin", "bread", "biscuit", "scone", "roll"],
     3, 90,
     "Wrap tightly or seal in a bag to prevent drying out."),
    (["cake", "pie", "cookie", "brownie", "dessert", "pudding"],
     5, 90,
     "Store covered at room temperature or in the fridge depending on fillings."),
    (["smoothie", "juice", "shake"],
     1, 7,
     "Best consumed fresh. Stir or shake well before drinking."),
]

# Default when no signals match.
_DEFAULT_FRIDGE = 4
_DEFAULT_FREEZE = 90
_DEFAULT_ADVICE = "Store in an airtight container in the fridge. Reheat until piping hot before eating."


def _contains_any(text: str, keywords: list[str]) -> bool:
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw)}\b", text, re.IGNORECASE):
            return True
    return False


def _scan_ingredients(ingredients: list[str]) -> tuple[int, int | None] | None:
    """Return (fridge_days, freeze_days) for the most-perishable protein found."""
    joined = " ".join(str(i) for i in ingredients).lower()
    best: tuple[int, int | None] | None = None
    for keywords, fridge, freeze in _PROTEIN_SIGNALS:
        if _contains_any(joined, keywords):
            if best is None or fridge < best[0]:
                best = (fridge, freeze)
    return best


def _scan_dish_type(text: str) -> tuple[int, int | None, str] | None:
    """Return (fridge_days, freeze_days, advice) for the first matching dish type."""
    for keywords, fridge, freeze, advice in _DISH_SIGNALS:
        if _contains_any(text, keywords):
            return fridge, freeze, advice
    return None


def predict_leftovers(
    title: str,
    ingredients: list[str],
    category: str | None = None,
    keywords: list[str] | None = None,
) -> LeftoversResult:
    """Predict cooked-leftover shelf life deterministically.

    Falls back gracefully — always returns a result even for unknown recipes.
    """
    # Build a combined text blob for dish-type scanning.
    search_text = " ".join(filter(None, [
        title,
        category or "",
        " ".join(keywords or []),
    ]))

    # Dish-type match takes structural priority over raw ingredient protein signal.
    dish = _scan_dish_type(search_text)
    protein = _scan_ingredients(ingredients)

    if dish:
        fridge_days, freeze_days, base_advice = dish
        # Still apply shortest-protein-wins if protein is more perishable than dish default.
        if protein and protein[0] < fridge_days:
            fridge_days = protein[0]
            if protein[1] is not None and (freeze_days is None or protein[1] < freeze_days):
                freeze_days = protein[1]
        advice = base_advice
    elif protein:
        fridge_days, freeze_days = protein
        advice = _DEFAULT_ADVICE
    else:
        fridge_days = _DEFAULT_FRIDGE
        freeze_days = _DEFAULT_FREEZE
        advice = _DEFAULT_ADVICE

    # freeze_by_day: recommend freezing on day 2 if fridge window is tight (≤3 days).
    freeze_by_day: int | None = None
    if freeze_days is not None and fridge_days <= 3:
        freeze_by_day = 2

    return LeftoversResult(
        fridge_days=fridge_days,
        freeze_days=freeze_days,
        freeze_by_day=freeze_by_day,
        storage_advice=advice,
    )


def predict_leftovers_from_row(recipe: dict[str, Any]) -> LeftoversResult:
    """Convenience wrapper that accepts a Store row dict directly."""
    import json as _json

    title = recipe.get("title") or ""

    raw_ingredients = recipe.get("ingredient_names") or []
    if isinstance(raw_ingredients, str):
        try:
            raw_ingredients = _json.loads(raw_ingredients)
        except Exception:
            raw_ingredients = [raw_ingredients]

    raw_keywords = recipe.get("keywords") or []
    if isinstance(raw_keywords, str):
        try:
            raw_keywords = _json.loads(raw_keywords)
        except Exception:
            raw_keywords = [raw_keywords]

    return predict_leftovers(
        title=title,
        ingredients=[str(i) for i in raw_ingredients],
        category=recipe.get("category"),
        keywords=[str(k) for k in raw_keywords],
    )
