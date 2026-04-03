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

from app.models.schemas.recipe import GroceryLink, NutritionPanel, RecipeRequest, RecipeResult, RecipeSuggestion, SwapCandidate
from app.services.recipe.assembly_recipes import match_assembly_templates
from app.services.recipe.element_classifier import ElementClassifier
from app.services.recipe.grocery_links import GroceryLinkBuilder
from app.services.recipe.substitution_engine import SubstitutionEngine

_LEFTOVER_DAILY_MAX_FREE = 5

# Words that carry no ingredient-identity signal — stripped before overlap scoring
_SWAP_STOPWORDS = frozenset({
    "a", "an", "the", "of", "in", "for", "with", "and", "or",
    "to", "from", "at", "by", "as", "on",
})

# Maps product-label substrings to recipe-corpus canonical terms.
# Kept in sync with Store._FTS_SYNONYMS — both must agree on canonical names.
# Used to expand pantry_set so single-word recipe ingredients can match
# multi-word product names (e.g. "hamburger" satisfied by "burger patties").
_PANTRY_LABEL_SYNONYMS: dict[str, str] = {
    "burger patt":  "hamburger",
    "beef patt":    "hamburger",
    "ground beef":  "hamburger",
    "ground chuck": "hamburger",
    "ground round": "hamburger",
    "mince":        "hamburger",
    "veggie burger":   "hamburger",
    "beyond burger":   "hamburger",
    "impossible burger": "hamburger",
    "plant burger":    "hamburger",
    "chicken patt":    "chicken patty",
    "kielbasa":     "sausage",
    "bratwurst":    "sausage",
    "frankfurter":  "hotdog",
    "wiener":       "hotdog",
    "chicken breast":   "chicken",
    "chicken thigh":    "chicken",
    "chicken drumstick": "chicken",
    "chicken wing":     "chicken",
    "rotisserie chicken": "chicken",
    "chicken tender":   "chicken",
    "chicken strip":    "chicken",
    "chicken piece":    "chicken",
    "fake chicken":     "chicken",
    "plant chicken":    "chicken",
    "vegan chicken":    "chicken",
    "daring":           "chicken",
    "gardein chick":    "chicken",
    "quorn chick":      "chicken",
    "chick'n":          "chicken",
    "chikn":            "chicken",
    "not-chicken":      "chicken",
    "no-chicken":       "chicken",
    # Plant-based beef subs → broad "beef" (strips ≠ ground; texture matters)
    "not-beef":         "beef",
    "no-beef":          "beef",
    "plant beef":       "beef",
    "vegan beef":       "beef",
    # Plant-based pork subs
    "not-pork":         "pork",
    "no-pork":          "pork",
    "plant pork":       "pork",
    "vegan pork":       "pork",
    "omnipork":         "pork",
    "omni pork":        "pork",
    # Generic alt-meat catch-alls → broad "beef"
    "fake meat":        "beef",
    "plant meat":       "beef",
    "vegan meat":       "beef",
    "meat-free":        "beef",
    "meatless":         "beef",
    "pork chop":    "pork",
    "pork loin":    "pork",
    "pork tenderloin": "pork",
    "marinara":     "tomato sauce",
    "pasta sauce":  "tomato sauce",
    "spaghetti sauce": "tomato sauce",
    "pizza sauce":  "tomato sauce",
    "macaroni":     "pasta",
    "noodles":      "pasta",
    "spaghetti":    "pasta",
    "penne":        "pasta",
    "fettuccine":   "pasta",
    "rigatoni":     "pasta",
    "linguine":     "pasta",
    "rotini":       "pasta",
    "farfalle":     "pasta",
    "shredded cheese":  "cheese",
    "sliced cheese":    "cheese",
    "american cheese":  "cheese",
    "cheddar":      "cheese",
    "mozzarella":   "cheese",
    "heavy cream":  "cream",
    "whipping cream": "cream",
    "half and half": "cream",
    "burger bun":   "buns",
    "hamburger bun": "buns",
    "hot dog bun":  "buns",
    "bread roll":   "buns",
    "dinner roll":  "buns",
    # Tortillas / wraps — assembly dishes (burritos, tacos, quesadillas)
    "flour tortilla": "tortillas",
    "corn tortilla":  "tortillas",
    "tortilla wrap":  "tortillas",
    "soft taco shell": "tortillas",
    "taco shell":     "taco shells",
    "pita bread":     "pita",
    "flatbread":      "flatbread",
    # Canned beans — extremely interchangeable in assembly dishes
    "black bean":     "beans",
    "pinto bean":     "beans",
    "kidney bean":    "beans",
    "refried bean":   "beans",
    "chickpea":       "beans",
    "garbanzo":       "beans",
    # Rice variants
    "white rice":     "rice",
    "brown rice":     "rice",
    "jasmine rice":   "rice",
    "basmati rice":   "rice",
    "instant rice":   "rice",
    "microwavable rice": "rice",
    # Salsa / hot sauce
    "hot sauce":      "salsa",
    "taco sauce":     "salsa",
    "enchilada sauce": "salsa",
    # Sour cream / Greek yogurt — functional substitutes
    "greek yogurt":   "sour cream",
    # Frozen/prepackaged meal token extraction — handled by individual token
    # fallback in _normalize_for_fts; these are the most common single-serve meal types
    "lean cuisine":   "casserole",
    "stouffer":       "casserole",
    "healthy choice": "casserole",
    "marie callender": "casserole",
}


