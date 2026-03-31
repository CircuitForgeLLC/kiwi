"""
ElementClassifier -- classify pantry items into culinary element tags.

Lookup order:
  1. ingredient_profiles table (pre-computed from USDA FDC)
  2. Keyword heuristic fallback (for unlisted ingredients)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.store import Store

# All valid ingredient-level element labels (Method is recipe-level, not ingredient-level)
ELEMENTS = frozenset({
    "Seasoning", "Richness", "Brightness", "Depth",
    "Aroma", "Structure", "Texture",
})

_HEURISTIC: list[tuple[list[str], str]] = [
    (["vinegar", "lemon", "lime", "citrus", "wine", "yogurt", "kefir",
      "buttermilk", "tomato", "tamarind"], "Brightness"),
    (["oil", "butter", "cream", "lard", "fat", "avocado", "coconut milk",
      "ghee", "shortening", "crisco"], "Richness"),
    (["salt", "soy", "miso", "tamari", "fish sauce", "worcestershire",
      "anchov", "capers", "olive", "brine"], "Seasoning"),
    (["mushroom", "parmesan", "miso", "nutritional yeast", "bouillon",
      "broth", "umami", "anchov", "dried tomato", "soy"], "Depth"),
    (["garlic", "onion", "shallot", "herb", "basil", "oregano", "thyme",
      "rosemary", "spice", "cumin", "coriander", "paprika", "chili",
      "ginger", "cinnamon", "pepper", "cilantro", "dill", "fennel",
      "cardamom", "turmeric", "smoke"], "Aroma"),
    (["flour", "starch", "cornstarch", "arrowroot", "egg", "gelatin",
      "agar", "breadcrumb", "panko", "roux"], "Structure"),
    (["nut", "seed", "cracker", "crisp", "wafer", "chip", "crouton",
      "granola", "tofu", "tempeh"], "Texture"),
]


@dataclass(frozen=True)
class IngredientProfile:
    name: str
    elements: list[str]
    fat_pct: float = 0.0
    fat_saturated_pct: float = 0.0
    moisture_pct: float = 0.0
    protein_pct: float = 0.0
    starch_pct: float = 0.0
    binding_score: int = 0
    glutamate_mg: float = 0.0
    ph_estimate: float | None = None
    flavor_molecule_ids: list[str] = field(default_factory=list)
    heat_stable: bool = True
    add_timing: str = "any"
    acid_type: str | None = None
    sodium_mg_per_100g: float = 0.0
    is_fermented: bool = False
    texture_profile: str = "neutral"
    smoke_point_c: float | None = None
    is_emulsifier: bool = False
    source: str = "heuristic"


class ElementClassifier:
    def __init__(self, store: "Store") -> None:
        self._store = store

    def classify(self, ingredient_name: str) -> IngredientProfile:
        """Return element profile for a single ingredient name."""
        name = ingredient_name.lower().strip()
        row = self._store._fetch_one(
            "SELECT * FROM ingredient_profiles WHERE name = ?", (name,)
        )
        if row:
            return self._row_to_profile(row)
        return self._heuristic_profile(name)

    def classify_batch(self, names: list[str]) -> list[IngredientProfile]:
        return [self.classify(n) for n in names]

    def identify_gaps(self, profiles: list[IngredientProfile]) -> list[str]:
        """Return element names that have no coverage in the given profile list."""
        covered = set()
        for p in profiles:
            covered.update(p.elements)
        return sorted(ELEMENTS - covered)

    def _row_to_profile(self, row: dict) -> IngredientProfile:
        return IngredientProfile(
            name=row["name"],
            elements=json.loads(row.get("elements") or "[]"),
            fat_pct=row.get("fat_pct") or 0.0,
            fat_saturated_pct=row.get("fat_saturated_pct") or 0.0,
            moisture_pct=row.get("moisture_pct") or 0.0,
            protein_pct=row.get("protein_pct") or 0.0,
            starch_pct=row.get("starch_pct") or 0.0,
            binding_score=row.get("binding_score") or 0,
            glutamate_mg=row.get("glutamate_mg") or 0.0,
            ph_estimate=row.get("ph_estimate"),
            flavor_molecule_ids=json.loads(row.get("flavor_molecule_ids") or "[]"),
            heat_stable=bool(row.get("heat_stable", 1)),
            add_timing=row.get("add_timing") or "any",
            acid_type=row.get("acid_type"),
            sodium_mg_per_100g=row.get("sodium_mg_per_100g") or 0.0,
            is_fermented=bool(row.get("is_fermented", 0)),
            texture_profile=row.get("texture_profile") or "neutral",
            smoke_point_c=row.get("smoke_point_c"),
            is_emulsifier=bool(row.get("is_emulsifier", 0)),
            source="db",
        )

    def _heuristic_profile(self, name: str) -> IngredientProfile:
        elements = []
        for keywords, element in _HEURISTIC:
            if any(kw in name for kw in keywords):
                elements.append(element)
        return IngredientProfile(name=name, elements=elements, source="heuristic")
