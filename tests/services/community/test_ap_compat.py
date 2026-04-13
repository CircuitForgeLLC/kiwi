# tests/services/community/test_ap_compat.py
import pytest
from datetime import datetime, timezone
from app.services.community.ap_compat import post_to_ap_json_ld


POST = {
    "slug": "kiwi-plan-test-pasta-week",
    "title": "Pasta Week",
    "description": "Seven days of carbs",
    "published": datetime(2026, 4, 12, 12, 0, 0, tzinfo=timezone.utc),
    "pseudonym": "PastaWitch",
    "dietary_tags": ["vegetarian"],
}


def test_ap_json_ld_context():
    doc = post_to_ap_json_ld(POST, base_url="https://menagerie.circuitforge.tech/kiwi")
    assert doc["@context"] == "https://www.w3.org/ns/activitystreams"


def test_ap_json_ld_type():
    doc = post_to_ap_json_ld(POST, base_url="https://menagerie.circuitforge.tech/kiwi")
    assert doc["type"] == "Note"


def test_ap_json_ld_id_is_uri():
    doc = post_to_ap_json_ld(POST, base_url="https://menagerie.circuitforge.tech/kiwi")
    assert doc["id"].startswith("https://")
    assert POST["slug"] in doc["id"]


def test_ap_json_ld_published_is_iso8601():
    doc = post_to_ap_json_ld(POST, base_url="https://menagerie.circuitforge.tech/kiwi")
    from datetime import datetime
    datetime.fromisoformat(doc["published"].replace("Z", "+00:00"))


def test_ap_json_ld_attributed_to_pseudonym():
    doc = post_to_ap_json_ld(POST, base_url="https://menagerie.circuitforge.tech/kiwi")
    assert doc["attributedTo"] == "PastaWitch"


def test_ap_json_ld_tags_include_kiwi():
    doc = post_to_ap_json_ld(POST, base_url="https://menagerie.circuitforge.tech/kiwi")
    tag_names = [t["name"] for t in doc.get("tag", [])]
    assert "#kiwi" in tag_names
