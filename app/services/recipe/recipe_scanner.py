"""Recipe scanner service (kiwi#9).

Extracts structured recipe data from one or more photos of recipe cards,
cookbook pages, or handwritten notes.

Pipeline:
  photo(s) -> EXIF correction -> VLM extraction -> JSON parse -> pantry cross-ref

Vision backend priority (mirrors receipt OCR pattern):
  1. cf-orch vision service (if CF_ORCH_URL set)
  2. Local Qwen2.5-VL (if GPU available)
  3. Anthropic API (BYOK -- if ANTHROPIC_API_KEY set)

BSL 1.1 -- requires Paid tier or BYOK.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum number of photos per scan call (to limit VLM context / VRAM)
MAX_IMAGES = 4

# VLM prompt -- adapted from tests/fixtures/recipe_scan/extract_test.py
_EXTRACTION_PROMPT = """
You are extracting a recipe from a photograph of a recipe card, cookbook page, or handwritten note.

If two or more images are provided, treat them as a single recipe across multiple pages
(e.g. ingredients on page 1, directions on page 2).

Return a single JSON object with these fields:
- title: recipe name (string)
- subtitle: any secondary title or serving suggestion e.g. "with Broccoli & Ranch Dressing" (string or null)
- servings: serving size if shown, as a string e.g. "2", "4-6" (string or null)
- cook_time: total cook time if shown, e.g. "15 min", "1 hour" (string or null)
- source_note: any attribution text like "From Betty Crocker" or "Purple Carrot" (string or null)
- ingredients: array of ingredient objects, each with:
  - name: normalized generic ingredient name, lowercase, no quantities, no brand names
    (e.g. "Follow Your Heart Vegan Ranch" becomes "ranch dressing")
  - qty: quantity as a string, preserving fractions e.g. "1/2", a quarter symbol (string or null)
  - unit: unit of measure, null for countable items (e.g. "3 eggs" has unit: null)
  - raw: the original ingredient line verbatim, exactly as it appears
- steps: ordered array of instruction strings, one distinct step per element
- notes: any tips, substitutions, storage instructions, or variations (string or null)
- confidence: "high" if text is clear and complete, "medium" if some parts are uncertain,
  "low" if mostly handwritten or significantly degraded
- warnings: array of strings describing anything the user should double-check
  (e.g. "Directions appear to continue on another page not shown")

