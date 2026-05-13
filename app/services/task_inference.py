# app/services/task_inference.py
# BSL 1.1 — LLM feature
"""Task-based service allocation via the cf-orch coordinator.

Calls POST /api/inference/task instead of a hardcoded service type.
The coordinator resolves model_id and service_type from assignments.yaml.

Fallback contract (for callers):
  - 404 → TaskNotRegistered  (fall back to direct client.allocate())
  - other error → RuntimeError
  - CF_ORCH_URL unset → RuntimeError (guard with os.environ.get first)
"""
from __future__ import annotations

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


class TaskNotRegistered(Exception):
    """Coordinator returned 404 for a product/task pair.

    Means the task is not yet in assignments.yaml. Callers should fall
    back to direct service allocation (client.allocate()).
    """


@dataclass(frozen=True)
class Allocation:
    url: str
    allocation_id: str
    service: str


def _orch_url() -> str:
    return os.environ.get("CF_ORCH_URL", "").rstrip("/")


@contextmanager
def task_allocate(
    product: str,
    task: str,
    *,
    service_hint: str,
    ttl_s: float = 120.0,
) -> Generator[Allocation, None, None]:
    """Context manager: allocate a service via task-based routing.

    Calls POST /api/inference/task, yields Allocation, releases on exit.
    Supports both `with task_allocate(...) as alloc:` and manual
    `ctx = task_allocate(...); alloc = ctx.__enter__()` patterns.

    **Sync-only**: uses the synchronous httpx API. Do not call from an
    ``async def`` handler without wrapping in ``asyncio.to_thread``. Current
    call sites (``llm_router.py``, ``vl_model.py``) are synchronous.

    Args:
        product: CF product name (e.g. "kiwi")
        task: Task identifier (e.g. "meal_plan", "ocr")
        service_hint: Service type for the release DELETE call. The
            coordinator response does not include service_type, so the
            caller provides it. When the coordinator is updated to return
            service in the response (cf-orch#63), this becomes unused.
        ttl_s: Allocation TTL in seconds.

    Raises:
        TaskNotRegistered: Coordinator returned 404.
        RuntimeError: Coordinator unreachable, returned non-404 error, or
            returned a malformed (non-JSON / missing fields) response.
        RuntimeError: CF_ORCH_URL is not set.
    """
    base = _orch_url()
    if not base:
        raise RuntimeError("CF_ORCH_URL is not set")

    try:
        resp = httpx.post(
            f"{base}/api/inference/task",
            json={"product": product, "task": task, "payload": {}},
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        raise RuntimeError(f"cf-orch unreachable: {exc}") from exc

    if resp.status_code == 404:
        raise TaskNotRegistered(
            f"No assignment for product={product!r} task={task!r} — "
            "ensure cf-orch#61/62 are deployed and coordinator reloaded"
        )
    if not resp.is_success:
        raise RuntimeError(
            f"cf-orch /api/inference/task failed: "
            f"HTTP {resp.status_code} — {resp.text[:200]}"
        )

    try:
        data = resp.json()
        alloc = Allocation(
            url=data["url"],
            allocation_id=data["allocation_id"],
            service=data.get("service") or service_hint,
        )
    except (KeyError, ValueError) as exc:
        raise RuntimeError(
            f"cf-orch /api/inference/task returned malformed response: {exc} — "
            f"body: {resp.text[:200]}"
        ) from exc

    try:
        yield alloc
    finally:
        try:
            httpx.delete(
                f"{base}/api/services/{alloc.service}/allocations/{alloc.allocation_id}",
                timeout=10.0,
            )
        except Exception as exc:
            logger.debug("cf-orch task allocation release failed (non-fatal): %s", exc)
