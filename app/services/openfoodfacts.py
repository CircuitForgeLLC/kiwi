"""
OpenFoodFacts API integration service.

This module provides functionality to look up product information
from the OpenFoodFacts database using barcodes (UPC/EAN).
"""

import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class OpenFoodFactsService:
    """
    Service for interacting with the OpenFoodFacts API.

    OpenFoodFacts is a free, open database of food products with
    ingredients, allergens, and nutrition facts.
    """

    BASE_URL = "https://world.openfoodfacts.org/api/v2"
    USER_AGENT = "Kiwi/0.1.0 (https://circuitforge.tech)"

    async def lookup_product(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Look up a product by barcode in the OpenFoodFacts database.

        Args:
            barcode: UPC/EAN barcode (8-13 digits)

        Returns:
            Dictionary with product information, or None if not found

        Example response:
        {
            "name": "Organic Milk",
            "brand": "Horizon",
            "categories": ["Dairy", "Milk"],
            "image_url": "https://...",
            "nutrition_data": {...},
            "raw_data": {...}  # Full API response
        }
        """
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.BASE_URL}/product/{barcode}.json"

                response = await client.get(
                    url,
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=10.0,
                )

                if response.status_code == 404:
                    logger.info(f"Product not found in OpenFoodFacts: {barcode}")
                    return None

                response.raise_for_status()
                data = response.json()

                if data.get("status") != 1:
                    logger.info(f"Product not found in OpenFoodFacts: {barcode}")
                    return None

                return self._parse_product_data(data, barcode)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error looking up barcode {barcode}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error looking up barcode {barcode}: {e}")
            return None

    def _parse_product_data(self, data: Dict[str, Any], barcode: str) -> Dict[str, Any]:
        """
        Parse OpenFoodFacts API response into our product format.

        Args:
            data: Raw API response
            barcode: Original barcode

        Returns:
            Parsed product dictionary
        """
        product = data.get("product", {})

        # Extract basic info
        name = (
            product.get("product_name")
            or product.get("product_name_en")
            or f"Unknown Product ({barcode})"
        )

        brand = product.get("brands", "").split(",")[0].strip() if product.get("brands") else None

        # Categories (comma-separated string to list)
        categories_str = product.get("categories", "")
        categories = [c.strip() for c in categories_str.split(",") if c.strip()]
        category = categories[0] if categories else None

        # Description
        description = product.get("generic_name") or product.get("generic_name_en")

        # Image
        image_url = product.get("image_url") or product.get("image_front_url")

        # Nutrition data
        nutrition_data = self._extract_nutrition_data(product)

        # Allergens and dietary info
        allergens = product.get("allergens_tags", [])
        labels = product.get("labels_tags", [])

        return {
            "name": name,
            "brand": brand,
            "category": category,
            "categories": categories,
            "description": description,
            "image_url": image_url,
            "nutrition_data": nutrition_data,
            "allergens": allergens,
            "labels": labels,
            "raw_data": product,  # Store full response for debugging
        }

    def _extract_nutrition_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract nutrition facts from product data.

        Args:
            product: Product data from OpenFoodFacts

        Returns:
            Dictionary of nutrition facts
        """
        nutriments = product.get("nutriments", {})

        # Extract common nutrients (per 100g)
        nutrition = {}

        # Energy
        if "energy-kcal_100g" in nutriments:
            nutrition["calories"] = nutriments["energy-kcal_100g"]
        elif "energy_100g" in nutriments:
            # Convert kJ to kcal (1 kcal = 4.184 kJ)
            nutrition["calories"] = round(nutriments["energy_100g"] / 4.184, 1)

        # Macronutrients
        if "fat_100g" in nutriments:
            nutrition["fat_g"] = nutriments["fat_100g"]
        if "saturated-fat_100g" in nutriments:
            nutrition["saturated_fat_g"] = nutriments["saturated-fat_100g"]
        if "carbohydrates_100g" in nutriments:
            nutrition["carbohydrates_g"] = nutriments["carbohydrates_100g"]
        if "sugars_100g" in nutriments:
            nutrition["sugars_g"] = nutriments["sugars_100g"]
        if "fiber_100g" in nutriments:
            nutrition["fiber_g"] = nutriments["fiber_100g"]
        if "proteins_100g" in nutriments:
            nutrition["protein_g"] = nutriments["proteins_100g"]

        # Minerals
        if "salt_100g" in nutriments:
            nutrition["salt_g"] = nutriments["salt_100g"]
        elif "sodium_100g" in nutriments:
            # Convert sodium to salt (1g sodium = 2.5g salt)
            nutrition["salt_g"] = round(nutriments["sodium_100g"] * 2.5, 2)

        # Serving size
        if "serving_size" in product:
            nutrition["serving_size"] = product["serving_size"]

        return nutrition

    async def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Search for products by name in OpenFoodFacts.

        Args:
            query: Search query
            page: Page number (1-indexed)
            page_size: Number of results per page

        Returns:
            Dictionary with search results and metadata
        """
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.BASE_URL}/search"

                response = await client.get(
                    url,
                    params={
                        "search_terms": query,
                        "page": page,
                        "page_size": page_size,
                        "json": 1,
                    },
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=10.0,
                )

                response.raise_for_status()
                data = response.json()

                products = [
                    self._parse_product_data({"product": p}, p.get("code", ""))
                    for p in data.get("products", [])
                ]

                return {
                    "products": products,
                    "count": data.get("count", 0),
                    "page": data.get("page", page),
                    "page_size": data.get("page_size", page_size),
                }

        except Exception as e:
            logger.error(f"Error searching OpenFoodFacts: {e}")
            return {
                "products": [],
                "count": 0,
                "page": page,
                "page_size": page_size,
            }