Return only valid JSON. No markdown fences. No explanation outside the JSON.
If the image does not appear to be a recipe at all, return: {"error": "not_a_recipe"}
""".strip()


# ── Data types ─────────────────────────────────────────────────────────────────

@dataclass
class ScannedIngredient:
    name: str
    qty: str | None = None
    unit: str | None = None
    raw: str | None = None
    in_pantry: bool = False


@dataclass
class ScannedRecipeResult:
    title: str | None
    subtitle: str | None
    servings: str | None
    cook_time: str | None
    source_note: str | None
    ingredients: list[ScannedIngredient]
    steps: list[str]
    notes: str | None
    tags: list[str]
    pantry_match_pct: int
    confidence: str
    warnings: list[str]


# ── Image helpers ──────────────────────────────────────────────────────────────

def _load_image_b64(path: Path) -> str:
    """Load image, apply EXIF rotation, return base64-encoded JPEG bytes."""
    from PIL import Image, ImageOps

    with open(path, "rb") as f:
        raw = f.read()
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()


# ── Vision backend ─────────────────────────────────────────────────────────────

def _call_via_anthropic(image_paths: list[Path], prompt: str) -> str:
    """Send image(s) + prompt to Anthropic API. Raises RuntimeError if unavailable."""
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package not installed") from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    content: list[dict] = []
    for i, path in enumerate(image_paths):
        if i > 0:
            content.append({"type": "text", "text": f"(Page {i + 1} of the same recipe:)"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": _load_image_b64(path),
            },
        })
    content.append({"type": "text", "text": prompt})

    msg = client.messages.create(
        # Haiku is cost-efficient for well-structured extraction prompts
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": content}],
    )
    return msg.content[0].text.strip()


def _call_via_local_vlm(image_paths: list[Path], prompt: str) -> str:
    """Send image(s) + prompt to local Qwen2.5-VL. Raises RuntimeError if unavailable."""
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("torch not installed") from exc

    if not torch.cuda.is_available():
        raise RuntimeError("No CUDA device -- local VLM unavailable")

    # Lazy import so the module loads fast when GPU is absent
    from PIL import Image, ImageOps
    from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

    model_name = "Qwen/Qwen2.5-VL-7B-Instruct"
    logger.info("Loading local VLM for recipe scan: %s", model_name)

    model = Qwen2VLForConditionalGeneration.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="auto",
        low_cpu_mem_usage=True,
    )
    processor = AutoProcessor.from_pretrained(model_name)
    model.train(False)  # inference mode

    images = []
    for path in image_paths:
        with open(path, "rb") as f:
            raw = f.read()
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img).convert("RGB")
        images.append(img)

    inputs = processor(images=images, text=prompt, return_tensors="pt")
    inputs = {k: v.to("cuda", torch.float16) if isinstance(v, torch.Tensor) else v
              for k, v in inputs.items()}

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=2048,
            do_sample=False,
            temperature=0.0,
        )

    output = processor.decode(output_ids[0], skip_special_tokens=True)
    output = output.replace(prompt, "").strip()

    # Free VRAM
    del model
    torch.cuda.empty_cache()

    return output


def _build_ocr_extraction_prompt(ocr_text: str) -> str:
    """Build a text-LLM prompt for structuring OCR output into recipe JSON.

    Swaps the image-centric preamble of _EXTRACTION_PROMPT for an OCR-centric
    one, then appends the combined OCR text as input. The JSON schema section
    is shared verbatim to keep the two paths in sync.
    """
    schema_idx = _EXTRACTION_PROMPT.find("Return a single JSON object")
    schema_part = _EXTRACTION_PROMPT[schema_idx:] if schema_idx != -1 else _EXTRACTION_PROMPT
    return (
        "You are extracting a recipe from OCR text taken from a recipe card, "
        "cookbook page, or handwritten note.\n\n"
        "The text below was obtained via optical character recognition and may "
        "contain minor scanning artifacts or formatting irregularities.\n\n"
        f"{schema_part}\n\nOCR Text:\n{ocr_text}"
    )


def _call_via_cf_text_vlm(alloc_url: str, image_paths: list[Path], prompt: str) -> str:
    """Call the cf-text OpenAI-compat API with images via the llama.cpp multimodal backend."""
    import httpx

    content: list[dict] = []
    for i, path in enumerate(image_paths):
        if i > 0:
            content.append({"type": "text", "text": f"(Page {i + 1} of the same recipe:)"})
        b64 = _load_image_b64(path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    content.append({"type": "text", "text": prompt})

    resp = httpx.post(
        f"{alloc_url.rstrip('/')}/v1/chat/completions",
        json={
            "model": "local",
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 2048,
            "temperature": 0.0,
        },
        timeout=180.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_vision_backend(
    image_paths: list[Path],
    prompt: str,
    progress_cb: "Callable[[str, str], None] | None" = None,
) -> str:
    """Dispatch to the best available vision backend.

    Priority: cf-orch (Qwen2-VL GGUF via cf-text) -> local Qwen2.5-VL -> Anthropic API.
    Raises RuntimeError with a clear message when no backend is available.

    Args:
        image_paths: Images to process.
        prompt: Extraction prompt (used by local VLM / Anthropic paths).
        progress_cb: Optional callback(status, message) for SSE progress events.
                     Called synchronously from the thread — caller bridges to async.
    """
    def _progress(status: str, message: str) -> None:
        if progress_cb:
            progress_cb(status, message)

    errors: list[str] = []

    # 1. Try cf-orch task allocation → cf-docuvision (Qwen2-VL GGUF via llama.cpp).
    #    Two-step: docuvision OCRs the image(s), then LLMRouter structures the text into JSON.
    cf_orch_url = os.environ.get("CF_ORCH_URL")
    if cf_orch_url:
        try:
            from circuitforge_core.llm.router import LLMRouter

            from app.services.ocr.docuvision_client import DocuvisionClient
            from app.services.task_inference import TaskNotRegistered, task_allocate

            try:
                _progress("allocating", "Starting vision service...")
                with task_allocate("kiwi", "recipe_scan", service_hint="cf-docuvision", ttl_s=120.0) as alloc:
                    _progress("scanning", "Extracting recipe text from photo...")
                    doc_client = DocuvisionClient(alloc.url)
                    ocr_parts: list[str] = []
                    for i, path in enumerate(image_paths):
                        result = doc_client.extract_text(path, hint="text")
                        prefix = f"(Page {i + 1} of the same recipe)\n" if len(image_paths) > 1 else ""
                        ocr_parts.append(f"{prefix}{result.text}")
                    combined_ocr = "\n\n".join(ocr_parts)

                    if not combined_ocr.strip():
                        raise ValueError("Docuvision returned no text — image may not be a recipe")

                    _progress("structuring", "Parsing recipe structure...")
                    text = LLMRouter().complete(
                        _build_ocr_extraction_prompt(combined_ocr),
                        system="You are a recipe data extractor. Return ONLY valid JSON. No markdown, no explanation, no code fences.",
                    )
                    if text:
                        return text

            except TaskNotRegistered:
                logger.debug("kiwi.recipe_scan not yet registered in cf-orch assignments")
        except Exception as exc:
            logger.debug("cf-orch vision failed for recipe scan: %s", exc)
            errors.append(f"cf-orch: {exc}")

    # 2. Try local Qwen2.5-VL
    try:
        return _call_via_local_vlm(image_paths, prompt)
    except Exception as exc:
        logger.debug("Local VLM unavailable for recipe scan: %s", exc)
        errors.append(f"local VLM: {exc}")

    # 3. Try Anthropic API (BYOK)
    try:
        return _call_via_anthropic(image_paths, prompt)
    except Exception as exc:
        logger.debug("Anthropic API failed for recipe scan: %s", exc)
        errors.append(f"Anthropic: {exc}")

    raise RuntimeError(
        "No vision backend configured for recipe scanning. "
        "Options: cf-orch (CF_ORCH_URL), local GPU, or ANTHROPIC_API_KEY (BYOK). "
        f"Errors: {'; '.join(errors)}"
    )


# ── Parsing helpers ────────────────────────────────────────────────────────────

def _normalize_ingredient_name(name: str) -> str:
    """Lowercase + strip whitespace. Preserves multi-word names as-is."""
    return name.lower().strip()


def _extract_json_object(text: str) -> str | None:
    """Return the first balanced JSON object from text, or None if not found.

    Uses brace-counting rather than a greedy regex so trailing prose and
    nested objects are handled correctly.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_scanner_json(raw_text: str) -> dict:
    """Extract and return the JSON dict from VLM output.

    Handles:
    - Pure JSON
    - JSON in ```json ... ``` markdown fences
    - Qwen3-style <think>...</think> or <thinking>...</thinking> preambles
    - JSON preceded or followed by prose

    Raises ValueError on not_a_recipe or unparseable output.
    """
    text = raw_text.strip()

    # Strip thinking-token blocks emitted by reasoning models (Qwen3, DeepSeek-R1, etc.)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()

    # Strip markdown fences if present
    if "```" in text:
        # Find the content between the first ``` pair
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

    # Try direct parse
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fall back to brace-balanced extraction from anywhere in the output
        candidate = _extract_json_object(text)
        if not candidate:
            logger.warning("Could not parse JSON from LLM output (first 400 chars): %r", text[:400])
            raise ValueError(f"Could not parse JSON from VLM output: {text[:200]!r}")
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            logger.warning("Brace-extracted JSON still invalid: %r", candidate[:400])
            raise ValueError(f"Could not parse JSON from VLM output: {exc}") from exc

    if isinstance(data, dict) and data.get("error") == "not_a_recipe":
        raise ValueError("not_a_recipe: image does not appear to contain a recipe")

    return data


