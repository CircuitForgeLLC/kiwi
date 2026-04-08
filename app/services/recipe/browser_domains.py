"""
Recipe browser domain schemas.

Each domain provides a two-level category hierarchy for browsing the recipe corpus.
Keyword matching is case-insensitive against the recipes.category column and the
recipes.keywords JSON array. A recipe may appear in multiple categories (correct).

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
            "Italian":        ["italian", "pasta", "pizza", "risotto", "lasagna", "carbonara"],
            "Mexican":        ["mexican", "tex-mex", "taco", "enchilada", "burrito", "salsa", "guacamole"],
            "Asian":          ["asian", "chinese", "japanese", "thai", "korean", "vietnamese", "stir fry", "stir-fry", "ramen", "sushi"],
            "American":       ["american", "southern", "bbq", "barbecue", "comfort food", "cajun", "creole"],
            "Mediterranean":  ["mediterranean", "greek", "middle eastern", "turkish", "moroccan", "lebanese"],
            "Indian":         ["indian", "curry", "lentil", "dal", "tikka", "masala", "biryani"],
            "European":       ["french", "german", "spanish", "british", "irish", "scandinavian"],
            "Latin American": ["latin american", "peruvian", "argentinian", "colombian", "cuban", "caribbean"],
        },
    },
    "meal_type": {
        "label": "Meal Type",
        "categories": {
            "Breakfast":   ["breakfast", "brunch", "eggs", "pancakes", "waffles", "oatmeal", "muffin"],
            "Lunch":       ["lunch", "sandwich", "wrap", "salad", "soup", "light meal"],
            "Dinner":      ["dinner", "main dish", "entree", "main course", "supper"],
            "Snack":       ["snack", "appetizer", "finger food", "dip", "bite", "starter"],
            "Dessert":     ["dessert", "cake", "cookie", "pie", "sweet", "pudding", "ice cream", "brownie"],
            "Beverage":    ["drink", "smoothie", "cocktail", "beverage", "juice", "shake"],
            "Side Dish":   ["side dish", "side", "accompaniment", "garnish"],
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
            "Chicken":    ["chicken", "poultry", "turkey"],
            "Beef":       ["beef", "ground beef", "steak", "brisket", "pot roast"],
            "Pork":       ["pork", "bacon", "ham", "sausage", "prosciutto"],
            "Fish":       ["fish", "salmon", "tuna", "tilapia", "cod", "halibut", "shrimp", "seafood"],
            "Pasta":      ["pasta", "noodle", "spaghetti", "penne", "fettuccine", "linguine"],
            "Vegetables": ["vegetable", "veggie", "cauliflower", "broccoli", "zucchini", "eggplant"],
            "Eggs":       ["egg", "frittata", "omelette", "omelet", "quiche"],
            "Legumes":    ["bean", "lentil", "chickpea", "tofu", "tempeh", "edamame"],
            "Grains":     ["rice", "quinoa", "barley", "farro", "oat", "grain"],
            "Cheese":     ["cheese", "ricotta", "mozzarella", "parmesan", "cheddar"],
        },
    },
}


def get_domain_labels() -> list[dict]:
    """Return [{id, label}] for all available domains."""
    return [{"id": k, "label": v["label"]} for k, v in DOMAINS.items()]


def get_keywords_for_category(domain: str, category: str) -> list[str]:
    """Return the keyword list for a domain/category pair, or [] if not found."""
    domain_data = DOMAINS.get(domain, {})
    categories = domain_data.get("categories", {})
    return categories.get(category, [])


def get_category_names(domain: str) -> list[str]:
    """Return category names for a domain, or [] if domain unknown."""
    domain_data = DOMAINS.get(domain, {})
    return list(domain_data.get("categories", {}).keys())
