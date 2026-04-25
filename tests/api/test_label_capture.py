"""
Tests for the visual label capture API endpoints (kiwi#79):
  POST /api/v1/inventory/scan/label-capture
  POST /api/v1/inventory/scan/label-confirm
  GET  /api/v1/inventory/scan/text   — cache hit + needs_visual_capture flag
"""
import io
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.cloud_session import get_session
from app.db.session import get_store


client = TestClient(app)


def _session(tier: str = "paid", has_byok: bool = False) -> MagicMock:
    m = MagicMock()
    m.tier = tier
    m.has_byok = has_byok
    m.user_id = "test-user"
    return m


def _store(**extra_returns) -> MagicMock:
    m = MagicMock()
    m.get_setting.return_value = None
    m.get_captured_product.return_value = None
    m.save_captured_product.return_value = {"id": 1, "barcode": "1234567890", "confirmed_by_user": 1}
    m.get_or_create_product.return_value = (
        {"id": 10, "name": "Test Product", "barcode": "1234567890",
         "brand": None, "category": None, "description": None,
         "image_url": None, "nutrition_data": {}, "source": "visual_capture",
         "created_at": "2026-01-01", "updated_at": "2026-01-01"},
        False,
    )
    m.add_inventory_item.return_value = {
        "id": 99, "product_id": 10, "product_name": "Test Product",
        "barcode": "1234567890", "category": None,
        "quantity": 1.0, "unit": "count", "location": "pantry",
        "sublocation": None, "purchase_date": None,
        "expiration_date": None, "opened_date": None,
        "opened_expiry_date": None, "secondary_state": None,
        "secondary_uses": None, "secondary_warning": None,
        "secondary_discard_signs": None, "status": "available",
        "notes": None, "disposal_reason": None,
        "source": "visual_capture", "created_at": "2026-01-01",
        "updated_at": "2026-01-01",
    }
    for k, v in extra_returns.items():
        setattr(m, k, v)
    return m


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("KIWI_LABEL_CAPTURE_MOCK", "1")
    yield
    monkeypatch.delenv("KIWI_LABEL_CAPTURE_MOCK", raising=False)


# ── /scan/label-capture ───────────────────────────────────────────────────────

class TestLabelCaptureEndpoint:
    def setup_method(self):
        self.session = _session(tier="paid")
        self.store = _store()
        app.dependency_overrides[get_session] = lambda: self.session
        app.dependency_overrides[get_store] = lambda: self.store

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_returns_200_for_paid_tier(self):
        resp = client.post(
            "/api/v1/inventory/scan/label-capture",
            data={"barcode": "1234567890"},
            files={"file": ("label.jpg", io.BytesIO(b"fake_image"), "image/jpeg")},
        )
        assert resp.status_code == 200

    def test_response_contains_barcode(self):
        resp = client.post(
            "/api/v1/inventory/scan/label-capture",
            data={"barcode": "5901234123457"},
            files={"file": ("label.jpg", io.BytesIO(b"fake_image"), "image/jpeg")},
        )
        data = resp.json()
        assert data["barcode"] == "5901234123457"

    def test_response_has_needs_review_field(self):
        resp = client.post(
            "/api/v1/inventory/scan/label-capture",
            data={"barcode": "1234567890"},
            files={"file": ("label.jpg", io.BytesIO(b"fake_image"), "image/jpeg")},
        )
        data = resp.json()
        assert "needs_review" in data

    def test_mock_extraction_has_zero_confidence(self):
        resp = client.post(
            "/api/v1/inventory/scan/label-capture",
            data={"barcode": "1234567890"},
            files={"file": ("label.jpg", io.BytesIO(b"fake_image"), "image/jpeg")},
        )
        data = resp.json()
        assert data["confidence"] == 0.0
        assert data["needs_review"] is True

    def test_free_tier_returns_403(self):
        app.dependency_overrides[get_session] = lambda: _session(tier="free")
        resp = client.post(
            "/api/v1/inventory/scan/label-capture",
            data={"barcode": "1234567890"},
            files={"file": ("label.jpg", io.BytesIO(b"fake_image"), "image/jpeg")},
        )
        assert resp.status_code == 403

    def test_local_tier_bypasses_gate(self):
        app.dependency_overrides[get_session] = lambda: _session(tier="local")
        resp = client.post(
            "/api/v1/inventory/scan/label-capture",
            data={"barcode": "1234567890"},
            files={"file": ("label.jpg", io.BytesIO(b"fake_image"), "image/jpeg")},
        )
        assert resp.status_code == 200


# ── /scan/label-confirm ───────────────────────────────────────────────────────

