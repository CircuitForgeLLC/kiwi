"""
GroceryLinkBuilder — affiliate deeplinks for missing ingredient grocery lists.

Free tier: URL construction only (Amazon Fresh, Walmart, Instacart).
Paid+: live product search API (stubbed — future task).

Config (env vars, all optional — missing = retailer disabled):
  AMAZON_AFFILIATE_TAG      — e.g. "circuitforge-20"
  INSTACART_AFFILIATE_ID    — e.g. "circuitforge"
  WALMART_AFFILIATE_ID      — e.g. "circuitforge" (Impact affiliate network)
"""
from __future__ import annotations

import os
from urllib.parse import quote_plus

from app.models.schemas.recipe import GroceryLink


def _amazon_link(ingredient: str, tag: str) -> GroceryLink:
    q = quote_plus(ingredient)
    url = f"https://www.amazon.com/s?k={q}&i=amazonfresh&tag={tag}"
    return GroceryLink(ingredient=ingredient, retailer="Amazon Fresh", url=url)


def _walmart_link(ingredient: str, affiliate_id: str) -> GroceryLink:
    q = quote_plus(ingredient)
    # Walmart Impact affiliate deeplink pattern
    url = f"https://goto.walmart.com/c/{affiliate_id}/walmart?u=https://www.walmart.com/search?q={q}"
    return GroceryLink(ingredient=ingredient, retailer="Walmart Grocery", url=url)


def _instacart_link(ingredient: str, affiliate_id: str) -> GroceryLink:
    q = quote_plus(ingredient)
    url = f"https://www.instacart.com/store/s?k={q}&aff={affiliate_id}"
    return GroceryLink(ingredient=ingredient, retailer="Instacart", url=url)


class GroceryLinkBuilder:
    def __init__(self, tier: str = "free", has_byok: bool = False) -> None:
        self._tier = tier
        self._has_byok = has_byok
        self._amazon_tag = os.environ.get("AMAZON_AFFILIATE_TAG", "")
        self._instacart_id = os.environ.get("INSTACART_AFFILIATE_ID", "")
        self._walmart_id = os.environ.get("WALMART_AFFILIATE_ID", "")

    def build_links(self, ingredient: str) -> list[GroceryLink]:
        """Build affiliate deeplinks for a single ingredient.

        Free tier: URL construction only.
        Paid+: would call live product search APIs (stubbed).
        """
        if not ingredient.strip():
            return []
        links: list[GroceryLink] = []

        if self._amazon_tag:
            links.append(_amazon_link(ingredient, self._amazon_tag))
        if self._walmart_id:
            links.append(_walmart_link(ingredient, self._walmart_id))
        if self._instacart_id:
            links.append(_instacart_link(ingredient, self._instacart_id))

        # Paid+: live API stub (future task)
        # if self._tier in ("paid", "premium") and not self._has_byok:
        #     links.extend(self._search_kroger_api(ingredient))

        return links

    def build_all(self, ingredients: list[str]) -> list[GroceryLink]:
        """Build links for a list of ingredients."""
        links: list[GroceryLink] = []
        for ingredient in ingredients:
            links.extend(self.build_links(ingredient))
        return links
