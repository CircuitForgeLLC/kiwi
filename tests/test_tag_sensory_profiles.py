"""Tests for scripts/tag_sensory_profiles.py classification logic."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.tag_sensory_profiles import (
    _classify_textures,
    _classify_smell,
    _classify_noise,
)


class TestClassifyTextures:
    def test_mushy_from_direction(self):
        assert "mushy" in _classify_textures([], ["stew the vegetables until soft"], set())

    def test_mushy_from_braise(self):
        assert "mushy" in _classify_textures([], ["braise for 2 hours"], set())

    def test_crunchy_from_roast(self):
        assert "crunchy" in _classify_textures([], ["roast at 425F until golden"], set())

    def test_crunchy_from_ingredient_name(self):
        assert "crunchy" in _classify_textures(["breadcrumbs", "chicken"], [], set())

    def test_slimy_from_okra(self):
        assert "slimy" in _classify_textures(["okra", "tomatoes"], [], set())

    def test_slimy_from_natto(self):
        assert "slimy" in _classify_textures(["natto", "rice"], [], set())

    def test_chewy_from_calamari(self):
        assert "chewy" in _classify_textures(["calamari", "lemon"], [], set())

    def test_chewy_from_jerky(self):
        assert "chewy" in _classify_textures(["beef jerky"], [], set())

    def test_creamy_from_profile(self):
        assert "creamy" in _classify_textures([], [], {"creamy"})

    def test_creamy_from_fatty_profile(self):
        assert "creamy" in _classify_textures([], [], {"fatty"})

    def test_creamy_from_blend_direction(self):
        assert "creamy" in _classify_textures([], ["blend until smooth"], set())

    def test_chunky_from_dice_direction(self):
        assert "chunky" in _classify_textures([], ["dice the potatoes", "add to stew"], set())

    def test_multiple_textures_can_fire(self):
        textures = _classify_textures(["okra", "breadcrumbs"], ["roast until crispy"], set())
        assert "slimy" in textures
        assert "crunchy" in textures

    def test_no_signals_returns_list(self):
        result = _classify_textures(["chicken", "rice"], ["cook for 20 minutes"], set())
        assert isinstance(result, list)

    def test_case_insensitive_matching(self):
        assert "slimy" in _classify_textures(["OKRA", "Tomatoes"], [], set())


class TestClassifySmell:
    def test_fermented_from_fish_sauce(self):
        assert _classify_smell(["fish sauce", "lime juice"]) == "fermented"

    def test_fermented_from_miso(self):
        assert _classify_smell(["miso paste", "ginger"]) == "fermented"

    def test_fermented_from_soy_sauce(self):
        assert _classify_smell(["soy sauce", "garlic"]) == "fermented"

    def test_fermented_wins_over_pungent(self):
        assert _classify_smell(["garlic", "soy sauce"]) == "fermented"

    def test_pungent_from_garlic(self):
        assert _classify_smell(["garlic", "onion", "chicken"]) == "pungent"

    def test_pungent_from_curry_powder(self):
        assert _classify_smell(["curry powder", "rice"]) == "pungent"

    def test_aromatic_from_basil(self):
        assert _classify_smell(["basil", "tomatoes", "pasta"]) == "aromatic"

    def test_aromatic_from_cinnamon(self):
        assert _classify_smell(["cinnamon", "apples", "sugar"]) == "aromatic"

    def test_mild_default(self):
        assert _classify_smell(["chicken", "broth", "salt"]) == "mild"

    def test_empty_ingredients_mild(self):
        assert _classify_smell([]) == "mild"

    def test_case_insensitive(self):
        assert _classify_smell(["Fish Sauce", "lime"]) == "fermented"


class TestClassifyNoise:
    def test_very_loud_from_deep_fry(self):
        assert _classify_noise(["deep fry the chicken at 375F"]) == "very_loud"

    def test_very_loud_from_pressure_cook(self):
        assert _classify_noise(["pressure cook on high for 20 minutes"]) == "very_loud"

    def test_very_loud_from_instant_pot(self):
        assert _classify_noise(["add to instant pot, seal, cook 15 min"]) == "very_loud"

    def test_loud_from_sear(self):
        assert _classify_noise(["sear the steak over high heat"]) == "loud"

    def test_loud_from_stir_fry(self):
        assert _classify_noise(["stir fry the vegetables"]) == "loud"

    def test_loud_from_wok(self):
        assert _classify_noise(["heat the wok until smoking"]) == "loud"

    def test_loud_from_bare_fry_no_deep(self):
        assert _classify_noise(["fry the eggs until set"]) == "loud"

    def test_very_loud_wins_over_loud(self):
        assert _classify_noise(["deep fry for 3 minutes"]) == "very_loud"

    def test_moderate_from_saute(self):
        assert _classify_noise(["saute the onions until translucent"]) == "moderate"

    def test_moderate_from_bake(self):
        assert _classify_noise(["bake at 350F for 30 minutes"]) == "moderate"

    def test_moderate_from_roast(self):
        assert _classify_noise(["roast the vegetables for 25 minutes"]) == "moderate"

    def test_quiet_default(self):
        assert _classify_noise(["mix the ingredients", "chill for 1 hour"]) == "quiet"

    def test_empty_directions_quiet(self):
        assert _classify_noise([]) == "quiet"

    def test_case_insensitive(self):
        assert _classify_noise(["Deep Fry the chicken"]) == "very_loud"
