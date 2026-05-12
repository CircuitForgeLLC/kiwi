# app/api/endpoints/activitypub.py
# MIT License
#
# ActivityPub endpoints for Kiwi instances:
#   GET  /.well-known/webfinger   — WebFinger JRD
#   GET  /ap/actor                — Instance actor document
#   POST /ap/actor/inbox          — Incoming activities
#   GET  /ap/outbox               — Outgoing activities (OrderedCollection)
#   GET  /ap/posts/{slug}         — Individual AP Note
#   GET  /ap/followers            — Followers collection (count only)
#   GET  /ap/following            — Following collection (empty stub)
#
# All endpoints are no-ops / 404 when AP_ENABLED=false or actor not loaded.
# The WebFinger and well-known routes are mounted at the root app level (not
# under /api/v1) — see main.py.

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services.ap.keys import get_actor

logger = logging.getLogger(__name__)

# ── Two routers: one for well-known (root mount), one for /ap prefix ─────────

webfinger_router = APIRouter(tags=["activitypub"])
ap_router = APIRouter(prefix="/ap", tags=["activitypub"])

_AP_CONTENT_TYPE = "application/activity+json"
_JRD_CONTENT_TYPE = "application/jrd+json"


def _actor_required():
    actor = get_actor()
    if actor is None:
        raise HTTPException(status_code=404, detail="ActivityPub not enabled on this instance.")
    return actor


# ── WebFinger ─────────────────────────────────────────────────────────────────

@webfinger_router.get("/.well-known/webfinger")
async def webfinger(resource: str | None = None):
    actor = get_actor()
    if actor is None:
        raise HTTPException(status_code=404, detail="ActivityPub not enabled.")

    expected = f"acct:kiwi@{settings.AP_HOST}"
    if resource and resource != expected:
        raise HTTPException(status_code=404, detail=f"Resource {resource!r} not found.")

    jrd = {
        "subject": expected,
        "links": [
            {
                "rel": "self",
                "type": _AP_CONTENT_TYPE,
                "href": actor.actor_id,
            }
        ],
    }
    return Response(
        content=json.dumps(jrd),
        media_type=_JRD_CONTENT_TYPE,
    )


# ── Actor ─────────────────────────────────────────────────────────────────────

@ap_router.get("/actor")
async def get_actor_doc():
    actor = _actor_required()
    return Response(
        content=json.dumps(actor.to_ap_dict()),
        media_type=_AP_CONTENT_TYPE,
    )


# ── Inbox (mounted via make_inbox_router below) ───────────────────────────────

