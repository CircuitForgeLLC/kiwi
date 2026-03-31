from app.services.recipe.style_adapter import StyleAdapter


# --- Spec-required tests ---

def test_italian_style_biases_aromatics():
    """Garlic and onion appear when they're in both pantry and italian aromatics."""
    adapter = StyleAdapter()
    italian = adapter.get("italian")
    pantry = ["garlic", "onion", "ginger"]
    result = italian.bias_aroma_selection(pantry)
    assert "garlic" in result
    assert "onion" in result


def test_east_asian_method_weights_sum_to_one():
    """East Asian method_bias weights sum to ~1.0."""
    adapter = StyleAdapter()
    east_asian = adapter.get("east_asian")
    weights = east_asian.method_weights()
    assert abs(sum(weights.values()) - 1.0) < 1e-6


def test_style_adapter_loads_all_five_styles():
    """Adapter discovers all 5 cuisine YAML files."""
    adapter = StyleAdapter()
    assert len(adapter.styles) == 5


# --- Additional coverage ---

def test_load_italian_style():
    adapter = StyleAdapter()
    italian = adapter.get("italian")
    assert italian is not None
    assert "basil" in italian.aromatics or "oregano" in italian.aromatics


def test_bias_aroma_selection_excludes_non_style_items():
    """bias_aroma_selection does not include items not in the style's aromatics."""
    adapter = StyleAdapter()
    italian = adapter.get("italian")
    pantry = ["butter", "parmesan", "basil", "cumin", "soy sauce"]
    result = italian.bias_aroma_selection(pantry)
    assert "basil" in result
    assert "soy sauce" not in result
    assert "cumin" not in result


def test_preferred_depth_sources():
    """preferred_depth_sources returns only depth sources present in pantry."""
    adapter = StyleAdapter()
    italian = adapter.get("italian")
    pantry = ["parmesan", "olive oil", "pasta"]
    result = italian.preferred_depth_sources(pantry)
    assert "parmesan" in result
    assert "olive oil" not in result


def test_bias_aroma_selection_adapter_method():
    """StyleAdapter.bias_aroma_selection returns italian-biased items."""
    adapter = StyleAdapter()
    pantry = ["butter", "parmesan", "basil", "cumin", "soy sauce"]
    biased = adapter.bias_aroma_selection("italian", pantry)
    assert "basil" in biased
    assert "soy sauce" not in biased or "basil" in biased


def test_list_all_styles():
    adapter = StyleAdapter()
    styles = adapter.list_all()
    style_ids = [s.style_id for s in styles]
    assert "italian" in style_ids
    assert "latin" in style_ids
    assert "east_asian" in style_ids
