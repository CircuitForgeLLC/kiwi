"""Unit tests for the recipe scanner service.

VLM calls are mocked — these tests cover JSON parsing, pantry cross-reference,
error handling, and result normalization. No GPU required.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.recipe.recipe_scanner import (
    RecipeScanner,
    ScannedIngredient,
    ScannedRecipeResult,
    _cross_reference_pantry,
    _parse_scanner_json,
    _normalize_ingredient_name,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

GOOD_JSON = {
    "title": "Green Goddess Bowls",
    "subtitle": "with Broccoli & Ranch Dressing",
    "servings": "2",
    "cook_time": "15 min",
    "source_note": "Purple Carrot",
    "ingredients": [
        {"name": "brown rice", "qty": "1/2", "unit": "cup", "raw": "1/2 cup brown rice"},
        {"name": "broccoli florets", "qty": "8", "unit": "oz", "raw": "8 oz broccoli florets"},
        {"name": "avocado", "qty": "1", "unit": None, "raw": "1 avocado"},
        {"name": "ranch dressing", "qty": "2", "unit": "tbsp", "raw": "2 tbsp Follow Your Heart Ranch"},
        {"name": "pumpkin seeds", "qty": "1", "unit": "tbsp", "raw": "1 tbsp pumpkin seeds"},
    ],
    "steps": [
        "Cook rice according to package directions.",
        "Steam broccoli for 5 minutes until tender.",
        "Slice avocado. Assemble bowls and top with ranch.",
    ],
    "notes": "Great leftover — keeps 3 days in the fridge.",
    "confidence": "high",
    "warnings": [],
}


def _fake_image_path(tmp_path: Path, name: str = "recipe.jpg") -> Path:
    """Create a tiny placeholder file so path-existence checks pass."""
    p = tmp_path / name
    p.write_bytes(b"\xff\xd8\xff")  # minimal JPEG magic bytes
    return p


# ── _normalize_ingredient_name ─────────────────────────────────────────────────

class TestNormalizeIngredientName:
    def test_lowercases(self):
        assert _normalize_ingredient_name("Brown Rice") == "brown rice"

    def test_strips_whitespace(self):
        assert _normalize_ingredient_name("  avocado  ") == "avocado"

    def test_removes_plural_s(self):
        # For matching purposes only — "pumpkin seeds" stays as-is (stop at spaces)
        assert _normalize_ingredient_name("avocados") == "avocados"

    def test_passthrough(self):
        assert _normalize_ingredient_name("ranch dressing") == "ranch dressing"


# ── _parse_scanner_json ───────────────────────────────────────────────────────

class TestParseScannerJson:
    def test_parses_good_json(self):
        result = _parse_scanner_json(json.dumps(GOOD_JSON))
        assert result["title"] == "Green Goddess Bowls"
        assert len(result["ingredients"]) == 5

    def test_strips_markdown_fences(self):
        wrapped = f"```json\n{json.dumps(GOOD_JSON)}\n```"
        result = _parse_scanner_json(wrapped)
        assert result["title"] == "Green Goddess Bowls"

    def test_not_a_recipe_error(self):
        with pytest.raises(ValueError, match="not_a_recipe"):
            _parse_scanner_json(json.dumps({"error": "not_a_recipe"}))

    def test_missing_title_returns_none_title(self):
        data = dict(GOOD_JSON)
        data.pop("title")
        result = _parse_scanner_json(json.dumps(data))
        assert result.get("title") is None

    def test_malformed_json_raises(self):
        with pytest.raises(ValueError, match="parse"):
            _parse_scanner_json("this is not json at all")

    def test_json_inside_prose(self):
        """Model sometimes adds leading text before the JSON object."""
        text = f"Here is the extracted recipe:\n{json.dumps(GOOD_JSON)}"
        result = _parse_scanner_json(text)
        assert result["title"] == "Green Goddess Bowls"


# ── _cross_reference_pantry ───────────────────────────────────────────────────

class TestCrossReferencePantry:
    PANTRY = ["brown rice", "pumpkin seeds", "olive oil", "broccoli"]

    def test_marks_exact_match(self):
        ingr = [
            ScannedIngredient(name="brown rice", qty="1/2", unit="cup"),
            ScannedIngredient(name="avocado", qty="1", unit=None),
        ]
        result, pct = _cross_reference_pantry(ingr, self.PANTRY)
        assert result[0].in_pantry is True
        assert result[1].in_pantry is False
        assert pct == 50

    def test_partial_word_match(self):
        """'broccoli florets' should match pantry item 'broccoli'."""
        ingr = [ScannedIngredient(name="broccoli florets", qty="8", unit="oz")]
        result, pct = _cross_reference_pantry(ingr, self.PANTRY)
        assert result[0].in_pantry is True
        assert pct == 100

    def test_empty_pantry_all_false(self):
        ingr = [ScannedIngredient(name="broccoli", qty="1", unit=None)]
        result, pct = _cross_reference_pantry(ingr, [])
        assert result[0].in_pantry is False
        assert pct == 0

    def test_empty_ingredients_zero_pct(self):
        _, pct = _cross_reference_pantry([], self.PANTRY)
        assert pct == 0

    def test_case_insensitive_match(self):
        ingr = [ScannedIngredient(name="Brown Rice", qty="1", unit="cup")]
        result, pct = _cross_reference_pantry(ingr, self.PANTRY)
        assert result[0].in_pantry is True


# ── RecipeScanner ─────────────────────────────────────────────────────────────

class TestRecipeScanner:
    def _make_scanner(self) -> RecipeScanner:
        return RecipeScanner()

    @patch("app.services.recipe.recipe_scanner._call_vision_backend")
    def test_scan_single_image_success(self, mock_call, tmp_path):
        mock_call.return_value = json.dumps(GOOD_JSON)
        img = _fake_image_path(tmp_path)

        scanner = self._make_scanner()
        result = scanner.scan([img], pantry_names=["brown rice", "avocado"])

        assert isinstance(result, ScannedRecipeResult)
        assert result.title == "Green Goddess Bowls"
        assert result.servings == "2"
        assert result.cook_time == "15 min"
        assert len(result.ingredients) == 5
        assert result.confidence == "high"
        assert result.pantry_match_pct == 40  # 2 of 5 in pantry

    @patch("app.services.recipe.recipe_scanner._call_vision_backend")
    def test_scan_multi_image(self, mock_call, tmp_path):
        """Two photos treated as one recipe — both passed to VLM."""
        mock_call.return_value = json.dumps(GOOD_JSON)
        img1 = _fake_image_path(tmp_path, "p1.jpg")
        img2 = _fake_image_path(tmp_path, "p2.jpg")

        scanner = self._make_scanner()
        result = scanner.scan([img1, img2])

        # Both images passed through
        call_args = mock_call.call_args
        assert len(call_args[0][0]) == 2  # image_paths list has 2 items
        assert result.title == "Green Goddess Bowls"

    @patch("app.services.recipe.recipe_scanner._call_vision_backend")
    def test_scan_not_a_recipe_raises(self, mock_call, tmp_path):
        mock_call.return_value = json.dumps({"error": "not_a_recipe"})
        img = _fake_image_path(tmp_path)

        scanner = self._make_scanner()
        with pytest.raises(ValueError, match="not_a_recipe"):
            scanner.scan([img])

    @patch("app.services.recipe.recipe_scanner._call_vision_backend")
    def test_warnings_propagated(self, mock_call, tmp_path):
        data = dict(GOOD_JSON)
        data["warnings"] = ["Directions appear to continue on another page not shown"]
        mock_call.return_value = json.dumps(data)
        img = _fake_image_path(tmp_path)

        scanner = self._make_scanner()
        result = scanner.scan([img])
        assert len(result.warnings) == 1
        assert "another page" in result.warnings[0]

    @patch("app.services.recipe.recipe_scanner._call_vision_backend")
    def test_scan_no_pantry_names(self, mock_call, tmp_path):
        mock_call.return_value = json.dumps(GOOD_JSON)
        img = _fake_image_path(tmp_path)

        scanner = self._make_scanner()
        result = scanner.scan([img])
        # No pantry passed — all in_pantry=False, pct=0
        assert result.pantry_match_pct == 0
        assert all(not i.in_pantry for i in result.ingredients)

    def test_scan_too_many_images_raises(self, tmp_path):
        imgs = [_fake_image_path(tmp_path, f"p{i}.jpg") for i in range(5)]
        scanner = self._make_scanner()
        with pytest.raises(ValueError, match="4 images"):
            scanner.scan(imgs)

    def test_scan_no_images_raises(self):
        scanner = self._make_scanner()
        with pytest.raises(ValueError, match="least one"):
            scanner.scan([])

    @patch("app.services.recipe.recipe_scanner._call_vision_backend")
    def test_backend_unavailable_raises(self, mock_call, tmp_path):
        mock_call.side_effect = RuntimeError("No vision backend configured")
        img = _fake_image_path(tmp_path)

        scanner = self._make_scanner()
        with pytest.raises(RuntimeError, match="No vision backend"):
            scanner.scan([img])
