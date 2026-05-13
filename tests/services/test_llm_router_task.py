"""Tests for task-based routing added to get_meal_plan_router()."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _make_task_ctx(url: str = "http://node:8080") -> MagicMock:
    """Mock context manager returned by task_allocate()."""
    alloc = MagicMock()
    alloc.url = url
    alloc.allocation_id = "alloc-task-1"
    alloc.service = "cf-text"
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=alloc)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _make_task_ctx_not_registered() -> MagicMock:
    """Mock context manager that raises TaskNotRegistered on enter."""
    from app.services.task_inference import TaskNotRegistered
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(side_effect=TaskNotRegistered("not registered"))
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _make_direct_alloc_ctx(url: str = "http://node:8080") -> MagicMock:
    """Mock context manager returned by CFOrchClient.allocate()."""
    alloc = MagicMock()
    alloc.url = url
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=alloc)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_task_path_returns_orch_router_on_success(monkeypatch):
    """get_meal_plan_router() returns _OrchTextRouter when task allocation succeeds."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    import unittest.mock as um
    # Patch the name as it exists in llm_router's own namespace (module-level import).
    with um.patch("app.services.meal_plan.llm_router.task_allocate",
                  return_value=_make_task_ctx(url="http://node:9001")):
        from app.services.meal_plan.llm_router import get_meal_plan_router, _OrchTextRouter
        router, ctx = get_meal_plan_router()

    assert isinstance(router, _OrchTextRouter)
    assert router._base_url == "http://node:9001"


def test_task_not_registered_falls_back_to_direct_allocate(monkeypatch):
    """get_meal_plan_router() falls back to direct cf-text allocation on TaskNotRegistered."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    direct_ctx = _make_direct_alloc_ctx(url="http://node:9002")

    import unittest.mock as um
    # Patch task_allocate in llm_router's namespace so TaskNotRegistered is raised.
    with um.patch("app.services.meal_plan.llm_router.task_allocate",
                  return_value=_make_task_ctx_not_registered()), \
         um.patch("app.services.meal_plan.llm_router.CFOrchClient") as MockClient:
        MockClient.return_value.allocate.return_value = direct_ctx
        from app.services.meal_plan.llm_router import get_meal_plan_router, _OrchTextRouter
        router, ctx = get_meal_plan_router()

    assert isinstance(router, _OrchTextRouter)
    assert router._base_url == "http://node:9002"


def test_no_cf_orch_url_returns_llm_router(monkeypatch):
    """get_meal_plan_router() returns LLMRouter when CF_ORCH_URL is not set."""
    monkeypatch.delenv("CF_ORCH_URL", raising=False)

    import unittest.mock as um
    mock_lr = MagicMock()
    with um.patch("app.services.meal_plan.llm_router.LLMRouter", return_value=mock_lr):
        from app.services.meal_plan.llm_router import get_meal_plan_router
        router, ctx = get_meal_plan_router()

    assert router is mock_lr
