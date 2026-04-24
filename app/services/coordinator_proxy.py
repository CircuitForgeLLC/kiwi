"""cf-orch coordinator proxy client.

Calls the coordinator's /proxy/authorize endpoint to obtain a one-time
stream URL + token for LLM streaming. Always raises CoordinatorError on
failure — callers decide how to handle it (stream-token endpoint returns
503 or 403 as appropriate).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)


class CoordinatorError(Exception):
    """Raised when the coordinator returns an error or is unreachable."""
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class StreamTokenResult:
    stream_url: str
    token: str
    expires_in_s: int


def _coordinator_url() -> str:
    return os.environ.get("COORDINATOR_URL", "http://10.1.10.71:7700")


def _product_key() -> str:
    return os.environ.get("COORDINATOR_KIWI_KEY", "")


async def coordinator_authorize(
    prompt: str,
    caller: str = "kiwi-recipe",
    ttl_s: int = 300,
) -> StreamTokenResult:
    """Call POST /proxy/authorize on the coordinator.

    Returns a StreamTokenResult with the stream URL and one-time token.
    Raises CoordinatorError on any failure (network, auth, capacity).
    """
    url = f"{_coordinator_url()}/proxy/authorize"
    key = _product_key()
    if not key:
        raise CoordinatorError(
            "COORDINATOR_KIWI_KEY env var is not set — streaming unavailable",
            status_code=503,
        )

    payload = {
        "product": "kiwi",
        "product_key": key,
        "caller": caller,
        "prompt": prompt,
        "params": {},
        "ttl_s": ttl_s,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
    except httpx.RequestError as exc:
        log.warning("coordinator_authorize network error: %s", exc)
        raise CoordinatorError(f"Coordinator unreachable: {exc}", status_code=503)

    if resp.status_code == 401:
        raise CoordinatorError("Invalid product key", status_code=401)
    if resp.status_code == 429:
        raise CoordinatorError("Too many concurrent streams", status_code=429)
    if resp.status_code == 503:
        raise CoordinatorError("No GPU available for streaming", status_code=503)
    if not resp.is_success:
        raise CoordinatorError(
            f"Coordinator error {resp.status_code}: {resp.text[:200]}",
            status_code=503,
        )

    data = resp.json()
    # Use public_stream_url if coordinator provides it (cloud mode), else stream_url
    stream_url = data.get("public_stream_url") or data["stream_url"]
    return StreamTokenResult(
        stream_url=stream_url,
        token=data["token"],
        expires_in_s=data["expires_in_s"],
    )
