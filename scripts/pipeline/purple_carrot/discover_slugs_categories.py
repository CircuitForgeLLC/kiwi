"""Discover Purple Carrot recipe slugs by crawling all recipe-category listing pages.

The site serves full server-rendered HTML for category pages, paginated via
?page=N.  Each page loads 18 recipe cards.  This script crawls every category
across all pages and writes a deduplicated slug inventory.

Usage:
    conda run -n cf python3 scripts/pipeline/purple_carrot/discover_slugs_categories.py \
        [--out /Library/Assets/kiwi/pipeline/recipes_purplecarrot_slugs.parquet] \
        [--delay 2.0] \
        [--max-pages 50]   # safety cap per category (comfort-foods has ~18)
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ── Config ─────────────────────────────────────────────────────────────────────

BASE = "https://www.purplecarrot.com"

# All known category slugs (from /plant-based-recipes nav)
CATEGORIES: list[str] = [
    "comfort-foods",
    "family-friendly",
    "healthy-desserts",
    "holiday-recipes",
    "quick-and-easy",
    "party-foods",
    "seasonal-menu",
    "spring-recipes",
    "summer-recipes",
    "fall-recipes",
    "winter-recipes",
    "african",
    "american",
    "asian",
    "comfort",
    "french",
    "indian",
    "italian",
    "mediterranean",
    "mexican",
    "middle-eastern",
    "soups",
    "salads",
    "bowls",
    "pasta",
    "sandwiches-wraps",
    "tacos",
    "breakfast",
    "snacks-sides",
]

DEFAULT_OUT = Path("/Library/Assets/kiwi/pipeline/recipes_purplecarrot_slugs.parquet")
EXISTING_PARQUET = Path("/Library/Assets/kiwi/pipeline/recipes_purplecarrot.parquet")

RECIPE_LINK_SELECTOR = "a.c-recipe__title"
SLUG_RE = re.compile(r"/recipe/([^?#]+)")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fetch_html(url: str, session: requests.Session) -> str | None:
    """Fetch URL and return HTML string, or None on failure."""
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.text
        if resp.status_code == 404:
            return None   # expected end of pagination
        print(f"  HTTP {resp.status_code} — {url}")
        return None
    except Exception as exc:
        print(f"  ERROR fetching {url}: {exc}")
        return None


def _extract_slugs(html: str) -> list[str]:
    """Pull recipe slugs from one listing-page HTML response."""
    soup = BeautifulSoup(html, "html.parser")
    slugs: list[str] = []
    for a in soup.select(RECIPE_LINK_SELECTOR):
        href = a.get("href", "")
        m = SLUG_RE.search(href)
        if m:
            slugs.append(m.group(1))
    return slugs


def _get_category_total(html: str) -> int | None:
    """Try to parse the recipe count shown on the category page (e.g. '319 Recipes')."""
    m = re.search(r"(\d+)\s+Recipes?\b", html)
    return int(m.group(1)) if m else None


def _discover_category(
    category: str,
    session: requests.Session,
    delay: float,
    max_pages: int,
) -> tuple[list[str], int]:
    """Crawl all pages of a category, return (slugs, pages_fetched)."""
    slugs: list[str] = []
    for page_num in range(1, max_pages + 1):
        if page_num == 1:
            url = f"{BASE}/recipe-categories/{category}"
        else:
            url = f"{BASE}/recipe-categories/{category}?page={page_num}"

        html = _fetch_html(url, session)
        if html is None:
            break   # 404 or error = past the end

        page_slugs = _extract_slugs(html)
        if not page_slugs:
            # Show total if we got a page but no links (category slug may be wrong)
            if page_num == 1:
                total = _get_category_total(html)
                if total is not None:
                    print(f"  page 1 loaded (total={total}) but 0 recipe links — selector may need updating")
            break

        slugs.extend(page_slugs)

        # Print progress
        total_hint = _get_category_total(html) if page_num == 1 else None
        total_str = f" / {total_hint}" if total_hint else ""
        print(f"  page {page_num}: +{len(page_slugs)} slugs ({len(slugs)}{total_str} cumulative)")

        if len(page_slugs) < 18:
            # Short page = last page
            break

        time.sleep(delay)

    return slugs, (len(slugs) + 17) // 18  # approximate pages


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Seconds between page requests")
    parser.add_argument("--max-pages", type=int, default=50,
                        help="Safety cap on pages per category")
    parser.add_argument("--categories", nargs="*",
                        help="Crawl only these category slugs (default: all)")
    args = parser.parse_args()

    categories = args.categories or CATEGORIES

    # Seed with any slugs from the Wayback parquet
    known_slugs: set[str] = set()
    if EXISTING_PARQUET.exists():
        df_wb = pd.read_parquet(EXISTING_PARQUET)
        known_slugs = set(df_wb["Slug"].dropna().tolist())
        print(f"Seeded with {len(known_slugs)} slugs from Wayback parquet")

    all_records: list[dict[str, Any]] = []
    session = requests.Session()

    for category in categories:
        print(f"\n[{category}]")
        cat_slugs, pages = _discover_category(category, session, args.delay, args.max_pages)
        for slug in cat_slugs:
            all_records.append({"Slug": slug, "Category": category, "Source": "purplecarrot_category"})
        print(f"  → {len(cat_slugs)} slugs across ~{pages} pages")
        time.sleep(args.delay)

    if not all_records:
        print("\nNo records found — check that categories are correct and the site is accessible")
        return

    # Deduplicate keeping first category encountered
    df_new = pd.DataFrame(all_records)
    df_new = df_new.drop_duplicates(subset=["Slug"], keep="first")

    # Also include Wayback slugs not already in the new set
    if known_slugs:
        wb_only = known_slugs - set(df_new["Slug"].tolist())
        if wb_only:
            df_wb_extra = pd.DataFrame([
                {"Slug": s, "Category": "wayback", "Source": "purplecarrot_wayback"}
                for s in wb_only
            ])
            df_new = pd.concat([df_new, df_wb_extra], ignore_index=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df_new.to_parquet(args.out, index=False)

    new_count = len(df_new)
    cat_count = len(df_new[df_new["Source"] == "purplecarrot_category"])
    print(f"\nDone — {new_count} total slugs saved to {args.out}")
    print(f"  {cat_count} from category pages, {new_count - cat_count} from Wayback only")


if __name__ == "__main__":
    main()
