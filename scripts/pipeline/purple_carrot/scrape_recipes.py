"""
scrape_recipes.py — fetch full recipe data for slugs in pc_slugs.jsonl.

For each slug:
  1. Try Wayback /api/v1/products/<slug> — oldest capture first (pre-HelloFresh
     acquisition data is more complete).
  2. If instructions are empty, try the recipe HTML page via Wayback and parse
     inline JSON state or structured markup.
  3. Merge with metadata already in the manifest (title, tags, cook_time, etc.)
  4. Emit one row per recipe to recipes_purplecarrot.parquet in food.com columnar
     format so build_recipe_index.py can import it unchanged.

Output columns (food.com schema + PC extras ignored by the indexer):
  RecipeId, Name, Subtitle, RecipeIngredientParts, RecipeInstructions,
  RecipeCategory, Keywords, Calories, FatContent, ProteinContent,
  SodiumContent, SugarContent, CarbohydrateContent, FiberContent,
  RecipeServings, Description, ImageURL, CookTime, Slug, Source

Usage:
  conda run -n cf python -m scripts.pipeline.purple_carrot.scrape_recipes
  conda run -n cf python -m scripts.pipeline.purple_carrot.scrape_recipes \\
      --slugs /Library/Assets/kiwi/pipeline/pc_slugs.jsonl \\
      --out   /Library/Assets/kiwi/pipeline/recipes_purplecarrot.parquet \\
      --resume
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

CDX_BASE = "https://web.archive.org/cdx/search/cdx"
WB_BASE = "https://web.archive.org/web"
PC_HOST = "www.purplecarrot.com"

REPLAY_DELAY = 2.0
CDX_DELAY = 3.0    # archive.org CDX rate-limits aggressively; be polite

DEFAULT_SLUGS = Path("/Library/Assets/kiwi/pipeline/pc_slugs.jsonl")
DEFAULT_OUT = Path("/Library/Assets/kiwi/pipeline/recipes_purplecarrot.parquet")

# Inline JSON state embedded by the SSR renderer — used as fallback HTML parser
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_REDUX_STATE_RE = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*\n', re.DOTALL)


# ── Wayback helpers ───────────────────────────────────────────────────────────

def _cdx_get(params: dict) -> list:
    """CDX request with retry on 429/503 (archive.org rate-limits aggressively)."""
    for attempt in range(4):
        try:
            resp = requests.get(CDX_BASE, params=params, timeout=25)
            if resp.status_code in (429, 503):
                wait = 15 * (2 ** attempt)
                logger.debug("CDX %s — backing off %ds", resp.status_code, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            rows = resp.json()
            return rows if rows else []
        except Exception as exc:
            logger.debug("CDX attempt %d failed: %s", attempt + 1, exc)
            time.sleep(5 * (attempt + 1))
    return []


def _cdx_timestamps(slug: str) -> list[str]:
    """Return captured timestamps for a product slug, oldest first (pre-2022 window)."""
    rows = _cdx_get({
        "url": f"{PC_HOST}/api/v1/products/{slug}",
        "output": "json",
        "fl": "timestamp,statuscode",
        "filter": "statuscode:200",
        "limit": "20",
        # Pre-HelloFresh-acquisition captures (2019-2021) are most likely
        # to have full instructions — API stripped them post-acquisition.
        "from": "20190101",
        "to": "20211231",
    })
    if len(rows) < 2:
        return []
    return [row[0] for row in rows[1:]]  # timestamps only, oldest first


def _wayback_json(url: str, timestamp: str) -> Any | None:
    replay = f"{WB_BASE}/{timestamp}/{url}"
    for attempt in range(3):
        try:
            resp = requests.get(replay, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (404, 410):
                return None
        except Exception as exc:
            logger.debug("Wayback JSON attempt %d failed (%s): %s", attempt + 1, url, exc)
        time.sleep(2 ** attempt)
    return None


def _wayback_html(url: str, timestamp: str) -> str | None:
    replay = f"{WB_BASE}/{timestamp}/{url}"
    for attempt in range(3):
        try:
            resp = requests.get(replay, timeout=30)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code in (404, 410):
                return None
        except Exception as exc:
            logger.debug("Wayback HTML attempt %d failed (%s): %s", attempt + 1, url, exc)
        time.sleep(2 ** attempt)
    return None


# ── Recipe extraction from API JSON ──────────────────────────────────────────

def _extract_from_api(data: dict) -> dict | None:
    """Parse a /api/v1/products/<slug> response into our recipe dict.

    Returns None if the response has no usable content (empty title, etc.).
    Returns a partial dict if only some fields are populated — caller merges
    with manifest metadata.
    """
    if not data or not isinstance(data, dict):
        return None

    title = data.get("title", "").strip()
    subtitle = data.get("subtitle", "").strip()
    slug = data.get("slug", "")

    skus = data.get("skus") or []
    sku = skus[0] if skus else {}

    # Instructions: list of {step_number, title, description}
    raw_instructions = sku.get("instructions") or []
    steps: list[str] = []
    for step in sorted(raw_instructions, key=lambda s: s.get("step_number", 0)):
        parts = []
        if step.get("title"):
            parts.append(step["title"])
        if step.get("description"):
            parts.append(step["description"])
        if parts:
            steps.append(". ".join(parts))

    # Ingredients: may be in ingredients_quantity or ingredients
    raw_ingr = sku.get("ingredients_quantity") or sku.get("ingredients") or []
    ingredients: list[str] = []
    for item in raw_ingr:
        if isinstance(item, dict):
            qty = item.get("quantity") or item.get("qty") or ""
            unit = item.get("unit") or ""
            name = item.get("name") or item.get("ingredient", {}).get("name", "") if isinstance(item.get("ingredient"), dict) else item.get("ingredient_name", "")
            raw = item.get("raw") or item.get("display_name") or ""
            line = raw or " ".join(filter(None, [str(qty), str(unit), str(name)])).strip()
            if line:
                ingredients.append(line)
        elif isinstance(item, str) and item.strip():
            ingredients.append(item.strip())

    nutrition = sku.get("nutrition_label") or {}
    calories = _num(nutrition.get("calories") or sku.get("calories"))
    fat = _num(nutrition.get("total_fat") or sku.get("fat"))
    protein = _num(nutrition.get("protein") or sku.get("protein"))
    sodium = _num(nutrition.get("sodium") or sku.get("sodium"))
    sugar = _num(nutrition.get("sugar") or nutrition.get("total_sugars"))
    carbs = _num(nutrition.get("total_carbohydrate") or sku.get("carbs"))
    fiber = _num(nutrition.get("dietary_fiber") or sku.get("fiber"))

    tags = sku.get("tags") or data.get("tags") or []
    category = sku.get("meal_type") or sku.get("product_type") or ""
    servings = _num(sku.get("servings"))

    cook_time = sku.get("prep_and_cook_time") or ""
    description = sku.get("description") or ""

    images = sku.get("hero_images") or sku.get("image_versions") or []
    # hero_images can be a list OR a dict keyed by size string — normalise to list
    if isinstance(images, dict):
        images = list(images.values())
    image_url = ""
    if images and isinstance(images[0], dict):
        image_url = images[0].get("image_url") or images[0].get("url") or ""
    if not image_url and data.get("square_image"):
        sq = data["square_image"]
        image_url = sq.get("url") if isinstance(sq, dict) else ""

    return {
        "slug": slug,
        "title": title,
        "subtitle": subtitle,
        "steps": steps,
        "ingredients": ingredients,
        "category": category,
        "tags": tags,
        "calories": calories,
        "fat": fat,
        "protein": protein,
        "sodium": sodium,
        "sugar": sugar,
        "carbs": carbs,
        "fiber": fiber,
        "servings": servings,
        "cook_time": cook_time,
        "description": description,
        "image_url": image_url,
        "has_full_recipe": bool(steps and ingredients),
    }


def _num(val: Any) -> float | None:
    if val is None:
        return None
    try:
        v = float(str(val).replace("g", "").replace("mg", "").split()[0])
        return v if v > 0 else None
    except Exception:
        return None


# ── Fallback: HTML inline state parsing ──────────────────────────────────────

def _extract_from_html(html: str, slug: str) -> dict | None:
    """Try to pull recipe data from inline JS state in older SSR pages."""
    # Attempt 1: Next.js __NEXT_DATA__
    m = _NEXT_DATA_RE.search(html)
    if m:
        try:
            state = json.loads(m.group(1))
            # Walk the Next.js page props tree looking for recipe data
            props = state.get("props", {}).get("pageProps", {})
            recipe = props.get("recipe") or props.get("product")
            if recipe and isinstance(recipe, dict) and recipe.get("title"):
                return _extract_from_api(recipe)
        except Exception:
            pass

    # Attempt 2: Redux __INITIAL_STATE__
    m = _REDUX_STATE_RE.search(html)
    if m:
        try:
            state = json.loads(m.group(1))
            # Try common Redux state shapes
            for key in ("recipe", "product", "currentRecipe", "currentProduct"):
                recipe = state.get(key)
                if recipe and isinstance(recipe, dict) and recipe.get("title"):
                    return _extract_from_api(recipe)
        except Exception:
            pass

    # Attempt 3: JSON-LD structured data
    ld_matches = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL
    )
    for raw in ld_matches:
        try:
            ld = json.loads(raw)
            if isinstance(ld, list):
                ld = next((x for x in ld if x.get("@type") == "Recipe"), None)
            if not ld or ld.get("@type") != "Recipe":
                continue
            steps = []
            for inst in (ld.get("recipeInstructions") or []):
                if isinstance(inst, dict):
                    steps.append(inst.get("text", ""))
                elif isinstance(inst, str):
                    steps.append(inst)
            ingredients = ld.get("recipeIngredient") or []
            return {
                "slug": slug,
                "title": ld.get("name", ""),
                "subtitle": "",
                "steps": [s for s in steps if s],
                "ingredients": [i for i in ingredients if i],
                "category": ld.get("recipeCategory", ""),
                "tags": ld.get("keywords", "").split(",") if isinstance(ld.get("keywords"), str) else [],
                "calories": _num((ld.get("nutrition") or {}).get("calories")),
                "fat": None, "protein": None, "sodium": None,
                "sugar": None, "carbs": None, "fiber": None,
                "servings": _num(ld.get("recipeYield")),
                "cook_time": str(ld.get("totalTime") or ld.get("cookTime") or ""),
                "description": ld.get("description", ""),
                "image_url": (ld["image"][0] if isinstance(ld.get("image"), list) else ld.get("image", "")) or "",
                "has_full_recipe": True,
            }
        except Exception:
            pass

    return None


# ── Per-slug fetch ─────────────────────────────────────────────────────────────

def fetch_recipe(slug: str, manifest_meta: dict) -> dict | None:
    """Fetch the fullest available recipe data for a slug from Wayback.

    Returns a merged dict of manifest metadata + API/HTML-extracted content.
    """
    api_url = f"https://{PC_HOST}/api/v1/products/{slug}"
    html_url = f"https://{PC_HOST}/recipe/{slug}"

    recipe: dict | None = None

    # Try product API — oldest captures are most likely to have full data
    timestamps = _cdx_timestamps(slug)
    time.sleep(CDX_DELAY)

    if not timestamps and manifest_meta.get("wayback_ts"):
        timestamps = [manifest_meta["wayback_ts"]]

    for ts in timestamps:
        data = _wayback_json(api_url, ts)
        time.sleep(REPLAY_DELAY)
        if not data:
            continue
        candidate = _extract_from_api(data)
        if not candidate:
            continue
        recipe = candidate
        if recipe.get("has_full_recipe"):
            logger.debug("[%s] Full recipe from API (ts=%s)", slug, ts)
            break
        logger.debug("[%s] Partial API data (ts=%s) — trying HTML fallback", slug, ts)

    # HTML fallback when API has no steps/ingredients
    if not recipe or not recipe.get("has_full_recipe"):
        html_ts_rows = _cdx_get({
            "url": f"{PC_HOST}/recipe/{slug}",
            "output": "json",
            "fl": "timestamp,statuscode",
            "filter": "statuscode:200",
            "limit": "10",
        })
        html_timestamps = [row[0] for row in html_ts_rows[1:]] if len(html_ts_rows) > 1 else []
        time.sleep(CDX_DELAY)

        for ts in html_timestamps:
            html = _wayback_html(html_url, ts)
            time.sleep(REPLAY_DELAY)
            if not html:
                continue
            html_recipe = _extract_from_html(html, slug)
            if html_recipe and html_recipe.get("has_full_recipe"):
                logger.debug("[%s] Full recipe from HTML (ts=%s)", slug, ts)
                recipe = html_recipe
                break

    # Build merged record: manifest metadata fills any gaps from API/HTML
    merged: dict = {
        "slug": slug,
        "title": manifest_meta.get("title", ""),
        "subtitle": manifest_meta.get("subtitle", ""),
        "steps": [],
        "ingredients": [],
        "category": "",
        "tags": manifest_meta.get("tags") or [],
        "calories": None,
        "fat": None,
        "protein": None,
        "sodium": None,
        "sugar": None,
        "carbs": None,
        "fiber": None,
        "servings": manifest_meta.get("serving_size"),
        "cook_time": manifest_meta.get("cook_time", ""),
        "description": manifest_meta.get("description", ""),
        "image_url": manifest_meta.get("image_url", ""),
        "source": "purple_carrot",
        "wayback_ts": manifest_meta.get("wayback_ts", ""),
        "has_full_recipe": False,
    }

    if recipe:
        for key in recipe:
            # Prefer API/HTML data; keep manifest value only when API field is empty
            val = recipe[key]
            if val or key not in merged or not merged[key]:
                merged[key] = val

    if not merged["title"]:
        logger.warning("[%s] No title — skipping", slug)
        return None

    return merged


# ── Output formatting ─────────────────────────────────────────────────────────

def _to_dataframe_row(r: dict) -> dict:
    """Convert merged recipe dict to food.com-compatible parquet row."""
    # Build plain-text input for allrecipes-style corpus compatibility
    lines = [r["title"]]
    if r.get("subtitle"):
        lines.append(r["subtitle"])
    if r.get("description"):
        lines.append("")
        lines.append(r["description"])
    if r.get("ingredients"):
        lines += ["", "Ingredients:"] + [f"- {i}" for i in r["ingredients"]]
    if r.get("steps"):
        lines += ["", "Directions:"] + [f"- {s}" for s in r["steps"]]
    plain_text = "\n".join(lines)

    source_url = f"https://www.purplecarrot.com/recipe/{r['slug']}"

    return {
        # food.com schema columns (used by build_recipe_index.py)
        "RecipeId": f"pc_{r['slug']}",
        "Name": r["title"],
        "RecipeIngredientParts": r.get("ingredients") or [],
        "RecipeInstructions": r.get("steps") or [],
        "RecipeCategory": r.get("category", ""),
        "Keywords": r.get("tags") or [],
        "Calories": r.get("calories"),
        "FatContent": r.get("fat"),
        "ProteinContent": r.get("protein"),
        "SodiumContent": r.get("sodium"),
        "SugarContent": r.get("sugar"),
        "CarbohydrateContent": r.get("carbs"),
        "FiberContent": r.get("fiber"),
        "RecipeServings": r.get("servings"),
        # PC-specific extras (ignored by indexer, used by training pipeline)
        "Subtitle": r.get("subtitle", ""),
        "Description": r.get("description", ""),
        "ImageURL": r.get("image_url", ""),
        "CookTime": r.get("cook_time", ""),
        "Slug": r["slug"],
        "Source": "purple_carrot",
        "SourceURL": source_url,       # canonical attribution link shown in recipe UI
        "HasFullRecipe": r.get("has_full_recipe", False),
        "WaybackTs": r.get("wayback_ts", ""),
        # Also emit plain-text input for allrecipes-compatible corpus search
        "input": plain_text,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def scrape(slugs_file: Path, out_file: Path, resume: bool = True) -> None:
    import pandas as pd

    # Load manifest
    if not slugs_file.exists():
        logger.error("Slugs manifest not found: %s", slugs_file)
        return

    manifest: dict[str, dict] = {}
    with open(slugs_file) as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                slug = rec["slug"]
                # Keep the richest metadata if slug appears from multiple sources
                if slug not in manifest or rec.get("source") == "menu":
                    manifest[slug] = rec

    logger.info("Manifest: %d unique slugs", len(manifest))

    # Load already-scraped slugs for resume
    done_slugs: set[str] = set()
    existing_rows: list[dict] = []
    if resume and out_file.exists():
        try:
            existing_df = pd.read_parquet(out_file)
            done_slugs = set(existing_df["Slug"].tolist())
            existing_rows = existing_df.to_dict("records")
            logger.info("Resume: %d already scraped", len(done_slugs))
        except Exception as exc:
            logger.warning("Could not load existing parquet for resume: %s", exc)

    todo = [s for s in manifest if s not in done_slugs]
    logger.info("%d slugs to fetch", len(todo))

    rows = list(existing_rows)
    for i, slug in enumerate(todo, 1):
        logger.info("[%d/%d] %s", i, len(todo), slug)
        recipe = fetch_recipe(slug, manifest[slug])
        if recipe:
            rows.append(_to_dataframe_row(recipe))
            status = "full" if recipe.get("has_full_recipe") else "partial"
            logger.info("  -> %s (%s)", recipe.get("title", "?"), status)
        else:
            logger.warning("  -> skipped (no title)")

        # Write checkpoint every 50 recipes
        if i % 50 == 0:
            _write_parquet(rows, out_file)
            logger.info("Checkpoint: %d recipes written", len(rows))

    _write_parquet(rows, out_file)
    full = sum(1 for r in rows if r.get("HasFullRecipe"))
    logger.info(
        "Done. %d recipes written to %s (%d full, %d partial).",
        len(rows), out_file, full, len(rows) - full,
    )


def _write_parquet(rows: list[dict], out_file: Path) -> None:
    import pandas as pd
    out_file.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out_file, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Purple Carrot recipes from Wayback")
    parser.add_argument("--slugs", type=Path, default=DEFAULT_SLUGS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--no-resume", dest="resume", action="store_false",
        help="Start fresh (ignore existing parquet)",
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from scripts.pipeline.log_utils import attach_pipeline_log
    attach_pipeline_log("scrape_recipes")

    scrape(args.slugs, args.out, resume=args.resume)


if __name__ == "__main__":
    main()
