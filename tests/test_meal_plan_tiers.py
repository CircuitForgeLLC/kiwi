# tests/test_meal_plan_tiers.py
from app.tiers import can_use


def test_meal_planning_is_free():
    """Basic meal planning (dinner-only, manual) is available to free tier."""
    assert can_use("meal_planning", "free") is True


def test_meal_plan_config_requires_paid():
    """Configurable meal types (breakfast/lunch/snack) require Paid."""
    assert can_use("meal_plan_config", "free") is False
    assert can_use("meal_plan_config", "paid") is True


def test_meal_plan_llm_byok_unlockable():
    """LLM plan generation is Paid but BYOK-unlockable on Free."""
    assert can_use("meal_plan_llm", "free", has_byok=False) is False
    assert can_use("meal_plan_llm", "free", has_byok=True) is True
    assert can_use("meal_plan_llm", "paid") is True


def test_meal_plan_llm_timing_byok_unlockable():
    """LLM time estimation is Paid but BYOK-unlockable on Free."""
    assert can_use("meal_plan_llm_timing", "free", has_byok=False) is False
    assert can_use("meal_plan_llm_timing", "free", has_byok=True) is True
    assert can_use("meal_plan_llm_timing", "paid") is True
