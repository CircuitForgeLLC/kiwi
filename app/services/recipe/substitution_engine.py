"""
SubstitutionEngine — deterministic ingredient swap candidates with compensation hints.

Powered by:
  - substitution_pairs table (derived from lishuyang/recipepairs)
  - ingredient_profiles functional metadata (USDA FDC)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.store import Store

# Compensation threshold — if |delta| exceeds this, surface a hint
_FAT_THRESHOLD = 5.0       # grams per 100g
_GLUTAMATE_THRESHOLD = 1.0 # mg per 100g
_MOISTURE_THRESHOLD = 15.0 # grams per 100g

_RICHNESS_COMPENSATORS = ["olive oil", "coconut oil", "butter", "shortening", "full-fat coconut milk"]
_DEPTH_COMPENSATORS    = ["nutritional yeast", "soy sauce", "miso", "mushroom powder",
                           "better than bouillon not-beef", "smoked paprika"]
_MOISTURE_BINDERS      = ["cornstarch", "flour", "arrowroot", "breadcrumbs"]


@dataclass(frozen=True)
class CompensationHint:
    ingredient: str
    reason: str
    element: str


@dataclass(frozen=True)
class SubstitutionSwap:
    original_name: str
    substitute_name: str
    constraint_label: str
    fat_delta: float
    moisture_delta: float
    glutamate_delta: float
    protein_delta: float
    occurrence_count: int
    compensation_hints: list[dict] = field(default_factory=list)
    explanation: str = ""


class SubstitutionEngine:
    def __init__(self, store: "Store") -> None:
        self._store = store

    def find_substitutes(
        self,
        ingredient_name: str,
        constraint: str,
    ) -> list[SubstitutionSwap]:
        rows = self._store._fetch_all("""
            SELECT substitute_name, constraint_label,
                   fat_delta, moisture_delta, glutamate_delta, protein_delta,
                   occurrence_count, compensation_hints
            FROM substitution_pairs
            WHERE original_name = ? AND constraint_label = ?
            ORDER BY occurrence_count DESC
        """, (ingredient_name.lower(), constraint))

        return [self._row_to_swap(ingredient_name, row) for row in rows]

    def _row_to_swap(self, original: str, row: dict) -> SubstitutionSwap:
        hints = self._build_hints(row)
        explanation = self._build_explanation(original, row, hints)
        return SubstitutionSwap(
            original_name=original,
            substitute_name=row["substitute_name"],
            constraint_label=row["constraint_label"],
            fat_delta=row.get("fat_delta") or 0.0,
            moisture_delta=row.get("moisture_delta") or 0.0,
            glutamate_delta=row.get("glutamate_delta") or 0.0,
            protein_delta=row.get("protein_delta") or 0.0,
            occurrence_count=row.get("occurrence_count") or 1,
            compensation_hints=[{"ingredient": h.ingredient, "reason": h.reason, "element": h.element} for h in hints],
            explanation=explanation,
        )

    def _build_hints(self, row: dict) -> list[CompensationHint]:
        hints = []
        fat_delta = row.get("fat_delta") or 0.0
        glutamate_delta = row.get("glutamate_delta") or 0.0
        moisture_delta = row.get("moisture_delta") or 0.0

        if fat_delta < -_FAT_THRESHOLD:
            missing = abs(fat_delta)
            sugg = _RICHNESS_COMPENSATORS[0]
            hints.append(CompensationHint(
                ingredient=sugg,
                reason=f"substitute has ~{missing:.0f}g/100g less fat — add {sugg} to restore Richness",
                element="Richness",
            ))

        if glutamate_delta < -_GLUTAMATE_THRESHOLD:
            sugg = _DEPTH_COMPENSATORS[0]
            hints.append(CompensationHint(
                ingredient=sugg,
                reason=f"substitute is lower in umami — add {sugg} to restore Depth",
                element="Depth",
            ))

        if moisture_delta > _MOISTURE_THRESHOLD:
            sugg = _MOISTURE_BINDERS[0]
            hints.append(CompensationHint(
                ingredient=sugg,
                reason=f"substitute adds ~{moisture_delta:.0f}g/100g more moisture — add {sugg} to maintain Structure",
                element="Structure",
            ))

        return hints

    def _build_explanation(
        self, original: str, row: dict, hints: list[CompensationHint]
    ) -> str:
        sub = row["substitute_name"]
        count = row.get("occurrence_count") or 1
        base = f"Replace {original} with {sub} (seen in {count} recipes)."
        if hints:
            base += " To compensate: " + "; ".join(h.reason for h in hints) + "."
        return base
