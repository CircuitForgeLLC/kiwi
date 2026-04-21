"""
Shopping locale configuration.

Maps a locale key to Amazon domain, currency metadata, and retailer availability.
Instacart and Walmart are US/CA-only; all other locales get Amazon only.
Amazon Fresh (&i=amazonfresh) is US-only — international domains use the general
grocery department (&rh=n:16310101) where available, plain search elsewhere.
"""
from __future__ import annotations

from typing import TypedDict


class LocaleConfig(TypedDict):
    amazon_domain: str
    amazon_grocery_dept: str   # URL fragment for grocery department on this locale's site
    currency_code: str
    currency_symbol: str
    instacart: bool
    walmart: bool


LOCALES: dict[str, LocaleConfig] = {
    "us": {
        "amazon_domain":       "amazon.com",
        "amazon_grocery_dept": "i=amazonfresh",
        "currency_code":       "USD",
        "currency_symbol":     "$",
        "instacart":           True,
        "walmart":             True,
    },
    "ca": {
        "amazon_domain":       "amazon.ca",
        "amazon_grocery_dept": "rh=n:6967215011",   # Grocery dept on .ca  # gitleaks:allow
        "currency_code":       "CAD",
        "currency_symbol":     "CA$",
        "instacart":           True,
        "walmart":             False,
    },
    "gb": {
        "amazon_domain":       "amazon.co.uk",
        "amazon_grocery_dept": "rh=n:340831031",    # Grocery dept on .co.uk
        "currency_code":       "GBP",
        "currency_symbol":     "£",
        "instacart":           False,
        "walmart":             False,
    },
    "au": {
        "amazon_domain":       "amazon.com.au",
        "amazon_grocery_dept": "rh=n:5765081051",   # Pantry/grocery on .com.au  # gitleaks:allow
        "currency_code":       "AUD",
        "currency_symbol":     "A$",
        "instacart":           False,
        "walmart":             False,
    },
    "nz": {
        # NZ has no Amazon storefront — route to .com.au as nearest option
        "amazon_domain":       "amazon.com.au",
        "amazon_grocery_dept": "rh=n:5765081051",  # gitleaks:allow
        "currency_code":       "NZD",
        "currency_symbol":     "NZ$",
        "instacart":           False,
        "walmart":             False,
    },
    "de": {
        "amazon_domain":       "amazon.de",
        "amazon_grocery_dept": "rh=n:340843031",    # Lebensmittel & Getränke
        "currency_code":       "EUR",
        "currency_symbol":     "€",
        "instacart":           False,
        "walmart":             False,
    },
    "fr": {
        "amazon_domain":       "amazon.fr",
        "amazon_grocery_dept": "rh=n:197858031",
        "currency_code":       "EUR",
        "currency_symbol":     "€",
        "instacart":           False,
        "walmart":             False,
    },
    "it": {
        "amazon_domain":       "amazon.it",
        "amazon_grocery_dept": "rh=n:525616031",
        "currency_code":       "EUR",
        "currency_symbol":     "€",
        "instacart":           False,
        "walmart":             False,
    },
    "es": {
        "amazon_domain":       "amazon.es",
        "amazon_grocery_dept": "rh=n:599364031",
        "currency_code":       "EUR",
        "currency_symbol":     "€",
        "instacart":           False,
        "walmart":             False,
    },
    "nl": {
        "amazon_domain":       "amazon.nl",
        "amazon_grocery_dept": "rh=n:16584827031",
        "currency_code":       "EUR",
        "currency_symbol":     "€",
        "instacart":           False,
        "walmart":             False,
    },
    "se": {
        "amazon_domain":       "amazon.se",
        "amazon_grocery_dept": "rh=n:20741393031",
        "currency_code":       "SEK",
        "currency_symbol":     "kr",
        "instacart":           False,
        "walmart":             False,
    },
    "jp": {
        "amazon_domain":       "amazon.co.jp",
        "amazon_grocery_dept": "rh=n:2246283051",  # gitleaks:allow
        "currency_code":       "JPY",
        "currency_symbol":     "¥",
        "instacart":           False,
        "walmart":             False,
    },
    "in": {
        "amazon_domain":       "amazon.in",
        "amazon_grocery_dept": "rh=n:2454178031",  # gitleaks:allow
        "currency_code":       "INR",
        "currency_symbol":     "₹",
        "instacart":           False,
        "walmart":             False,
    },
    "mx": {
        "amazon_domain":       "amazon.com.mx",
        "amazon_grocery_dept": "rh=n:10737659011",
        "currency_code":       "MXN",
        "currency_symbol":     "MX$",
        "instacart":           False,
        "walmart":             False,
    },
    "br": {
        "amazon_domain":       "amazon.com.br",
        "amazon_grocery_dept": "rh=n:17878420011",
        "currency_code":       "BRL",
        "currency_symbol":     "R$",
        "instacart":           False,
        "walmart":             False,
    },
    "sg": {
        "amazon_domain":       "amazon.sg",
        "amazon_grocery_dept": "rh=n:6981647051",  # gitleaks:allow
        "currency_code":       "SGD",
        "currency_symbol":     "S$",
        "instacart":           False,
        "walmart":             False,
    },
}

DEFAULT_LOCALE = "us"


def get_locale(key: str) -> LocaleConfig:
    """Return locale config for *key*, falling back to US if unknown."""
    return LOCALES.get(key, LOCALES[DEFAULT_LOCALE])
