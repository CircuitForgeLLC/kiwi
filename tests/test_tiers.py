from app.tiers import can_use


def test_leftover_mode_free_tier():
    """Leftover mode is now available to free users (rate-limited at API layer, not hard-gated)."""
    assert can_use("leftover_mode", "free") is True


def test_style_picker_requires_paid():
    assert can_use("style_picker", "free") is False
    assert can_use("style_picker", "paid") is True


def test_staple_library_is_free():
    assert can_use("staple_library", "free") is True


def test_recipe_suggestions_byok_unlockable():
    assert can_use("recipe_suggestions", "free", has_byok=False) is False
    assert can_use("recipe_suggestions", "free", has_byok=True) is True