# ── Pantry cross-reference ─────────────────────────────────────────────────────

def _cross_reference_pantry(
    ingredients: list[ScannedIngredient],
    pantry_names: list[str],
) -> tuple[list[ScannedIngredient], int]:
    """Mark ingredients found in the pantry and return updated list + match percent.

    Matching is bidirectional by token:
    - "broccoli florets" matches pantry item "broccoli" (pantry token in ingredient)
    - "pumpkin seeds" matches pantry "pumpkin seeds" (exact)

    Returns (updated_ingredients, pantry_match_pct).
    """
    if not ingredients:
        return ingredients, 0

    normalized_pantry = [_normalize_ingredient_name(p) for p in pantry_names]
    updated: list[ScannedIngredient] = []
    matched = 0

    for ingr in ingredients:
        norm_ingr = _normalize_ingredient_name(ingr.name)
        in_pantry = any(
            (p_tok in norm_ingr or norm_ingr in p_tok)
            for p in normalized_pantry
            for p_tok in p.split()
            if len(p_tok) >= 4  # skip short stop-words like "of", "and", "the"
        )
        updated.append(ScannedIngredient(
            name=ingr.name,
            qty=ingr.qty,
            unit=ingr.unit,
            raw=ingr.raw,
            in_pantry=in_pantry,
        ))
        if in_pantry:
            matched += 1

    pct = round(matched / len(ingredients) * 100)
    return updated, pct


