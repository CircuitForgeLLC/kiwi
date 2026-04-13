# app/services/community/feed.py
# MIT License

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring


def posts_to_rss(posts: list[dict], base_url: str) -> str:
    """Generate an RSS 2.0 feed from a list of community post dicts.

    base_url: the root URL of this Kiwi instance (no trailing slash).
    Returns UTF-8 XML string.
    """
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    _sub(channel, "title", "Kiwi Community Feed")
    _sub(channel, "link", f"{base_url}/community")
    _sub(channel, "description", "Meal plans and recipe outcomes from the Kiwi community")
    _sub(channel, "language", "en")
    _sub(channel, "lastBuildDate", format_datetime(datetime.now(timezone.utc)))

    for post in posts:
        item = SubElement(channel, "item")
        _sub(item, "title", post.get("title") or "Untitled")
        _sub(item, "link", f"{base_url}/api/v1/community/posts/{post['slug']}")
        _sub(item, "guid", f"{base_url}/api/v1/community/posts/{post['slug']}")
        if post.get("description"):
            _sub(item, "description", post["description"])
        published = post.get("published")
        if isinstance(published, datetime):
            _sub(item, "pubDate", format_datetime(published))

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="unicode")


def _sub(parent: Element, tag: str, text: str) -> Element:
    el = SubElement(parent, tag)
    el.text = text
    return el
