"""
Recipe tag inference engine.

Derives normalized tags from a recipe's title, ingredient names, existing corpus
tags (category + keywords), enriched ingredient profile data, and optional
nutrition data.

Tags are organized into five namespaces:
  cuisine:*     -- cuisine/region classification
  dietary:*     -- dietary restriction / nutrition profile
  flavor:*      -- flavor profile (spicy, smoky, sweet, etc.)
  time:*        -- effort / time signals
  meal:*        -- meal type
  can_be:*      -- achievable with substitutions (e.g. can_be:Gluten-Free)

Output is a flat sorted list of strings, e.g.:
  ["can_be:Gluten-Free", "cuisine:Italian", "dietary:Low-Carb",
   "flavor:Savory", "flavor:Umami", "time:Quick"]

These populate recipes.inferred_tags and are FTS5-indexed so browse domain
queries find recipes the food.com corpus tags alone would miss.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Text-signal tables
# (tag, [case-insensitive substrings to search in combined title+ingredient text])
# ---------------------------------------------------------------------------

_CUISINE_SIGNALS: list[tuple[str, list[str]]] = [
    ("cuisine:Japanese",       ["miso", "dashi", "ramen", "sushi", "teriyaki", "sake", "mirin",
                                  "wasabi", "panko", "edamame", "tonkatsu", "yakitori", "ponzu"]),
    ("cuisine:Korean",         ["gochujang", "kimchi", "doenjang", "gochugaru",
                                  "bulgogi", "bibimbap", "japchae"]),
    ("cuisine:Thai",           ["fish sauce", "lemongrass", "galangal", "pad thai", "thai basil",
                                  "kaffir lime", "tom yum", "green curry", "red curry", "nam pla"]),
    ("cuisine:Chinese",        ["hoisin", "oyster sauce", "five spice", "bok choy", "chow mein",
                                  "dumpling", "wonton", "mapo", "char siu", "sichuan"]),
    ("cuisine:Vietnamese",     ["pho", "banh mi", "nuoc cham", "rice paper", "vietnamese"]),
    ("cuisine:Indian",         ["garam masala", "turmeric", "cardamom", "fenugreek", "paneer",
                                  "tikka", "masala", "biryani", "dal", "naan", "tandoori",
                                  "curry leaf", "tamarind", "chutney"]),
    ("cuisine:Middle Eastern", ["tahini", "harissa", "za'atar", "sumac", "baharat", "rose water",
                                  "pomegranate molasses", "freekeh", "fattoush", "shakshuka"]),
    ("cuisine:Greek",          ["feta", "tzatziki", "moussaka", "spanakopita", "orzo",
                                  "kalamata", "gyro", "souvlaki", "dolma"]),
    ("cuisine:Mediterranean",  ["hummus", "pita", "couscous", "preserved lemon"]),
    ("cuisine:Italian",        ["pasta", "pizza", "risotto", "lasagna", "carbonara", "gnocchi",
                                  "parmesan", "mozzarella", "ricotta", "prosciutto", "pancetta",
                                  "arancini", "osso buco", "tiramisu", "pesto", "bolognese",
                                  "cannoli", "polenta", "bruschetta", "focaccia"]),
    ("cuisine:French",         ["croissant", "quiche", "crepe", "coq au vin",
                                  "ratatouille", "bearnaise", "hollandaise", "bouillabaisse",
                                  "herbes de provence", "dijon", "gruyere", "brie", "cassoulet"]),
    ("cuisine:Spanish",        ["paella", "chorizo", "gazpacho", "tapas", "patatas bravas",
                                  "sofrito", "manchego", "albondigas"]),
    ("cuisine:German",         ["sauerkraut", "bratwurst", "schnitzel", "pretzel", "strudel",
                                  "spaetzle", "sauerbraten"]),
    ("cuisine:Mexican",        ["taco", "burrito", "enchilada", "salsa", "guacamole", "chipotle",
                                  "queso", "tamale", "mole", "jalapeno", "tortilla", "carnitas",
                                  "chile verde", "posole", "tostada", "quesadilla"]),
    ("cuisine:Latin American", ["plantain", "yuca", "chimichurri", "ceviche", "adobo", "empanada"]),
    ("cuisine:American",       ["bbq sauce", "buffalo sauce", "ranch dressing", "coleslaw",
                                  "cornbread", "mac and cheese", "brisket", "cheeseburger"]),
    ("cuisine:Southern",       ["collard greens", "black-eyed peas", "okra", "grits", "catfish",
                                  "hush puppies", "pecan pie"]),
    ("cuisine:Cajun",          ["cajun", "creole", "gumbo", "jambalaya", "andouille", "etouffee"]),
    ("cuisine:African",        ["injera", "berbere", "jollof", "suya", "egusi", "fufu", "tagine"]),
    ("cuisine:Caribbean",      ["jerk", "scotch bonnet", "callaloo", "ackee"]),
]

_DIETARY_SIGNALS: list[tuple[str, list[str]]] = [
    ("dietary:Vegan",        ["vegan", "plant-based", "plant based"]),
    ("dietary:Vegetarian",   ["vegetarian", "meatless"]),
    ("dietary:Gluten-Free",  ["gluten-free", "gluten free", "celiac"]),
    ("dietary:Dairy-Free",   ["dairy-free", "dairy free", "lactose free", "non-dairy"]),
    ("dietary:Low-Carb",     ["low-carb", "low carb", "keto", "ketogenic", "very low carbs"]),
    ("dietary:High-Protein", ["high protein", "high-protein"]),
    ("dietary:Low-Fat",      ["low-fat", "low fat", "fat-free", "reduced fat"]),
    ("dietary:Paleo",        ["paleo", "whole30"]),
    ("dietary:Nut-Free",     ["nut-free", "nut free", "peanut free"]),
    ("dietary:Egg-Free",     ["egg-free", "egg free"]),
    ("dietary:Low-Sodium",   ["low sodium", "no salt"]),
    ("dietary:Healthy",      ["healthy", "low cholesterol", "heart healthy", "wholesome"]),
]

_FLAVOR_SIGNALS: list[tuple[str, list[str]]] = [
    ("flavor:Spicy",   ["jalapeno", "habanero", "ghost pepper", "sriracha",
                         "chili flake", "red pepper flake", "cayenne", "hot sauce",
                         "gochujang", "harissa", "scotch bonnet", "szechuan pepper", "spicy"]),
    ("flavor:Smoky",   ["smoked", "liquid smoke", "smoked paprika",
                         "bbq sauce", "barbecue", "hickory", "mesquite"]),
    ("flavor:Sweet",   ["honey", "maple syrup", "brown sugar", "caramel", "chocolate",
                         "vanilla", "condensed milk", "molasses", "agave"]),
    ("flavor:Savory",  ["soy sauce", "fish sauce", "miso", "worcestershire", "anchovy",
                         "parmesan", "blue cheese", "bone broth"]),
    ("flavor:Tangy",   ["lemon juice", "lime juice", "vinegar", "balsamic", "buttermilk",
                         "sour cream", "fermented", "pickled", "tamarind", "sumac"]),
    ("flavor:Herby",   ["fresh basil", "fresh cilantro", "fresh dill", "fresh mint",
                         "fresh tarragon", "fresh thyme", "herbes de provence"]),
    ("flavor:Rich",    ["heavy cream", "creme fraiche", "mascarpone", "double cream",
                         "ghee", "coconut cream", "cream cheese"]),
    ("flavor:Umami",   ["mushroom", "nutritional yeast", "tomato paste",
                         "parmesan rind", "bonito", "kombu"]),
]

_TIME_SIGNALS: list[tuple[str, list[str]]] = [
    ("time:Quick",        ["< 15 mins", "< 30 mins", "weeknight", "easy"]),
    ("time:Under 1 Hour", ["< 60 mins"]),
    ("time:Make-Ahead",   ["freezer", "overnight", "refrigerator", "make-ahead", "make ahead"]),
    ("time:Slow Cook",    ["slow cooker", "crockpot", "< 4 hours", "braise"]),
]

# food.com corpus tag -> normalized tags
_CORPUS_TAG_MAP: dict[str, list[str]] = {
    "european":        ["cuisine:Italian", "cuisine:French", "cuisine:German",
                         "cuisine:Spanish"],
    "asian":           ["cuisine:Chinese", "cuisine:Japanese", "cuisine:Thai",
                         "cuisine:Korean", "cuisine:Vietnamese"],
    "chinese":         ["cuisine:Chinese"],
    "japanese":        ["cuisine:Japanese"],
    "thai":            ["cuisine:Thai"],
    "vietnamese":      ["cuisine:Vietnamese"],
    "indian":          ["cuisine:Indian"],
    "greek":           ["cuisine:Greek"],
    "mexican":         ["cuisine:Mexican"],
    "african":         ["cuisine:African"],
    "caribbean":       ["cuisine:Caribbean"],
    "vegan":           ["dietary:Vegan", "dietary:Vegetarian"],
    "vegetarian":      ["dietary:Vegetarian"],
    "healthy":         ["dietary:Healthy"],
    "low cholesterol": ["dietary:Healthy"],
    "very low carbs":  ["dietary:Low-Carb"],
    "high in...":      ["dietary:High-Protein"],
    "lactose free":    ["dietary:Dairy-Free"],
    "egg free":        ["dietary:Egg-Free"],
    "< 15 mins":       ["time:Quick"],
    "< 30 mins":       ["time:Quick"],
    "< 60 mins":       ["time:Under 1 Hour"],
    "< 4 hours":       ["time:Slow Cook"],
    "weeknight":       ["time:Quick"],
    "freezer":         ["time:Make-Ahead"],
    "dessert":         ["meal:Dessert"],
    "breakfast":       ["meal:Breakfast"],
    "lunch/snacks":    ["meal:Lunch", "meal:Snack"],
    "beverages":       ["meal:Beverage"],
    "cookie & brownie": ["meal:Dessert"],
    "breads":          ["meal:Bread"],
}

# ingredient_profiles.elements value -> flavor tag
_ELEMENT_TO_FLAVOR: dict[str, str] = {
    "Aroma":      "flavor:Herby",
    "Richness":   "flavor:Rich",
    "Structure":  "",   # no flavor tag
    "Binding":    "",
    "Crust":      "flavor:Smoky",
    "Lift":       "",
    "Emulsion":   "flavor:Rich",
    "Acid":       "flavor:Tangy",
}


def _build_text(title: str, ingredient_names: list[str]) -> str:
    parts = [title.lower()]
    parts.extend(i.lower() for i in ingredient_names)
    return " ".join(parts)


def _match_signals(text: str, table: list[tuple[str, list[str]]]) -> list[str]:
    return [tag for tag, pats in table if any(p in text for p in pats)]


def infer_tags(
    title: str,
    ingredient_names: list[str],
    corpus_keywords: list[str],
    corpus_category: str = "",
    # Enriched ingredient profile signals (from ingredient_profiles cross-ref)
    element_coverage: dict[str, float] | None = None,
    fermented_count: int = 0,
    glutamate_total: float = 0.0,
    ph_min: float | None = None,
    available_sub_constraints: list[str] | None = None,
    # Nutrition data for macro-based tags
    calories: float | None = None,
    protein_g: float | None = None,
    fat_g: float | None = None,
    carbs_g: float | None = None,
    servings: float | None = None,
) -> list[str]:
    """
    Derive normalized tags for a recipe.

    Parameters
    ----------
    title, ingredient_names, corpus_keywords, corpus_category
        : Primary recipe data.
    element_coverage
        : Dict from recipes.element_coverage -- element name to coverage ratio
          (e.g. {"Aroma": 0.6, "Richness": 0.4}). Derived from ingredient_profiles.
    fermented_count
        : Number of fermented ingredients (from ingredient_profiles.is_fermented).
    glutamate_total
        : Sum of glutamate_mg across all profiled ingredients. High values signal umami.
    ph_min
        : Minimum ph_estimate across profiled ingredients. Low values signal acidity.
    available_sub_constraints
        : Substitution constraint labels achievable for this recipe
          (e.g. ["gluten_free", "low_carb"]). From substitution_pairs cross-ref.
          These become can_be:* tags.
    calories, protein_g, fat_g, carbs_g, servings
        : Nutrition data for macro-based dietary tags.

    Returns
    -------
    Sorted list of unique normalized tag strings.
    """
    tags: set[str] = set()

    # 1. Map corpus tags to normalized vocabulary
    for kw in corpus_keywords:
        for t in _CORPUS_TAG_MAP.get(kw.lower(), []):
            tags.add(t)
    if corpus_category:
        for t in _CORPUS_TAG_MAP.get(corpus_category.lower(), []):
            tags.add(t)

    # 2. Text-signal matching
    text = _build_text(title, ingredient_names)
    tags.update(_match_signals(text, _CUISINE_SIGNALS))
    tags.update(_match_signals(text, _DIETARY_SIGNALS))
    tags.update(_match_signals(text, _FLAVOR_SIGNALS))

    # 3. Time signals from corpus keywords + text
    corpus_text = " ".join(kw.lower() for kw in corpus_keywords)
    tags.update(_match_signals(corpus_text, _TIME_SIGNALS))
    tags.update(_match_signals(text, _TIME_SIGNALS))

    # 4. Enriched profile signals
    if element_coverage:
        for element, coverage in element_coverage.items():
            if coverage > 0.2:  # >20% of ingredients carry this element
                flavor_tag = _ELEMENT_TO_FLAVOR.get(element, "")
                if flavor_tag:
                    tags.add(flavor_tag)

    if glutamate_total > 50:
        tags.add("flavor:Umami")

    if fermented_count > 0:
        tags.add("flavor:Tangy")

    if ph_min is not None and ph_min < 4.5:
        tags.add("flavor:Tangy")

    # 5. Achievable-via-substitution tags
    if available_sub_constraints:
        label_to_tag = {
            "gluten_free":   "can_be:Gluten-Free",
            "low_calorie":   "can_be:Low-Calorie",
            "low_carb":      "can_be:Low-Carb",
            "vegan":         "can_be:Vegan",
            "dairy_free":    "can_be:Dairy-Free",
            "low_sodium":    "can_be:Low-Sodium",
        }
        for label in available_sub_constraints:
            tag = label_to_tag.get(label)
            if tag:
                tags.add(tag)

    # 6. Macro-based dietary tags
    if servings and servings > 0 and any(
        v is not None for v in (protein_g, fat_g, carbs_g, calories)
    ):
        def _per(v: float | None) -> float | None:
            return v / servings if v is not None else None

        prot_s = _per(protein_g)
        fat_s = _per(fat_g)
        carb_s = _per(carbs_g)
        cal_s = _per(calories)

        if prot_s is not None and prot_s >= 20:
            tags.add("dietary:High-Protein")
        if fat_s is not None and fat_s <= 5:
            tags.add("dietary:Low-Fat")
        if carb_s is not None and carb_s <= 10:
            tags.add("dietary:Low-Carb")
        if cal_s is not None and cal_s <= 250:
            tags.add("dietary:Light")
    elif protein_g is not None and protein_g >= 20:
        tags.add("dietary:High-Protein")

    # 7. Vegan implies vegetarian
    if "dietary:Vegan" in tags:
        tags.add("dietary:Vegetarian")

    return sorted(tags)
