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
