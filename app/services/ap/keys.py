# app/services/ap/keys.py
# MIT License

from __future__ import annotations

import logging
from pathlib import Path

from circuitforge_core.activitypub import CFActor, generate_rsa_keypair, load_actor_from_key_file

logger = logging.getLogger(__name__)

_actor: CFActor | None = None


def get_actor() -> CFActor | None:
    """Return the loaded instance actor, or None if AP is not enabled."""
    return _actor


def init_actor(host: str, key_path: Path) -> CFActor:
    """Load or generate the instance RSA keypair and build the CFActor singleton.

    Called once at startup when AP_ENABLED=true. Generates a new 2048-bit keypair
    if the key file does not yet exist (first boot).
    """
    global _actor

    key_path.parent.mkdir(parents=True, exist_ok=True)

    if not key_path.exists():
        logger.info("AP: no key file found at %s — generating new RSA-2048 keypair", key_path)
        private_pem, _pub = generate_rsa_keypair(bits=2048)
        key_path.write_text(private_pem, encoding="utf-8")
        key_path.chmod(0o600)

    base = f"https://{host}"
    actor_id = f"{base}/ap/actor"

    _actor = load_actor_from_key_file(
        actor_id=actor_id,
        username="kiwi",
        display_name="Kiwi Pantry",
        private_key_path=str(key_path),
        summary="Community pantry and recipe feed from a Kiwi instance.",
    )
    logger.info("AP: instance actor loaded — %s", actor_id)
    return _actor
