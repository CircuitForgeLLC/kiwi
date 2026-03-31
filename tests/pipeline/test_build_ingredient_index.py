import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))

def test_normalize_ingredient_name():
    from scripts.pipeline.build_ingredient_index import normalize_name
    assert normalize_name("Ground Beef (85% lean)") == "ground beef"
    assert normalize_name("  Olive Oil  ") == "olive oil"
    assert normalize_name("Cheddar Cheese, shredded") == "cheddar cheese"

def test_derive_elements_from_usda_row():
    from scripts.pipeline.build_ingredient_index import derive_elements
    row = {"fat_pct": 20.0, "protein_pct": 17.0, "moisture_pct": 60.0,
           "sodium_mg_per_100g": 65.0, "glutamate_mg": 2.8, "starch_pct": 0.0}
    elements = derive_elements(row)
    assert "Richness" in elements   # high fat
    assert "Depth" in elements      # notable glutamate

def test_derive_binding_score():
    from scripts.pipeline.build_ingredient_index import derive_binding_score
    assert derive_binding_score({"protein_pct": 12.0, "starch_pct": 68.0}) == 3  # flour
    assert derive_binding_score({"protein_pct": 1.0, "starch_pct": 0.5}) == 0   # water
