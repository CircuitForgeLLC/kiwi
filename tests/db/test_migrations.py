import pytest
from pathlib import Path
from app.db.store import Store


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


def test_migration_028_adds_community_pseudonyms(tmp_db):
    """Migration 028 adds community_pseudonyms table to per-user kiwi.db."""
    store = Store(tmp_db)
    cur = store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='community_pseudonyms'"
    )
    assert cur.fetchone() is not None
    store.close()
