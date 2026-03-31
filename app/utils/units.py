"""
Unit normalization and conversion for Kiwi inventory.

Source of truth: metric.
  - Mass   → grams (g)
  - Volume → milliliters (ml)
  - Count  → each (dimensionless)

All inventory quantities are stored in the base metric unit.
Conversion to display units happens at the API/frontend boundary.

Usage:
    from app.utils.units import normalize_to_metric, convert_from_metric

    # Normalise OCR input
    qty, unit = normalize_to_metric(2.0, "lb")   # → (907.18, "g")
    qty, unit = normalize_to_metric(1.0, "gal")  # → (3785.41, "ml")
    qty, unit = normalize_to_metric(3.0, "each") # → (3.0, "each")

    # Convert for display
    display_qty, display_unit = convert_from_metric(907.18, "g", preferred="imperial")
    # → (2.0, "lb")
"""
from __future__ import annotations

# ── Unit categories ───────────────────────────────────────────────────────────

MASS_UNITS:   frozenset[str] = frozenset({"g", "kg", "mg", "lb", "lbs", "oz"})
VOLUME_UNITS: frozenset[str] = frozenset({
    "ml", "l",
    "fl oz", "floz", "fluid oz", "fluid ounce", "fluid ounces",
    "cup", "cups", "pt", "pint", "pints",
    "qt", "quart", "quarts", "gal", "gallon", "gallons",
})
COUNT_UNITS:  frozenset[str] = frozenset({
    "each", "ea", "pc", "pcs", "piece", "pieces",
    "ct", "count", "item", "items",
    "pk", "pack", "packs", "bag", "bags",
    "bunch", "bunches", "head", "heads",
    "can", "cans", "bottle", "bottles", "box", "boxes",
    "jar", "jars", "tube", "tubes", "roll", "rolls",
    "loaf", "loaves", "dozen",
})

# ── Conversion factors to base metric unit ────────────────────────────────────
# All values are: 1 <unit> = N <base_unit>

# Mass → grams
_TO_GRAMS: dict[str, float] = {
    "g":   1.0,
    "mg":  0.001,
    "kg":  1_000.0,
    "oz":  28.3495,
    "lb":  453.592,
    "lbs": 453.592,
}

# Volume → millilitres
_TO_ML: dict[str, float] = {
    "ml":           1.0,
    "l":            1_000.0,
    "fl oz":        29.5735,
    "floz":         29.5735,
    "fluid oz":     29.5735,
    "fluid ounce":  29.5735,
    "fluid ounces": 29.5735,
    "cup":          236.588,
    "cups":         236.588,
    "pt":           473.176,
    "pint":         473.176,
    "pints":        473.176,
    "qt":           946.353,
    "quart":        946.353,
    "quarts":       946.353,
    "gal":          3_785.41,
    "gallon":       3_785.41,
    "gallons":      3_785.41,
}

# ── Imperial display preferences ─────────────────────────────────────────────
# For convert_from_metric — which metric threshold triggers the next
# larger imperial unit. Keeps display numbers human-readable.

_IMPERIAL_MASS_THRESHOLDS: list[tuple[float, str, float]] = [
    # (min grams, display unit, grams-per-unit)
    (453.592, "lb",  453.592),   # ≥ 1 lb → show in lb
    (0.0,     "oz",  28.3495),   # otherwise → oz
]

_METRIC_MASS_THRESHOLDS: list[tuple[float, str, float]] = [
    (1_000.0, "kg", 1_000.0),
    (0.0,     "g",  1.0),
]

_IMPERIAL_VOLUME_THRESHOLDS: list[tuple[float, str, float]] = [
    (3_785.41, "gal",   3_785.41),
    (946.353,  "qt",    946.353),
    (473.176,  "pt",    473.176),
    (236.588,  "cup",   236.588),
    (0.0,      "fl oz", 29.5735),
]

_METRIC_VOLUME_THRESHOLDS: list[tuple[float, str, float]] = [
    (1_000.0, "l",  1_000.0),
    (0.0,     "ml", 1.0),
]


# ── Public API ────────────────────────────────────────────────────────────────

def normalize_unit(raw: str) -> str:
    """Canonicalize a raw unit string (lowercase, stripped)."""
    return raw.strip().lower()


def classify_unit(unit: str) -> str:
    """Return 'mass', 'volume', or 'count' for a canonical unit string."""
    u = normalize_unit(unit)
    if u in MASS_UNITS:
        return "mass"
    if u in VOLUME_UNITS:
        return "volume"
    return "count"


def normalize_to_metric(quantity: float, unit: str) -> tuple[float, str]:
    """Convert quantity + unit to the canonical metric base unit.

    Returns (metric_quantity, base_unit) where base_unit is one of:
      'g'    — grams     (for all mass units)
      'ml'   — millilitres (for all volume units)
      'each' — countable items (for everything else)

    Unknown or ambiguous units (e.g. 'bag', 'bunch') are treated as count.
    """
    u = normalize_unit(unit)

    if u in _TO_GRAMS:
        return round(quantity * _TO_GRAMS[u], 4), "g"

    if u in _TO_ML:
        return round(quantity * _TO_ML[u], 4), "ml"

    # Count / ambiguous — store as-is
    return quantity, "each"


def convert_from_metric(
    quantity: float,
    base_unit: str,
    preferred: str = "metric",
) -> tuple[float, str]:
    """Convert a stored metric quantity to a display unit.

    Args:
        quantity:  stored metric quantity
        base_unit: 'g', 'ml', or 'each'
        preferred: 'metric' or 'imperial'

    Returns (display_quantity, display_unit).
    Rounds to 2 decimal places.
    """
    if base_unit == "each":
        return quantity, "each"

    thresholds: list[tuple[float, str, float]]

    if base_unit == "g":
        thresholds = (
            _IMPERIAL_MASS_THRESHOLDS if preferred == "imperial"
            else _METRIC_MASS_THRESHOLDS
        )
    elif base_unit == "ml":
        thresholds = (
            _IMPERIAL_VOLUME_THRESHOLDS if preferred == "imperial"
            else _METRIC_VOLUME_THRESHOLDS
        )
    else:
        return quantity, base_unit

    for min_qty, display_unit, factor in thresholds:
        if quantity >= min_qty:
            return round(quantity / factor, 2), display_unit

    return round(quantity, 2), base_unit
