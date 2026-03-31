def test_diff_ingredient_lists():
    from scripts.pipeline.derive_substitutions import diff_ingredients
    base =   ["ground beef", "chicken broth", "olive oil", "onion"]
    target = ["lentils",     "vegetable broth", "olive oil", "onion"]
    removed, added = diff_ingredients(base, target)
    assert "ground beef" in removed
    assert "chicken broth" in removed
    assert "lentils" in added
    assert "vegetable broth" in added
    assert "olive oil" not in removed  # unchanged
