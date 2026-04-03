"""
Feedback endpoint — creates Forgejo issues from in-app feedback.
Ported from peregrine/scripts/feedback_api.py; adapted for Kiwi context.
"""
from __future__ import annotations

import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.db.store import get_db

router = APIRouter()

_ROOT = Path(__file__).resolve().parents[3]

# ── Forgejo helpers ────────────────────────────────────────────────────────────

_LABEL_COLORS = {
    "beta-feedback": "#0075ca",
    "needs-triage": "#e4e669",
    "bug": "#d73a4a",
    "feature-request": "#a2eeef",
    "question": "#d876e3",
}


def _forgejo_headers() -> dict:
    token = os.environ.get("FORGEJO_API_TOKEN", "")
    return {"Authorization": f"token {token}", "Content-Type": "application/json"}


def _ensure_labels(label_names: list[str]) -> list[int]:
    base = os.environ.get("FORGEJO_API_URL", "https://git.opensourcesolarpunk.com/api/v1")
    repo = os.environ.get("FORGEJO_REPO", "Circuit-Forge/kiwi")
    headers = _forgejo_headers()
    resp = requests.get(f"{base}/repos/{repo}/labels", headers=headers, timeout=10)
    existing = {lb["name"]: lb["id"] for lb in resp.json()} if resp.ok else {}
    ids: list[int] = []
    for name in label_names:
        if name in existing:
            ids.append(existing[name])
        else:
            r = requests.post(
                f"{base}/repos/{repo}/labels",
                headers=headers,
                json={"name": name, "color": _LABEL_COLORS.get(name, "#ededed")},
                timeout=10,
            )
            if r.ok:
                ids.append(r.json()["id"])
    return ids


def _collect_context(tab: str) -> dict:
    """Collect lightweight app context: tab, version, platform, timestamp."""
    try:
        version = subprocess.check_output(
            ["git", "describe", "--tags", "--always"],
            cwd=_ROOT, text=True, timeout=5,
        ).strip()
    except Exception:
        version = "dev"

    return {
        "tab": tab,
        "version": version,
        "demo_mode": settings.DEMO_MODE,
        "cloud_mode": settings.CLOUD_MODE,
        "platform": platform.platform(),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _build_issue_body(form: dict, context: dict) -> str:
    _TYPE_LABELS = {"bug": "🐛 Bug", "feature": "✨ Feature Request", "other": "💬 Other"}
    lines: list[str] = [
        f"## {_TYPE_LABELS.get(form.get('type', 'other'), '💬 Other')}",
        "",
        form.get("description", ""),
        "",
    ]
    if form.get("type") == "bug" and form.get("repro"):
        lines += ["### Reproduction Steps", "", form["repro"], ""]

    lines += ["### Context", ""]
    for k, v in context.items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")

    if form.get("submitter"):
        lines += ["---", f"*Submitted by: {form['submitter']}*"]

    return "\n".join(lines)


# ── Schemas ────────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    title: str
    description: str
    type: Literal["bug", "feature", "other"] = "other"
    repro: str = ""
    tab: str = "unknown"
    submitter: str = ""  # optional "Name <email>" attribution


class FeedbackResponse(BaseModel):
    issue_number: int
    issue_url: str


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest) -> FeedbackResponse:
    """
    File a Forgejo issue from in-app feedback.
    Silently disabled when FORGEJO_API_TOKEN is not set (demo/offline mode).
    """
    token = os.environ.get("FORGEJO_API_TOKEN", "")
    if not token:
        raise HTTPException(
            status_code=503,
            detail="Feedback disabled: FORGEJO_API_TOKEN not configured.",
        )
    if settings.DEMO_MODE:
        raise HTTPException(status_code=403, detail="Feedback disabled in demo mode.")

    context = _collect_context(payload.tab)
    form = {
        "type": payload.type,
        "description": payload.description,
        "repro": payload.repro,
        "submitter": payload.submitter,
    }
    body = _build_issue_body(form, context)
    labels = ["beta-feedback", "needs-triage"]
    labels.append({"bug": "bug", "feature": "feature-request"}.get(payload.type, "question"))

    base = os.environ.get("FORGEJO_API_URL", "https://git.opensourcesolarpunk.com/api/v1")
    repo = os.environ.get("FORGEJO_REPO", "Circuit-Forge/kiwi")
    headers = _forgejo_headers()

    label_ids = _ensure_labels(labels)
    resp = requests.post(
        f"{base}/repos/{repo}/issues",
        headers=headers,
        json={"title": payload.title, "body": body, "labels": label_ids},
        timeout=15,
    )
    if not resp.ok:
        raise HTTPException(status_code=502, detail=f"Forgejo error: {resp.text[:200]}")

    data = resp.json()
    return FeedbackResponse(issue_number=data["number"], issue_url=data["html_url"])
