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

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def extract_text(self, image_path: str | Path) -> DocuvisionResult:
        """Send an image to docuvision and return extracted text."""
        image_bytes = Path(image_path).read_bytes()
        b64 = base64.b64encode(image_bytes).decode()

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self._base_url}/extract",
                json={"image": b64},
            )
            resp.raise_for_status()
            data = resp.json()

        return DocuvisionResult(
            text=data.get("text", ""),
            confidence=data.get("confidence"),
            raw=data,
        )

    async def extract_text_async(self, image_path: str | Path) -> DocuvisionResult:
        """Async version."""
        image_bytes = Path(image_path).read_bytes()
        b64 = base64.b64encode(image_bytes).decode()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/extract",
                json={"image": b64},
            )
            resp.raise_for_status()
            data = resp.json()

        return DocuvisionResult(
            text=data.get("text", ""),
            confidence=data.get("confidence"),
            raw=data,
        )
