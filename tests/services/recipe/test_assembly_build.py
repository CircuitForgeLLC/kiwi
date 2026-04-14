"""Tests for Build Your Own recipe assembly schemas."""
import pytest
from app.models.schemas.recipe import (
    AssemblyRoleOut,
    AssemblyTemplateOut,
    RoleCandidateItem,
    RoleCandidatesResponse,
    BuildRequest,
)


def test_assembly_role_out_schema():
    """Test AssemblyRoleOut schema creation and field access."""
    role = AssemblyRoleOut(
        display="protein",
        required=True,
        keywords=["chicken"],
        hint="Main ingredient"
    )
    assert role.display == "protein"
    assert role.required is True
    assert role.keywords == ["chicken"]
    assert role.hint == "Main ingredient"


def test_assembly_template_out_schema():
    """Test AssemblyTemplateOut schema with nested roles."""
    tmpl = AssemblyTemplateOut(
        id="burrito_taco",
        title="Burrito / Taco",
        icon="🌯",
        descriptor="Protein, veg, and sauce in a tortilla or over rice",
        role_sequence=[
            AssemblyRoleOut(
                display="base",
                required=True,
                keywords=["tortilla"],
                hint="The wrap"
            ),
        ],
    )
    assert tmpl.id == "burrito_taco"
    assert tmpl.title == "Burrito / Taco"
    assert tmpl.icon == "🌯"
    assert len(tmpl.role_sequence) == 1
    assert tmpl.role_sequence[0].display == "base"


def test_role_candidate_item_schema():
    """Test RoleCandidateItem schema with tags."""
    item = RoleCandidateItem(
        name="bell pepper",
        in_pantry=True,
        tags=["sweet", "vegetable"]
    )
    assert item.name == "bell pepper"
    assert item.in_pantry is True
    assert "sweet" in item.tags


def test_role_candidates_response_schema():
    """Test RoleCandidatesResponse with compatible and other candidates."""
    resp = RoleCandidatesResponse(
        compatible=[
            RoleCandidateItem(name="bell pepper", in_pantry=True, tags=["sweet"])
        ],
        other=[
            RoleCandidateItem(
                name="corn",
                in_pantry=False,
                tags=["sweet", "starchy"]
            )
        ],
        available_tags=["sweet", "starchy"],
    )
    assert len(resp.compatible) == 1
    assert resp.compatible[0].name == "bell pepper"
    assert len(resp.other) == 1
    assert "sweet" in resp.available_tags
    assert "starchy" in resp.available_tags


def test_build_request_schema():
    """Test BuildRequest schema with template and role overrides."""
    req = BuildRequest(
        template_id="burrito_taco",
        role_overrides={"protein": "chicken", "sauce": "verde"}
    )
    assert req.template_id == "burrito_taco"
    assert req.role_overrides["protein"] == "chicken"
    assert req.role_overrides["sauce"] == "verde"


def test_role_candidates_response_defaults():
    """Test RoleCandidatesResponse with default factory fields."""
    resp = RoleCandidatesResponse()
    assert resp.compatible == []
    assert resp.other == []
    assert resp.available_tags == []


def test_build_request_defaults():
    """Test BuildRequest with default role_overrides."""
    req = BuildRequest(template_id="test_template")
    assert req.template_id == "test_template"
    assert req.role_overrides == {}


def test_get_templates_for_api_returns_13():
    from app.services.recipe.assembly_recipes import get_templates_for_api
    templates = get_templates_for_api()
    assert len(templates) == 13


def test_get_templates_for_api_shape():
    from app.services.recipe.assembly_recipes import get_templates_for_api
    templates = get_templates_for_api()
    t = next(t for t in templates if t["id"] == "burrito_taco")
    assert t["title"] == "Burrito / Taco"
    assert t["icon"] == "🌯"
    assert isinstance(t["role_sequence"], list)
    assert len(t["role_sequence"]) >= 1
    role = t["role_sequence"][0]
    assert "display" in role
    assert "required" in role
    assert "keywords" in role
    assert "hint" in role


def test_get_templates_for_api_all_have_slugs():
    from app.services.recipe.assembly_recipes import get_templates_for_api
    templates = get_templates_for_api()
    slugs = {t["id"] for t in templates}
    assert len(slugs) == 13
    assert all(isinstance(s, str) and len(s) > 3 for s in slugs)


def test_get_role_candidates_splits_compatible_other():
    from app.services.recipe.assembly_recipes import get_role_candidates
    profile_index = {
        "rice": ["Starch", "Structure"],
        "chicken": ["Protein"],
        "broccoli": ["Vegetable"],
    }
    result = get_role_candidates(
        template_slug="stir_fry",
        role_display="protein",
        pantry_set={"rice", "chicken", "broccoli"},
        prior_picks=["rice"],
        profile_index=profile_index,
    )
    assert isinstance(result["compatible"], list)
    assert isinstance(result["other"], list)
    assert isinstance(result["available_tags"], list)
    all_names = [c["name"] for c in result["compatible"] + result["other"]]
    assert "chicken" in all_names


def test_get_role_candidates_available_tags():
    from app.services.recipe.assembly_recipes import get_role_candidates
    profile_index = {
        "chicken": ["Protein", "Umami"],
        "tofu": ["Protein"],
    }
    result = get_role_candidates(
        template_slug="stir_fry",
        role_display="protein",
        pantry_set={"chicken", "tofu"},
        prior_picks=[],
        profile_index=profile_index,
    )
    assert "Protein" in result["available_tags"]


def test_get_role_candidates_unknown_template_returns_empty():
    from app.services.recipe.assembly_recipes import get_role_candidates
    result = get_role_candidates(
        template_slug="nonexistent_template",
        role_display="protein",
        pantry_set={"chicken"},
        prior_picks=[],
        profile_index={},
    )
    assert result == {"compatible": [], "other": [], "available_tags": []}


def test_build_from_selection_returns_recipe():
    from app.services.recipe.assembly_recipes import build_from_selection
    result = build_from_selection(
        template_slug="burrito_taco",
        role_overrides={"tortilla or wrap": "flour tortilla", "protein": "chicken"},
        pantry_set={"flour tortilla", "chicken", "salsa"},
    )
    assert result is not None
    assert len(result.directions) > 0
    assert result.id == -1


def test_build_from_selection_missing_required_role_returns_none():
    from app.services.recipe.assembly_recipes import build_from_selection
    result = build_from_selection(
        template_slug="burrito_taco",
        role_overrides={"protein": "chicken"},
        pantry_set={"chicken"},
    )
    assert result is None


def test_build_from_selection_unknown_template_returns_none():
    from app.services.recipe.assembly_recipes import build_from_selection
    result = build_from_selection(
        template_slug="does_not_exist",
        role_overrides={},
        pantry_set={"chicken"},
    )
    assert result is None
