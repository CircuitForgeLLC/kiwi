# app/api/endpoints/community.py
# MIT License

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.cloud_session import CloudUser, get_session
from app.core.config import settings
from app.db.store import Store
from app.services.community.feed import posts_to_rss

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/community", tags=["community"])

_community_store = None


def _get_community_store():
    return _community_store


def init_community_store(community_db_url: str | None) -> None:
    global _community_store
    if not community_db_url:
        logger.info(
            "COMMUNITY_DB_URL not set — community write features disabled. "
            "Browse still works via cloud feed."
        )
        return
    from circuitforge_core.community import CommunityDB
    from app.services.community.community_store import KiwiCommunityStore
    db = CommunityDB(dsn=community_db_url)
    db.run_migrations()
    _community_store = KiwiCommunityStore(db)
    logger.info("Community store initialized.")


def _visible(post, session=None) -> bool:
    """Return False for premium-tier posts when the session is not paid/premium."""
    tier = getattr(post, "tier", None)
    if tier == "premium":
        if session is None or getattr(session, "tier", None) not in ("paid", "premium"):
            return False
    return True


@router.get("/posts")
async def list_posts(
    post_type: str | None = None,
    dietary_tags: str | None = None,
    allergen_exclude: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    store = _get_community_store()
    if store is None:
        return {"posts": [], "total": 0, "note": "Community DB not available on this instance."}

    dietary = [t.strip() for t in dietary_tags.split(",")] if dietary_tags else None
    allergen_ex = [t.strip() for t in allergen_exclude.split(",")] if allergen_exclude else None
    offset = (page - 1) * min(page_size, 100)

    posts = await asyncio.to_thread(
        store.list_posts,
        limit=min(page_size, 100),
        offset=offset,
        post_type=post_type,
        dietary_tags=dietary,
        allergen_exclude=allergen_ex,
    )
    return {"posts": [_post_to_dict(p) for p in posts if _visible(p)], "page": page, "page_size": page_size}


@router.get("/posts/{slug}")
async def get_post(slug: str, request: Request):
    store = _get_community_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Community DB not available on this instance.")

    post = await asyncio.to_thread(store.get_post_by_slug, slug)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")

    accept = request.headers.get("accept", "")
    if "application/activity+json" in accept or "application/ld+json" in accept:
        from app.services.community.ap_compat import post_to_ap_json_ld
        base_url = str(request.base_url).rstrip("/")
        return post_to_ap_json_ld(_post_to_dict(post), base_url=base_url)

    return _post_to_dict(post)


@router.get("/feed.rss")
async def get_rss_feed(request: Request):
    store = _get_community_store()
    posts_data: list[dict] = []
    if store is not None:
        posts = await asyncio.to_thread(store.list_posts, limit=50)
        posts_data = [_post_to_dict(p) for p in posts]

    base_url = str(request.base_url).rstrip("/")
    rss = posts_to_rss(posts_data, base_url=base_url)
    return Response(content=rss, media_type="application/rss+xml; charset=utf-8")


@router.get("/local-feed")
async def local_feed():
    store = _get_community_store()
    if store is None:
        return []
    posts = await asyncio.to_thread(store.list_posts, limit=50)
    return [_post_to_dict(p) for p in posts]


@router.post("/posts", status_code=201)
async def publish_post(body: dict, session: CloudUser = Depends(get_session)):
    from app.tiers import can_use
    if not can_use("community_publish", session.tier, session.has_byok):
        raise HTTPException(status_code=402, detail="Community publishing requires Paid tier.")

    store = _get_community_store()
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="This Kiwi instance is not connected to a community database. "
                   "Publishing is only available on cloud instances.",
        )

    from app.services.community.community_store import get_or_create_pseudonym
    def _get_pseudonym():
        s = Store(session.db)
        try:
            return get_or_create_pseudonym(
                store=s,
                directus_user_id=session.user_id,
                requested_name=body.get("pseudonym_name"),
            )
        finally:
            s.close()
    pseudonym = await asyncio.to_thread(_get_pseudonym)

    recipe_ids = [slot["recipe_id"] for slot in body.get("slots", []) if slot.get("recipe_id")]
    from app.services.community.element_snapshot import compute_snapshot
    def _snapshot():
        s = Store(session.db)
        try:
            return compute_snapshot(recipe_ids=recipe_ids, store=s)
        finally:
            s.close()
    snapshot = await asyncio.to_thread(_snapshot)

    slug_title = re.sub(r"[^a-z0-9]+", "-", (body.get("title") or "plan").lower()).strip("-")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = f"kiwi-{_post_type_prefix(body.get('post_type', 'plan'))}-{pseudonym.lower().replace(' ', '')}-{today}-{slug_title}"[:120]

    from circuitforge_core.community.models import CommunityPost
    post = CommunityPost(
        slug=slug,
        pseudonym=pseudonym,
        post_type=body.get("post_type", "plan"),
        published=datetime.now(timezone.utc),
        title=body.get("title", "Untitled"),
        description=body.get("description"),
        photo_url=body.get("photo_url"),
        slots=body.get("slots", []),
        recipe_id=body.get("recipe_id"),
        recipe_name=body.get("recipe_name"),
        level=body.get("level"),
        outcome_notes=body.get("outcome_notes"),
        seasoning_score=snapshot.seasoning_score,
        richness_score=snapshot.richness_score,
        brightness_score=snapshot.brightness_score,
        depth_score=snapshot.depth_score,
        aroma_score=snapshot.aroma_score,
        structure_score=snapshot.structure_score,
        texture_profile=snapshot.texture_profile,
        dietary_tags=list(snapshot.dietary_tags),
        allergen_flags=list(snapshot.allergen_flags),
        flavor_molecules=list(snapshot.flavor_molecules),
        fat_pct=snapshot.fat_pct,
        protein_pct=snapshot.protein_pct,
        moisture_pct=snapshot.moisture_pct,
    )

    inserted = await asyncio.to_thread(store.insert_post, post)
    return _post_to_dict(inserted)


