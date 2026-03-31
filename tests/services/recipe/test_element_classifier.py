import pytest
import sqlite3
import json
import tempfile
from pathlib import Path

from app.db.store import Store


@pytest.fixture
def store_with_profiles(tmp_path):
    db_path = tmp_path / "test.db"
    store = Store(db_path)
    # Seed ingredient_profiles
    store.conn.execute("""
        INSERT INTO ingredient_profiles
          (name, elements, fat_pct, moisture_pct, glutamate_mg, binding_score,
           sodium_mg_per_100g, is_fermented, texture_profile)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, ("butter", json.dumps(["Richness"]), 81.0, 16.0, 0.1, 0, 11.0, 0, "creamy"))
    store.conn.execute("""
        INSERT INTO ingredient_profiles
          (name, elements, fat_pct, moisture_pct, glutamate_mg, binding_score,
           sodium_mg_per_100g, is_fermented, texture_profile)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, ("parmesan", json.dumps(["Depth", "Seasoning"]), 29.0, 29.0, 1.2, 1, 1600.0, 0, "neutral"))
    store.conn.commit()
    return store


def test_classify_known_ingredient(store_with_profiles):
    from app.services.recipe.element_classifier import ElementClassifier
    clf = ElementClassifier(store_with_profiles)
    profile = clf.classify("butter")
    assert "Richness" in profile.elements
    assert profile.fat_pct == pytest.approx(81.0)
    assert profile.name == "butter"


def test_classify_unknown_ingredient_uses_heuristic(store_with_profiles):
    from app.services.recipe.element_classifier import ElementClassifier
    clf = ElementClassifier(store_with_profiles)
    profile = clf.classify("ghost pepper hot sauce")
    # Heuristic should detect acid / aroma
    assert len(profile.elements) > 0
    assert profile.name == "ghost pepper hot sauce"


def test_classify_batch(store_with_profiles):
    from app.services.recipe.element_classifier import ElementClassifier
    clf = ElementClassifier(store_with_profiles)
    results = clf.classify_batch(["butter", "parmesan", "unknown herb"])
    assert len(results) == 3
    assert results[0].name == "butter"
    assert results[1].name == "parmesan"


def test_identify_gaps(store_with_profiles):
    from app.services.recipe.element_classifier import ElementClassifier
    clf = ElementClassifier(store_with_profiles)
    profiles = [
        clf.classify("butter"),
        clf.classify("parmesan"),
    ]
    gaps = clf.identify_gaps(profiles)
    # We have Richness + Depth + Seasoning; should flag Brightness, Aroma, Structure, Texture
    assert "Brightness" in gaps
    assert "Richness" not in gaps
