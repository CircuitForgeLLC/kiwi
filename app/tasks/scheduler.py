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


def _orch_available() -> bool:
    """Return True if circuitforge_orch is installed in this environment."""
    try:
        import circuitforge_orch  # noqa: F401
        return True
    except ImportError:
        return False


def _use_orch() -> bool:
    """Return True if the OrchestratedScheduler should be used.

    Priority order:
      1. USE_ORCH_SCHEDULER env var — explicit override always wins.
      2. CLOUD_MODE=true — use orch in managed cloud deployments.
      3. circuitforge_orch installed — paid+ local users who have cf-orch
         set up get coordinator-aware scheduling (local GPU first) automatically.
    """
    override = settings.USE_ORCH_SCHEDULER
    if override is not None:
        return override
    return CLOUD_MODE or _orch_available()


def get_scheduler(db_path: Path) -> TaskScheduler:
    """Return the process-level TaskScheduler singleton for Kiwi.

    OrchestratedScheduler: coordinator-aware, fans out concurrent jobs across
    all registered cf-orch GPU nodes. Active when USE_ORCH_SCHEDULER=true,
    CLOUD_MODE=true, or circuitforge_orch is installed locally (paid+ users
    running their own cf-orch stack get this automatically; local GPU is
    preferred by the coordinator's allocation queue).

    LocalScheduler: serial FIFO, no coordinator dependency. Free-tier local
    installs without circuitforge_orch installed use this automatically.
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
