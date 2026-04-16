"""Screenshot attachment endpoint for in-app feedback.

After the cf-core feedback router creates a Forgejo issue, the frontend
can call POST /feedback/attach to upload a screenshot and pin it as a
comment on that issue.

The endpoint is separate from the cf-core router so Kiwi owns it
without modifying shared infrastructure.
"""
from __future__ import annotations

import base64
import os

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

_FORGEJO_BASE = os.environ.get(
    "FORGEJO_API_URL", "https://git.opensourcesolarpunk.com/api/v1"
)
_REPO = "Circuit-Forge/kiwi"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


class AttachRequest(BaseModel):
    issue_number: int
    filename: str = Field(default="screenshot.png", max_length=80)
    image_b64: str  # data URI or raw base64


class AttachResponse(BaseModel):
    comment_url: str


def _forgejo_headers() -> dict[str, str]:
    token = os.environ.get("FORGEJO_API_TOKEN", "")
    return {"Authorization": f"token {token}"}


def _decode_image(image_b64: str) -> tuple[bytes, str]:
    """Return (raw_bytes, mime_type) from a base64 string or data URI."""
    if image_b64.startswith("data:"):
        header, _, data = image_b64.partition(",")
        mime = header.split(";")[0].split(":")[1] if ":" in header else "image/png"
    else:
        data = image_b64
        mime = "image/png"
    return base64.b64decode(data), mime


@router.post("/attach", response_model=AttachResponse)
def attach_screenshot(payload: AttachRequest) -> AttachResponse:
    """Upload a screenshot to a Forgejo issue as a comment with embedded image.

    The image is uploaded as an issue asset, then referenced in a comment
    so it is visible inline when the issue is viewed.
    """
    token = os.environ.get("FORGEJO_API_TOKEN", "")
    if not token:
        raise HTTPException(status_code=503, detail="Feedback not configured.")

    raw_bytes, mime = _decode_image(payload.image_b64)

    if len(raw_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Screenshot exceeds 5 MB limit ({len(raw_bytes) // 1024} KB received).",
        )

    # Upload image as issue asset
    asset_resp = requests.post(
        f"{_FORGEJO_BASE}/repos/{_REPO}/issues/{payload.issue_number}/assets",
        headers=_forgejo_headers(),
        files={"attachment": (payload.filename, raw_bytes, mime)},
        timeout=20,
    )
    if not asset_resp.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Forgejo asset upload failed: {asset_resp.text[:200]}",
        )

    asset_url = asset_resp.json().get("browser_download_url", "")

    # Pin as a comment so the image is visible inline
    comment_body = f"**Screenshot attached by reporter:**\n\n![screenshot]({asset_url})"
    comment_resp = requests.post(
        f"{_FORGEJO_BASE}/repos/{_REPO}/issues/{payload.issue_number}/comments",
        headers={**_forgejo_headers(), "Content-Type": "application/json"},
        json={"body": comment_body},
        timeout=15,
    )
    if not comment_resp.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Forgejo comment failed: {comment_resp.text[:200]}",
        )

    comment_url = comment_resp.json().get("html_url", "")
    return AttachResponse(comment_url=comment_url)
