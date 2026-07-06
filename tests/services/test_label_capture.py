"""
Tests for app.services.label_capture.

All tests set KIWI_LABEL_CAPTURE_MOCK=1 so no vision model weights are needed.
"""
import json

import pytest


@pytest.fixture(autouse=True)
def mock_vision(monkeypatch):
    monkeypatch.setenv("KIWI_LABEL_CAPTURE_MOCK", "1")
    yield
    monkeypatch.delenv("KIWI_LABEL_CAPTURE_MOCK", raising=False)


# ── TestExtractLabel ──────────────────────────────────────────────────────────

class TestExtractLabel:
    def test_mock_returns_dict(self):
        from app.services.label_capture import extract_label
        result = extract_label(b"fake image bytes")
        assert isinstance(result, dict)

    def test_mock_returns_all_required_keys(self):
        from app.services.label_capture import extract_label
        result = extract_label(b"fake image bytes")
        for key in ("product_name", "brand", "calories", "fat_g", "carbs_g",
                    "protein_g", "sodium_mg", "ingredient_names", "allergens",
                    "confidence"):
            assert key in result, f"missing key: {key}"

    def test_mock_ingredient_names_is_list(self):
        from app.services.label_capture import extract_label
        result = extract_label(b"fake")
        assert isinstance(result["ingredient_names"], list)

    def test_mock_allergens_is_list(self):
        from app.services.label_capture import extract_label
        result = extract_label(b"fake")
        assert isinstance(result["allergens"], list)

    def test_mock_confidence_zero(self):
        from app.services.label_capture import extract_label
        result = extract_label(b"fake")
        assert result["confidence"] == 0.0

    def _patch_vision(self, monkeypatch, caption_text: str):
        """Patch circuitforge_core.vision.caption to return a VisionResult with caption_text."""
        from circuitforge_core.vision.backends.base import VisionResult

        def _fake_caption(image_bytes, prompt=""):
            return VisionResult(caption=caption_text)

        import circuitforge_core.vision as vision_mod
        monkeypatch.setattr(vision_mod, "caption", _fake_caption)

    def test_exception_falls_back_to_mock(self, monkeypatch):
        """Any exception from the vision backend returns mock extraction."""
        monkeypatch.delenv("KIWI_LABEL_CAPTURE_MOCK", raising=False)

        import circuitforge_core.vision as vision_mod
        monkeypatch.setattr(vision_mod, "caption", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("GPU unavailable")))

        import app.services.label_capture as svc_mod
        result = svc_mod.extract_label(b"image")
        assert result["confidence"] == 0.0
        assert isinstance(result["ingredient_names"], list)

    def test_live_path_parses_json_string(self, monkeypatch):
        """When the vision backend returns valid JSON, it is parsed correctly."""
        monkeypatch.delenv("KIWI_LABEL_CAPTURE_MOCK", raising=False)

        payload = {
            "product_name": "Test Crackers",
            "brand": "Test Brand",
            "serving_size_g": 30.0,
            "calories": 120.0,
            "fat_g": 4.0,
            "saturated_fat_g": 0.5,
            "carbs_g": 20.0,
            "sugar_g": 2.0,
            "fiber_g": 1.0,
            "protein_g": 3.0,
            "sodium_mg": 200.0,
            "ingredient_names": ["wheat flour", "canola oil", "salt"],
            "allergens": ["wheat"],
            "confidence": 0.92,
        }
        self._patch_vision(monkeypatch, json.dumps(payload))

        import app.services.label_capture as svc_mod
        result = svc_mod.extract_label(b"image")
        assert result["product_name"] == "Test Crackers"
        assert result["calories"] == 120.0
        assert result["ingredient_names"] == ["wheat flour", "canola oil", "salt"]
        assert result["allergens"] == ["wheat"]
        assert result["confidence"] == 0.92

    def test_live_path_strips_markdown_fences(self, monkeypatch):
        """JSON wrapped in ```json ... ``` fences is still parsed."""
        monkeypatch.delenv("KIWI_LABEL_CAPTURE_MOCK", raising=False)

        payload = {"product_name": "Fancy", "brand": None, "serving_size_g": None,
                   "calories": None, "fat_g": None, "saturated_fat_g": None,
                   "carbs_g": None, "sugar_g": None, "fiber_g": None,
                   "protein_g": None, "sodium_mg": None,
                   "ingredient_names": [], "allergens": [], "confidence": 0.5}
        self._patch_vision(monkeypatch, f"```json\n{json.dumps(payload)}\n```")

        import app.services.label_capture as svc_mod
        result = svc_mod.extract_label(b"image")
        assert result["product_name"] == "Fancy"

    def test_live_path_bad_json_falls_back(self, monkeypatch):
        monkeypatch.delenv("KIWI_LABEL_CAPTURE_MOCK", raising=False)
        self._patch_vision(monkeypatch, "this is not json")

        import app.services.label_capture as svc_mod
        result = svc_mod.extract_label(b"image")
        assert result["confidence"] == 0.0

    def test_confidence_clamped_above_one(self, monkeypatch):
        monkeypatch.delenv("KIWI_LABEL_CAPTURE_MOCK", raising=False)

        payload = {"product_name": None, "brand": None, "serving_size_g": None,
                   "calories": None, "fat_g": None, "saturated_fat_g": None,
                   "carbs_g": None, "sugar_g": None, "fiber_g": None,
                   "protein_g": None, "sodium_mg": None,
                   "ingredient_names": [], "allergens": [], "confidence": 5.0}
        self._patch_vision(monkeypatch, json.dumps(payload))

        import app.services.label_capture as svc_mod
        result = svc_mod.extract_label(b"image")
        assert result["confidence"] == 1.0

    def test_none_list_fields_normalised_to_empty(self, monkeypatch):
        monkeypatch.delenv("KIWI_LABEL_CAPTURE_MOCK", raising=False)

        payload = {"product_name": None, "brand": None, "serving_size_g": None,
                   "calories": None, "fat_g": None, "saturated_fat_g": None,
                   "carbs_g": None, "sugar_g": None, "fiber_g": None,
                   "protein_g": None, "sodium_mg": None,
                   "ingredient_names": None, "allergens": None, "confidence": 0.8}
        self._patch_vision(monkeypatch, json.dumps(payload))

        import app.services.label_capture as svc_mod
        result = svc_mod.extract_label(b"image")
        assert result["ingredient_names"] == []
        assert result["allergens"] == []


# ── TestNeedsReview ───────────────────────────────────────────────────────────

class TestNeedsReview:
    def test_below_threshold_needs_review(self):
        from app.services.label_capture import REVIEW_THRESHOLD, needs_review
        assert needs_review({"confidence": REVIEW_THRESHOLD - 0.01})

    def test_at_threshold_no_review(self):
        from app.services.label_capture import REVIEW_THRESHOLD, needs_review
        assert not needs_review({"confidence": REVIEW_THRESHOLD})

    def test_above_threshold_no_review(self):
        from app.services.label_capture import needs_review
        assert not needs_review({"confidence": 0.95})

    def test_missing_confidence_needs_review(self):
        from app.services.label_capture import needs_review
        assert needs_review({})
