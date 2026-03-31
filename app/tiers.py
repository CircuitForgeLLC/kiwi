"""
Kiwi tier gates.

Tiers: free < paid < premium
(Ultra not used in Kiwi — no human-in-the-loop operations.)

Uses circuitforge-core can_use() with Kiwi's feature map.
"""
from __future__ import annotations

from circuitforge_core.tiers.tiers import can_use as _can_use, BYOK_UNLOCKABLE

# Features that unlock when the user supplies their own LLM backend.
KIWI_BYOK_UNLOCKABLE: frozenset[str] = frozenset({
    "recipe_suggestions",
    "expiry_llm_matching",
    "receipt_ocr",
})

# Feature → minimum tier required
KIWI_FEATURES: dict[str, str] = {
    # Free tier
    "inventory_crud":        "free",
    "barcode_scan":          "free",
    "receipt_upload":        "free",
    "expiry_alerts":         "free",
    "export_csv":            "free",
    "leftover_mode":         "free",      # Rate-limited at API layer, not tier-gated
    "staple_library":        "free",

    # Paid tier
    "receipt_ocr":           "paid",   # BYOK-unlockable
    "recipe_suggestions":    "paid",   # BYOK-unlockable
    "expiry_llm_matching":   "paid",   # BYOK-unlockable
    "meal_planning":         "paid",
    "dietary_profiles":      "paid",
    "style_picker":          "paid",

    # Premium tier
    "multi_household":       "premium",
    "background_monitoring": "premium",
}


def can_use(feature: str, tier: str, has_byok: bool = False) -> bool:
    """Return True if the given tier can access the feature."""
    return _can_use(
        feature,
        tier,
        has_byok=has_byok,
        _features=KIWI_FEATURES,
        _byok_unlockable=KIWI_BYOK_UNLOCKABLE,
    )


def require_feature(feature: str, tier: str, has_byok: bool = False) -> None:
    """Raise ValueError if the tier cannot access the feature."""
    if not can_use(feature, tier, has_byok):
        from circuitforge_core.tiers.tiers import tier_label
        needed = tier_label(
            feature,
            has_byok=has_byok,
            _features=KIWI_FEATURES,
            _byok_unlockable=KIWI_BYOK_UNLOCKABLE,
        )
        raise ValueError(
            f"Feature '{feature}' requires {needed} tier. "
            f"Current tier: {tier}."
        )
