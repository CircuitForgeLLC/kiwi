# app/services/ap/mastodon.py
# MIT License

from __future__ import annotations

import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_APP_SCOPES = "write:statuses"
_APP_NAME = "Kiwi Pantry"
_APP_WEBSITE = "https://circuitforge.tech/kiwi"


def register_app(instance_url: str, redirect_uri: str) -> dict:
    """Dynamically register Kiwi as an OAuth app on the user's Mastodon instance.

    Returns the app credentials dict (client_id, client_secret, etc.).
    Raises httpx.HTTPError on failure.
    """
    url = instance_url.rstrip("/") + "/api/v1/apps"
    resp = httpx.post(
        url,
        data={
            "client_name": _APP_NAME,
            "redirect_uris": redirect_uri,
            "scopes": _APP_SCOPES,
            "website": _APP_WEBSITE,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


def build_authorize_url(instance_url: str, client_id: str, redirect_uri: str) -> str:
    """Return the OAuth authorize URL to redirect the user to."""
    return (
        f"{instance_url.rstrip('/')}/oauth/authorize"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={_APP_SCOPES}"
    )


def exchange_code(
    instance_url: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> str:
    """Exchange an authorization code for an access token. Returns the token string."""
    url = instance_url.rstrip("/") + "/oauth/token"
    resp = httpx.post(
        url,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
            "scope": _APP_SCOPES,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def post_status(instance_url: str, access_token: str, content: str) -> dict:
    """Post a status to the user's Mastodon account. Returns the status response dict."""
    url = instance_url.rstrip("/") + "/api/v1/statuses"
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        json={"status": content, "visibility": "public"},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def build_post_content(post: dict) -> str:
    """Format a community post dict as Mastodon-ready plain text."""
    title = post.get("title") or "Untitled"
    recipe = post.get("recipe_name")
    notes = post.get("outcome_notes") or post.get("description")
    tags_raw: list[str] = post.get("dietary_tags") or []

    lines = []
    if recipe and recipe != title:
        lines.append(f"🍽 {title} — {recipe}")
    else:
        lines.append(f"🍽 {title}")

    if notes:
        snippet = notes[:200].strip()
        if len(notes) > 200:
            snippet += "…"
        lines.append(f"\n{snippet}")

    hashtags = ["#Kiwi", "#Cooking"]
    for tag in tags_raw[:3]:
        ht = "#" + "".join(w.capitalize() for w in tag.replace("-", " ").split())
        hashtags.append(ht)
    lines.append("\n" + " ".join(hashtags))

    return "\n".join(lines)


def store_token(
    db_path: Path,
    directus_user_id: str,
    instance_url: str,
    access_token: str,
    encryption_key: str | None,
) -> None:
    """Persist a Mastodon access token in the user's local kiwi.db."""
    token_to_store = _encrypt(access_token, encryption_key)
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT INTO mastodon_tokens (directus_user_id, instance_url, access_token)
               VALUES (?, ?, ?)
               ON CONFLICT(directus_user_id) DO UPDATE SET
                 instance_url=excluded.instance_url,
                 access_token=excluded.access_token,
                 updated_at=datetime('now')""",
            (directus_user_id, instance_url.rstrip("/"), token_to_store),
        )
        conn.commit()
    finally:
        conn.close()


def get_token(
    db_path: Path,
    directus_user_id: str,
    encryption_key: str | None,
) -> tuple[str, str] | None:
    """Return (instance_url, plaintext_access_token) or None if not connected."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT instance_url, access_token FROM mastodon_tokens WHERE directus_user_id = ?",
            (directus_user_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return row[0], _decrypt(row[1], encryption_key)


def delete_token(db_path: Path, directus_user_id: str) -> None:
    """Remove the user's stored Mastodon token."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "DELETE FROM mastodon_tokens WHERE directus_user_id = ?", (directus_user_id,)
        )
        conn.commit()
    finally:
        conn.close()


def _encrypt(plaintext: str, key: str | None) -> str:
    if key is None:
        return plaintext
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode()).encrypt(plaintext.encode()).decode()
    except Exception:
        logger.warning("Mastodon token encryption failed — storing plaintext")
        return plaintext


def _decrypt(ciphertext: str, key: str | None) -> str:
    if key is None:
        return ciphertext
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode()).decrypt(ciphertext.encode()).decode()
    except Exception:
        logger.warning("Mastodon token decryption failed — returning as-is")
        return ciphertext
