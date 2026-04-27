"""Tests for app.services.recipe.time_effort — run RED before implementing."""
import pytest
from app.services.recipe.time_effort import (
    TimeEffortProfile,
    StepAnalysis,
    parse_time_effort,
)


# ── Step classification ────────────────────────────────────────────────────

class TestPassiveClassification:
    def test_simmer_is_passive(self):
        result = parse_time_effort(["Simmer for 10 minutes."])
        assert result.step_analyses[0].is_passive is True

    def test_bake_is_passive(self):
        result = parse_time_effort(["Bake at 375°F for 30 minutes."])
        assert result.step_analyses[0].is_passive is True

    def test_chop_is_active(self):
        result = parse_time_effort(["Chop the onion finely."])
        assert result.step_analyses[0].is_passive is False

    def test_sear_is_active(self):
        result = parse_time_effort(["Sear chicken over high heat."])
        assert result.step_analyses[0].is_passive is False

    def test_let_rest_is_passive(self):
        result = parse_time_effort(["Let the dough rest for 20 minutes."])
        assert result.step_analyses[0].is_passive is True

    def test_passive_keywords_matched_as_whole_words(self):
        # "settle" contains "set" — must NOT match as passive
        result = parse_time_effort(["Settle the dish on the table."])
        assert result.step_analyses[0].is_passive is False

    def test_overnight_is_passive(self):
        result = parse_time_effort(["Marinate overnight in the fridge."])
        assert result.step_analyses[0].is_passive is True

    def test_slow_cook_multiword_is_passive(self):
        result = parse_time_effort(["Slow cook on low for 6 hours."])
        assert result.step_analyses[0].is_passive is True

    def test_pressure_cook_multiword_is_passive(self):
        result = parse_time_effort(["Pressure cook on high for 15 minutes."])
        assert result.step_analyses[0].is_passive is True


# ── Time extraction ────────────────────────────────────────────────────────

class TestTimeExtraction:
    def test_simple_minutes(self):
        result = parse_time_effort(["Cook for 10 minutes."])
        assert result.step_analyses[0].detected_minutes == 10

    def test_simple_hours_converted(self):
        result = parse_time_effort(["Braise for 2 hours."])
        assert result.step_analyses[0].detected_minutes == 120

    def test_range_takes_midpoint(self):
        # "15-20 minutes" → midpoint = 17 (int division: (15+20)//2 = 17)
        result = parse_time_effort(["Cook for 15-20 minutes."])
        assert result.step_analyses[0].detected_minutes == 17

    def test_range_with_endash(self):
        result = parse_time_effort(["Simmer for 15–20 minutes."])
        assert result.step_analyses[0].detected_minutes == 17

    def test_abbreviated_min(self):
        result = parse_time_effort(["Heat oil for 5 min."])
        assert result.step_analyses[0].detected_minutes == 5

    def test_abbreviated_hr(self):
        result = parse_time_effort(["Rest for 1 hr."])
        assert result.step_analyses[0].detected_minutes == 60

    def test_no_time_returns_none(self):
        result = parse_time_effort(["Add salt to taste."])
        assert result.step_analyses[0].detected_minutes is None

    def test_cap_at_480_minutes(self):
        # 10 hours would be 600 min — capped at 480
        result = parse_time_effort(["Ferment for 10 hours."])
        assert result.step_analyses[0].detected_minutes == 480

    def test_seconds_converted(self):
        result = parse_time_effort(["Blend for 30 seconds."])
        assert result.step_analyses[0].detected_minutes == 1  # rounds up: ceil(30/60) or 1 as min floor


# ── Time totals ────────────────────────────────────────────────────────────

class TestTimeTotals:
    def test_active_passive_split(self):
        steps = [
            "Chop onions finely.",                   # active; chop action → 2 min prep
            "Sear chicken for 5 minutes per side.",  # active, 5 min explicit
            "Simmer for 20 minutes.",                # passive, 20 min explicit
        ]
        result = parse_time_effort(steps)
        # "Chop onions" now contributes prep_min (chop base=2.0) + 5 explicit = 7 active
        assert result.active_min == 7
        assert result.passive_min == 20
        assert result.total_min == 27

    def test_all_active_passive_zero(self):
        steps = ["Dice vegetables.", "Season with salt.", "Plate and serve."]
        result = parse_time_effort(steps)
        assert result.passive_min == 0

    def test_zero_directions_returns_zero_profile(self):
        result = parse_time_effort([])
        assert result.active_min == 0
        assert result.passive_min == 0
        assert result.total_min == 0
        assert result.step_analyses == []
        assert result.equipment == []
        assert result.effort_label == "quick"


