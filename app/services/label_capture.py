"""Visual label capture service for unenriched products (kiwi#79).

Wraps the cf-core VisionRouter to extract structured nutrition data from a
photographed nutrition facts panel.  When the VisionRouter is not yet wired
(NotImplementedError) the service falls back to a mock extraction so the
barcode scan flow can be exercised end-to-end in development.

JSON contract returned by the vision model (and mock):
  {
    "product_name": str | null,
    "brand":        str | null,
    "serving_size_g": number | null,
    "calories":       number | null,
    "fat_g":          number | null,
    "saturated_fat_g": number | null,
    "carbs_g":        number | null,
    "sugar_g":        number | null,
    "fiber_g":        number | null,
    "protein_g":      number | null,
    "sodium_mg":      number | null,
    "ingredient_names": [str],
    "allergens":        [str],
    "confidence":       number (0.0–1.0)
  }
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger(__name__)

# Confidence below this threshold surfaces amber highlights in the UI.
REVIEW_THRESHOLD = 0.7

_MOCK_EXTRACTION: dict[str, Any] = {
    "product_name": "Unknown Product",
    "brand": None,
    "serving_size_g": None,
    "calories": None,
    "fat_g": None,
    "saturated_fat_g": None,
    "carbs_g": None,
    "sugar_g": None,
    "fiber_g": None,
    "protein_g": None,
    "sodium_mg": None,
    "ingredient_names": [],
    "allergens": [],
    "confidence": 0.0,
}

_EXTRACTION_PROMPT = """You are reading a nutrition facts label photograph.
Extract the following fields as a JSON object with no extra text:

{
  "product_name": <product name or null>,
  "brand": <brand name or null>,
  "serving_size_g": <serving size in grams as a number or null>,
  "calories": <calories per serving as a number or null>,
  "fat_g": <total fat grams or null>,
  "saturated_fat_g": <saturated fat grams or null>,
  "carbs_g": <total carbohydrates grams or null>,
  "sugar_g": <sugars grams or null>,
  "fiber_g": <dietary fiber grams or null>,
  "protein_g": <protein grams or null>,
  "sodium_mg": <sodium milligrams or null>,
  "ingredient_names": [list of individual ingredients as strings],
  "allergens": [list of allergens explicitly stated on label],
  "confidence": <your confidence this extraction is correct, 0.0 to 1.0>
}

Use null for any field you cannot read clearly. Do not guess values.
Respond with JSON only."""


def extract_label(image_bytes: bytes) -> dict[str, Any]:
    """Run vision model extraction on raw label image bytes.

    Returns a dict matching the nutrition JSON contract above.
    Falls back to a zero-confidence mock if the VisionRouter is not yet
    implemented (stub) or if the model returns unparseable output.
    """
    # Allow unit tests to bypass the vision model entirely.
    if os.environ.get("KIWI_LABEL_CAPTURE_MOCK") == "1":
        log.debug("label_capture: mock mode active")
        return dict(_MOCK_EXTRACTION)

    try:
        from circuitforge_core.vision import caption as vision_caption
        result = vision_caption(image_bytes, prompt=_EXTRACTION_PROMPT)
        raw = result.caption or ""
        return _parse_extraction(raw)
    except Exception as exc:
        log.warning("label_capture: extraction failed (%s) — returning mock extraction", exc)
        return dict(_MOCK_EXTRACTION)


def _parse_extraction(raw: str) -> dict[str, Any]:
    """Parse the JSON string returned by the vision model.

    Strips markdown code fences if present.  Validates required shape.
    Returns the mock on any parse error.
    """
    text = raw.strip()
    if text.startswith("```"):
        # Strip ```json ... ``` fences
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("label_capture: could not parse vision response: %s", exc)
        return dict(_MOCK_EXTRACTION)

    if not isinstance(data, dict):
        log.warning("label_capture: vision response is not a dict")
        return dict(_MOCK_EXTRACTION)

    # Normalise list fields — model may return None instead of []
    for list_key in ("ingredient_names", "allergens"):
        if not isinstance(data.get(list_key), list):
            data[list_key] = []

    # Clamp confidence to [0, 1]
    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    data["confidence"] = max(0.0, min(1.0, float(confidence)))

    return data


def needs_review(extraction: dict[str, Any]) -> bool:
    """Return True when the extraction confidence is below REVIEW_THRESHOLD."""
    return float(extraction.get("confidence", 0.0)) < REVIEW_THRESHOLD
