"""Tests for app/services/recipe/sensory.py."""
from __future__ import annotations

import json

from app.services.recipe.sensory import (
    SensoryExclude,
    build_sensory_exclude,
    passes_sensory_filter,
)


class TestBuildSensoryExclude:
    def test_none_input_returns_empty(self):
        assert build_sensory_exclude(None).is_empty()

    def test_empty_string_returns_empty(self):
        assert build_sensory_exclude("").is_empty()

    def test_malformed_json_returns_empty(self):
        assert build_sensory_exclude("{not valid json}").is_empty()

    def test_parses_avoid_textures(self):
        prefs = json.dumps({"avoid_textures": ["mushy", "slimy"], "max_smell": None, "max_noise": None})
        result = build_sensory_exclude(prefs)
        assert "mushy" in result.textures
        assert "slimy" in result.textures

    def test_parses_max_smell(self):
        prefs = json.dumps({"avoid_textures": [], "max_smell": "pungent", "max_noise": None})
        result = build_sensory_exclude(prefs)
        assert result.smell_above == "pungent"

    def test_parses_max_noise(self):
        prefs = json.dumps({"avoid_textures": [], "max_smell": None, "max_noise": "loud"})
        result = build_sensory_exclude(prefs)
        assert result.noise_above == "loud"

    def test_unknown_smell_level_becomes_none(self):
        prefs = json.dumps({"avoid_textures": [], "max_smell": "extremely_pungent", "max_noise": None})
        result = build_sensory_exclude(prefs)
        assert result.smell_above is None

    def test_unknown_noise_level_becomes_none(self):
        prefs = json.dumps({"avoid_textures": [], "max_smell": None, "max_noise": "ear_splitting"})
        result = build_sensory_exclude(prefs)
        assert result.noise_above is None

    def test_null_max_smell_is_none(self):
        prefs = json.dumps({"avoid_textures": [], "max_smell": None, "max_noise": None})
        assert build_sensory_exclude(prefs).smell_above is None

    def test_is_empty_all_none(self):
        prefs = json.dumps({"avoid_textures": [], "max_smell": None, "max_noise": None})
        assert build_sensory_exclude(prefs).is_empty()

    def test_is_not_empty_with_textures(self):
        prefs = json.dumps({"avoid_textures": ["mushy"]})
        assert not build_sensory_exclude(prefs).is_empty()


class TestPassesSensoryFilter:
    def _tags(self, textures=None, smell="mild", noise="quiet") -> str:
        return json.dumps({"textures": textures or [], "smell": smell, "noise": noise})

    def test_empty_exclude_always_passes(self):
        tags = self._tags(textures=["mushy"], smell="fermented", noise="very_loud")
        assert passes_sensory_filter(tags, SensoryExclude.empty()) is True

    def test_untagged_recipe_always_passes(self):
        exclude = SensoryExclude(textures=("mushy",), smell_above="pungent")
        assert passes_sensory_filter("{}", exclude) is True
        assert passes_sensory_filter(None, exclude) is True
        assert passes_sensory_filter({}, exclude) is True

    def test_texture_hit_returns_false(self):
        tags = self._tags(textures=["mushy", "creamy"])
        exclude = SensoryExclude(textures=("mushy",))
        assert passes_sensory_filter(tags, exclude) is False

    def test_texture_no_overlap_passes(self):
        tags = self._tags(textures=["crunchy"])
        exclude = SensoryExclude(textures=("mushy", "slimy"))
        assert passes_sensory_filter(tags, exclude) is True

    def test_smell_above_threshold_excluded(self):
        tags = self._tags(smell="fermented")
        exclude = SensoryExclude(smell_above="pungent")
        assert passes_sensory_filter(tags, exclude) is False

    def test_smell_at_threshold_passes(self):
        tags = self._tags(smell="pungent")
        exclude = SensoryExclude(smell_above="pungent")
        assert passes_sensory_filter(tags, exclude) is True

    def test_smell_below_threshold_passes(self):
        for smell in ("aromatic", "mild"):
            tags = self._tags(smell=smell)
            exclude = SensoryExclude(smell_above="pungent")
            assert passes_sensory_filter(tags, exclude) is True

    def test_noise_above_threshold_excluded(self):
        tags = self._tags(noise="very_loud")
        exclude = SensoryExclude(noise_above="loud")
        assert passes_sensory_filter(tags, exclude) is False

    def test_noise_at_threshold_passes(self):
        tags = self._tags(noise="loud")
        exclude = SensoryExclude(noise_above="loud")
        assert passes_sensory_filter(tags, exclude) is True

    def test_noise_below_threshold_passes(self):
        for noise in ("quiet", "moderate"):
            tags = self._tags(noise=noise)
            exclude = SensoryExclude(noise_above="loud")
            assert passes_sensory_filter(tags, exclude) is True

    def test_combined_texture_and_smell(self):
        tags = self._tags(textures=["creamy"], smell="fermented")
        exclude = SensoryExclude(textures=("creamy",), smell_above="pungent")
        assert passes_sensory_filter(tags, exclude) is False

    def test_dict_input_works(self):
        tags_dict = {"textures": ["mushy"], "smell": "mild", "noise": "quiet"}
        exclude = SensoryExclude(textures=("mushy",))
        assert passes_sensory_filter(tags_dict, exclude) is False

    def test_malformed_sensory_tags_passes(self):
        exclude = SensoryExclude(textures=("mushy",), smell_above="pungent")
        assert passes_sensory_filter("{bad json", exclude) is True
