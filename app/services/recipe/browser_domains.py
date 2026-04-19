"""
Recipe browser domain schemas.

Each domain provides a two-level category hierarchy for browsing the recipe corpus.
Keyword matching is case-insensitive against the recipes.category column and the
recipes.keywords JSON array. A recipe may appear in multiple categories (correct).

Category values are either:
  - list[str]  — flat keyword list (no subcategories)
  - dict       — {"keywords": list[str], "subcategories": {name: list[str]}}
                  keywords covers the whole category (used for "All X" browse);
                  subcategories each have their own narrower keyword list.

These are starter mappings based on the food.com dataset structure. Run:

    SELECT category, count(*) FROM recipes
    GROUP BY category ORDER BY count(*) DESC LIMIT 50;

against the corpus to verify coverage and refine keyword lists before the first
production deploy.
"""
from __future__ import annotations

DOMAINS: dict[str, dict] = {
    "cuisine": {
        "label": "Cuisine",
        "categories": {
            "Italian": {
                "keywords": ["italian", "pasta", "pizza", "risotto", "lasagna", "carbonara"],
                "subcategories": {
                    "Sicilian":   ["sicilian", "sicily", "arancini", "caponata",
                                   "involtini", "cannoli"],
                    "Neapolitan": ["neapolitan", "naples", "pizza napoletana",
                                   "sfogliatelle", "ragù"],
                    "Tuscan":     ["tuscan", "tuscany", "ribollita", "bistecca",
                                   "pappardelle", "crostini"],
                    "Roman":      ["roman", "rome", "cacio e pepe", "carbonara",
                                   "amatriciana", "gricia", "supplì"],
                    "Venetian":   ["venetian", "venice", "risotto", "bigoli",
                                   "baccalà", "sarde in saor"],
                    "Ligurian":   ["ligurian", "liguria", "pesto", "focaccia",
                                   "trofie", "farinata"],
                },
            },
            "Mexican": {
                "keywords": ["mexican", "tex-mex", "taco", "enchilada", "burrito",
                             "salsa", "guacamole"],
                "subcategories": {
                    "Oaxacan":   ["oaxacan", "oaxaca", "mole negro", "tlayuda",
                                  "chapulines", "mezcal"],
                    "Yucatecan": ["yucatecan", "yucatan", "cochinita pibil", "poc chuc",
                                  "sopa de lima", "panuchos"],
                    "Veracruz":  ["veracruz", "huachinango", "picadas", "enfrijoladas"],
                    "Street Food": ["taco", "elote", "tlacoyos", "torta",
                                    "tamale", "quesadilla"],
                    "Mole":      ["mole", "mole negro", "mole rojo", "mole verde",
                                  "mole poblano"],
                },
            },
            "Asian": {
                "keywords": ["asian", "chinese", "japanese", "thai", "korean", "vietnamese",
                             "stir fry", "stir-fry", "ramen", "sushi"],
                "subcategories": {
                    "Korean":     ["korean", "kimchi", "bibimbap", "bulgogi", "japchae",
                                   "doenjang", "gochujang"],
                    "Japanese":   ["japanese", "sushi", "ramen", "tempura", "miso",
                                   "teriyaki", "udon", "soba", "bento", "yakitori"],
                    "Chinese":    ["chinese", "dim sum", "fried rice", "dumplings", "wonton",
                                   "spring roll", "szechuan", "sichuan", "cantonese",
                                   "chow mein", "mapo", "lo mein"],
                    "Thai":       ["thai", "pad thai", "green curry", "red curry",
                                   "coconut milk", "lemongrass", "satay", "tom yum"],
                    "Vietnamese": ["vietnamese", "pho", "banh mi", "spring rolls",
                                   "vermicelli", "nuoc cham", "bun bo"],
                    "Filipino":   ["filipino", "adobo", "sinigang", "pancit", "lumpia",
                                   "kare-kare", "lechon"],
                    "Indonesian": ["indonesian", "rendang", "nasi goreng", "gado-gado",
                                   "tempeh", "sambal"],
                },
            },
            "Indian": {
                "keywords": ["indian", "curry", "lentil", "dal", "tikka", "masala",
                             "biryani", "naan", "chutney"],
                "subcategories": {
                    "North Indian": ["north indian", "punjabi", "mughal", "tikka masala",
                                     "naan", "tandoori", "butter chicken", "palak"],
                    "South Indian": ["south indian", "tamil", "kerala", "dosa", "idli",
                                     "sambar", "rasam", "coconut chutney"],
                    "Bengali":      ["bengali", "mustard fish", "hilsa", "shorshe"],
                    "Gujarati":     ["gujarati", "dhokla", "thepla", "undhiyu"],
                },
            },
            "Mediterranean": {
                "keywords": ["mediterranean", "greek", "middle eastern", "turkish",
                             "moroccan", "lebanese"],
                "subcategories": {
                    "Greek":          ["greek", "feta", "tzatziki", "moussaka", "spanakopita",
                                       "souvlaki", "dolmades"],
                    "Turkish":        ["turkish", "kebab", "borek", "meze", "baklava",
                                       "lahmacun"],
                    "Moroccan":       ["moroccan", "tagine", "couscous", "harissa",
                                       "chermoula", "preserved lemon"],
                    "Lebanese":       ["lebanese", "middle eastern", "hummus", "falafel",
                                       "tabbouleh", "kibbeh", "fattoush"],
                    "Israeli":        ["israeli", "shakshuka", "sabich", "za'atar",
                                       "tahini"],
                },
            },
            "American": {
                "keywords": ["american", "southern", "bbq", "barbecue", "comfort food",
                             "cajun", "creole"],
                "subcategories": {
                    "Southern":     ["southern", "soul food", "fried chicken",
                                     "collard greens", "cornbread", "biscuits and gravy"],
                    "Cajun/Creole": ["cajun", "creole", "new orleans", "gumbo",
                                     "jambalaya", "etouffee", "dirty rice"],
                    "BBQ":          ["bbq", "barbecue", "smoked", "brisket", "pulled pork",
                                     "ribs", "pit"],
                    "Tex-Mex":      ["tex-mex", "southwestern", "chili", "fajita",
                                     "queso"],
                    "New England":  ["new england", "chowder", "lobster", "clam",
                                     "maple", "yankee"],
                },
            },
            "European": {
                "keywords": ["french", "german", "spanish", "british", "irish",
                             "scandinavian"],
                "subcategories": {
                    "French":        ["french", "provencal", "beurre", "crepe",
                                      "ratatouille", "cassoulet", "bouillabaisse"],
                    "Spanish":       ["spanish", "paella", "tapas", "gazpacho",
                                      "tortilla espanola", "chorizo"],
                    "German":        ["german", "bratwurst", "sauerkraut", "schnitzel",
                                      "pretzel", "strudel"],
                    "British/Irish": ["british", "irish", "english", "pub food",
                                      "shepherd's pie", "bangers", "scones"],
                    "Scandinavian":  ["scandinavian", "nordic", "swedish", "norwegian",
                                      "danish", "gravlax", "meatballs"],
                },
            },
            "Latin American": {
                "keywords": ["latin american", "peruvian", "argentinian", "colombian",
                             "cuban", "caribbean", "brazilian"],
                "subcategories": {
                    "Peruvian":  ["peruvian", "ceviche", "lomo saltado", "anticucho",
                                  "aji amarillo"],
                    "Brazilian": ["brazilian", "churrasco", "feijoada", "pao de queijo",
                                  "brigadeiro"],
                    "Colombian": ["colombian", "bandeja paisa", "arepas", "empanadas",
                                  "sancocho"],
                    "Cuban":     ["cuban", "ropa vieja", "moros y cristianos",
                                  "picadillo", "mojito"],
                    "Caribbean": ["caribbean", "jamaican", "jerk", "trinidadian",
                                  "plantain", "roti"],
                },
            },
        },
    },
    "meal_type": {
        "label": "Meal Type",
        "categories": {
            "Breakfast": {
                "keywords": ["breakfast", "brunch", "eggs", "pancakes", "waffles",
                             "oatmeal", "muffin"],
                "subcategories": {
                    "Eggs":              ["egg", "omelette", "frittata", "quiche",
                                          "scrambled", "benedict", "shakshuka"],
                    "Pancakes & Waffles": ["pancake", "waffle", "crepe", "french toast"],
                    "Baked Goods":       ["muffin", "scone", "biscuit", "quick bread",
                                          "coffee cake", "danish"],
                    "Oats & Grains":     ["oatmeal", "granola", "porridge", "muesli",
                                          "overnight oats"],
                },
            },
            "Lunch": {
                "keywords": ["lunch", "sandwich", "wrap", "salad", "soup", "light meal"],
                "subcategories": {
                    "Sandwiches": ["sandwich", "sub", "hoagie", "panini", "club",
                                   "grilled cheese", "blt"],
                    "Salads":     ["salad", "grain bowl", "chopped", "caesar",
                                   "niçoise", "cobb"],
                    "Soups":      ["soup", "bisque", "chowder", "gazpacho",
                                   "minestrone", "lentil soup"],
                    "Wraps":      ["wrap", "burrito bowl", "pita", "lettuce wrap",
                                   "quesadilla"],
                },
            },
            "Dinner": {
                "keywords": ["dinner", "main dish", "entree", "main course", "supper"],
                "subcategories": {
                    "Casseroles": ["casserole", "bake", "gratin", "lasagna",
                                   "sheperd's pie", "pot pie"],
                    "Stews":      ["stew", "braise", "slow cooker", "pot roast",
                                   "daube", "ragù"],
                    "Grilled":    ["grilled", "grill", "barbecue", "charred",
                                   "kebab", "skewer"],
                    "Stir-Fries": ["stir fry", "stir-fry", "wok", "sauté",
                                   "sauteed"],
                    "Roasts":     ["roast", "roasted", "oven", "baked chicken",
                                   "pot roast"],
                },
            },
            "Snack": {
                "keywords": ["snack", "appetizer", "finger food", "dip", "bite",
                             "starter"],
                "subcategories": {
                    "Dips & Spreads": ["dip", "spread", "hummus", "guacamole",
                                       "salsa", "pate"],
                    "Finger Foods":   ["finger food", "bite", "skewer", "slider",
                                       "wing", "nugget"],
                    "Chips & Crackers": ["chip", "cracker", "crisp", "popcorn",
                                          "pretzel"],
                },
            },
            "Dessert": {
                "keywords": ["dessert", "cake", "cookie", "pie", "sweet", "pudding",
                             "ice cream", "brownie"],
                "subcategories": {
                    "Cakes":         ["cake", "cupcake", "layer cake", "bundt",
                                      "cheesecake", "torte"],
                    "Cookies & Bars": ["cookie", "brownie", "blondie", "bar",
                                       "biscotti", "shortbread"],
                    "Pies & Tarts":  ["pie", "tart", "galette", "cobbler", "crisp",
                                       "crumble"],
                    "Frozen":        ["ice cream", "gelato", "sorbet", "frozen dessert",
                                      "popsicle", "granita"],
                    "Puddings":      ["pudding", "custard", "mousse", "panna cotta",
                                      "flan", "creme brulee"],
                    "Candy":         ["candy", "fudge", "truffle", "brittle",
                                      "caramel", "toffee"],
                },
            },
            "Beverage": ["drink", "smoothie", "cocktail", "beverage", "juice", "shake"],
            "Side Dish": ["side dish", "side", "accompaniment", "garnish"],
        },
    },
    "dietary": {
        "label": "Dietary",
        "categories": {
            "Vegetarian":   ["vegetarian"],
            "Vegan":        ["vegan", "plant-based", "plant based"],
            "Gluten-Free":  ["gluten-free", "gluten free", "celiac"],
            "Low-Carb":     ["low-carb", "low carb", "keto", "ketogenic"],
            "High-Protein": ["high protein", "high-protein"],
            "Low-Fat":      ["low-fat", "low fat", "light"],
            "Dairy-Free":   ["dairy-free", "dairy free", "lactose"],
        },
    },
    "main_ingredient": {
        "label": "Main Ingredient",
        "categories": {
            # keywords use exact inferred_tag strings (main:X) — indexed into recipe_browser_fts.
            "Chicken": {
                "keywords": ["main:Chicken"],
                "subcategories": {
                    "Baked":    ["baked chicken", "roast chicken", "chicken casserole",
                                 "chicken bake"],
                    "Grilled":  ["grilled chicken", "chicken kebab", "bbq chicken",
                                 "chicken skewer"],
                    "Fried":    ["fried chicken", "chicken cutlet", "chicken schnitzel",
                                 "crispy chicken"],
                    "Stewed":   ["chicken stew", "chicken soup", "coq au vin",
                                 "chicken curry", "chicken braise"],
                },
            },
            "Beef": {
                "keywords": ["main:Beef"],
                "subcategories": {
                    "Ground Beef": ["ground beef", "hamburger", "meatball", "meatloaf",
                                    "bolognese", "burger"],
                    "Steak":       ["steak", "sirloin", "ribeye", "flank steak",
                                    "filet mignon", "t-bone"],
                    "Roasts":      ["beef roast", "pot roast", "brisket", "prime rib",
                                    "chuck roast"],
                    "Stews":       ["beef stew", "beef braise", "beef bourguignon",
                                    "short ribs"],
                },
            },
            "Pork": {
                "keywords": ["main:Pork"],
                "subcategories": {
                    "Chops":        ["pork chop", "pork loin", "pork cutlet"],
                    "Pulled/Slow":  ["pulled pork", "pork shoulder", "pork butt",
                                     "carnitas", "slow cooker pork"],
                    "Sausage":      ["sausage", "bratwurst", "chorizo", "andouille",
                                     "Italian sausage"],
                    "Ribs":         ["pork ribs", "baby back ribs", "spare ribs",
                                     "pork belly"],
                },
            },
            "Fish": {
                "keywords": ["main:Fish"],
                "subcategories": {
                    "Salmon":    ["salmon", "smoked salmon", "gravlax"],
                    "Tuna":      ["tuna", "albacore", "ahi"],
                    "White Fish": ["cod", "tilapia", "halibut", "sole", "snapper",
                                   "flounder", "bass"],
                    "Shellfish": ["shrimp", "prawn", "crab", "lobster", "scallop",
                                  "mussel", "clam", "oyster"],
                },
            },
            "Pasta":      ["main:Pasta"],
            "Vegetables": {
                "keywords": ["main:Vegetables"],
                "subcategories": {
                    "Root Veg":    ["potato", "sweet potato", "carrot", "beet",
                                    "parsnip", "turnip"],
                    "Leafy":       ["spinach", "kale", "chard", "arugula",
                                    "collard greens", "lettuce"],
                    "Brassicas":   ["broccoli", "cauliflower", "brussels sprouts",
                                    "cabbage", "bok choy"],
                    "Nightshades": ["tomato", "eggplant", "bell pepper", "zucchini",
                                    "squash"],
                    "Mushrooms":   ["mushroom", "portobello", "shiitake", "oyster mushroom",
                                    "chanterelle"],
                },
            },
            "Eggs":    ["main:Eggs"],
            "Legumes": ["main:Legumes"],
            "Grains":  ["main:Grains"],
            "Cheese":  ["main:Cheese"],
        },
    },
}


