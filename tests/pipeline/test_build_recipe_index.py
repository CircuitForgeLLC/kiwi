def test_extract_ingredient_names():
    from scripts.pipeline.build_recipe_index import extract_ingredient_names
    raw = ["2 cups all-purpose flour", "1 lb ground beef (85/15)", "salt to taste"]
    names = extract_ingredient_names(raw)
    assert "flour" in names or "all-purpose flour" in names
    assert "ground beef" in names
    assert "salt" in names

def test_compute_element_coverage():
    from scripts.pipeline.build_recipe_index import compute_element_coverage
    profiles = [
        {"elements": ["Richness", "Depth"]},
        {"elements": ["Brightness"]},
        {"elements": ["Seasoning"]},
    ]
    coverage = compute_element_coverage(profiles)
    assert coverage["Richness"] > 0
    assert coverage["Brightness"] > 0
    assert coverage.get("Aroma", 0) == 0
