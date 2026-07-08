"""Shared pytest fixtures for kiwi test suite."""
import json

import pytest

from app.db.store import Store


@pytest.fixture
def store_with_profiles(tmp_path):
    db_path = tmp_path / "test.db"
    store = Store(db_path)
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


@pytest.fixture
def store_with_recipes(store_with_profiles):
    store_with_profiles.conn.executemany("""
        INSERT INTO recipes (external_id, title, ingredients, ingredient_names,
                             directions, category, keywords, element_coverage)
        VALUES (?,?,?,?,?,?,?,?)
    """, [
        ("1", "Butter Pasta", '["butter","pasta","parmesan"]',
         '["butter","pasta","parmesan"]', '["boil pasta","toss with butter"]',
         "Italian", '["quick","pasta"]',
         '{"Richness":0.5,"Depth":0.3,"Structure":0.2}'),
        ("2", "Lentil Soup", '["lentils","carrots","onion","broth"]',
         '["lentils","carrots","onion","broth"]', '["simmer all"]',
         "Soup", '["vegan","hearty"]',
         '{"Depth":0.4,"Seasoning":0.3}'),
    ])
    store_with_profiles.conn.commit()
    return store_with_profiles
