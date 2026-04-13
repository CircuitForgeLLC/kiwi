# app/services/community/ap_compat.py
# MIT License — AP (ActivityPub) scaffold only (no actor, inbox, outbox)

from __future__ import annotations

from datetime import datetime, timezone


def post_to_ap_json_ld(post: dict, base_url: str) -> dict:
    """Serialize a community post dict to an ActivityPub-compatible JSON-LD Note.

    This is a read-only scaffold. No AP actor, inbox, or outbox is implemented.
    The slug URI is stable so a future full AP implementation can envelope posts
    without a database migration.
    """
    slug = post["slug"]
    published = post.get("published")
    if isinstance(published, datetime):
        published_str = published.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        published_str = str(published)

    dietary_tags: list[str] = post.get("dietary_tags") or []
    tags = [{"type": "Hashtag", "name": "#kiwi"}]
    for tag in dietary_tags:
        tags.append({"type": "Hashtag", "name": f"#{tag.replace('-', '').replace(' ', '')}"})

    return {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Note",
        "id": f"{base_url}/api/v1/community/posts/{slug}",
        "attributedTo": post.get("pseudonym", "anonymous"),
        "content": _build_content(post),
        "published": published_str,
        "tag": tags,
    }


def _build_content(post: dict) -> str:
    title = post.get("title") or "Untitled"
    desc = post.get("description")
    if desc:
        return f"{title} — {desc}"
    return title
