"""
OpenFoodFacts API integration service.

This module provides functionality to look up product information
from the OpenFoodFacts database using barcodes (UPC/EAN).
"""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class OpenFoodFactsService:
    """
    Service for interacting with the Open*Facts family of databases.

    Primary: OpenFoodFacts (food products).
    Fallback chain: Open Beauty Facts (personal care) → Open Products Facts (household).
    All three databases share the same API path and JSON format.
    """

    BASE_URL = "https://world.openfoodfacts.org/api/v2"
    USER_AGENT = "Kiwi/0.1.0 (https://circuitforge.tech)"

    # Fallback databases tried in order when OFFs returns no match.
    # Same API format as OFFs — only the host differs.
    _FALLBACK_DATABASES = [
        "https://world.openbeautyfacts.org/api/v2",
        "https://world.openproductsfacts.org/api/v2",
    ]

    async def _lookup_in_database(
        self, barcode: str, base_url: str, client: httpx.AsyncClient
    ) -> Optional[Dict[str, Any]]:
        """Try one Open*Facts database using an existing client. Returns parsed product dict or None."""
        try:
            response = await client.get(
                f"{base_url}/product/{barcode}.json",
                headers={"User-Agent": self.USER_AGENT},
                timeout=10.0,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            if data.get("status") != 1:
                return None
            return self._parse_product_data(data, barcode)
        except httpx.HTTPError as e:
            logger.debug("HTTP error for %s at %s: %s", barcode, base_url, e)
            return None
        except Exception as e:
            logger.debug("Lookup failed for %s at %s: %s", barcode, base_url, e)
            return None

    async def lookup_product(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Look up a product by barcode, trying OFFs then fallback databases.

        A single httpx.AsyncClient is created for the whole lookup chain so that
        connection pooling and TLS session reuse apply across all database attempts.

        Args:
            barcode: UPC/EAN barcode (8-13 digits)

        Returns:
            Dictionary with product information, or None if not found in any database.
        """
        async with httpx.AsyncClient() as client:
            result = await self._lookup_in_database(barcode, self.BASE_URL, client)
            if result:
                return result

            for db_url in self._FALLBACK_DATABASES:
                result = await self._lookup_in_database(barcode, db_url, client)
                if result:
                    logger.info("Barcode %s found in fallback database: %s", barcode, db_url)
                    return result

        logger.info("Barcode %s not found in any Open*Facts database", barcode)
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

        # Pack size detection: prefer explicit unit_count, fall back to serving count
        pack_quantity, pack_unit = self._extract_pack_size(product)

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
            "pack_quantity": pack_quantity,
            "pack_unit": pack_unit,
            "raw_data": product,  # Store full response for debugging
        }

    def _extract_pack_size(self, product: Dict[str, Any]) -> tuple[float | None, str | None]:
        """Return (quantity, unit) for multi-pack products, or (None, None).

        OFFs fields tried in order:
          1. `number_of_units` (explicit count, highest confidence)
          2. `serving_quantity` + `product_quantity_unit` (e.g. 6 x 150g yoghurt)
          3. Parse `quantity` string like "4 x 113 g" or "6 pack"

        Returns None, None when data is absent, ambiguous, or single-unit.
        """
        import re

        # Field 1: explicit unit count
        unit_count = product.get("number_of_units")
        if unit_count:
            try:
                n = float(unit_count)
                if n > 1:
                    return n, product.get("serving_size_unit") or "unit"
            except (ValueError, TypeError):
                pass

        # Field 2: parse quantity string for "N x ..." pattern
        qty_str = product.get("quantity", "")
        if qty_str:
            m = re.match(r"^(\d+(?:\.\d+)?)\s*[xX×]\s*", qty_str.strip())
            if m:
                n = float(m.group(1))
                if n > 1:
                    # Try to get a sensible sub-unit label from the rest
                    rest = qty_str[m.end():].strip()
                    unit_label = re.sub(r"[\d.,\s]+", "", rest).strip()[:20] or "unit"
                    return n, unit_label

        return None, None

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
