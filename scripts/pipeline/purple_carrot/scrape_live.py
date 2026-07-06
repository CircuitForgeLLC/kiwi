"""Playwright scraper for live purplecarrot.com recipe pages.

Uses the slug inventory already in recipes_purplecarrot.parquet and fills in
the missing ingredients/instructions by hitting the live site directly.

Usage:
    conda run -n cf python3 scripts/pipeline/purple_carrot/scrape_live.py \
        [--out /Library/Assets/kiwi/pipeline/recipes_purplecarrot_live.parquet] \
        [--delay 2.5] \
        [--limit 20]
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PWTimeout

# ── Config ─────────────────────────────────────────────────────────────────────

BASE_URL = "https://www.purplecarrot.com/recipe/{slug}"
DEFAULT_OUT = Path("/Library/Assets/kiwi/pipeline/recipes_purplecarrot_live.parquet")
EXISTING_PARQUET = Path("/Library/Assets/kiwi/pipeline/recipes_purplecarrot.parquet")

RENDER_WAIT_MS = 2500   # JS render settle time
NAV_TIMEOUT_MS = 20_000


# ── Page parser ────────────────────────────────────────────────────────────────

def _text(page: Page, selector: str) -> str:
    el = page.query_selector(selector)
    return el.inner_text().strip() if el else ""


def _texts(page: Page, selector: str) -> list[str]:
    return [el.inner_text().strip() for el in page.query_selector_all(selector)]


def _parse_recipe(page: Page, slug: str, source_url: str) -> dict[str, Any] | None:
    """Extract structured recipe data from the rendered page."""
    body = page.inner_text("body")

    # Abort if we've been bounced to a generic listing / 404
    if "Page Not Found" in body or slug not in page.url:
        return None

    # ── Title ──────────────────────────────────────────────────────────────────
    # The <h1> on product pages tends to be the recipe name
    title = (_text(page, "h1") or _text(page, "[class*='recipe-title']")).strip()
    if not title:
        # Fallback: first heading-like text before "Ingredients"
        idx = body.find("Ingredients\n")
        title = body[:idx].strip().splitlines()[-1] if idx > 0 else ""

    # ── Ingredients / Instructions via body text ───────────────────────────────
    ing_start = body.find("\nIngredients\n")
    inst_start = body.find("\nInstructions\n")
    footer_start = body.find("\nShop\n")   # footer sentinel

    if ing_start == -1:
        return None   # page didn't render recipe content

    raw_ingredients: list[str] = []
    raw_instructions: list[str] = []

    if ing_start != -1 and inst_start != -1:
        ing_block = body[ing_start + len("\nIngredients\n"):inst_start].strip()
        raw_ingredients = [l.strip() for l in ing_block.splitlines() if l.strip()]

    if inst_start != -1:
        end = footer_start if footer_start > inst_start else len(body)
        inst_block = body[inst_start + len("\nInstructions\n"):end].strip()
        # Steps start with a digit
        steps: list[str] = []
        current: list[str] = []
        for line in inst_block.splitlines():
            line = line.strip()
            if not line:
                continue
            if re.match(r"^\d+$", line):
                if current:
                    steps.append(" ".join(current))
                current = []
            elif line.startswith("CULINARY NOTES"):
                break
            else:
                current.append(line)
        if current:
            steps.append(" ".join(current))
        raw_instructions = steps

    # ── Nutrition ──────────────────────────────────────────────────────────────
    def _extract_num(pattern: str) -> float | None:
        m = re.search(pattern, body)
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None

    cal   = _extract_num(r"(\d+)\s*CAL")
    fat   = _extract_num(r"(\d+(?:\.\d+)?)g\s*FAT")
    carbs = _extract_num(r"(\d+(?:\.\d+)?)g\s*CARBS")
    prot  = _extract_num(r"(\d+(?:\.\d+)?)g\s*PROTEIN")
    fiber = _extract_num(r"(\d+(?:\.\d+)?)g\s*FIBER")

    # ── Allergens / tags ───────────────────────────────────────────────────────
    allergen_m = re.search(r"Allergens?:\s*([^\n]+)", body)
    allergens = allergen_m.group(1).strip() if allergen_m else ""

    # Feature tags like HIGH-PROTEIN, QUICK, etc. appear before Ingredients
    pre_ing = body[:ing_start]
    tags = re.findall(r"\b(HIGH-PROTEIN|QUICK|SPICY|LOW[\-\s]CALORIE|VEGAN|FAMILY\s+FRIENDLY)\b", pre_ing)

    return {
        "Slug": slug,
        "Name": title,
        "SourceURL": source_url,
        "Source": "purplecarrot_live",
        "RecipeIngredientParts": raw_ingredients,
        "RecipeInstructions": raw_instructions,
        "Calories": cal,
        "FatContent": fat,
        "CarbohydrateContent": carbs,
        "ProteinContent": prot,
        "FiberContent": fiber,
        "Allergens": allergens,
        "Keywords": tags,
        "HasFullRecipe": bool(raw_ingredients and raw_instructions),
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--delay", type=float, default=2.5,
                        help="Seconds between requests (be polite)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Stop after N slugs (0 = all)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip slugs already present in --out")
    parser.add_argument("--slugs-from", type=Path, default=None,
                        help="Read slug inventory from this parquet instead of the default Wayback one")
    args = parser.parse_args()

    # Load slug inventory — either from a custom parquet or the default Wayback run
    slugs_parquet = args.slugs_from if args.slugs_from else EXISTING_PARQUET
    df_existing = pd.read_parquet(slugs_parquet)
    slugs = df_existing["Slug"].dropna().unique().tolist()
    # source_urls may not be present in custom parcets — fall back to constructing from slug
    if "SourceURL" in df_existing.columns:
        source_urls = dict(zip(df_existing["Slug"], df_existing["SourceURL"]))
    else:
        source_urls = {s: BASE_URL.format(slug=s) for s in slugs}

    # Resume support
    done_slugs: set[str] = set()
    if args.resume and args.out.exists():
        df_done = pd.read_parquet(args.out)
        done_slugs = set(df_done["Slug"].dropna().tolist())
        print(f"Resuming — {len(done_slugs)} slugs already scraped")

    if args.limit:
        slugs = slugs[: args.limit]

    results: list[dict[str, Any]] = []
    skipped = 0
    failed = 0

    _UA = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for i, slug in enumerate(slugs):
            if slug in done_slugs:
                skipped += 1
                continue

            url = BASE_URL.format(slug=slug)
            print(f"[{i+1}/{len(slugs)}] {slug} … ", end="", flush=True)

            # Use a fresh browser context per slug to avoid Cloudflare session-level
            # bot detection, which fires on the 2nd+ request in the same context.
            context = browser.new_context(
                user_agent=_UA,
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()

            try:
                page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
                page.wait_for_timeout(RENDER_WAIT_MS)
                recipe = _parse_recipe(page, slug, source_urls.get(slug, url))
            except PWTimeout:
                print("TIMEOUT")
                failed += 1
            except Exception as exc:
                print(f"ERROR: {exc}")
                failed += 1
            else:
                if recipe is None:
                    print("no content (404 or redirect)")
                    failed += 1
                elif recipe["HasFullRecipe"]:
                    n = len(recipe["RecipeIngredientParts"])
                    s = len(recipe["RecipeInstructions"])
                    print(f"OK  ({n} ingredients, {s} steps)")
                    results.append(recipe)
                else:
                    print(f"partial (ings={len(recipe['RecipeIngredientParts'])}, steps={len(recipe['RecipeInstructions'])})")
                    results.append(recipe)
            finally:
                context.close()

            time.sleep(args.delay)

        browser.close()

    print(f"\nDone — {len(results)} scraped, {skipped} skipped, {failed} failed")

    if results:
        df_out = pd.DataFrame(results)
        # Merge with existing metadata (nutrition stubs, wayback fields) for slugs
        # that didn't previously have full data
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.resume and args.out.exists():
            df_prev = pd.read_parquet(args.out)
            df_out = pd.concat([df_prev, df_out], ignore_index=True)
            df_out = df_out.drop_duplicates(subset=["Slug"], keep="last")
        df_out.to_parquet(args.out, index=False)
        full_count = df_out["HasFullRecipe"].sum() if "HasFullRecipe" in df_out.columns else "?"
        print(f"Saved {len(df_out)} rows to {args.out}  ({full_count} with full recipes)")
    else:
        print("No results — output not written")


if __name__ == "__main__":
    main()