# Matches leading quantity/unit prefixes in recipe ingredient strings,
# e.g. "2 cups flour" → "flour", "1/2 c. ketchup" → "ketchup",
#      "3 oz. butter" → "butter"
_QUANTITY_PREFIX = re.compile(
    r"^\s*(?:\d+(?:[./]\d+)?\s*)?"       # optional leading number (1, 1/2, 2.5)
    r"(?:to\s+\d+\s*)?"                   # optional "to N" range
    r"(?:c\.|cup|cups|tbsp|tsp|oz|lb|lbs|g|kg|ml|l|"
    r"can|cans|pkg|pkg\.|package|slice|slices|clove|cloves|"
    r"small|medium|large|bunch|head|piece|pieces|"
    r"pinch|dash|handful|sprig|sprigs)\s*\b",
    re.IGNORECASE,
)


# Preparation-state words that modify an ingredient without changing what it is.
# Stripped from both ends so "melted butter", "butter, melted" both → "butter".
_PREP_STATES = re.compile(
    r"\b(melted|softened|cold|warm|hot|room.temperature|"
    r"diced|sliced|chopped|minced|grated|shredded|shredded|beaten|whipped|"
    r"cooked|raw|frozen|canned|dried|dehydrated|marinated|seasoned|"
    r"roasted|toasted|ground|crushed|pressed|peeled|seeded|pitted|"
    r"boneless|skinless|trimmed|halved|quartered|julienned|"
    r"thinly|finely|roughly|coarsely|freshly|lightly|"
    r"packed|heaping|level|sifted|divided|optional)\b",
    re.IGNORECASE,
)
# Trailing comma + optional prep state (e.g. "butter, melted")
_TRAILING_PREP = re.compile(r",\s*\w+$")


# Maps prep-state words to human-readable instruction templates.
# {ingredient} is replaced with the actual ingredient name.
# None means the state is passive (frozen, canned) — no note needed.
_PREP_INSTRUCTIONS: dict[str, str | None] = {
    "melted":           "Melt the {ingredient} before starting.",
    "softened":         "Let the {ingredient} soften to room temperature before using.",
    "room temperature": "Bring the {ingredient} to room temperature before using.",
    "beaten":           "Beat the {ingredient} lightly before adding.",
    "whipped":          "Whip the {ingredient} until soft peaks form.",
    "sifted":           "Sift the {ingredient} before measuring.",
    "toasted":          "Toast the {ingredient} in a dry pan until fragrant.",
    "roasted":          "Roast the {ingredient} before using.",
    "pressed":          "Press the {ingredient} to remove excess moisture.",
    "diced":            "Dice the {ingredient} into small pieces.",
    "sliced":           "Slice the {ingredient} thinly.",
    "chopped":          "Chop the {ingredient} roughly.",
    "minced":           "Mince the {ingredient} finely.",
    "grated":           "Grate the {ingredient}.",
    "shredded":         "Shred the {ingredient}.",
    "ground":           "Grind the {ingredient}.",
    "crushed":          "Crush the {ingredient}.",
    "peeled":           "Peel the {ingredient} before use.",
    "seeded":           "Remove seeds from the {ingredient}.",
    "pitted":           "Pit the {ingredient} before use.",
    "trimmed":          "Trim any excess from the {ingredient}.",
    "julienned":        "Cut the {ingredient} into thin matchstick strips.",
    "cooked":           "Pre-cook the {ingredient} before adding.",
    # Passive states — ingredient is used as-is, no prep note needed
    "cold":             None,
    "warm":             None,
    "hot":              None,
    "raw":              None,
    "frozen":           None,
    "canned":           None,
    "dried":            None,
    "dehydrated":       None,
    "marinated":        None,
    "seasoned":         None,
    "boneless":         None,
    "skinless":         None,
    "divided":          None,
    "optional":         None,
    "fresh":            None,
    "freshly":          None,
    "thinly":           None,
    "finely":           None,
    "roughly":          None,
    "coarsely":         None,
    "lightly":          None,
    "packed":           None,
    "heaping":          None,
    "level":            None,
}

