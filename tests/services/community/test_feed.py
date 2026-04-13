# tests/services/community/test_feed.py
import pytest
from datetime import datetime, timezone
from app.services.community.feed import posts_to_rss


def make_post_dict(**kwargs):
    defaults = dict(
        slug="kiwi-plan-test-pasta-week",
        title="Pasta Week",
        description="Seven days of carbs",
        published=datetime(2026, 4, 12, 12, 0, 0, tzinfo=timezone.utc),
        post_type="plan",
        pseudonym="PastaWitch",
    )
    defaults.update(kwargs)
    return defaults


def test_rss_is_valid_xml():
    import xml.etree.ElementTree as ET
    rss = posts_to_rss([make_post_dict()], base_url="https://menagerie.circuitforge.tech/kiwi")
    root = ET.fromstring(rss)
    assert root.tag == "rss"
    assert root.attrib.get("version") == "2.0"


def test_rss_contains_item():
    import xml.etree.ElementTree as ET
    rss = posts_to_rss([make_post_dict()], base_url="https://menagerie.circuitforge.tech/kiwi")
    root = ET.fromstring(rss)
    items = root.findall(".//item")
    assert len(items) == 1


def test_rss_item_has_required_fields():
    import xml.etree.ElementTree as ET
    rss = posts_to_rss([make_post_dict()], base_url="https://menagerie.circuitforge.tech/kiwi")
    root = ET.fromstring(rss)
    item = root.find(".//item")
    assert item.find("title") is not None
    assert item.find("link") is not None
    assert item.find("pubDate") is not None


def test_rss_empty_posts():
    import xml.etree.ElementTree as ET
    rss = posts_to_rss([], base_url="https://menagerie.circuitforge.tech/kiwi")
    root = ET.fromstring(rss)
    items = root.findall(".//item")
    assert len(items) == 0
