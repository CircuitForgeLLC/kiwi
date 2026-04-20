# app/tasks/scheduler.py
"""Kiwi LLM task scheduler — thin shim over circuitforge_core.tasks.scheduler.

Local mode (CLOUD_MODE unset): LocalScheduler — simple FIFO, no coordinator.
Cloud mode (CLOUD_MODE=true): OrchestratedScheduler — coordinator-aware, fans
out concurrent jobs across all registered cf-orch GPU nodes.
"""
from __future__ import annotations

from pathlib import Path

from circuitforge_core.tasks.scheduler import (
    TaskScheduler,
    get_scheduler as _base_get_scheduler,
    reset_scheduler as _reset_local,  # re-export for tests
)

from app.cloud_session import CLOUD_MODE
from app.core.config import settings
from app.tasks.runner import LLM_TASK_TYPES, VRAM_BUDGETS, run_task


def _use_orch() -> bool:
    """Return True if the OrchestratedScheduler should be used.

    Explicit USE_ORCH_SCHEDULER env var takes priority; falls back to CLOUD_MODE.
    """
    override = settings.USE_ORCH_SCHEDULER
    return CLOUD_MODE if override is None else override


def get_scheduler(db_path: Path) -> TaskScheduler:
    """Return the process-level TaskScheduler singleton for Kiwi.

    OrchestratedScheduler: coordinator-aware, fans out concurrent jobs across
    all registered cf-orch GPU nodes. Active when USE_ORCH_SCHEDULER=true or
    CLOUD_MODE=true (and USE_ORCH_SCHEDULER is not explicitly false).

    LocalScheduler: serial FIFO, no coordinator dependency. Default for local dev.
    """
    if _use_orch():
        try:
            from circuitforge_orch.scheduler import get_orch_scheduler
        except ImportError:
            import logging
            logging.getLogger(__name__).warning(
                "circuitforge_orch not installed — falling back to LocalScheduler"
            )
        else:
            return get_orch_scheduler(
                db_path=db_path,
                run_task_fn=run_task,
                task_types=LLM_TASK_TYPES,
                vram_budgets=VRAM_BUDGETS,
                coordinator_url=settings.COORDINATOR_URL,
                service_name="kiwi",
            )

    return _base_get_scheduler(
        db_path=db_path,
        run_task_fn=run_task,
        task_types=LLM_TASK_TYPES,
        vram_budgets=VRAM_BUDGETS,
        coordinator_url=settings.COORDINATOR_URL,
        service_name="kiwi",
    )


def reset_scheduler() -> None:
    """Shut down and clear the active scheduler singleton. TEST TEARDOWN ONLY."""
    if _use_orch():
        try:
            from circuitforge_orch.scheduler import reset_orch_scheduler
            reset_orch_scheduler()
            return
        except ImportError:
            pass
    _reset_local()
