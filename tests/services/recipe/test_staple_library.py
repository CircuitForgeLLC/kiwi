def test_seitan_staple_has_yield_formats():
    from app.services.recipe.staple_library import StapleLibrary
    lib = StapleLibrary()
    seitan = lib.get("seitan")
    assert seitan is not None
    assert "fresh" in seitan.yield_formats
    assert "frozen" in seitan.yield_formats


def test_staple_yield_format_has_elements():
    from app.services.recipe.staple_library import StapleLibrary
    lib = StapleLibrary()
    seitan = lib.get("seitan")
    fresh = seitan.yield_formats["fresh"]
    assert "Structure" in fresh["elements"]


def test_list_all_staples():
    from app.services.recipe.staple_library import StapleLibrary
    lib = StapleLibrary()
    all_staples = lib.list_all()
    slugs = [s.slug for s in all_staples]
    assert "seitan" in slugs
    assert "tempeh" in slugs


def test_tofu_firm_is_loadable():
    from app.services.recipe.staple_library import StapleLibrary
    lib = StapleLibrary()
    tofu = lib.get("tofu_firm")
    assert tofu is not None
    assert tofu.slug == "tofu_firm"


def test_filter_by_dietary_vegan():
    from app.services.recipe.staple_library import StapleLibrary
    lib = StapleLibrary()
    vegan = lib.filter_by_dietary("vegan")
    assert len(vegan) > 0
    assert all("vegan" in s.dietary_labels for s in vegan)


def test_list_all_returns_all_three():
    from app.services.recipe.staple_library import StapleLibrary
    lib = StapleLibrary()
    all_staples = lib.list_all()
    slugs = {s.slug for s in all_staples}
    assert {"seitan", "tempeh", "tofu_firm"} == slugs
