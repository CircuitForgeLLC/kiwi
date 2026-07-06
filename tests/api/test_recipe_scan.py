"""API tests for recipe scan endpoints (kiwi#9).

VLM calls are mocked at the service level -- no GPU or API key needed.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.cloud_session import get_session
from app.db.session import get_store
from app.main import app

client = TestClient(app)

_GOOD_SCAN_JSON = {
    "title": "Green Goddess Bowls",
    "subtitle": "with Broccoli & Ranch Dressing",
    "servings": "2",
    "cook_time": "15 min",
    "source_note": "Purple Carrot",
    "ingredients": [
        {"name": "brown rice", "qty": "1/2", "unit": "cup", "raw": "1/2 cup brown rice"},
        {"name": "broccoli florets", "qty": "8", "unit": "oz", "raw": "8 oz broccoli florets"},
        {"name": "avocado", "qty": "1", "unit": None, "raw": "1 avocado"},
    ],
    "steps": ["Cook rice.", "Steam broccoli.", "Assemble bowls."],
    "notes": None,
    "confidence": "high",
    "warnings": [],
}


def _make_session(tier: str = "paid", has_byok: bool = False) -> MagicMock:
    mock = MagicMock()
    mock.tier = tier
    mock.has_byok = has_byok
    mock.db = ":memory:"
    return mock


def _make_store() -> MagicMock:
    mock = MagicMock()
    mock.list_inventory.return_value = [
        {"product_name": "brown rice"},
        {"product_name": "avocado"},
    ]
    mock.create_user_recipe.return_value = {
        "id": 1,
        "title": "Green Goddess Bowls",
        "subtitle": "with Broccoli & Ranch Dressing",
        "servings": "2",
        "cook_time": "15 min",
        "source_note": "Purple Carrot",
        "ingredients": _GOOD_SCAN_JSON["ingredients"],
        "steps": _GOOD_SCAN_JSON["steps"],
        "notes": None,
        "tags": [],
        "source": "scan",
        "pantry_match_pct": None,
        "created_at": "2026-04-27T00:00:00",
    }
    mock.list_user_recipes.return_value = []
    mock.get_user_recipe.return_value = None
    mock.delete_user_recipe.return_value = False
    return mock


def _fake_image() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100  # minimal JPEG magic


@pytest.fixture(autouse=True)
def override_deps():
    session_mock = _make_session()
    store_mock = _make_store()
    app.dependency_overrides[get_session] = lambda: session_mock
    app.dependency_overrides[get_store] = lambda: store_mock
    yield session_mock, store_mock
    app.dependency_overrides.clear()


# ── POST /recipes/scan ─────────────────────────────────────────────────────────

def _make_scan_result(title: str = "Green Goddess Bowls"):
    """Create a fake ScannedRecipeResult for tests."""
    from app.services.recipe.recipe_scanner import ScannedIngredient, ScannedRecipeResult
    return ScannedRecipeResult(
        title=title,
        subtitle="with Broccoli & Ranch Dressing",
        servings="2",
        cook_time="15 min",
        source_note="Purple Carrot",
        ingredients=[
            ScannedIngredient("brown rice", "1/2", "cup", in_pantry=True),
            ScannedIngredient("broccoli florets", "8", "oz"),
            ScannedIngredient("avocado", "1", None, in_pantry=True),
        ],
        steps=["Cook rice.", "Steam broccoli.", "Assemble bowls."],
        notes=None,
        tags=[],
        pantry_match_pct=67,
        confidence="high",
        warnings=[],
    )


@pytest.fixture
def mock_scan_infra(tmp_path):
    """Patch file-saving and VLM calls so scan endpoint tests don't need disk or GPU."""
    fake_path = tmp_path / "recipe.jpg"
    fake_path.write_bytes(_fake_image())

    async def _fake_save(upload_file):
        return fake_path

    with patch("app.api.endpoints.recipe_scan._save_upload_temp", side_effect=_fake_save):
        with patch("app.api.endpoints.recipe_scan.asyncio.to_thread") as mock_thread:
            yield mock_thread, fake_path


