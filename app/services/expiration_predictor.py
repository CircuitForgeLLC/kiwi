"""
Expiration Date Prediction Service.

Predicts expiration dates for food items based on category and storage location.
Fast path: deterministic lookup table (USDA FoodKeeper / FDA guidelines).
Fallback path: LLMRouter — only fires for unknown products when tier allows it
               and a LLM backend is configured.
"""

import logging
import re
from datetime import date, timedelta
from typing import Optional, List

from circuitforge_core.llm.router import LLMRouter
from app.tiers import can_use

logger = logging.getLogger(__name__)


class ExpirationPredictor:
    """Predict expiration dates based on product category and storage location."""

    # Default shelf life in days by category and location
    # Sources: USDA FoodKeeper app, FDA guidelines
    SHELF_LIFE = {
        # Dairy
        'dairy': {'fridge': 7, 'freezer': 90},
        'milk': {'fridge': 7, 'freezer': 90},
        'cheese': {'fridge': 21, 'freezer': 180},
        'yogurt': {'fridge': 14, 'freezer': 60},
        'butter': {'fridge': 30, 'freezer': 365},
        'cream': {'fridge': 5, 'freezer': 60},
        # Meat & Poultry
        'meat': {'fridge': 3, 'freezer': 180},
        'beef': {'fridge': 3, 'freezer': 270},
        'pork': {'fridge': 3, 'freezer': 180},
        'lamb': {'fridge': 3, 'freezer': 270},
        'poultry': {'fridge': 2, 'freezer': 270},
        'chicken': {'fridge': 2, 'freezer': 270},
        'turkey': {'fridge': 2, 'freezer': 270},
        'ground_meat': {'fridge': 2, 'freezer': 120},
        # Seafood
        'fish': {'fridge': 2, 'freezer': 180},
        'seafood': {'fridge': 2, 'freezer': 180},
        'shrimp': {'fridge': 2, 'freezer': 180},
        'salmon': {'fridge': 2, 'freezer': 180},
        # Eggs
        'eggs': {'fridge': 35, 'freezer': None},
        # Produce
        'vegetables': {'fridge': 7, 'pantry': 5, 'freezer': 270},
        'fruits': {'fridge': 7, 'pantry': 5, 'freezer': 365},
        'leafy_greens': {'fridge': 5, 'freezer': 270},
        'berries': {'fridge': 5, 'freezer': 270},
        'apples': {'fridge': 30, 'pantry': 14},
        'bananas': {'pantry': 5, 'fridge': 7},
        'citrus': {'fridge': 21, 'pantry': 7},
        # Bread & Bakery
        'bread': {'pantry': 5, 'freezer': 90},
        'bakery': {'pantry': 3, 'fridge': 7, 'freezer': 90},
        # Frozen
        'frozen_foods': {'freezer': 180},
        'frozen_vegetables': {'freezer': 270},
        'frozen_fruit': {'freezer': 365},
        'ice_cream': {'freezer': 60},
        # Pantry Staples
        'canned_goods': {'pantry': 730, 'cabinet': 730},
        'dry_goods': {'pantry': 365, 'cabinet': 365},
        'pasta': {'pantry': 730, 'cabinet': 730},
        'rice': {'pantry': 730, 'cabinet': 730},
        'flour': {'pantry': 180, 'cabinet': 180},
        'sugar': {'pantry': 730, 'cabinet': 730},
        'cereal': {'pantry': 180, 'cabinet': 180},
        'chips': {'pantry': 90, 'cabinet': 90},
        'cookies': {'pantry': 90, 'cabinet': 90},
        # Condiments
        'condiments': {'fridge': 90, 'pantry': 180},
        'ketchup': {'fridge': 180, 'pantry': 365},
        'mustard': {'fridge': 365, 'pantry': 365},
        'mayo': {'fridge': 60, 'pantry': 180},
        'salad_dressing': {'fridge': 90, 'pantry': 180},
        'soy_sauce': {'fridge': 730, 'pantry': 730},
        # Beverages
        'beverages': {'fridge': 14, 'pantry': 180},
        'juice': {'fridge': 7, 'freezer': 90},
        'soda': {'fridge': 270, 'pantry': 270},
        'water': {'fridge': 365, 'pantry': 365},
        # Other
        'deli_meat': {'fridge': 5, 'freezer': 60},
        'leftovers': {'fridge': 4, 'freezer': 90},
        'prepared_foods': {'fridge': 4, 'freezer': 90},
    }

    CATEGORY_KEYWORDS = {
        'milk': ['milk', 'whole milk', '2% milk', 'skim milk', 'almond milk', 'oat milk', 'soy milk'],
        'cheese': ['cheese', 'cheddar', 'mozzarella', 'swiss', 'parmesan', 'feta', 'gouda'],
        'yogurt': ['yogurt', 'greek yogurt', 'yoghurt'],
        'butter': ['butter', 'margarine'],
        'cream': ['cream', 'heavy cream', 'whipping cream', 'sour cream'],
        'eggs': ['eggs', 'egg'],
        'beef': ['beef', 'steak', 'roast', 'brisket', 'ribeye', 'sirloin'],
        'pork': ['pork', 'bacon', 'ham', 'sausage', 'pork chop'],
        'chicken': ['chicken', 'chicken breast', 'chicken thigh', 'chicken wings'],
        'turkey': ['turkey', 'turkey breast', 'ground turkey'],
        'ground_meat': ['ground beef', 'ground pork', 'ground chicken', 'hamburger'],
        'fish': ['fish', 'cod', 'tilapia', 'halibut'],
        'salmon': ['salmon'],
        'shrimp': ['shrimp', 'prawns'],
        'leafy_greens': ['lettuce', 'spinach', 'kale', 'arugula', 'mixed greens', 'salad'],
        'berries': ['strawberries', 'blueberries', 'raspberries', 'blackberries'],
        'apples': ['apple', 'apples'],
        'bananas': ['banana', 'bananas'],
        'citrus': ['orange', 'lemon', 'lime', 'grapefruit', 'tangerine'],
        'bread': ['bread', 'loaf', 'baguette', 'roll', 'bagel', 'bun'],
        'bakery': ['muffin', 'croissant', 'donut', 'danish', 'pastry'],
        'deli_meat': ['deli', 'sliced turkey', 'sliced ham', 'lunch meat', 'cold cuts'],
        'frozen_vegetables': ['frozen veg', 'frozen corn', 'frozen peas', 'frozen broccoli'],
        'frozen_fruit': ['frozen berries', 'frozen mango', 'frozen strawberries'],
        'ice_cream': ['ice cream', 'gelato', 'frozen yogurt'],
        'pasta': ['pasta', 'spaghetti', 'penne', 'macaroni', 'noodles'],
        'rice': ['rice', 'brown rice', 'white rice', 'jasmine'],
        'cereal': ['cereal', 'granola', 'oatmeal'],
        'chips': ['chips', 'crisps', 'tortilla chips'],
        'cookies': ['cookies', 'biscuits', 'crackers'],
        'ketchup': ['ketchup', 'catsup'],
        'mustard': ['mustard'],
        'mayo': ['mayo', 'mayonnaise', 'miracle whip'],
        'salad_dressing': ['salad dressing', 'ranch', 'italian dressing', 'vinaigrette'],
        'soy_sauce': ['soy sauce', 'tamari'],
        'juice': ['juice', 'orange juice', 'apple juice'],
        'soda': ['soda', 'pop', 'cola', 'sprite', 'pepsi', 'coke'],
    }

    def __init__(self) -> None:
        self._router: Optional[LLMRouter] = None
        try:
            self._router = LLMRouter()
        except FileNotFoundError:
            logger.debug("LLM config not found — expiry LLM fallback disabled")
        except Exception as e:
            logger.warning("LLMRouter init failed (%s) — expiry LLM fallback disabled", e)

    # ── Public API ────────────────────────────────────────────────────────────

    def predict_expiration(
        self,
        category: Optional[str],
        location: str,
        purchase_date: Optional[date] = None,
        product_name: Optional[str] = None,
        tier: str = "free",
        has_byok: bool = False,
    ) -> Optional[date]:
        """
        Predict expiration date.

        Fast path: deterministic lookup table.
        Fallback: LLM query when table has no match, tier allows it, and a
                  backend is configured. Returns None rather than crashing if
                  inference fails.
        """
        if not purchase_date:
            purchase_date = date.today()

        days = self._lookup_days(category, location)

        if days is None and product_name and self._router and can_use("expiry_llm_matching", tier, has_byok):
            days = self._llm_predict_days(product_name, category, location)

        if days is None:
            return None
        return purchase_date + timedelta(days=days)

    def get_category_from_product(
        self,
        product_name: str,
        product_category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Determine category from product name, existing category, and tags."""
        if product_category:
            cat = product_category.lower().strip()
            if cat in self.SHELF_LIFE:
                return cat
            for key in self.SHELF_LIFE:
                if key in cat or cat in key:
                    return key

        if tags:
            for tag in tags:
                t = tag.lower().strip()
                if t in self.SHELF_LIFE:
                    return t

        name = product_name.lower().strip()
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in name for kw in keywords):
                return category

        for words, fallback in [
            (['meat', 'beef', 'pork', 'chicken'], 'meat'),
            (['vegetable', 'veggie', 'produce'], 'vegetables'),
            (['fruit'], 'fruits'),
            (['dairy'], 'dairy'),
            (['frozen'], 'frozen_foods'),
        ]:
            if any(w in name for w in words):
                return fallback

        return 'dry_goods'

    def get_shelf_life_info(self, category: str, location: str) -> Optional[int]:
        """Shelf life in days for a given category + location, or None."""
        return self.SHELF_LIFE.get(category.lower().strip(), {}).get(location)

    def list_categories(self) -> List[str]:
        return list(self.SHELF_LIFE.keys())

    def list_locations(self) -> List[str]:
        locations: set[str] = set()
        for shelf_life in self.SHELF_LIFE.values():
            locations.update(shelf_life.keys())
        return sorted(locations)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _lookup_days(self, category: Optional[str], location: str) -> Optional[int]:
        """Pure deterministic lookup — no I/O."""
        if not category:
            return None
        cat = category.lower().strip()
        if cat not in self.SHELF_LIFE:
            for key in self.SHELF_LIFE:
                if key in cat or cat in key:
                    cat = key
                    break
            else:
                return None

        days = self.SHELF_LIFE[cat].get(location)
        if days is None:
            for loc in ('fridge', 'pantry', 'freezer', 'cabinet'):
                days = self.SHELF_LIFE[cat].get(loc)
                if days is not None:
                    break
        return days

    def _llm_predict_days(
        self,
        product_name: str,
        category: Optional[str],
        location: str,
    ) -> Optional[int]:
        """
        Ask the LLM how many days this product keeps in the given location.

        TODO: Fill in the prompts below. Good prompts should:
          - Give enough context for the LLM to reason about food safety
          - Specify output format clearly (just an integer — nothing else)
          - Err conservative (shorter shelf life) when uncertain
          - Stay concise — this fires on every unknown barcode scan

        Parameters available:
          product_name — e.g. "Trader Joe's Organic Tempeh"
          category     — best-guess from get_category_from_product(), may be None
          location     — "fridge" | "freezer" | "pantry" | "cabinet"
        """
        assert self._router is not None

        system = (
            "You are a food safety expert. Given a food product name, an optional "
            "category hint, and a storage location, respond with ONLY a single "
            "integer: the number of days the product typically remains safe to eat "
            "from purchase when stored as specified. No explanation, no units, no "
            "punctuation — just the integer. When uncertain, give the conservative "
            "(shorter) estimate."
        )

        parts = [f"Product: {product_name}"]
        if category:
            parts.append(f"Category: {category}")
        parts.append(f"Storage location: {location}")
        parts.append("Days until expiry from purchase:")
        prompt = "\n".join(parts)

        try:
            raw = self._router.complete(prompt, system=system, max_tokens=16)
            match = re.search(r'\b(\d+)\b', raw)
            if match:
                days = int(match.group(1))
                # Sanity cap: >5 years is implausible for a perishable unknown to
                # the deterministic table. If the LLM returns something absurd,
                # fall back to None rather than storing a misleading date.
                if days > 1825:
                    logger.warning(
                        "LLM returned implausible shelf life (%d days) for %r — discarding",
                        days, product_name,
                    )
                    return None
                logger.debug(
                    "LLM shelf life for %r in %s: %d days", product_name, location, days
                )
                return days
        except Exception as e:
            logger.warning("LLM expiry prediction failed for %r: %s", product_name, e)
        return None
