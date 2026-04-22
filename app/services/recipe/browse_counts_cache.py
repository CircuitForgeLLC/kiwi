"""
Browse counts cache — pre-computes and persists recipe counts for all
browse domain keyword sets so category/subcategory page loads never
hit the 3.8 GB FTS index at request time.

Counts change only when the corpus changes (after a pipeline run).
The cache is a small SQLite file separate from both the read-only
corpus DB and per-user kiwi.db files, so the container can write it.

Refresh triggers:
  1. Startup     — if cache is missing or older than STALE_DAYS
  2. Nightly     — asyncio background task started in main.py lifespan
  3. Pipeline    — infer_recipe_tags.py calls refresh() at end of run

The in-memory _COUNT_CACHE in store.py is pre-warmed from this file
on startup, so FTS queries are never needed for known keyword sets.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

STALE_DAYS = 7


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _kw_key(keywords: list[str]) -> str:
    """Stable string key for a keyword list — sorted and pipe-joined."""
    return "|".join(sorted(keywords))


def _fts_match_expr(keywords: list[str]) -> str:
    phrases = ['"' + kw.replace('"', '""') + '"' for kw in keywords]
    return " OR ".join(phrases)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS browse_counts (
            keywords_key  TEXT PRIMARY KEY,
            count         INTEGER NOT NULL,
            computed_at   TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS browse_counts_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_stale(cache_path: Path, max_age_days: int = STALE_DAYS) -> bool:
    """Return True if the cache is missing, empty, or older than max_age_days."""
    if not cache_path.exists():
        return True
    try:
        conn = sqlite3.connect(cache_path)
        row = conn.execute(
            "SELECT value FROM browse_counts_meta WHERE key = 'refreshed_at'"
        ).fetchone()
        conn.close()
        if row is None:
            return True
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(row[0])).days
        return age >= max_age_days
    except Exception:
        return True


def load_into_memory(cache_path: Path, count_cache: dict, corpus_path: str) -> int:
    """
    Load all rows from the cache file into the in-memory count_cache dict.

    Uses corpus_path (the current RECIPE_DB_PATH env value) as the cache key,
    not what was stored in the file — the file may have been built against a
    different mount path (e.g. pipeline ran on host, container sees a different
    path). Counts are corpus-content-derived and path-independent.

    Returns the number of entries loaded.
    """
    if not cache_path.exists():
        return 0
    try:
        conn = sqlite3.connect(cache_path)
        rows = conn.execute("SELECT keywords_key, count FROM browse_counts").fetchall()
        conn.close()
        loaded = 0
        for kw_key, count in rows:
            keywords = kw_key.split("|") if kw_key else []
            cache_key = (corpus_path, *sorted(keywords))
            count_cache[cache_key] = count
            loaded += 1
        logger.info("browse_counts: warmed %d entries from %s", loaded, cache_path)
        return loaded
    except Exception as exc:
        logger.warning("browse_counts: load failed: %s", exc)
        return 0


def refresh(corpus_path: str, cache_path: Path) -> int:
    """
    Run FTS5 queries for every keyword set in browser_domains.DOMAINS
    and write results to cache_path.

    Safe to call from both the host pipeline script and the in-container
    nightly task. The corpus_path must be reachable and readable from
    the calling process.

    Returns the number of keyword sets computed.
    """
    from app.services.recipe.browser_domains import DOMAINS  # local import — avoid circular

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_conn = sqlite3.connect(cache_path)
    _ensure_schema(cache_conn)

    # Collect every unique keyword list across all domains/categories/subcategories.
    # DOMAINS structure: {domain: {label: str, categories: {cat_name: {keywords, subcategories}}}}
    seen: dict[str, list[str]] = {}
    for domain_data in DOMAINS.values():
        for cat_data in domain_data.get("categories", {}).values():
            if not isinstance(cat_data, dict):
                continue
            top_kws = cat_data.get("keywords", [])
            if top_kws:
                seen[_kw_key(top_kws)] = top_kws
            for subcat_kws in cat_data.get("subcategories", {}).values():
                if subcat_kws:
                    seen[_kw_key(subcat_kws)] = subcat_kws

    try:
        corpus_conn = sqlite3.connect(f"file:{corpus_path}?mode=ro", uri=True)
    except Exception as exc:
        logger.error("browse_counts: cannot open corpus %s: %s", corpus_path, exc)
        cache_conn.close()
        return 0

    now = datetime.now(timezone.utc).isoformat()
    computed = 0

    try:
        for kw_key, kws in seen.items():
            try:
                row = corpus_conn.execute(
                    "SELECT count(*) FROM recipe_browser_fts WHERE recipe_browser_fts MATCH ?",
                    (_fts_match_expr(kws),),
                ).fetchone()
                count = row[0] if row else 0
                cache_conn.execute(
                    "INSERT OR REPLACE INTO browse_counts (keywords_key, count, computed_at)"
                    " VALUES (?, ?, ?)",
                    (kw_key, count, now),
                )
                computed += 1
            except Exception as exc:
                logger.warning("browse_counts: query failed key=%r: %s", kw_key[:60], exc)

        # Merge accepted community tags into counts.
        # For each (domain, category, subcategory) that has accepted community
        # tags, add the count of distinct tagged recipe_ids to the FTS count.
        # The two overlap rarely (community tags exist precisely because FTS
        # missed those recipes), so simple addition is accurate enough.
        try:
            _merge_community_tag_counts(cache_conn, DOMAINS, now)
        except Exception as exc:
            logger.warning("browse_counts: community merge skipped: %s", exc)

        cache_conn.execute(
            "INSERT OR REPLACE INTO browse_counts_meta (key, value) VALUES ('refreshed_at', ?)",
            (now,),
        )
        cache_conn.execute(
            "INSERT OR REPLACE INTO browse_counts_meta (key, value) VALUES ('corpus_path', ?)",
            (corpus_path,),
        )
        cache_conn.commit()
        logger.info("browse_counts: wrote %d counts → %s", computed, cache_path)
    finally:
        corpus_conn.close()
        cache_conn.close()

    return computed


def _merge_community_tag_counts(
    cache_conn: sqlite3.Connection,
    domains: dict,
    now: str,
    threshold: int = 2,
) -> None:
    """Add accepted community tag counts on top of FTS counts in the cache.

    Queries the community PostgreSQL store (if available) for accepted tags
    grouped by (domain, category, subcategory), maps each back to its keyword
    set key, then increments the cached count.

    Silently skips if community features are unavailable.
    """
    try:
        from app.api.endpoints.community import _get_community_store
        store = _get_community_store()
        if store is None:
            return
    except Exception:
        return

    for domain_id, domain_data in domains.items():
        for cat_name, cat_data in domain_data.get("categories", {}).items():
            if not isinstance(cat_data, dict):
                continue
            # Check subcategories
            for subcat_name, subcat_kws in cat_data.get("subcategories", {}).items():
                if not subcat_kws:
                    continue
                ids = store.get_accepted_recipe_ids_for_subcategory(
                    domain=domain_id,
                    category=cat_name,
                    subcategory=subcat_name,
                    threshold=threshold,
                )
                if not ids:
                    continue
                kw_key = _kw_key(subcat_kws)
                cache_conn.execute(
                    "UPDATE browse_counts SET count = count + ? WHERE keywords_key = ?",
                    (len(ids), kw_key),
                )
            # Check category-level tags (subcategory IS NULL)
            top_kws = cat_data.get("keywords", [])
            if top_kws:
                ids = store.get_accepted_recipe_ids_for_subcategory(
                    domain=domain_id,
                    category=cat_name,
                    subcategory=None,
                    threshold=threshold,
                )
                if ids:
                    kw_key = _kw_key(top_kws)
                    cache_conn.execute(
                        "UPDATE browse_counts SET count = count + ? WHERE keywords_key = ?",
                        (len(ids), kw_key),
                    )
    logger.info("browse_counts: community tag counts merged")
