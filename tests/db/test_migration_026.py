# tests/db/test_migration_026.py
import pytest
from pathlib import Path
from app.db.store import Store


def test_migration_026_adds_community_pseudonyms(tmp_path):
    """Migration 026 adds community_pseudonyms table to per-user kiwi.db."""
    store = Store(tmp_path / "test.db")
    cur = store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='community_pseudonyms'"
    )
    assert cur.fetchone() is not None, "community_pseudonyms table must exist after migrations"
    store.close()


def test_migration_026_unique_index_enforces_single_current_pseudonym(tmp_path):
    """Only one is_current=1 pseudonym per directus_user_id is allowed."""
    store = Store(tmp_path / "test.db")
    store.conn.execute(
        "INSERT INTO community_pseudonyms (pseudonym, directus_user_id, is_current) VALUES (?, ?, 1)",
        ("PastaWitch", "user-abc-123"),
    )
    store.conn.commit()

    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "INSERT INTO community_pseudonyms (pseudonym, directus_user_id, is_current) VALUES (?, ?, 1)",
            ("NoodleNinja", "user-abc-123"),
        )
        store.conn.commit()

    store.close()


def test_migration_026_allows_historical_pseudonyms(tmp_path):
    """Multiple is_current=0 pseudonyms are allowed for the same user."""
    store = Store(tmp_path / "test.db")
    store.conn.executemany(
        "INSERT INTO community_pseudonyms (pseudonym, directus_user_id, is_current) VALUES (?, ?, 0)",
        [("OldName1", "user-abc-123"), ("OldName2", "user-abc-123")],
    )
    store.conn.commit()
    cur = store.conn.execute(
        "SELECT COUNT(*) FROM community_pseudonyms WHERE directus_user_id='user-abc-123'"
    )
    assert cur.fetchone()[0] == 2
    store.close()
