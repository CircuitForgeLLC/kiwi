"""Heimdall cf-orch budget client.

Calls Heimdall's /orch/* endpoints to gate and record cf-orch usage for
lifetime/founders license holders. Always fails open on network errors —
a Heimdall outage should never block the user.
"""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

HEIMDALL_URL: str = os.environ.get("HEIMDALL_URL", "https://license.circuitforge.tech")
HEIMDALL_ADMIN_TOKEN: str = os.environ.get("HEIMDALL_ADMIN_TOKEN", "")


def _headers() -> dict[str, str]:
    if HEIMDALL_ADMIN_TOKEN:
        return {"Authorization": f"Bearer {HEIMDALL_ADMIN_TOKEN}"}
    return {}


def check_orch_budget(key_display: str, product: str) -> dict:
    """Call POST /orch/check and return the response dict.

    On any error (network, auth, etc.) returns a permissive dict so the
    caller can proceed without blocking the user.
    """
    try:
        resp = requests.post(
            f"{HEIMDALL_URL}/orch/check",
            json={"key_display": key_display, "product": product},
            headers=_headers(),
            timeout=5,
        )
        if resp.ok:
            return resp.json()
        log.warning("Heimdall orch/check returned %s for key %s", resp.status_code, key_display[:12])
    except Exception as exc:
        log.warning("Heimdall orch/check failed (fail-open): %s", exc)

    # Fail open — Heimdall outage must never block the user
    return {
        "allowed": True,
        "calls_used": 0,
        "calls_total": 0,
        "topup_calls": 0,
        "period_start": "",
        "resets_on": "",
    }


def get_orch_usage(key_display: str, product: str) -> dict:
    """Call GET /orch/usage and return the response dict.

    Returns zeros on error (non-blocking).
    """
    try:
        resp = requests.get(
            f"{HEIMDALL_URL}/orch/usage",
            params={"key_display": key_display, "product": product},
            headers=_headers(),
            timeout=5,
        )
        if resp.ok:
            return resp.json()
        log.warning("Heimdall orch/usage returned %s", resp.status_code)
    except Exception as exc:
        log.warning("Heimdall orch/usage failed: %s", exc)

    return {
        "calls_used": 0,
        "topup_calls": 0,
        "calls_total": 0,
        "period_start": "",
        "resets_on": "",
    }