class TestLabelConfirmEndpoint:
    def setup_method(self):
        self.session = _session(tier="paid")
        self.store = _store()
        app.dependency_overrides[get_session] = lambda: self.session
        app.dependency_overrides[get_store] = lambda: self.store

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_returns_200(self):
        resp = client.post("/api/v1/inventory/scan/label-confirm", json={
            "barcode": "1234567890",
            "product_name": "Test Crackers",
            "calories": 120.0,
            "ingredient_names": ["flour", "salt"],
            "allergens": ["wheat"],
            "confidence": 0.88,
            "auto_add": True,
            "location": "pantry",
            "quantity": 1.0,
        })
        assert resp.status_code == 200

    def test_ok_true_in_response(self):
        resp = client.post("/api/v1/inventory/scan/label-confirm", json={
            "barcode": "1234567890",
            "auto_add": False,
        })
        assert resp.json()["ok"] is True

    def test_save_captured_product_called(self):
        client.post("/api/v1/inventory/scan/label-confirm", json={
            "barcode": "1234567890",
            "product_name": "Test",
            "auto_add": False,
        })
        self.store.save_captured_product.assert_called_once()
        call_kwargs = self.store.save_captured_product.call_args
        assert call_kwargs[0][0] == "1234567890"

    def test_auto_add_true_creates_inventory_item(self):
        resp = client.post("/api/v1/inventory/scan/label-confirm", json={
            "barcode": "1234567890",
            "auto_add": True,
        })
        data = resp.json()
        assert data["inventory_item_id"] is not None
        self.store.add_inventory_item.assert_called_once()

    def test_auto_add_false_skips_inventory(self):
        resp = client.post("/api/v1/inventory/scan/label-confirm", json={
            "barcode": "1234567890",
            "auto_add": False,
        })
        data = resp.json()
        assert data["inventory_item_id"] is None
        self.store.add_inventory_item.assert_not_called()

    def test_free_tier_blocked(self):
        app.dependency_overrides[get_session] = lambda: _session(tier="free")
        resp = client.post("/api/v1/inventory/scan/label-confirm", json={"barcode": "1234567890"})
        assert resp.status_code == 403


# ── /scan/text cache hit + needs_visual_capture ───────────────────────────────

class TestScanTextWithCaptureGating:
    def teardown_method(self):
        app.dependency_overrides.clear()

    def _setup(self, tier: str, cached=None, off_result=None):
        store = _store()
        store.get_captured_product.return_value = cached
        session = _session(tier=tier)
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_store] = lambda: store
        return store

    def _off_patch(self, result):
        """Patch OpenFoodFactsService.lookup_product at the class level."""
        from unittest.mock import AsyncMock, patch
        return patch(
            "app.services.openfoodfacts.OpenFoodFactsService.lookup_product",
            new=AsyncMock(return_value=result),
        )

    def test_paid_tier_no_product_sets_needs_visual_capture(self):
        self._setup(tier="paid")
        with self._off_patch(None):
            resp = client.post("/api/v1/inventory/scan/text", json={
                "barcode": "0000000000000", "location": "pantry",
            })
        assert resp.status_code == 200
        result = resp.json()["results"][0]
        assert result["needs_visual_capture"] is True
        assert result["needs_manual_entry"] is False

    def test_free_tier_no_product_sets_needs_manual_entry(self):
        self._setup(tier="free")
        with self._off_patch(None):
            resp = client.post("/api/v1/inventory/scan/text", json={
                "barcode": "0000000000000", "location": "pantry",
            })
        result = resp.json()["results"][0]
        assert result["needs_visual_capture"] is False
        assert result["needs_manual_entry"] is True

    def test_cache_hit_uses_captured_product(self):
        cached = {
            "barcode": "9999999999999",
            "product_name": "Cached Crackers",
            "brand": "TestBrand",
            "confirmed_by_user": 1,
            "ingredient_names": ["flour"],
            "allergens": [],
            "calories": 110.0,
            "fat_g": None, "saturated_fat_g": None, "carbs_g": None,
            "sugar_g": None, "fiber_g": None, "protein_g": None,
            "sodium_mg": None, "serving_size_g": None,
        }
        store = self._setup(tier="paid", cached=cached)
        store.get_inventory_item.return_value = store.add_inventory_item.return_value

        with self._off_patch(None):  # OFF never called when cache hits
            resp = client.post("/api/v1/inventory/scan/text", json={
                "barcode": "9999999999999", "location": "pantry",
            })

        assert resp.status_code == 200
        result = resp.json()["results"][0]
        assert result["added_to_inventory"] is True
        assert result["needs_visual_capture"] is False
        # OFF was not called (cache resolved it)
        # store.get_captured_product was called with the barcode
        store.get_captured_product.assert_called_once_with("9999999999999")
