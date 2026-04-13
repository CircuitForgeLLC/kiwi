# app/services/community/element_snapshot.py
# MIT License

from __future__ import annotations

from dataclasses import dataclass

# Ingredient name substrings → allergen flag
_ALLERGEN_MAP: dict[str, str] = {
    "milk": "dairy", "cream": "dairy", "cheese": "dairy", "butter": "dairy",
    "yogurt": "dairy", "whey": "dairy",
    "egg": "eggs",
    "wheat": "gluten", "pasta": "gluten", "flour": "gluten", "bread": "gluten",
    "barley": "gluten", "rye": "gluten",
    "peanut": "nuts", "almond": "nuts", "cashew": "nuts", "walnut": "nuts",
    "pecan": "nuts", "hazelnut": "nuts", "pistachio": "nuts", "macadamia": "nuts",
    "soy": "soy", "tofu": "soy", "edamame": "soy", "miso": "soy", "tempeh": "soy",
    "shrimp": "shellfish", "crab": "shellfish", "lobster": "shellfish",
    "clam": "shellfish", "mussel": "shellfish", "scallop": "shellfish",
    "fish": "fish", "salmon": "fish", "tuna": "fish", "cod": "fish",
    "tilapia": "fish", "halibut": "fish",
    "sesame": "sesame",
}

_MEAT_KEYWORDS = frozenset([
    "chicken", "beef", "pork", "lamb", "turkey", "bacon", "ham", "sausage",
    "salami", "prosciutto", "guanciale", "pancetta", "steak", "ground meat",
    "mince", "veal", "duck", "venison", "bison", "lard",
])
_SEAFOOD_KEYWORDS = frozenset([
    "fish", "shrimp", "crab", "lobster", "tuna", "salmon", "clam", "mussel",
    "scallop", "anchovy", "sardine", "cod", "tilapia",
])
_ANIMAL_PRODUCT_KEYWORDS = frozenset([
    "milk", "cream", "cheese", "butter", "egg", "honey", "yogurt", "whey",
])


def _detect_allergens(ingredient_names: list[str]) -> list[str]:
    found: set[str] = set()
    lowered = [n.lower() for n in ingredient_names]
    for ingredient in lowered:
        for keyword, flag in _ALLERGEN_MAP.items():
            if keyword in ingredient:
                found.add(flag)
    return sorted(found)


def _detect_dietary_tags(ingredient_names: list[str]) -> list[str]:
    lowered = [n.lower() for n in ingredient_names]
    all_text = " ".join(lowered)

    has_meat = any(k in all_text for k in _MEAT_KEYWORDS)
    has_seafood = any(k in all_text for k in _SEAFOOD_KEYWORDS)
    has_animal_products = any(k in all_text for k in _ANIMAL_PRODUCT_KEYWORDS)

    tags: list[str] = []
    if not has_meat and not has_seafood:
        tags.append("vegetarian")
    if not has_meat and not has_seafood and not has_animal_products:
        tags.append("vegan")
    return tags


@dataclass(frozen=True)
class ElementSnapshot:
    seasoning_score: float
    richness_score: float
    brightness_score: float
    depth_score: float
    aroma_score: float
    structure_score: float
    texture_profile: str
    dietary_tags: tuple
    allergen_flags: tuple
    flavor_molecules: tuple
    fat_pct: float | None
    protein_pct: float | None
    moisture_pct: float | None


def compute_snapshot(recipe_ids: list[int], store) -> ElementSnapshot:
    """Compute an element snapshot from a list of recipe IDs.

    Pulls SFAH scores, ingredient lists, and USDA FDC macros from the corpus.
    Averages numeric scores across all recipes. Unions allergen flags and dietary tags.
    Call at publish time only — snapshot is stored denormalized in community_posts.
    """
    if not recipe_ids:
        return ElementSnapshot(
            seasoning_score=0.0, richness_score=0.0, brightness_score=0.0,
            depth_score=0.0, aroma_score=0.0, structure_score=0.0,
            texture_profile="", dietary_tags=(), allergen_flags=(),
            flavor_molecules=(), fat_pct=None, protein_pct=None, moisture_pct=None,
        )

    rows = store.get_recipes_by_ids(recipe_ids)
    if not rows:
        return ElementSnapshot(
            seasoning_score=0.0, richness_score=0.0, brightness_score=0.0,
            depth_score=0.0, aroma_score=0.0, structure_score=0.0,
            texture_profile="", dietary_tags=(), allergen_flags=(),
            flavor_molecules=(), fat_pct=None, protein_pct=None, moisture_pct=None,
        )

    def _avg(field: str) -> float:
        vals = [r.get(field) or 0.0 for r in rows]
        return sum(vals) / len(vals)

    all_ingredients: list[str] = []
    for r in rows:
        names = r.get("ingredient_names") or []
        all_ingredients.extend(names if isinstance(names, list) else [])

    allergens = _detect_allergens(all_ingredients)
    dietary = _detect_dietary_tags(all_ingredients)

    texture = rows[0].get("texture_profile") or ""

    fat_vals = [r.get("fat") for r in rows if r.get("fat") is not None]
    prot_vals = [r.get("protein") for r in rows if r.get("protein") is not None]
    moist_vals = [r.get("moisture") for r in rows if r.get("moisture") is not None]

    return ElementSnapshot(
        seasoning_score=_avg("seasoning_score"),
        richness_score=_avg("richness_score"),
        brightness_score=_avg("brightness_score"),
        depth_score=_avg("depth_score"),
        aroma_score=_avg("aroma_score"),
        structure_score=_avg("structure_score"),
        texture_profile=texture,
        dietary_tags=tuple(dietary),
        allergen_flags=tuple(allergens),
        flavor_molecules=(),
        fat_pct=(sum(fat_vals) / len(fat_vals)) if fat_vals else None,
        protein_pct=(sum(prot_vals) / len(prot_vals)) if prot_vals else None,
        moisture_pct=(sum(moist_vals) / len(moist_vals)) if moist_vals else None,
    )
