"""Tests for captured_products store methods (kiwi#79)."""
import pytest
from pathlib import Path
from app.db.store import Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "test.db")
    yield s
    s.close()


class TestMigration:
    def test_captured_products_table_exists(self, store):
        cur = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='captured_products'"
        )
        assert cur.fetchone() is not None

    def test_captured_products_columns(self, store):
        cur = store.conn.execute("PRAGMA table_info(captured_products)")
        # PRAGMA returns plain tuples: (cid, name, type, notnull, dflt_value, pk)
        cols = {row[1] for row in cur.fetchall()}
        expected = {
            "id", "barcode", "product_name", "brand", "serving_size_g",
            "calories", "fat_g", "saturated_fat_g", "carbs_g", "sugar_g",
            "fiber_g", "protein_g", "sodium_mg", "ingredient_names",
            "allergens", "confidence", "source", "captured_at",
            "confirmed_by_user",
        }
        assert expected.issubset(cols)


class TestGetCapturedProduct:
    def test_returns_none_for_unknown_barcode(self, store):
        assert store.get_captured_product("0000000000000") is None

    def test_returns_row_after_save(self, store):
        store.save_captured_product("1234567890123", product_name="Test Crackers")
        result = store.get_captured_product("1234567890123")
        assert result is not None
        assert result["product_name"] == "Test Crackers"

    def test_ingredient_names_decoded_as_list(self, store):
        store.save_captured_product(
            "1111111111111",
            ingredient_names=["wheat flour", "salt"],
        )
        result = store.get_captured_product("1111111111111")
        assert result["ingredient_names"] == ["wheat flour", "salt"]

    def test_allergens_decoded_as_list(self, store):
        store.save_captured_product(
            "2222222222222",
            allergens=["wheat", "milk"],
        )
        result = store.get_captured_product("2222222222222")
        assert result["allergens"] == ["wheat", "milk"]


class TestSaveCapturedProduct:
    def test_all_nutrition_fields_persisted(self, store):
        store.save_captured_product(
            "3333333333333",
            product_name="Oat Crackers",
            brand="TestBrand",
            serving_size_g=30.0,
            calories=120.0,
            fat_g=4.0,
            saturated_fat_g=0.5,
            carbs_g=20.0,
            sugar_g=2.0,
            fiber_g=1.0,
            protein_g=3.0,
            sodium_mg=200.0,
            confidence=0.92,
        )
        row = store.get_captured_product("3333333333333")
        assert row["brand"] == "TestBrand"
        assert row["calories"] == 120.0
        assert row["protein_g"] == 3.0
        assert row["confidence"] == 0.92

    def test_confirmed_by_user_defaults_true(self, store):
        store.save_captured_product("4444444444444")
        row = store.get_captured_product("4444444444444")
        assert row["confirmed_by_user"] == 1

    def test_confirmed_by_user_false(self, store):
        store.save_captured_product("5555555555555", confirmed_by_user=False)
        row = store.get_captured_product("5555555555555")
        assert row["confirmed_by_user"] == 0

    def test_upsert_on_conflict(self, store):
        """Second save for same barcode updates in-place rather than erroring."""
        store.save_captured_product("6666666666666", product_name="Old Name")
        store.save_captured_product("6666666666666", product_name="New Name")
        row = store.get_captured_product("6666666666666")
        assert row["product_name"] == "New Name"
        # Still only one row
        cur = store.conn.execute(
            "SELECT count(*) FROM captured_products WHERE barcode='6666666666666'"
        )
        assert cur.fetchone()[0] == 1

    def test_empty_lists_stored_and_retrieved(self, store):
        store.save_captured_product("7777777777777", ingredient_names=[], allergens=[])
        row = store.get_captured_product("7777777777777")
        assert row["ingredient_names"] == []
        assert row["allergens"] == []

    def test_source_default(self, store):
        store.save_captured_product("8888888888888")
        row = store.get_captured_product("8888888888888")
        assert row["source"] == "visual_capture"