class TestScanEndpoint:
    def test_scan_returns_200(self, override_deps, mock_scan_infra):
        """Happy path: paid tier, valid JPEG, VLM returns good JSON."""
        _, store_mock = override_deps
        mock_thread, _ = mock_scan_infra

        scan_result = _make_scan_result()
        call_count = 0

        def side_effect(fn, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return store_mock.list_inventory() if call_count == 1 else scan_result

        mock_thread.side_effect = side_effect

        resp = client.post(
            "/api/v1/recipes/scan",
            files=[("files", ("recipe.jpg", _fake_image(), "image/jpeg"))],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Green Goddess Bowls"
        assert data["confidence"] == "high"
        assert data["pantry_match_pct"] == 67
        assert len(data["ingredients"]) == 3

    def test_scan_requires_paid_tier(self, override_deps):
        """Free tier without BYOK should get 403."""
        session_mock, _ = override_deps
        session_mock.tier = "free"
        session_mock.has_byok = False

        resp = client.post(
            "/api/v1/recipes/scan",
            files=[("files", ("recipe.jpg", _fake_image(), "image/jpeg"))],
        )
        assert resp.status_code == 403

    def test_scan_byok_free_tier_allowed(self, override_deps, mock_scan_infra):
        """Free tier WITH BYOK should be allowed through the tier gate."""
        session_mock, store_mock = override_deps
        session_mock.tier = "free"
        session_mock.has_byok = True

        mock_thread, _ = mock_scan_infra
        scan_result = _make_scan_result("Simple Bowl")
        call_count = 0

        def _side(fn, *a, **kw):
            nonlocal call_count
            call_count += 1
            return store_mock.list_inventory() if call_count == 1 else scan_result

        mock_thread.side_effect = _side
        resp = client.post(
            "/api/v1/recipes/scan",
            files=[("files", ("recipe.jpg", _fake_image(), "image/jpeg"))],
        )
        assert resp.status_code == 200

    def test_scan_no_files_rejected(self, override_deps):
        """Missing files field returns 422."""
        resp = client.post("/api/v1/recipes/scan", files=[])
        assert resp.status_code in (422, 400)

    def test_scan_too_many_files(self, override_deps, mock_scan_infra):
        """More than 4 files should return 422."""
        mock_thread, _ = mock_scan_infra
        mock_thread.return_value = []
        files = [("files", (f"p{i}.jpg", _fake_image(), "image/jpeg")) for i in range(5)]
        resp = client.post("/api/v1/recipes/scan", files=files)
        assert resp.status_code == 422

    def test_scan_not_a_recipe_returns_422(self, override_deps, mock_scan_infra):
        _, store_mock = override_deps
        mock_thread, _ = mock_scan_infra
        call_count = 0

        def _side(fn, *a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return store_mock.list_inventory()
            raise ValueError("not_a_recipe: image does not appear to contain a recipe")

        mock_thread.side_effect = _side
        resp = client.post(
            "/api/v1/recipes/scan",
            files=[("files", ("photo.jpg", _fake_image(), "image/jpeg"))],
        )
        assert resp.status_code == 422
        assert "recipe" in resp.json()["detail"].lower()

    def test_scan_backend_unavailable_returns_503(self, override_deps, mock_scan_infra):
        _, store_mock = override_deps
        mock_thread, _ = mock_scan_infra
        call_count = 0

        def _side(fn, *a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return store_mock.list_inventory()
            raise RuntimeError("No vision backend configured")

        mock_thread.side_effect = _side
        resp = client.post(
            "/api/v1/recipes/scan",
            files=[("files", ("photo.jpg", _fake_image(), "image/jpeg"))],
        )
        assert resp.status_code == 503


# ── POST /recipes/scan/save ────────────────────────────────────────────────────

class TestSaveEndpoint:
    def test_save_returns_201(self, override_deps):
        _, store_mock = override_deps
        store_mock.create_user_recipe.return_value = {
            "id": 42,
            "title": "Green Goddess Bowls",
            "subtitle": None,
            "servings": "2",
            "cook_time": "15 min",
            "source_note": None,
            "ingredients": [{"name": "brown rice", "qty": "1", "unit": "cup", "raw": None, "in_pantry": False}],
            "steps": ["Cook it."],
            "notes": None,
            "tags": [],
            "source": "scan",
            "pantry_match_pct": None,
            "created_at": "2026-04-27T00:00:00",
        }

        payload = {
            "title": "Green Goddess Bowls",
            "servings": "2",
            "cook_time": "15 min",
            "ingredients": [{"name": "brown rice", "qty": "1", "unit": "cup"}],
            "steps": ["Cook it."],
            "source": "scan",
        }
        resp = client.post("/api/v1/recipes/scan/save", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == 42
        assert data["title"] == "Green Goddess Bowls"

    def test_save_missing_title_rejected(self, override_deps):
        payload = {
            "ingredients": [{"name": "eggs", "qty": "2"}],
            "steps": ["Scramble."],
        }
        resp = client.post("/api/v1/recipes/scan/save", json=payload)
        assert resp.status_code == 422


# ── GET /recipes/user ──────────────────────────────────────────────────────────

class TestUserRecipeEndpoints:
    def test_list_empty(self, override_deps):
        _, store_mock = override_deps
        store_mock.list_user_recipes.return_value = []
        resp = client.get("/api/v1/recipes/user")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_not_found(self, override_deps):
        _, store_mock = override_deps
        store_mock.get_user_recipe.return_value = None
        resp = client.get("/api/v1/recipes/user/999")
        assert resp.status_code == 404

    def test_delete_not_found(self, override_deps):
        _, store_mock = override_deps
        store_mock.delete_user_recipe.return_value = False
        resp = client.delete("/api/v1/recipes/user/999")
        assert resp.status_code == 404