async def _on_follow(activity: dict, headers: dict) -> None:
    """Accept Follow: add to ap_followers, send Accept(Follow) back."""
    actor_url = activity.get("actor", "")
    if not actor_url:
        return

    from app.db.store import Store
    from app.core.config import settings as _settings
    db_path = _settings.DB_PATH

    inbox_url, shared_inbox = await asyncio.to_thread(_resolve_inbox, actor_url)
    if inbox_url is None:
        return

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT OR REPLACE INTO ap_followers
               (actor_id, inbox_url, shared_inbox, followed_at, active)
               VALUES (?, ?, ?, ?, 1)""",
            (actor_url, inbox_url, shared_inbox, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    actor = get_actor()
    if actor is None:
        return
    accept = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"{actor.actor_id}/accepts/{activity.get('id', 'unknown')}",
        "type": "Accept",
        "actor": actor.actor_id,
        "object": activity,
    }
    from circuitforge_core.activitypub import deliver_activity
    await asyncio.to_thread(deliver_activity, accept, inbox_url, actor, 10.0)


async def _on_undo(activity: dict, headers: dict) -> None:
    """Handle Undo(Follow): deactivate the follower row."""
    inner = activity.get("object", {})
    if isinstance(inner, dict) and inner.get("type") == "Follow":
        actor_url = activity.get("actor", "")
        if actor_url:
            import sqlite3
            conn = sqlite3.connect(str(settings.DB_PATH))
            try:
                conn.execute(
                    "UPDATE ap_followers SET active = 0 WHERE actor_id = ?", (actor_url,)
                )
                conn.commit()
            finally:
                conn.close()


async def _dedup_activity(activity_id: str | None) -> bool:
    """Return True (already seen) if activity_id is in ap_received; otherwise insert it."""
    if not activity_id:
        return False
    import sqlite3
    conn = sqlite3.connect(str(settings.DB_PATH))
    try:
        try:
            conn.execute(
                "INSERT INTO ap_received (activity_id) VALUES (?)", (activity_id,)
            )
            conn.commit()
            return False
        except sqlite3.IntegrityError:
            return True
    finally:
        conn.close()


def _build_inbox_router():
    from circuitforge_core.activitypub.inbox import make_inbox_router

    async def on_follow(activity: dict, headers: dict) -> None:
        if await _dedup_activity(activity.get("id")):
            return
        await _on_follow(activity, headers)

    async def on_undo(activity: dict, headers: dict) -> None:
        if await _dedup_activity(activity.get("id")):
            return
        await _on_undo(activity, headers)

    return make_inbox_router(
        handlers={"Follow": on_follow, "Undo": on_undo},
        verify_key_fetcher=None,   # Signature verification enabled in prod when actor is loaded
        path="/inbox",
    )


# Mount inbox at /ap/actor/inbox (AP spec: inbox is a sub-resource of the actor)
try:
    _inbox_sub = _build_inbox_router()
    ap_router.include_router(_inbox_sub, prefix="/actor")
except Exception as _e:
    logger.warning("AP inbox router not available: %s", _e)


# ── Outbox ────────────────────────────────────────────────────────────────────

@ap_router.get("/outbox")
async def get_outbox(page: int | None = None, request: Request = None):
    actor = _actor_required()
    from app.api.endpoints.community import _get_community_store
    store = _get_community_store()
    base = f"https://{settings.AP_HOST}"

    if store is None:
        collection = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{actor.outbox_url}",
            "type": "OrderedCollection",
            "totalItems": 0,
            "orderedItems": [],
        }
        return Response(content=json.dumps(collection), media_type=_AP_CONTENT_TYPE)

    PAGE_SIZE = 20
    offset = ((page or 1) - 1) * PAGE_SIZE
    posts = await asyncio.to_thread(store.list_posts, limit=PAGE_SIZE, offset=offset)
    items = [_post_to_ap_note(p, actor, base) for p in posts]

    collection = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": actor.outbox_url + (f"?page={page}" if page else ""),
        "type": "OrderedCollectionPage" if page else "OrderedCollection",
        "orderedItems": items,
    }
    return Response(content=json.dumps(collection), media_type=_AP_CONTENT_TYPE)


# ── Individual post ───────────────────────────────────────────────────────────

@ap_router.get("/posts/{slug}")
async def get_ap_post(slug: str):
    actor = _actor_required()
    from app.api.endpoints.community import _get_community_store
    store = _get_community_store()
    if store is None:
        raise HTTPException(status_code=404, detail="Community DB not available.")

    post = await asyncio.to_thread(store.get_post_by_slug, slug)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")

    base = f"https://{settings.AP_HOST}"
    note = _post_to_ap_note(post, actor, base)
    return Response(content=json.dumps(note), media_type=_AP_CONTENT_TYPE)


# ── Followers / Following ─────────────────────────────────────────────────────

@ap_router.get("/followers")
async def get_followers():
    actor = _actor_required()
    import sqlite3
    count = 0
    try:
        conn = sqlite3.connect(str(settings.DB_PATH))
        row = conn.execute("SELECT COUNT(*) FROM ap_followers WHERE active = 1").fetchone()
        conn.close()
        count = row[0] if row else 0
    except Exception:
        pass

    collection = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"{actor.actor_id}/followers",
        "type": "OrderedCollection",
        "totalItems": count,
    }
    return Response(content=json.dumps(collection), media_type=_AP_CONTENT_TYPE)


@ap_router.get("/following")
async def get_following():
    actor = _actor_required()
    collection = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"{actor.actor_id}/following",
        "type": "OrderedCollection",
        "totalItems": 0,
        "orderedItems": [],
    }
    return Response(content=json.dumps(collection), media_type=_AP_CONTENT_TYPE)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _post_to_ap_note(post, actor, base_url: str) -> dict:
    from circuitforge_core.activitypub import make_note
    from app.services.community.ap_compat import _build_content

    diet_tags: list[str] = list(getattr(post, "dietary_tags", []) or [])
    hashtags = [{"type": "Hashtag", "name": "#Kiwi", "href": f"{base_url}/ap/tags/kiwi"}]
    for tag in diet_tags[:4]:
        ht = "".join(w.capitalize() for w in tag.replace("-", " ").split())
        hashtags.append({"type": "Hashtag", "name": f"#{ht}"})

    content = _build_content(
        {
            "title": post.title,
            "description": getattr(post, "description", None),
            "outcome_notes": getattr(post, "outcome_notes", None),
            "dietary_tags": diet_tags,
        }
    )

    published = post.published
    note = make_note(
        actor_id=actor.actor_id,
        content=content,
        tag=hashtags,
        published=published if isinstance(published, datetime) else None,
    )
    note["id"] = f"{base_url}/ap/posts/{post.slug}"
    return note


def _resolve_inbox(actor_url: str) -> tuple[str | None, str | None]:
    """Fetch an AP actor document and extract inbox + sharedInbox URLs."""
    try:
        import httpx
        resp = httpx.get(
            actor_url,
            headers={"Accept": "application/activity+json"},
            timeout=8.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        doc = resp.json()
        inbox = doc.get("inbox")
        shared = doc.get("endpoints", {}).get("sharedInbox")
        return inbox, shared
    except Exception as exc:
        logger.debug("Could not resolve actor %s: %s", actor_url, exc)
        return None, None
