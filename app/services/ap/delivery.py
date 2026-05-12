# app/services/ap/delivery.py
# MIT License

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from circuitforge_core.activitypub import deliver_activity

from app.services.ap.keys import get_actor

logger = logging.getLogger(__name__)

_RETRIES = 3
_BACKOFF = [1.0, 4.0, 16.0]


def deliver_to_followers(post_slug: str, activity: dict, db_path: Path) -> None:
    """Deliver an AP activity to all active followers. Called as a background task.

    Retries each inbox up to 3 times with exponential backoff.
    Logs each attempt to ap_deliveries in the local kiwi.db.
    """
    actor = get_actor()
    if actor is None:
        return

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        followers = conn.execute(
            "SELECT inbox_url, shared_inbox FROM ap_followers WHERE active = 1"
        ).fetchall()
    finally:
        conn.close()

    # Deduplicate by shared_inbox where available
    inboxes: set[str] = set()
    for row in followers:
        inbox = row["shared_inbox"] or row["inbox_url"]
        inboxes.add(inbox)

    for inbox_url in inboxes:
        _deliver_with_retry(post_slug=post_slug, activity=activity, inbox_url=inbox_url, db_path=db_path)


def _deliver_with_retry(
    post_slug: str,
    activity: dict,
    inbox_url: str,
    db_path: Path,
) -> None:
    actor = get_actor()
    if actor is None:
        return

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT OR IGNORE INTO ap_deliveries (post_slug, target_inbox, status) VALUES (?,?,?)",
            (post_slug, inbox_url, "pending"),
        )
        conn.commit()
    finally:
        conn.close()

    last_error: str | None = None
    for attempt, delay in enumerate(_BACKOFF[:_RETRIES]):
        try:
            resp = deliver_activity(activity=activity, inbox_url=inbox_url, actor=actor, timeout=10.0)
            if resp.status_code < 300:
                _update_delivery(db_path, post_slug, inbox_url, "delivered", None)
                return
            last_error = f"HTTP {resp.status_code}"
        except Exception as exc:
            last_error = str(exc)[:200]

        if attempt < _RETRIES - 1:
            time.sleep(delay)

    _update_delivery(db_path, post_slug, inbox_url, "failed", last_error)
    logger.warning("AP delivery failed after %d attempts to %s: %s", _RETRIES, inbox_url, last_error)


def _update_delivery(
    db_path: Path,
    post_slug: str,
    inbox_url: str,
    status: str,
    error: str | None,
) -> None:
    import sqlite3
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(str(db_path))
    try:
        if status == "delivered":
            conn.execute(
                """UPDATE ap_deliveries SET status=?, attempts=attempts+1, delivered_at=?
                   WHERE post_slug=? AND target_inbox=?""",
                (status, now, post_slug, inbox_url),
            )
        else:
            conn.execute(
                """UPDATE ap_deliveries SET status=?, attempts=attempts+1, last_error=?
                   WHERE post_slug=? AND target_inbox=?""",
                (status, error, post_slug, inbox_url),
            )
        conn.commit()
    finally:
        conn.close()
