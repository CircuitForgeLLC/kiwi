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


def test_get_element_profiles_returns_known_items(store_with_profiles):
    profiles = store_with_profiles.get_element_profiles(["butter", "parmesan", "unknown_item"])
    assert profiles["butter"] == ["Richness"]
    assert "Depth" in profiles["parmesan"]
    assert "unknown_item" not in profiles


def test_get_element_profiles_empty_list(store_with_profiles):
    profiles = store_with_profiles.get_element_profiles([])
    assert profiles == {}
