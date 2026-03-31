import json, pytest
from tests.services.recipe.test_element_classifier import store_with_profiles


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


def test_search_recipes_by_ingredient_names(store_with_recipes):
    results = store_with_recipes.search_recipes_by_ingredients(["butter", "parmesan"])
    assert len(results) >= 1
    assert any(r["title"] == "Butter Pasta" for r in results)

def test_search_recipes_respects_limit(store_with_recipes):
    results = store_with_recipes.search_recipes_by_ingredients(["butter"], limit=1)
    assert len(results) <= 1

def test_check_rate_limit_first_call(store_with_recipes):
    allowed, count = store_with_recipes.check_and_increment_rate_limit("leftover_mode", daily_max=5)
    assert allowed is True
    assert count == 1

def test_check_rate_limit_exceeded(store_with_recipes):
    for _ in range(5):
        store_with_recipes.check_and_increment_rate_limit("leftover_mode", daily_max=5)
    allowed, count = store_with_recipes.check_and_increment_rate_limit("leftover_mode", daily_max=5)
    assert allowed is False
    assert count == 5
