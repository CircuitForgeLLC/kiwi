#!/usr/bin/env python3
"""
Prompt validation harness for recipe scanner (kiwi#9).

Runs the draft extraction prompt against fixture images using the Anthropic API
directly (bypasses llm.yaml — for prompt dev only, not production path).

Usage:
    python extract_test.py <image1.jpg> [image2.jpg]
"""
import base64
import io
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageOps
import anthropic

PROMPT = """
You are extracting a recipe from a photograph of a recipe card, cookbook page, or handwritten note.

If two images are provided, treat them as a single recipe across two pages (e.g. ingredients on page 1, directions on page 2).

Return a single JSON object with these fields:
- title: recipe name (string)
- subtitle: any secondary title or serving suggestion e.g. "with Broccoli & Ranch Dressing" (string or null)
- servings: serving size if shown, as a string e.g. "2", "4-6" (string or null)
- cook_time: total cook time if shown, e.g. "15 min", "1 hour" (string or null)
- source_note: any attribution text like "From Betty Crocker" or "Purple Carrot" (string or null)
- ingredients: array of ingredient objects, each with:
  - name: normalized generic ingredient name, lowercase, no quantities, no brand names
    (e.g. "Follow Your Heart® Vegan Ranch" → "ranch dressing")
  - qty: quantity as a string, preserving fractions e.g. "1/2", "¼" (string or null)
  - unit: unit of measure, null for countable items (e.g. "3 eggs" → unit: null)
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


def load_image_b64(path: Path) -> str:
    """Load image, apply EXIF rotation, return base64-encoded JPEG."""
    with open(path, "rb") as f:
        img = Image.open(io.BytesIO(f.read()))
        img = ImageOps.exif_transpose(img)  # fix phone rotation
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode()


def extract(image_paths: list[Path]) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    content = []
    for i, path in enumerate(image_paths):
        if i > 0:
            content.append({"type": "text", "text": f"(Page {i + 1} of the same recipe:)"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": load_image_b64(path),
            },
        })
    content.append({"type": "text", "text": PROMPT})

    msg = client.messages.create(
        model="claude-opus-4-6",  # best vision for prompt dev; production uses VisionRouter
        max_tokens=2048,
        messages=[{"role": "user", "content": content}],
    )
    raw = msg.content[0].text.strip()
    # Strip markdown fences if the model adds them anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


if __name__ == "__main__":
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        print("Usage: python extract_test.py <image1.jpg> [image2.jpg]")
        sys.exit(1)

    for p in paths:
        if not p.exists():
            print(f"File not found: {p}")
            sys.exit(1)

    print(f"Extracting from: {[p.name for p in paths]}")
    print("Applying EXIF rotation + sending to claude-opus-4-6...\n")

    result = extract(paths)
    print(json.dumps(result, indent=2, ensure_ascii=False))
