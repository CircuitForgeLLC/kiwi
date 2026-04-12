# app/services/meal_plan/shopping_list.py
"""Compute a shopping list from a meal plan and current pantry inventory.

Pure function — no DB or network calls. Takes plain dicts from the Store
and returns GapItem dataclasses.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GapItem:
    ingredient_name: str
    needed_raw: str | None       # first quantity token from recipe text, e.g. "300g"
    have_quantity: float | None  # pantry quantity when partial match
    have_unit: str | None
    covered: bool
    retailer_links: list = field(default_factory=list)  # filled by API layer


_QUANTITY_RE = re.compile(r"^(\d+[\d./]*\s*(?:g|kg|ml|l|oz|lb|cup|cups|tsp|tbsp|tbsps|tsps)?)\b", re.I)


def _extract_quantity(ingredient_text: str) -> str | None:
    """Pull the leading quantity string from a raw ingredient line."""
    m = _QUANTITY_RE.match(ingredient_text.strip())
    return m.group(1).strip() if m else None


def _normalise(name: str) -> str:
    """Lowercase, strip possessives and plural -s for fuzzy matching."""
    return name.lower().strip().rstrip("s")


def compute_shopping_list(
    recipes: list[dict],
    inventory: list[dict],
) -> tuple[list[GapItem], list[GapItem]]:
    """Return (gap_items, covered_items) for a list of recipe dicts + inventory dicts.

    Deduplicates by normalised ingredient name — the first recipe's quantity
    string wins when the same ingredient appears in multiple recipes.
    """
    if not recipes:
        return [], []

    # Build pantry lookup: normalised_name → inventory row
    pantry: dict[str, dict] = {}
    for item in inventory:
        pantry[_normalise(item["name"])] = item

    # Collect unique ingredients with their first quantity token
    seen: dict[str, str | None] = {}  # normalised_name → needed_raw
    for recipe in recipes:
        names: list[str] = recipe.get("ingredient_names") or []
        raw_lines: list[str] = recipe.get("ingredients") or []
        for i, name in enumerate(names):
            key = _normalise(name)
            if key in seen:
                continue
            raw = raw_lines[i] if i < len(raw_lines) else ""
            seen[key] = _extract_quantity(raw)

    gaps: list[GapItem] = []
    covered: list[GapItem] = []

    for norm_name, needed_raw in seen.items():
        pantry_row = pantry.get(norm_name)
        if pantry_row:
            covered.append(GapItem(
                ingredient_name=norm_name,
                needed_raw=needed_raw,
                have_quantity=pantry_row.get("quantity"),
                have_unit=pantry_row.get("unit"),
                covered=True,
            ))
        else:
            gaps.append(GapItem(
                ingredient_name=norm_name,
                needed_raw=needed_raw,
                have_quantity=None,
                have_unit=None,
                covered=False,
            ))

    return gaps, covered