# ── Main scanner class ─────────────────────────────────────────────────────────

class RecipeScanner:
    """Stateless recipe scanner. One instance can be reused across requests."""

    def scan(
        self,
        image_paths: list[Path],
        pantry_names: list[str] | None = None,
        progress_cb: Callable[[str, str], None] | None = None,
    ) -> ScannedRecipeResult:
        """Extract a structured recipe from one or more photos.

        Args:
            image_paths: 1-4 image files (phone photos, scans).
            pantry_names: Flat list of product names from user's inventory.
                          Pass [] or None to skip pantry cross-reference.

        Returns:
            ScannedRecipeResult with all fields populated.

        Raises:
            ValueError: Image is not a recipe, or JSON could not be parsed.
            RuntimeError: No vision backend is configured.
        """
        if not image_paths:
            raise ValueError("At least one image is required")
        if len(image_paths) > MAX_IMAGES:
            raise ValueError(f"Maximum {MAX_IMAGES} images per scan (got {len(image_paths)})")

        # Call vision backend
        raw_text = _call_vision_backend(image_paths, _EXTRACTION_PROMPT, progress_cb=progress_cb)

        # Parse JSON from VLM output
        data = _parse_scanner_json(raw_text)

        # Build ingredient list
        raw_ingredients = data.get("ingredients") or []
        ingredients: list[ScannedIngredient] = [
            ScannedIngredient(
                name=str(item.get("name") or "").strip() or "unknown",
                qty=str(item["qty"]) if item.get("qty") is not None else None,
                unit=str(item["unit"]) if item.get("unit") is not None else None,
                raw=str(item["raw"]) if item.get("raw") is not None else None,
            )
            for item in raw_ingredients
            if isinstance(item, dict)
        ]

        # Pantry cross-reference
        ingredients, pct = _cross_reference_pantry(
            ingredients,
            pantry_names or [],
        )

        return ScannedRecipeResult(
            title=data.get("title") or None,
            subtitle=data.get("subtitle") or None,
            servings=str(data["servings"]) if data.get("servings") is not None else None,
            cook_time=str(data["cook_time"]) if data.get("cook_time") is not None else None,
            source_note=data.get("source_note") or None,
            ingredients=ingredients,
            steps=[str(s) for s in (data.get("steps") or []) if s],
            notes=data.get("notes") or None,
            tags=list(data.get("tags") or []),
            pantry_match_pct=pct,
            confidence=data.get("confidence") or "medium",
            warnings=list(data.get("warnings") or []),
        )
