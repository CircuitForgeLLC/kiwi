"""Discover Purple Carrot's current weekly menu recipe slugs.

The main /plant-based-recipes listing page always renders the current week's
menu as server-side HTML.  This script pulls those slugs and writes them to a
parquet that can be passed directly to scrape_live.py via --slugs-from.

Run weekly (e.g. via cron) to accumulate new recipes as the menu rotates.

Usage:
    conda run -n cf python3 scripts/pipeline/purple_carrot/discover_current_menu.py \
        [--out /Library/Assets/kiwi/pipeline/recipes_purplecarrot_menu.parquet]

Then scrape:
    conda run -n cf python3 scripts/pipeline/purple_carrot/scrape_live.py \
        --slugs-from /Library/Assets/kiwi/pipeline/recipes_purplecarrot_menu.parquet \
        --out /Library/Assets/kiwi/pipeline/recipes_purplecarrot_live.parquet \
        --resume
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ── Config ─────────────────────────────────────────────────────────────────────

LISTING_URL = "https://www.purplecarrot.com/plant-based-recipes"
BASE_URL = "https://www.purplecarrot.com/recipe/{slug}"

DEFAULT_OUT = Path("/Library/Assets/kiwi/pipeline/recipes_purplecarrot_menu.parquet")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

RECIPE_HREF_RE = re.compile(r"/recipe/([^?#]+)")


# ── Main ───────────────────────────────────────────────────────────────────────

def discover_current_slugs() -> list[str]:
    """Fetch the listing page and return unique recipe slugs from the current menu."""
    resp = requests.get(LISTING_URL, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        print(f"ERROR: listing page returned HTTP {resp.status_code}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    slugs: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=RECIPE_HREF_RE):
        m = RECIPE_HREF_RE.search(a["href"])
        if m:
            slug = m.group(1)
            if slug not in seen:
                seen.add(slug)
                slugs.append(slug)
    return slugs


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    print(f"Fetching current menu from {LISTING_URL} …")
    slugs = discover_current_slugs()

    if not slugs:
        print("No slugs found — the listing page may have changed structure or blocked the request.")
        sys.exit(1)

    today = date.today().isoformat()
    records = [
        {
            "Slug": slug,
            "SourceURL": BASE_URL.format(slug=slug),
            "Source": "purplecarrot_menu",
            "DiscoveredDate": today,
        }
        for slug in slugs
    ]

    # Merge with any existing menu parquet (accumulate weeks)
    df_new = pd.DataFrame(records)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    if args.out.exists():
        df_prev = pd.read_parquet(args.out)
        combined = pd.concat([df_prev, df_new], ignore_index=True)
        combined = combined.drop_duplicates(subset=["Slug"], keep="first")
        df_new = combined

    df_new.to_parquet(args.out, index=False)

    print(f"Found {len(slugs)} current-menu slugs this week:")
    for s in slugs:
        print(f"  {s}")
    print(f"\nSaved {len(df_new)} total slugs (accumulated) to {args.out}")
    print("\nTo scrape full recipes:")
    print("  conda run -n cf python3 scripts/pipeline/purple_carrot/scrape_live.py \\")
    print(f"    --slugs-from {args.out} \\")
    print("    --out /Library/Assets/kiwi/pipeline/recipes_purplecarrot_live.parquet \\")
    print("    --resume")


if __name__ == "__main__":
    main()