# ── Effort label ───────────────────────────────────────────────────────────

class TestEffortLabel:
    def test_one_step_is_quick(self):
        result = parse_time_effort(["Serve cold."])
        assert result.effort_label == "quick"

    def test_three_steps_is_quick(self):
        result = parse_time_effort(["a", "b", "c"])
        assert result.effort_label == "quick"

    def test_bake_recipe_is_moderate(self):
        # Passive default for "bake" = 30 min → moderate (21-45 min range)
        result = parse_time_effort([
            "Mix dry ingredients.",
            "Combine wet ingredients.",
            "Fold together until just combined.",
            "Bake until a toothpick comes out clean.",
        ])
        assert result.effort_label == "moderate"

    def test_slow_cook_recipe_is_involved(self):
        # Passive default for "slow cook" = 300 min → involved (>45 min)
        result = parse_time_effort([
            "Brown the meat in batches.",
            "Add vegetables and broth.",
            "Slow cook until tender.",
        ])
        assert result.effort_label == "involved"

    def test_explicit_time_drives_effort_label(self):
        # Explicit passive time of 90 min → involved
        result = parse_time_effort(["Braise for 90 minutes."])
        assert result.effort_label == "involved"


# ── Equipment detection ────────────────────────────────────────────────────

class TestEquipmentDetection:
    def test_knife_detected(self):
        result = parse_time_effort(["Dice the onion.", "Mince the garlic."])
        assert "Knife" in result.equipment

    def test_skillet_keyword_fry(self):
        result = parse_time_effort(["Pan-fry the chicken over medium heat."])
        assert "Skillet" in result.equipment

    def test_oven_detected(self):
        result = parse_time_effort(["Preheat oven to 400°F.", "Bake for 25 minutes."])
        assert "Oven" in result.equipment

    def test_pot_detected(self):
        result = parse_time_effort(["Bring a large pot of water to boil."])
        assert "Pot" in result.equipment

    def test_timer_added_when_any_passive_step(self):
        result = parse_time_effort(["Chop onion.", "Simmer for 10 minutes."])
        assert "Timer" in result.equipment

    def test_no_timer_when_all_active(self):
        result = parse_time_effort(["Chop vegetables.", "Toss with dressing."])
        assert "Timer" not in result.equipment

    def test_equipment_deduplicated(self):
        # Multiple steps with 'dice' should still yield only one Knife
        result = parse_time_effort(["Dice onion.", "Dice carrot.", "Dice celery."])
        assert result.equipment.count("Knife") == 1

    def test_no_equipment_when_empty(self):
        result = parse_time_effort([])
        assert result.equipment == []

    def test_slow_cooker_detected(self):
        result = parse_time_effort(["Place everything in the slow cooker."])
        assert "Slow cooker" in result.equipment

    def test_pressure_cooker_detected(self):
        result = parse_time_effort(["Set instant pot to high pressure."])
        assert "Pressure cooker" in result.equipment

    def test_colander_detected(self):
        result = parse_time_effort(["Drain the pasta through a colander."])
        assert "Colander" in result.equipment

    def test_blender_detected(self):
        result = parse_time_effort(["Blend until smooth."])
        assert "Blender" in result.equipment


# ── Dataclass immutability ────────────────────────────────────────────────

class TestImmutability:
    def test_time_effort_profile_is_frozen(self):
        result = parse_time_effort(["Chop onion."])
        with pytest.raises((AttributeError, TypeError)):
            result.active_min = 99  # type: ignore[misc]

    def test_step_analysis_is_frozen(self):
        result = parse_time_effort(["Simmer for 10 min."])
        with pytest.raises((AttributeError, TypeError)):
            result.step_analyses[0].is_passive = False  # type: ignore[misc]