# Finds the first actionable prep state in an ingredient string
_PREP_STATE_SEARCH = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _PREP_INSTRUCTIONS) + r")\b",
    re.IGNORECASE,
)


def _strip_quantity(ingredient: str) -> str:
    """Remove leading quantity/unit and preparation-state words from a recipe ingredient.

    e.g. "2 tbsp melted butter" → "butter"
         "butter, melted"       → "butter"
         "1/4 cup flour, sifted" → "flour"
    """
    stripped = _QUANTITY_PREFIX.sub("", ingredient).strip()
    # Strip any remaining leading number (e.g. "3 eggs" → "eggs")
    stripped = re.sub(r"^\d+\s+", "", stripped)
    # Strip trailing ", prep_state"
    stripped = _TRAILING_PREP.sub("", stripped).strip()
    # Strip prep-state words (may be leading or embedded)
    stripped = _PREP_STATES.sub("", stripped).strip()
    # Clean up any double spaces left behind
    stripped = re.sub(r"\s{2,}", " ", stripped).strip()
    return stripped or ingredient


def _prep_note_for(ingredient: str) -> str | None:
    """Return a human-readable prep instruction for this ingredient string, or None.

    e.g. "2 tbsp melted butter" → "Melt the butter before starting."
         "onion, diced"         → "Dice the onion into small pieces."
         "frozen peas"          → None  (passive state, no action needed)
    """
    match = _PREP_STATE_SEARCH.search(ingredient)
    if not match:
        return None
    state = match.group(1).lower()
    template = _PREP_INSTRUCTIONS.get(state)
    if not template:
        return None
    # Use the stripped ingredient name as the subject
    ingredient_name = _strip_quantity(ingredient)
    return template.format(ingredient=ingredient_name)


def _expand_pantry_set(pantry_items: list[str]) -> set[str]:
    """Return pantry_set expanded with canonical recipe-corpus synonyms.

    For each pantry item, checks _PANTRY_LABEL_SYNONYMS for substring matches
    and adds the canonical form.  This lets single-word recipe ingredients
    ("hamburger", "chicken") match product-label pantry entries
    ("burger patties", "rotisserie chicken").
    """
    expanded: set[str] = set()
    for item in pantry_items:
        lower = item.lower().strip()
        expanded.add(lower)
        for pattern, canonical in _PANTRY_LABEL_SYNONYMS.items():
            if pattern in lower:
                expanded.add(canonical)
    return expanded


def _ingredient_in_pantry(ingredient: str, pantry_set: set[str]) -> bool:
    """Return True if the recipe ingredient is satisfied by the pantry.

    Checks three layers in order:
    1. Exact match after quantity stripping
    2. Synonym lookup: ingredient → canonical → in pantry_set
       (handles "ground beef" matched by "burger patties" via shared canonical)
    3. Token subset: all content tokens of the ingredient appear in pantry
       (handles "diced onions" when "onions" is in pantry)
    """
    clean = _strip_quantity(ingredient).lower()
    if clean in pantry_set:
        return True

    # Check if this recipe ingredient maps to a canonical that's in pantry
    for pattern, canonical in _PANTRY_LABEL_SYNONYMS.items():
        if pattern in clean and canonical in pantry_set:
            return True

    # Single-token ingredient whose token appears in pantry (e.g. "ketchup" in "c. ketchup")
    tokens = [t for t in clean.split() if t not in _SWAP_STOPWORDS and len(t) > 2]
    if tokens and all(t in pantry_set for t in tokens):
        return True

    return False


def _content_tokens(text: str) -> frozenset[str]:
    return frozenset(
        w for w in text.lower().split()
        if w not in _SWAP_STOPWORDS and len(w) > 1
    )


