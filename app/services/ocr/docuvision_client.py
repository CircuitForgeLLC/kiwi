"""Thin HTTP client for the cf-docuvision document vision service."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import httpx


@dataclass
class DocuvisionResult:
    text: str
    confidence: float | None = None
    raw: dict | None = None


class DocuvisionClient:
    """Thin client for the cf-docuvision service."""

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def extract_text(self, image_path: str | Path, hint: str = "text") -> DocuvisionResult:
        """Send an image to docuvision and return extracted text.

        Args:
            image_path: Path to the image file.
            hint: Docuvision extraction hint — "text" for dense prose (recipes),
                  "table" for tabular data, "form" for form fields, "auto" for
                  automatic detection.
        """
        image_bytes = Path(image_path).read_bytes()
        b64 = base64.b64encode(image_bytes).decode()

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._base_url}/extract",
                json={"image_b64": b64, "hint": hint},
            )
            resp.raise_for_status()
            data = resp.json()

        return DocuvisionResult(
            text=data.get("raw_text", ""),
            confidence=data.get("metadata", {}).get("confidence"),
            raw=data,
        )

    async def extract_text_async(self, image_path: str | Path, hint: str = "text") -> DocuvisionResult:
        """Async version."""
        image_bytes = Path(image_path).read_bytes()
        b64 = base64.b64encode(image_bytes).decode()

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/extract",
                json={"image_b64": b64, "hint": hint},
            )
            resp.raise_for_status()
            data = resp.json()

        return DocuvisionResult(
            text=data.get("raw_text", ""),
            confidence=data.get("metadata", {}).get("confidence"),
            raw=data,
        )