def _get_category_def(domain: str, category: str) -> list[str] | dict | None:
    """Return the raw category definition, or None if not found."""
    return DOMAINS.get(domain, {}).get("categories", {}).get(category)


def get_domain_labels() -> list[dict]:
    """Return [{id, label}] for all available domains."""
    return [{"id": k, "label": v["label"]} for k, v in DOMAINS.items()]


def get_keywords_for_category(domain: str, category: str) -> list[str]:
    """Return the keyword list for the category (top-level, covers all subcategories).

    For flat categories returns the list directly.
    For nested categories returns the 'keywords' key.
    Returns [] if category or domain not found.
    """
    cat_def = _get_category_def(domain, category)
    if cat_def is None:
        return []
    if isinstance(cat_def, list):
        return cat_def
    return cat_def.get("keywords", [])


def category_has_subcategories(domain: str, category: str) -> bool:
    """Return True when a category has a subcategory level."""
    cat_def = _get_category_def(domain, category)
    if not isinstance(cat_def, dict):
        return False
    return bool(cat_def.get("subcategories"))


def get_subcategory_names(domain: str, category: str) -> list[str]:
    """Return subcategory names for a category, or [] if none exist."""
    cat_def = _get_category_def(domain, category)
    if not isinstance(cat_def, dict):
        return []
    return list(cat_def.get("subcategories", {}).keys())


def get_keywords_for_subcategory(domain: str, category: str, subcategory: str) -> list[str]:
    """Return keyword list for a specific subcategory, or [] if not found."""
    cat_def = _get_category_def(domain, category)
    if not isinstance(cat_def, dict):
        return []
    return cat_def.get("subcategories", {}).get(subcategory, [])


def get_category_names(domain: str) -> list[str]:
    """Return category names for a domain, or [] if domain unknown."""
    domain_data = DOMAINS.get(domain, {})
    return list(domain_data.get("categories", {}).keys())
