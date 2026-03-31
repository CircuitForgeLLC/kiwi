"""Tests for kiwi background task runner."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tasks.runner import (
    LLM_TASK_TYPES,
    VRAM_BUDGETS,
    insert_task,
    run_task,
)


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db = tmp_path / "kiwi.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE background_tasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type  TEXT    NOT NULL,
            job_id     INTEGER NOT NULL DEFAULT 0,
            status     TEXT    NOT NULL DEFAULT 'queued',
            params     TEXT,
            error      TEXT,
            created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE inventory_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            expiry_date TEXT
        );
        INSERT INTO inventory_items (name, expiry_date) VALUES ('mystery tofu', NULL);
    """)
    conn.commit()
    conn.close()
    return db


def test_llm_task_types_defined():
    assert "expiry_llm_fallback" in LLM_TASK_TYPES


def test_vram_budgets_defined():
    assert "expiry_llm_fallback" in VRAM_BUDGETS
    assert VRAM_BUDGETS["expiry_llm_fallback"] > 0


def test_insert_task_creates_row(tmp_db: Path):
    task_id, is_new = insert_task(tmp_db, "expiry_llm_fallback", job_id=1)
    assert is_new is True
    conn = sqlite3.connect(tmp_db)
    row = conn.execute("SELECT status FROM background_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    assert row[0] == "queued"


def test_insert_task_dedup(tmp_db: Path):
    id1, new1 = insert_task(tmp_db, "expiry_llm_fallback", job_id=1)
    id2, new2 = insert_task(tmp_db, "expiry_llm_fallback", job_id=1)
    assert id1 == id2
    assert new1 is True
    assert new2 is False


def test_run_task_expiry_success(tmp_db: Path):
    params = json.dumps({"product_name": "Tofu", "category": "protein", "location": "fridge"})
    task_id, _ = insert_task(tmp_db, "expiry_llm_fallback", job_id=1, params=params)

    with patch("app.tasks.runner.ExpirationPredictor") as MockPredictor:
        instance = MockPredictor.return_value
        instance._llm_predict_days.return_value = 7
        run_task(tmp_db, task_id, "expiry_llm_fallback", 1, params)

    conn = sqlite3.connect(tmp_db)
    item = conn.execute("SELECT expiry_date FROM inventory_items WHERE id=1").fetchone()
    task = conn.execute("SELECT status FROM background_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    assert item[0] is not None, "expiry_date should be set"
    assert task[0] == "completed"


def test_run_task_expiry_llm_returns_none(tmp_db: Path):
    """If LLM returns None, task completes without writing expiry_date."""
    params = json.dumps({"product_name": "Unknown widget", "location": "fridge"})
    task_id, _ = insert_task(tmp_db, "expiry_llm_fallback", job_id=1, params=params)

    with patch("app.tasks.runner.ExpirationPredictor") as MockPredictor:
        instance = MockPredictor.return_value
        instance._llm_predict_days.return_value = None
        run_task(tmp_db, task_id, "expiry_llm_fallback", 1, params)

    conn = sqlite3.connect(tmp_db)
    item = conn.execute("SELECT expiry_date FROM inventory_items WHERE id=1").fetchone()
    task = conn.execute("SELECT status FROM background_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    assert item[0] is None, "expiry_date should remain NULL when LLM returns None"
    assert task[0] == "completed"


def test_run_task_missing_product_name_marks_failed(tmp_db: Path):
    params = json.dumps({})
    task_id, _ = insert_task(tmp_db, "expiry_llm_fallback", job_id=1, params=params)
    run_task(tmp_db, task_id, "expiry_llm_fallback", 1, params)

    conn = sqlite3.connect(tmp_db)
    task = conn.execute("SELECT status, error FROM background_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    assert task[0] == "failed"
    assert "product_name" in task[1]


def test_run_task_unknown_type_marks_failed(tmp_db: Path):
    task_id, _ = insert_task(tmp_db, "expiry_llm_fallback", job_id=1)
    run_task(tmp_db, task_id, "unknown_type", 1, None)

    conn = sqlite3.connect(tmp_db)
    task = conn.execute("SELECT status FROM background_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    assert task[0] == "failed"
