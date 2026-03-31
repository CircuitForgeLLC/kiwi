from tests.services.recipe.test_element_classifier import store_with_profiles


def test_load_italian_style():
    from app.services.recipe.style_adapter import StyleAdapter
    adapter = StyleAdapter()
    italian = adapter.get("italian")
    assert italian is not None
    assert "basil" in italian.aromatics or "oregano" in italian.aromatics


def test_bias_aroma_toward_style(store_with_profiles):
    from app.services.recipe.style_adapter import StyleAdapter
    adapter = StyleAdapter()
    pantry = ["butter", "parmesan", "basil", "cumin", "soy sauce"]
    biased = adapter.bias_aroma_selection("italian", pantry)
    assert "basil" in biased
    assert "soy sauce" not in biased or "basil" in biased


def test_list_all_styles():
    from app.services.recipe.style_adapter import StyleAdapter
    adapter = StyleAdapter()
    styles = adapter.list_all()
    style_ids = [s.style_id for s in styles]
    assert "italian" in style_ids
    assert "latin" in style_ids
    assert "east_asian" in style_ids
