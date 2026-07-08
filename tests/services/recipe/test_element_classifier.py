import pytest


def test_classify_known_ingredient(store_with_profiles):
    from app.services.recipe.element_classifier import ElementClassifier
    clf = ElementClassifier(store_with_profiles)
    profile = clf.classify("butter")
    assert "Richness" in profile.elements
    assert profile.fat_pct == pytest.approx(81.0)
    assert profile.name == "butter"
    assert profile.source == "db"


def test_classify_unknown_ingredient_uses_heuristic(store_with_profiles):
    from app.services.recipe.element_classifier import ElementClassifier
    clf = ElementClassifier(store_with_profiles)
    profile = clf.classify("ghost pepper hot sauce")
    # Heuristic should detect acid / aroma
    assert "Aroma" in profile.elements  # "pepper" in name matches Aroma heuristic
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
