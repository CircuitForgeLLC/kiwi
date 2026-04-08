"""
Assembly-dish template matcher for Level 1/2.

Assembly dishes (burritos, stir fry, fried rice, omelettes, sandwiches, etc.)
are defined by structural roles -- container + filler + sauce -- not by a fixed
ingredient list.  The corpus can never fully cover them.

This module fires when the pantry covers all *required* roles of a template.
Results are injected at the top of the Level 1/2 suggestion list with negative
ids (client displays them identically to corpus recipes).

Templates define:
  - required: list of role sets -- ALL must have at least one pantry match
  - optional: role sets whose matched items are shown as extras
  - directions: short cooking instructions
  - notes: serving suggestions / variations
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.models.schemas.recipe import RecipeSuggestion


# IDs in range -100..-1 are reserved for assembly-generated suggestions
_ASSEMBLY_ID_START = -1


@dataclass
class AssemblyRole:
    """One role in a template (e.g. 'protein').

    display:  human-readable role label
    keywords: substrings matched against pantry item (lowercased)
    """
    display: str
    keywords: list[str]


@dataclass
class AssemblyTemplate:
    """A template assembly dish."""
    id: int
    title: str
    required: list[AssemblyRole]
    optional: list[AssemblyRole]
    directions: list[str]
    notes: str = ""


def _matches_role(role: AssemblyRole, pantry_set: set[str]) -> list[str]:
    """Return pantry items that satisfy this role.

    Single-word keywords use whole-word matching (word must appear as a
    discrete token) so short words like 'pea', 'ham', 'egg' don't false-match
    inside longer words like 'peanut', 'hamburger', 'eggnog'.
    Multi-word keywords (e.g. 'burger patt') use substring matching.
    """
    hits: list[str] = []
    for item in pantry_set:
        item_lower = item.lower()
        item_words = set(item_lower.split())
        for kw in role.keywords:
            if " " in kw:
                # Multi-word: substring match
                if kw in item_lower:
                    hits.append(item)
                    break
            else:
                # Single-word: whole-word match only
                if kw in item_words:
                    hits.append(item)
                    break
    return hits


def _pick_one(items: list[str], seed: int) -> str:
    """Deterministically pick one item from a list using a seed."""
    return sorted(items)[seed % len(items)]


def _pantry_hash(pantry_set: set[str]) -> int:
    """Stable integer derived from pantry contents — used for deterministic picks."""
    key = ",".join(sorted(pantry_set))
    return int(hashlib.md5(key.encode()).hexdigest(), 16)  # noqa: S324 — non-crypto use


def _keyword_label(item: str, role: AssemblyRole) -> str:
    """Return a short, clean label derived from the keyword that matched.

    Uses the longest matching keyword (most specific) as the base label,
    then title-cases it.  This avoids pasting full raw pantry names like
    'Organic Extra Firm Tofu' into titles — just 'Tofu' instead.
    """
    lower = item.lower()
    best_kw = ""
    for kw in role.keywords:
        if kw in lower and len(kw) > len(best_kw):
            best_kw = kw
    label = (best_kw or item).strip().title()
    # Drop trailing 's' from keywords like "beans" → "Bean" when it reads better
    return label


def _personalized_title(tmpl: AssemblyTemplate, pantry_set: set[str], seed: int) -> str:
    """Build a specific title using actual pantry items, e.g. 'Chicken & Broccoli Burrito'.

    Uses the matched keyword as the label (not the full pantry item name) so
    'Organic Extra Firm Tofu Block' → 'Tofu' in the title.
    Picks at most two roles; prefers protein then vegetable.
    """
    priority_displays = ["protein", "vegetables", "sauce base", "cheese"]

    picked: list[str] = []
    for display in priority_displays:
        for role in tmpl.optional:
            if role.display != display:
                continue
            hits = _matches_role(role, pantry_set)
            if hits:
                item = _pick_one(hits, seed)
                label = _keyword_label(item, role)
                if label not in picked:
                    picked.append(label)
        if len(picked) >= 2:
            break

    if not picked:
        return tmpl.title
    return f"{' & '.join(picked)} {tmpl.title}"


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------

ASSEMBLY_TEMPLATES: list[AssemblyTemplate] = [
    AssemblyTemplate(
        id=-1,
        title="Burrito / Taco",
        required=[
            AssemblyRole("tortilla or wrap", [
                "tortilla", "wrap", "taco shell", "flatbread", "pita",
            ]),
        ],
        optional=[
            AssemblyRole("protein", [
                "chicken", "beef", "steak", "pork", "sausage", "hamburger",
                "burger patt", "shrimp", "egg", "tofu", "beans", "bean",
            ]),
            AssemblyRole("rice or starch", ["rice", "quinoa", "potato"]),
            AssemblyRole("cheese", [
                "cheese", "cheddar", "mozzarella", "monterey", "queso",
            ]),
            AssemblyRole("salsa or sauce", [
                "salsa", "hot sauce", "taco sauce", "enchilada", "guacamole",
            ]),
            AssemblyRole("sour cream or yogurt", ["sour cream", "greek yogurt", "crema"]),
            AssemblyRole("vegetables", [
                "pepper", "onion", "tomato", "lettuce", "corn", "avocado",
                "spinach", "broccoli", "zucchini",
            ]),
        ],
        directions=[
            "Warm the tortilla in a dry skillet or microwave for 20 seconds.",
            "Heat any proteins or vegetables in a pan until cooked through.",
            "Layer ingredients down the center: rice first, then protein, then vegetables.",
            "Add cheese, salsa, and sour cream last so they stay cool.",
            "Fold in the sides and roll tightly. Optionally toast seam-side down 1-2 minutes.",
        ],
        notes="Works as a burrito (rolled), taco (folded), or quesadilla (cheese only, pressed flat).",
    ),
    AssemblyTemplate(
        id=-2,
        title="Fried Rice",
        required=[
            AssemblyRole("cooked rice", [
                "rice", "leftover rice", "instant rice", "microwavable rice",
            ]),
        ],
        optional=[
            AssemblyRole("protein", [
                "chicken", "beef", "pork", "shrimp", "egg", "tofu",
                "sausage", "ham", "spam",
            ]),
            AssemblyRole("soy sauce or seasoning", [
                "soy sauce", "tamari", "teriyaki", "oyster sauce", "fish sauce",
            ]),
            AssemblyRole("oil", ["oil", "butter", "sesame"]),
            AssemblyRole("egg", ["egg"]),
            AssemblyRole("vegetables", [
                "carrot", "peas", "corn", "onion", "scallion", "green onion",
                "broccoli", "bok choy", "bean sprout", "zucchini", "spinach",
            ]),
            AssemblyRole("garlic or ginger", ["garlic", "ginger"]),
        ],
        directions=[
            "Use day-old cold rice if available -- it fries better than fresh.",
            "Heat oil in a large skillet or wok over high heat.",
            "Add garlic/ginger and any raw vegetables; stir fry 2-3 minutes.",
            "Push to the side, scramble eggs in the same pan if using.",
            "Add protein (pre-cooked or raw) and cook through.",
            "Add rice, breaking up clumps. Stir fry until heated and lightly toasted.",
            "Season with soy sauce and any other sauces. Toss to combine.",
        ],
        notes="Add a fried egg on top. A drizzle of sesame oil at the end adds a lot.",
    ),
    AssemblyTemplate(
        id=-3,
        title="Omelette / Scramble",
        required=[
            AssemblyRole("eggs", ["egg"]),
        ],
        optional=[
            AssemblyRole("cheese", [
                "cheese", "cheddar", "mozzarella", "feta", "parmesan",
            ]),
            AssemblyRole("vegetables", [
                "pepper", "onion", "tomato", "spinach", "mushroom",
                "broccoli", "zucchini", "scallion", "avocado",
            ]),
            AssemblyRole("protein", [
                "ham", "bacon", "sausage", "chicken", "turkey",
                "smoked salmon",
            ]),
            AssemblyRole("herbs or seasoning", [
                "herb", "basil", "chive", "parsley", "salt", "pepper",
                "hot sauce", "salsa",
            ]),
        ],
        directions=[
            "Beat eggs with a splash of water or milk and a pinch of salt.",
            "Saute any vegetables and proteins in butter or oil over medium heat until softened.",
            "Pour eggs over fillings (scramble) or pour into a clean buttered pan (omelette).",
            "For omelette: cook until nearly set, add fillings to one side, fold over.",
            "For scramble: stir gently over medium-low heat until just set.",
            "Season and serve immediately.",
        ],
        notes="Works for breakfast, lunch, or a quick dinner. Any leftover vegetables work well.",
    ),
    AssemblyTemplate(
        id=-4,
        title="Stir Fry",
        required=[
            AssemblyRole("vegetables", [
                "pepper", "broccoli", "carrot", "snap pea", "bok choy",
                "zucchini", "mushroom", "corn", "onion", "bean sprout",
                "cabbage", "spinach", "asparagus",
            ]),
            # Starch base required — prevents this from firing on any pantry with vegetables
            AssemblyRole("starch base", ["rice", "noodle", "pasta", "ramen", "cauliflower rice"]),
        ],
        optional=[
            AssemblyRole("protein", [
                "chicken", "beef", "pork", "shrimp", "tofu", "egg",
            ]),
            AssemblyRole("sauce", [
                "soy sauce", "teriyaki", "oyster sauce", "hoisin",
                "stir fry sauce", "sesame",
            ]),
            AssemblyRole("garlic or ginger", ["garlic", "ginger"]),
            AssemblyRole("oil", ["oil", "sesame"]),
        ],
        directions=[
            "Cut all proteins and vegetables into similar-sized pieces for even cooking.",
            "Heat oil in a wok or large skillet over the highest heat your stove allows.",
            "Cook protein first until nearly done; remove and set aside.",
            "Add dense vegetables (carrots, broccoli) first; quick-cooking veg last.",
            "Return protein, add sauce, and toss everything together for 1-2 minutes.",
            "Serve over rice or noodles.",
        ],
        notes="High heat is the key. Do not crowd the pan -- cook in batches if needed.",
    ),
    AssemblyTemplate(
        id=-5,
        title="Pasta with Whatever You Have",
        required=[
            AssemblyRole("pasta", [
                "pasta", "spaghetti", "penne", "fettuccine", "rigatoni",
                "linguine", "rotini", "farfalle", "macaroni", "noodle",
            ]),
        ],
        optional=[
            AssemblyRole("sauce base", [
                "tomato", "marinara", "pasta sauce", "cream", "butter",
                "olive oil", "pesto",
            ]),
            AssemblyRole("protein", [
                "chicken", "beef", "pork", "shrimp", "sausage", "bacon",
                "ham", "tuna", "canned fish",
            ]),
            AssemblyRole("cheese", [
                "parmesan", "romano", "mozzarella", "ricotta", "feta",
            ]),
            AssemblyRole("vegetables", [
                "tomato", "spinach", "mushroom", "pepper", "zucchini",
                "broccoli", "artichoke", "olive", "onion",
            ]),
            AssemblyRole("garlic", ["garlic"]),
        ],
        directions=[
            "Cook pasta in well-salted boiling water until al dente. Reserve 1 cup pasta water.",
            "While pasta cooks, saute garlic in olive oil over medium heat.",
            "Add proteins and cook through; add vegetables until tender.",
            "Add sauce base and simmer 5 minutes. Add pasta water to loosen if needed.",
            "Toss cooked pasta with sauce. Finish with cheese if using.",
        ],
        notes="Pasta water is the secret -- the starch thickens and binds any sauce.",
    ),
    AssemblyTemplate(
        id=-6,
        title="Sandwich / Wrap",
        required=[
            AssemblyRole("bread or wrap", [
                "bread", "roll", "bun", "wrap", "tortilla", "pita",
                "bagel", "english muffin", "croissant", "flatbread",
            ]),
        ],
        optional=[
            AssemblyRole("protein", [
                "chicken", "turkey", "ham", "roast beef", "tuna", "egg",
                "bacon", "salami", "pepperoni", "tofu", "tempeh",
            ]),
            AssemblyRole("cheese", [
                "cheese", "cheddar", "swiss", "provolone", "mozzarella",
            ]),
            AssemblyRole("condiment", [
                "mayo", "mustard", "ketchup", "hot sauce", "ranch",
                "hummus", "pesto", "aioli",
            ]),
            AssemblyRole("vegetables", [
                "lettuce", "tomato", "onion", "cucumber", "avocado",
                "pepper", "sprout", "arugula",
            ]),
        ],
        directions=[
            "Toast bread if desired.",
            "Spread condiments on both inner surfaces.",
            "Layer protein first, then cheese, then vegetables.",
            "Press together and cut diagonally.",
        ],
        notes="Leftovers, deli meat, canned fish -- nearly anything works between bread.",
    ),
    AssemblyTemplate(
        id=-7,
        title="Grain Bowl",
        required=[
            AssemblyRole("grain base", [
                "rice", "quinoa", "farro", "barley", "couscous",
                "bulgur", "freekeh", "polenta",
            ]),
        ],
        optional=[
            AssemblyRole("protein", [
                "chicken", "beef", "pork", "tofu", "egg", "shrimp",
                "beans", "bean", "lentil", "chickpea",
            ]),
            AssemblyRole("vegetables", [
                "roasted", "broccoli", "carrot", "kale", "spinach",
                "cucumber", "tomato", "corn", "edamame", "avocado",
                "beet", "sweet potato",
            ]),
            AssemblyRole("dressing or sauce", [
                "dressing", "tahini", "vinaigrette", "sauce",
                "olive oil", "lemon", "soy sauce",
            ]),
            AssemblyRole("toppings", [
                "nut", "seed", "feta", "parmesan", "herb",
            ]),
        ],
        directions=[
            "Cook grain base according to package directions; season with salt.",
            "Roast or saute vegetables with oil, salt, and pepper until tender.",
            "Cook or slice protein.",
            "Arrange grain in a bowl, top with protein and vegetables.",
            "Drizzle with dressing and add toppings.",
        ],
        notes="Great for meal prep -- cook grains and proteins in bulk, assemble bowls all week.",
    ),
    AssemblyTemplate(
        id=-8,
        title="Soup / Stew",
        required=[
            # Narrow to dedicated soup bases — tomato sauce and coconut milk are
            # pantry staples used in too many non-soup dishes to serve as anchors.
            AssemblyRole("broth or stock", [
                "broth", "stock", "bouillon", "cream of",
            ]),
        ],
        optional=[
            AssemblyRole("protein", [
                "chicken", "beef", "pork", "sausage", "shrimp",
                "beans", "bean", "lentil", "tofu",
            ]),
            AssemblyRole("vegetables", [
                "carrot", "celery", "onion", "potato", "tomato",
                "spinach", "kale", "corn", "pea", "zucchini",
            ]),
            AssemblyRole("starch thickener", [
                "potato", "pasta", "noodle", "rice", "barley",
                "flour", "cornstarch",
            ]),
            AssemblyRole("seasoning", [
                "garlic", "herb", "bay leaf", "thyme", "rosemary",
                "cumin", "paprika", "chili",
            ]),
        ],
        directions=[
            "Saute onion, celery, and garlic in oil until softened, about 5 minutes.",
            "Add any raw proteins and cook until browned.",
            "Add broth or liquid base and bring to a simmer.",
            "Add dense vegetables (carrots, potatoes) first; quick-cooking veg in the last 10 minutes.",
            "Add starches and cook until tender.",
            "Season to taste and simmer at least 20 minutes for flavors to develop.",
        ],
        notes="Soups and stews improve overnight in the fridge. Almost any combination works.",
    ),
    AssemblyTemplate(
        id=-9,
        title="Casserole / Bake",
        required=[
            AssemblyRole("starch or base", [
                "pasta", "rice", "potato", "noodle", "bread",
                "tortilla", "polenta", "grits", "macaroni",
            ]),
            AssemblyRole("binder or sauce", [
                "cream of", "cheese", "cream cheese", "sour cream",
                "soup mix", "gravy", "tomato sauce", "marinara",
                "broth", "stock", "milk", "cream",
            ]),
        ],
        optional=[
            AssemblyRole("protein", [
                "chicken", "beef", "pork", "tuna", "ham", "sausage",
                "ground", "shrimp", "beans", "bean", "lentil",
            ]),
            AssemblyRole("vegetables", [
                "broccoli", "corn", "pea", "onion", "mushroom",
                "spinach", "zucchini", "tomato", "pepper", "carrot",
            ]),
            AssemblyRole("cheese topping", [
                "cheddar", "mozzarella", "parmesan", "swiss",
                "cheese", "breadcrumb",
            ]),
            AssemblyRole("seasoning", [
                "garlic", "herb", "thyme", "rosemary", "paprika",
                "onion powder", "salt", "pepper",
            ]),
        ],
        directions=[
            "Preheat oven to 375 F (190 C). Grease a 9x13 baking dish.",
            "Cook starch base (pasta, rice, potato) until just underdone -- it finishes in the oven.",
            "Mix cooked starch with sauce/binder, protein, and vegetables in the dish.",
            "Season generously -- casseroles need salt.",
            "Top with cheese or breadcrumbs if using.",
            "Bake covered 25 minutes, then uncovered 15 minutes until golden and bubbly.",
        ],
        notes="Classic pantry dump dinner. Cream of anything soup is the universal binder.",
    ),
    AssemblyTemplate(
        id=-10,
        title="Pancakes / Waffles / Quick Bread",
        required=[
            AssemblyRole("flour or baking mix", [
                "flour", "bisquick", "pancake mix", "waffle mix",
                "baking mix", "cornmeal", "oats",
            ]),
            AssemblyRole("leavening or egg", [
                "egg", "baking powder", "baking soda", "yeast",
            ]),
        ],
        optional=[
            AssemblyRole("liquid", [
                "milk", "buttermilk", "water", "juice",
                "almond milk", "oat milk", "sour cream",
            ]),
            AssemblyRole("fat", [
                "butter", "oil", "margarine",
            ]),
            AssemblyRole("sweetener", [
                "sugar", "honey", "maple syrup", "brown sugar",
            ]),
            AssemblyRole("mix-ins", [
                "blueberr", "banana", "apple", "chocolate chip",
                "nut", "berry", "cinnamon", "vanilla",
            ]),
        ],
        directions=[
            "Whisk dry ingredients (flour, leavening, sugar, salt) together in a bowl.",
            "Whisk wet ingredients (egg, milk, melted butter) in a separate bowl.",
            "Fold wet into dry until just combined -- lumps are fine, do not overmix.",
            "For pancakes: cook on a buttered griddle over medium heat, flip when bubbles form.",
            "For waffles: pour into preheated waffle iron according to manufacturer instructions.",
            "For muffins or quick bread: pour into greased pan, bake at 375 F until a toothpick comes out clean.",
        ],
        notes="Overmixing develops gluten and makes pancakes tough. Stop when just combined.",
    ),
    AssemblyTemplate(
        id=-11,
        title="Porridge / Oatmeal",
        required=[
            AssemblyRole("oats or grain porridge", [
                "oat", "porridge", "grits", "semolina", "cream of wheat",
                "polenta", "congee", "rice porridge",
            ]),
        ],
        optional=[
            AssemblyRole("liquid", ["milk", "water", "almond milk", "oat milk", "coconut milk"]),
            AssemblyRole("sweetener", ["sugar", "honey", "maple syrup", "brown sugar", "agave"]),
            AssemblyRole("fruit", ["banana", "berry", "apple", "raisin", "date", "mango"]),
            AssemblyRole("toppings", ["nut", "seed", "granola", "coconut", "chocolate"]),
            AssemblyRole("spice", ["cinnamon", "nutmeg", "vanilla", "cardamom"]),
        ],
        directions=[
            "Combine oats with liquid in a pot — typically 1 part oats to 2 parts liquid.",
            "Bring to a gentle simmer over medium heat, stirring occasionally.",
            "Cook 5 minutes (rolled oats) or 2 minutes (quick oats) until thickened to your liking.",
            "Stir in sweetener and spices.",
            "Top with fruit, nuts, or seeds and serve immediately.",
        ],
        notes="Overnight oats: skip cooking — soak oats in cold milk overnight in the fridge.",
    ),
    AssemblyTemplate(
        id=-12,
        title="Pie / Pot Pie",
        required=[
            AssemblyRole("pastry or crust", [
                "pastry", "puff pastry", "pie crust", "shortcrust",
                "pie shell", "phyllo", "filo", "biscuit",
            ]),
        ],
        optional=[
            AssemblyRole("protein filling", [
                "chicken", "beef", "pork", "lamb", "turkey", "tofu",
                "mushroom", "beans", "bean", "lentil", "tuna", "salmon",
            ]),
            AssemblyRole("vegetables", [
                "carrot", "pea", "corn", "potato", "onion", "leek",
                "broccoli", "spinach", "mushroom", "parsnip", "swede",
            ]),
            AssemblyRole("sauce or binder", [
                "gravy", "cream of", "stock", "broth", "cream",
                "white sauce", "bechamel", "cheese sauce",
            ]),
            AssemblyRole("seasoning", [
                "thyme", "rosemary", "sage", "garlic", "herb",
                "mustard", "worcestershire",
            ]),
            AssemblyRole("sweet filling", [
                "apple", "berry", "cherry", "pear", "peach",
                "rhubarb", "plum", "custard",
            ]),
        ],
        directions=[
            "For pot pie: make a sauce by combining stock or cream-of-something with cooked vegetables and protein.",
            "Season generously — fillings need more salt than you think.",
            "Pour filling into a baking dish and top with pastry, pressing edges to seal.",
            "Cut a few slits in the top to release steam. Brush with egg wash or milk if available.",
            "Bake at 400 F (200 C) for 25-35 minutes until pastry is golden brown.",
            "For sweet pie: fill unbaked crust with fruit filling, top with second crust or crumble, bake similarly.",
        ],
        notes="Puff pastry from the freezer is the shortcut to impressive pot pies. Thaw in the fridge overnight.",
    ),
    AssemblyTemplate(
        id=-13,
        title="Pudding / Custard",
        required=[
            AssemblyRole("dairy or dairy-free milk", [
                "milk", "cream", "oat milk", "almond milk",
                "soy milk", "coconut milk",
            ]),
            AssemblyRole("thickener or set", [
                "egg", "cornstarch", "custard powder", "gelatin",
                "agar", "tapioca", "arrowroot",
            ]),
            # Require a clear dessert-intent signal — milk + eggs alone is too generic
            # (also covers white sauce, quiche, etc.)
            AssemblyRole("sweetener or flavouring", [
                "sugar", "honey", "maple syrup", "condensed milk",
                "vanilla", "chocolate", "cocoa", "caramel", "custard powder",
            ]),
        ],
        optional=[
            AssemblyRole("sweetener", ["sugar", "honey", "maple syrup", "condensed milk"]),
            AssemblyRole("flavouring", [
                "vanilla", "chocolate", "cocoa", "caramel",
                "lemon", "orange", "cinnamon", "nutmeg",
            ]),
            AssemblyRole("starchy base", [
                "rice", "bread", "sponge", "cake", "biscuit",
            ]),
            AssemblyRole("fruit", ["raisin", "sultana", "berry", "banana", "apple"]),
        ],
        directions=[
            "For stovetop custard: whisk eggs and sugar together, heat milk until steaming.",
            "Slowly pour hot milk into egg mixture while whisking constantly (tempering).",
            "Return to low heat and stir until mixture coats the back of a spoon.",
            "For cornstarch pudding: whisk cornstarch into cold milk first, then heat while stirring.",
            "Add flavourings (vanilla, cocoa) once off heat.",
            "Pour into dishes and refrigerate at least 2 hours to set.",
        ],
        notes="UK-style pudding is broad — bread pudding, rice pudding, spotted dick, treacle sponge all count.",
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_assembly_templates(
    pantry_items: list[str],
    pantry_set: set[str],
    excluded_ids: list[int],
    expiring_set: set[str] | None = None,
) -> list[RecipeSuggestion]:
    """Return assembly-dish suggestions whose required roles are all satisfied.

    Titles are personalized with specific pantry items (deterministically chosen
    from the pantry contents so the same pantry always produces the same title).
    Skips templates whose id is in excluded_ids (dismiss/load-more support).

    expiring_set: expanded pantry set of items close to expiry.  Templates that
    use an expiring item in a required role get +2 added to match_count so they
    rank higher when the caller sorts the combined result list.
    """
    excluded = set(excluded_ids)
    expiring = expiring_set or set()
    seed = _pantry_hash(pantry_set)
    results: list[RecipeSuggestion] = []

    for tmpl in ASSEMBLY_TEMPLATES:
        if tmpl.id in excluded:
            continue

        # All required roles must be satisfied; collect matched items for required roles
        required_matches: list[str] = []
        skip = False
        for role in tmpl.required:
            hits = _matches_role(role, pantry_set)
            if not hits:
                skip = True
                break
            required_matches.append(_pick_one(hits, seed + tmpl.id))
        if skip:
            continue

        # Collect matched items for optional roles (one representative per matched role)
        optional_matches: list[str] = []
        for role in tmpl.optional:
            hits = _matches_role(role, pantry_set)
            if hits:
                optional_matches.append(_pick_one(hits, seed + tmpl.id))

        matched = required_matches + optional_matches

        # Expiry boost: +2 if any required ingredient is in the expiring set,
        # so time-sensitive templates surface first in the merged ranking.
        expiry_bonus = 2 if expiring and any(
            item.lower() in expiring for item in required_matches
        ) else 0

        results.append(RecipeSuggestion(
            id=tmpl.id,
            title=_personalized_title(tmpl, pantry_set, seed + tmpl.id),
            match_count=len(matched) + expiry_bonus,
            element_coverage={},
            swap_candidates=[],
            matched_ingredients=matched,
            missing_ingredients=[],
            directions=tmpl.directions,
            notes=tmpl.notes,
            level=1,
            is_wildcard=False,
            nutrition=None,
        ))

    # Sort by optional coverage descending — best-matched templates first
    results.sort(key=lambda s: s.match_count, reverse=True)
    return results
