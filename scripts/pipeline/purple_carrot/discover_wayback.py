"""
discover_wayback.py — enumerate Purple Carrot recipe slugs via the Wayback Machine.

Strategy:
  1. CDX API  → all archived /api/v2/menus/* URLs (multiple timestamps)
  2. Replay   → fetch each menu's menuItems, extract productPath slugs
  3. CDX API  → all archived /api/v1/products/* URLs (direct slug capture)
  4. CDX API  → /recipe-categories/* HTML pages for older slugs
  5. Deduplicate and write manifest to OUT_FILE

Output (JSONL, one record per recipe):
  {"slug": "...", "title": "...", "subtitle": "...", "cook_time": "...",
   "tags": [...], "serving_size": 2, "image_url": "...",
   "wayback_ts": "20260412150557", "source": "menu|product_api|category_page"}

Usage:
  conda run -n cf python -m scripts.pipeline.purple_carrot.discover_wayback
  conda run -n cf python -m scripts.pipeline.purple_carrot.discover_wayback --out /Library/Assets/kiwi/pipeline/pc_slugs.jsonl
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

CDX_BASE = "https://web.archive.org/cdx/search/cdx"
WB_BASE = "https://web.archive.org/web"
PC_HOST = "www.purplecarrot.com"

# Polite delay between Wayback replay fetches (seconds)
REPLAY_DELAY = 1.0
CDX_DELAY = 0.5

DEFAULT_OUT = Path("/Library/Assets/kiwi/pipeline/pc_slugs.jsonl")


# ── CDX helpers ───────────────────────────────────────────────────────────────

def cdx_query(url_pattern: str, **kwargs) -> list[dict]:
    """Run a CDX search and return a list of result dicts."""
    params = {
        "url": url_pattern,
        "output": "json",
        "fl": "original,timestamp,statuscode",
        "collapse": "urlkey",
        "filter": "statuscode:200",
        **kwargs,
    }
    for attempt in range(3):
        try:
            resp = requests.get(CDX_BASE, params=params, timeout=30)
            resp.raise_for_status()
            rows = resp.json()
            if not rows or len(rows) < 2:
                return []
            headers = rows[0]
            return [dict(zip(headers, row)) for row in rows[1:]]
        except Exception as exc:
            logger.warning("CDX attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2 ** attempt)
    return []


def wayback_get(url: str, timestamp: str) -> Any | None:
    """Fetch a Wayback replay of a URL and return parsed JSON (or None)."""
    replay_url = f"{WB_BASE}/{timestamp}/{url}"
    for attempt in range(3):
        try:
            resp = requests.get(replay_url, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                return None
        except Exception as exc:
            logger.warning("Wayback GET attempt %d failed for %s: %s", attempt + 1, url, exc)
        time.sleep(2 ** attempt)
    return None


# ── Slug extraction ───────────────────────────────────────────────────────────

def slug_from_product_path(path: str) -> str | None:
    """'/recipe/foo-bar-baz' → 'foo-bar-baz'."""
    if not path:
        return None
    return path.strip("/").split("/")[-1] or None


def _menu_item_to_record(item: dict, wayback_ts: str) -> dict | None:
    slug = slug_from_product_path(item.get("productPath", ""))
    if not slug:
        return None
    return {
        "slug": slug,
        "title": item.get("title", ""),
        "subtitle": item.get("subtitle", ""),
        "cook_time": item.get("cookTime", ""),
        "tags": item.get("filterTags") or [],
        "serving_size": item.get("servingSize"),
        "image_url": item.get("imageURL", ""),
        "description": item.get("description", ""),
        "wayback_ts": wayback_ts,
        "source": "menu",
    }


# ── Discovery passes ──────────────────────────────────────────────────────────

def pass_menus(seen_slugs: set[str]) -> list[dict]:
    """Walk all archived /api/v2/menus/* captures to extract slugs."""
    records: list[dict] = []

    # Find all distinct archived menu URLs
    menu_cdx = cdx_query(f"{PC_HOST}/api/v2/menus/*", limit="500")
    logger.info("CDX: %d archived menu URLs found", len(menu_cdx))
    time.sleep(CDX_DELAY)

    processed_menu_ids: set[str] = set()

    for entry in menu_cdx:
        url = entry["original"]
        ts = entry["timestamp"]

        # Skip the listing endpoint, only process individual menus
        if not url.split("?")[0].rstrip("/").split("/")[-1].isdigit():
            continue

        menu_id = url.split("?")[0].rstrip("/").split("/")[-1]
        if menu_id in processed_menu_ids:
            continue
        processed_menu_ids.add(menu_id)

        logger.info("Fetching menu %s (ts=%s) ...", menu_id, ts)
        data = wayback_get(url.split("?")[0] + "?logged_out=true", ts)
        time.sleep(REPLAY_DELAY)

        if not data or "menuItems" not in data:
            continue

        for item in data["menuItems"]:
            rec = _menu_item_to_record(item, ts)
            if rec and rec["slug"] not in seen_slugs:
                seen_slugs.add(rec["slug"])
                records.append(rec)
                logger.debug("  + %s", rec["slug"])

        logger.info("  %d new slugs (total so far: %d)", len(records), len(seen_slugs))

    return records


def pass_product_api(seen_slugs: set[str]) -> list[dict]:
    """Pick up any directly archived /api/v1/products/* URLs the menu pass missed."""
    records: list[dict] = []

    product_cdx = cdx_query(f"{PC_HOST}/api/v1/products/*", limit="5000")
    logger.info("CDX: %d archived product API URLs found", len(product_cdx))
    time.sleep(CDX_DELAY)

    for entry in product_cdx:
        slug = entry["original"].rstrip("/").split("/")[-1]
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        records.append({
            "slug": slug,
            "title": "",
            "subtitle": "",
            "cook_time": "",
            "tags": [],
            "serving_size": None,
            "image_url": "",
            "description": "",
            "wayback_ts": entry["timestamp"],
            "source": "product_api",
        })

    logger.info("product_api pass: %d new slugs", len(records))
    return records


def pass_category_pages(seen_slugs: set[str]) -> list[dict]:
    """Parse archived recipe-categories HTML pages for slugs not in the API.

    Category pages are rendered SSR/with inline JSON state on older captures,
    so we do a simple regex scan for /recipe/<slug> patterns.
    """
    import re

    records: list[dict] = []
    SLUG_RE = re.compile(r'["\s]/recipe/([a-z0-9][a-z0-9\-]{3,})["\s/?]')

    cat_cdx = cdx_query(f"{PC_HOST}/recipe-categories/*", limit="200")
    logger.info("CDX: %d archived category pages found", len(cat_cdx))
    time.sleep(CDX_DELAY)

    seen_category_urls: set[str] = set()

    for entry in cat_cdx:
        url = entry["original"].split("?")[0]
        if url in seen_category_urls:
            continue
        seen_category_urls.add(url)

        replay_url = f"{WB_BASE}/{entry['timestamp']}/{url}"
        try:
            resp = requests.get(replay_url, timeout=30)
            time.sleep(REPLAY_DELAY)
            if resp.status_code != 200:
                continue
        except Exception as exc:
            logger.warning("Category page fetch failed: %s", exc)
            continue

        for slug in SLUG_RE.findall(resp.text):
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            records.append({
                "slug": slug,
                "title": "",
                "subtitle": "",
                "cook_time": "",
                "tags": [],
                "serving_size": None,
                "image_url": "",
                "description": "",
                "wayback_ts": entry["timestamp"],
                "source": "category_page",
            })

    logger.info("category_pages pass: %d new slugs", len(records))
    return records


# ── Main ──────────────────────────────────────────────────────────────────────

def discover(out_file: Path) -> None:
    seen: set[str] = set()

    # Load previously discovered slugs so reruns are incremental
    existing: list[dict] = []
    if out_file.exists():
        with open(out_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    seen.add(rec["slug"])
                    existing.append(rec)
        logger.info("Loaded %d existing slugs from %s", len(seen), out_file)

    new_records: list[dict] = []
    new_records += pass_menus(seen)
    new_records += pass_product_api(seen)
    new_records += pass_category_pages(seen)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "a") as f:
        for rec in new_records:
            f.write(json.dumps(rec) + "\n")

    total = len(existing) + len(new_records)
    logger.info(
        "Done. %d new slugs written to %s (%d total).",
        len(new_records), out_file, total,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Purple Carrot recipe slugs via Wayback")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output JSONL manifest (default: {DEFAULT_OUT})",
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from scripts.pipeline.log_utils import attach_pipeline_log
    attach_pipeline_log("discover_wayback")

    discover(args.out)


if __name__ == "__main__":
    main()