def _pantry_creative_swap(required: str, pantry_items: set[str]) -> str | None:
    """Return a pantry item that's a plausible creative substitute, or None.

    Requires ≥2 shared content tokens AND ≥50% bidirectional overlap so that
    single-word differences (cream-of-mushroom vs cream-of-potato) qualify while
    single-word ingredients (butter, flour) don't accidentally match supersets
    (peanut butter, bread flour).
    """
    req_tokens = _content_tokens(required)
    if len(req_tokens) < 2:
        return None  # single-word ingredients must already be in pantry_set

    best: str | None = None
    best_score = 0.0
    for item in pantry_items:
        if item.lower() == required.lower():
            continue
        pan_tokens = _content_tokens(item)
        if not pan_tokens:
            continue
        overlap = len(req_tokens & pan_tokens)
        if overlap < 2:
            continue
        score = min(overlap / len(req_tokens), overlap / len(pan_tokens))
        if score >= 0.5 and score > best_score:
            best_score = score
            best = item
    return best


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
        # Load cooking equipment from user settings when hard_day_mode is active
        if req.hard_day_mode and available_equipment is None:
            equipment_json = self._store.get_setting("cooking_equipment")
            if equipment_json:
                try:
                    available_equipment = json.loads(equipment_json)
                except (json.JSONDecodeError, TypeError):
                    available_equipment = []
            else:
                available_equipment = []
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
        pantry_set = _expand_pantry_set(req.pantry_items)

        if req.level >= 3:
            from app.services.recipe.llm_recipe import LLMRecipeGenerator
            gen = LLMRecipeGenerator(self._store)
            return gen.generate(req, profiles, gaps)

        # Level 1 & 2: deterministic path
        nf = req.nutrition_filters
        rows = self._store.search_recipes_by_ingredients(
            req.pantry_items,
            limit=20,
            category=req.category or None,
            max_calories=nf.max_calories,
            max_sugar_g=nf.max_sugar_g,
            max_carbs_g=nf.max_carbs_g,
            max_sodium_mg=nf.max_sodium_mg,
            excluded_ids=req.excluded_ids or [],
        )
        suggestions = []

        for row in rows:
            ingredient_names: list[str] = row.get("ingredient_names") or []
            if isinstance(ingredient_names, str):
                try:
                    ingredient_names = json.loads(ingredient_names)
                except Exception:
                    ingredient_names = []

            # Compute missing ingredients, detecting pantry coverage first.
            # When covered, collect any prep-state annotations (e.g. "melted butter"
            # → note "Melt the butter before starting.") to surface separately.
            swap_candidates: list[SwapCandidate] = []
            missing: list[str] = []
            prep_note_set: set[str] = set()
            for n in ingredient_names:
                if _ingredient_in_pantry(n, pantry_set):
                    note = _prep_note_for(n)
                    if note:
                        prep_note_set.add(note)
                    continue
                swap_item = _pantry_creative_swap(n, pantry_set)
                if swap_item:
                    swap_candidates.append(SwapCandidate(
                        original_name=n,
                        substitute_name=swap_item,
                        constraint_label="pantry_swap",
                        explanation=f"You have {swap_item} — use it in place of {n}.",
                        compensation_hints=[],
                    ))
                else:
                    missing.append(n)

            # Filter by max_missing (pantry swaps don't count as missing)
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

            # Level 2: also add dietary constraint swaps from substitution_pairs
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

            servings = row.get("servings") or None
            nutrition = NutritionPanel(
                calories=row.get("calories"),
                fat_g=row.get("fat_g"),
                protein_g=row.get("protein_g"),
                carbs_g=row.get("carbs_g"),
                fiber_g=row.get("fiber_g"),
                sugar_g=row.get("sugar_g"),
                sodium_mg=row.get("sodium_mg"),
                servings=servings,
                estimated=bool(row.get("nutrition_estimated", 0)),
            )
            has_nutrition = any(
                v is not None
                for v in (nutrition.calories, nutrition.sugar_g, nutrition.carbs_g)
            )
            suggestions.append(RecipeSuggestion(
                id=row["id"],
                title=row["title"],
                match_count=int(row.get("match_count") or 0),
                element_coverage=coverage_raw,
                swap_candidates=swap_candidates,
                missing_ingredients=missing,
                prep_notes=sorted(prep_note_set),
                level=req.level,
                nutrition=nutrition if has_nutrition else None,
            ))

        # Prepend assembly-dish templates (burrito, stir fry, omelette, etc.)
        # These fire regardless of corpus coverage — any pantry can make a burrito.
        assembly = match_assembly_templates(
            pantry_items=req.pantry_items,
            pantry_set=pantry_set,
            excluded_ids=req.excluded_ids or [],
        )
        suggestions = assembly + suggestions

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
