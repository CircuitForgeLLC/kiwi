# app/tasks/runner.py
"""Kiwi background task runner.

Implements the run_task_fn interface expected by circuitforge_core.tasks.scheduler.
Each kiwi LLM task type has its own handler below.

Public API:
    LLM_TASK_TYPES  — frozenset of task type strings to route through the scheduler
    VRAM_BUDGETS    — VRAM GB estimates per task type
    insert_task()   — deduplicating task insertion
    run_task()      — called by the scheduler batch worker
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from app.services.expiration_predictor import ExpirationPredictor

log = logging.getLogger(__name__)

LLM_TASK_TYPES: frozenset[str] = frozenset({"expiry_llm_fallback"})

VRAM_BUDGETS: dict[str, float] = {
    # ExpirationPredictor uses a small LLM (16 tokens out, single pass).
    "expiry_llm_fallback": 2.0,
}


def insert_task(
    db_path: Path,
    task_type: str,
    job_id: int,
    *,
    params: str | None = None,
) -> tuple[int, bool]:
    """Insert a background task if no identical task is already in-flight.

    Returns (task_id, True) if a new task was created.
    Returns (existing_id, False) if an identical task is already queued/running.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    existing = conn.execute(
        "SELECT id FROM background_tasks "
        "WHERE task_type=? AND job_id=? AND status IN ('queued','running')",
        (task_type, job_id),
    ).fetchone()
    if existing:
        conn.close()
        return existing["id"], False
    cursor = conn.execute(
        "INSERT INTO background_tasks (task_type, job_id, params) VALUES (?,?,?)",
        (task_type, job_id, params),
    )
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return task_id, True


def _update_task_status(
    db_path: Path, task_id: int, status: str, *, error: str = ""
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE background_tasks "
            "SET status=?, error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, error, task_id),
        )


def run_task(
    db_path: Path,
    task_id: int,
    task_type: str,
    job_id: int,
    params: str | None = None,
) -> None:
    """Execute one background task. Called by the scheduler's batch worker."""
    _update_task_status(db_path, task_id, "running")
    try:
        if task_type == "expiry_llm_fallback":
            _run_expiry_llm_fallback(db_path, job_id, params)
        else:
            raise ValueError(f"Unknown kiwi task type: {task_type!r}")
        _update_task_status(db_path, task_id, "completed")
    except Exception as exc:
        log.exception("Task %d (%s) failed: %s", task_id, task_type, exc)
        _update_task_status(db_path, task_id, "failed", error=str(exc))


def _run_expiry_llm_fallback(
    db_path: Path,
    item_id: int,
    params: str | None,
) -> None:
    """Predict expiry date via LLM for an inventory item and write result to DB.

    params JSON keys:
        product_name  (required) — e.g. "Trader Joe's Organic Tempeh"
        category      (optional) — category hint for the predictor
        location      (optional) — "fridge" | "freezer" | "pantry" (default: "fridge")
    """
    p = json.loads(params or "{}")
    product_name = p.get("product_name", "")
    category = p.get("category")
    location = p.get("location", "fridge")

    if not product_name:
        raise ValueError("expiry_llm_fallback: 'product_name' is required in params")

    predictor = ExpirationPredictor()
    days = predictor._llm_predict_days(product_name, category, location)

    if days is None:
        log.warning(
            "LLM expiry fallback returned None for item_id=%d product=%r — "
            "expiry_date will remain NULL",
            item_id,
            product_name,
        )
        return

    expiry = (date.today() + timedelta(days=days)).isoformat()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE inventory_items SET expiry_date=? WHERE id=?",
            (expiry, item_id),
        )

    log.info(
        "LLM expiry fallback: item_id=%d %r → %s (%d days)",
        item_id,
        product_name,
        expiry,
        days,
    )
