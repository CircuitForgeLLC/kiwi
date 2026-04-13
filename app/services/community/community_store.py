# app/services/community/community_store.py
# MIT License

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_or_create_pseudonym(
    store,
    directus_user_id: str,
    requested_name: str | None,
) -> str:
    """Return the user's current pseudonym, creating it if it doesn't exist.

    If the user has an existing pseudonym, return it (ignore requested_name).
    If not, create using requested_name (must be provided for first-time setup).

    Raises ValueError if no existing pseudonym and requested_name is None or blank.
    """
    existing = store.get_current_pseudonym(directus_user_id)
    if existing:
        return existing

    if not requested_name or not requested_name.strip():
        raise ValueError(
            "A pseudonym is required for first publish. "
            "Pass requested_name with your chosen display name."
        )

    name = requested_name.strip()
    if "@" in name:
        raise ValueError(
            "Pseudonym must not contain '@' — use a display name, not an email address."
        )

    store.set_pseudonym(directus_user_id, name)
    return name


try:
    from circuitforge_core.community import SharedStore, CommunityPost

    class KiwiCommunityStore(SharedStore):
        """Kiwi-specific community store: adds kiwi-domain query methods on top of SharedStore."""

        def list_meal_plans(
            self,
            limit: int = 20,
            offset: int = 0,
            dietary_tags: list[str] | None = None,
            allergen_exclude: list[str] | None = None,
        ) -> list[CommunityPost]:
            return self.list_posts(
                limit=limit,
                offset=offset,
                post_type="plan",
                dietary_tags=dietary_tags,
                allergen_exclude=allergen_exclude,
                source_product="kiwi",
            )

        def list_outcomes(
            self,
            limit: int = 20,
            offset: int = 0,
            post_type: str | None = None,
        ) -> list[CommunityPost]:
            if post_type in ("recipe_success", "recipe_blooper"):
                return self.list_posts(
                    limit=limit, offset=offset,
                    post_type=post_type, source_product="kiwi",
                )
            # Fetch both types and merge by published date
            success = self.list_posts(
                limit=limit, offset=0, post_type="recipe_success", source_product="kiwi",
            )
            bloopers = self.list_posts(
                limit=limit, offset=0, post_type="recipe_blooper", source_product="kiwi",
            )
            merged = sorted(success + bloopers, key=lambda p: p.published, reverse=True)
            return merged[:limit]

except ImportError:
    # cf-core community module not yet merged — stub for local dev without community DB
    class KiwiCommunityStore:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass

        def list_meal_plans(self, **kwargs):
            return []

        def list_outcomes(self, **kwargs):
            return []

        def list_posts(self, **kwargs):
            return []

        def get_post_by_slug(self, slug):
            return None

        def insert_post(self, post):
            return post

        def delete_post(self, slug, pseudonym):
            return False
