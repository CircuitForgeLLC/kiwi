"""
GroceryLinkBuilder — affiliate deeplinks for missing ingredient grocery lists.

Delegates URL wrapping to circuitforge_core.affiliates.wrap_url, which handles
the full resolution chain: opt-out → BYOK id → CF env var → plain URL.

Registered programs (via cf-core):
  amazon     — Amazon Associates (env: AMAZON_ASSOCIATES_TAG)
  instacart  — Instacart         (env: INSTACART_AFFILIATE_ID)

Walmart is kept inline until cf-core adds Impact network support:
  env: WALMART_AFFILIATE_ID

Links are always generated (plain URLs are useful even without affiliate IDs).
Walmart links only appear when WALMART_AFFILIATE_ID is set.
"""
from __future__ import annotations

import logging
import os
from urllib.parse import quote_plus

from circuitforge_core.affiliates import wrap_url

from app.models.schemas.recipe import GroceryLink

logger = logging.getLogger(__name__)


def _amazon_fresh_link(ingredient: str) -> GroceryLink:
    q = quote_plus(ingredient)
    base = f"https://www.amazon.com/s?k={q}&i=amazonfresh"
    return GroceryLink(ingredient=ingredient, retailer="Amazon Fresh", url=wrap_url(base, "amazon"))


def _instacart_link(ingredient: str) -> GroceryLink:
    q = quote_plus(ingredient)
    base = f"https://www.instacart.com/store/s?k={q}"
    return GroceryLink(ingredient=ingredient, retailer="Instacart", url=wrap_url(base, "instacart"))


def _walmart_link(ingredient: str, affiliate_id: str) -> GroceryLink:
    q = quote_plus(ingredient)
    # Walmart uses Impact network — affiliate ID is in the redirect path, not a param
    url = (
        f"https://goto.walmart.com/c/{affiliate_id}/walmart"
        f"?u=https://www.walmart.com/search?q={q}"
    )
    return GroceryLink(ingredient=ingredient, retailer="Walmart Grocery", url=url)


class GroceryLinkBuilder:
    def __init__(self, tier: str = "free", has_byok: bool = False) -> None:
        self._tier = tier
        self._walmart_id = os.environ.get("WALMART_AFFILIATE_ID", "").strip()

    def build_links(self, ingredient: str) -> list[GroceryLink]:
        """Build grocery deeplinks for a single ingredient.

        Amazon Fresh and Instacart links are always included; wrap_url handles
        affiliate ID injection (or returns a plain URL if none is configured).
        Walmart requires WALMART_AFFILIATE_ID to be set (Impact network uses a
        path-based redirect that doesn't degrade cleanly to a plain URL).
        """
        if not ingredient.strip():
            return []

        links: list[GroceryLink] = [
            _amazon_fresh_link(ingredient),
            _instacart_link(ingredient),
        ]
        if self._walmart_id:
            links.append(_walmart_link(ingredient, self._walmart_id))

        return links

    def build_all(self, ingredients: list[str]) -> list[GroceryLink]:
        """Build links for a list of ingredients."""
        links: list[GroceryLink] = []
        for ingredient in ingredients:
            links.extend(self.build_links(ingredient))
        return links
