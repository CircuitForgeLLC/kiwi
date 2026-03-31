import json, pytest
from tests.services.recipe.test_element_classifier import store_with_profiles


@pytest.fixture
def store_with_subs(store_with_profiles):
    store_with_profiles.conn.execute("""
        INSERT INTO substitution_pairs
          (original_name, substitute_name, constraint_label,
           fat_delta, moisture_delta, glutamate_delta, protein_delta, occurrence_count)
        VALUES (?,?,?,?,?,?,?,?)
    """, ("butter", "coconut oil", "vegan", -1.0, 0.0, 0.0, 0.0, 15))
    store_with_profiles.conn.execute("""
        INSERT INTO substitution_pairs
          (original_name, substitute_name, constraint_label,
           fat_delta, moisture_delta, glutamate_delta, protein_delta, occurrence_count)
        VALUES (?,?,?,?,?,?,?,?)
    """, ("ground beef", "lentils", "vegan", -15.0, 10.0, -2.0, 5.0, 45))
    store_with_profiles.conn.commit()
    return store_with_profiles


def test_find_substitutes_for_constraint(store_with_subs):
    from app.services.recipe.substitution_engine import SubstitutionEngine
    engine = SubstitutionEngine(store_with_subs)
    results = engine.find_substitutes("butter", constraint="vegan")
    assert len(results) > 0
    assert results[0].substitute_name == "coconut oil"


def test_compensation_hints_for_large_delta(store_with_subs):
    from app.services.recipe.substitution_engine import SubstitutionEngine
    engine = SubstitutionEngine(store_with_subs)
    results = engine.find_substitutes("ground beef", constraint="vegan")
    assert len(results) > 0
    swap = results[0]
    # Fat delta is -15g — should suggest a Richness compensation
    assert any(h["element"] == "Richness" for h in swap.compensation_hints)


def test_no_substitutes_returns_empty(store_with_subs):
    from app.services.recipe.substitution_engine import SubstitutionEngine
    engine = SubstitutionEngine(store_with_subs)
    results = engine.find_substitutes("unobtainium", constraint="vegan")
    assert results == []