@router.delete("/posts/{slug}", status_code=204)
async def delete_post(slug: str, session: CloudUser = Depends(get_session)):
    store = _get_community_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Community DB not available.")

    def _get_pseudonym():
        s = Store(session.db)
        try:
            return s.get_current_pseudonym(session.user_id)
        finally:
            s.close()
    pseudonym = await asyncio.to_thread(_get_pseudonym)
    if not pseudonym:
        raise HTTPException(status_code=400, detail="No pseudonym set. Cannot delete posts.")

    deleted = await asyncio.to_thread(store.delete_post, slug=slug, pseudonym=pseudonym)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found or you are not the author.")


@router.post("/posts/{slug}/fork", status_code=201)
async def fork_post(slug: str, session: CloudUser = Depends(get_session)):
    store = _get_community_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Community DB not available.")

    post = await asyncio.to_thread(store.get_post_by_slug, slug)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found.")
    if post.post_type != "plan":
        raise HTTPException(status_code=400, detail="Only plan posts can be forked as a meal plan.")

    from datetime import date
    week_start = date.today().strftime("%Y-%m-%d")

    def _create_plan():
        s = Store(session.db)
        try:
            meal_types = list({slot["meal_type"] for slot in post.slots})
            plan = s.create_meal_plan(week_start=week_start, meal_types=meal_types or ["dinner"])
            for slot in post.slots:
                s.assign_recipe_to_slot(
                    plan_id=plan["id"],
                    day_of_week=slot["day"],
                    meal_type=slot["meal_type"],
                    recipe_id=slot["recipe_id"],
                )
            return plan
        finally:
            s.close()

    plan = await asyncio.to_thread(_create_plan)
    return {"plan_id": plan["id"], "week_start": plan["week_start"], "forked_from": slug}


@router.post("/posts/{slug}/fork-adapt", status_code=201)
async def fork_adapt_post(slug: str, session: CloudUser = Depends(get_session)):
    from app.tiers import can_use
    if not can_use("community_fork_adapt", session.tier, session.has_byok):
        raise HTTPException(status_code=402, detail="Fork with adaptation requires Paid tier or BYOK.")
    # Stub: full LLM adaptation deferred
    raise HTTPException(status_code=501, detail="Fork-adapt not yet implemented.")


def _post_to_dict(post) -> dict:
    return {
        "slug": post.slug,
        "pseudonym": post.pseudonym,
        "post_type": post.post_type,
        "published": post.published.isoformat() if hasattr(post.published, "isoformat") else str(post.published),
        "title": post.title,
        "description": post.description,
        "photo_url": post.photo_url,
        "slots": list(post.slots),
        "recipe_id": post.recipe_id,
        "recipe_name": post.recipe_name,
        "level": post.level,
        "outcome_notes": post.outcome_notes,
        "element_profiles": {
            "seasoning_score": post.seasoning_score,
            "richness_score": post.richness_score,
            "brightness_score": post.brightness_score,
            "depth_score": post.depth_score,
            "aroma_score": post.aroma_score,
            "structure_score": post.structure_score,
            "texture_profile": post.texture_profile,
        },
        "dietary_tags": list(post.dietary_tags),
        "allergen_flags": list(post.allergen_flags),
        "flavor_molecules": list(post.flavor_molecules),
        "fat_pct": post.fat_pct,
        "protein_pct": post.protein_pct,
        "moisture_pct": post.moisture_pct,
    }


def _post_type_prefix(post_type: str) -> str:
    return {"plan": "plan", "recipe_success": "success", "recipe_blooper": "blooper"}.get(post_type, "post")
