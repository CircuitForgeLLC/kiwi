# app/services/meal_plan/llm_router.py
# BSL 1.1 — LLM feature
"""Provide a router-compatible LLM client for meal plan generation tasks.

Cloud (CF_ORCH_URL set), tier 1 — task-based routing (preferred):
  Calls /api/inference/task with product=kiwi, task=meal_plan.
  The coordinator resolves the model from assignments.yaml.

Cloud (CF_ORCH_URL set), tier 2 — direct allocation (fallback):
  Allocates cf-text directly via client.allocate(). Used when the task
  is not yet registered in the coordinator (cf-orch#61 not deployed).

Local / self-hosted (no CF_ORCH_URL):
  Returns an LLMRouter instance which tries ollama, vllm, or any
  backend configured in ~/.config/circuitforge/llm.yaml.

All paths expose the same (router, ctx) interface so llm_planner.py
needs no knowledge of the backend.
"""
from __future__ import annotations

import logging
import os
from contextlib import nullcontext

logger = logging.getLogger(__name__)

# cf-orch service name and TTL for direct-allocate fallback path.
_SERVICE_TYPE = "cf-text"
_TTL_S = 120.0
_CALLER = "kiwi-meal-plan"


class _OrchTextRouter:
    """Thin adapter that makes a cf-text HTTP endpoint look like LLMRouter."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def complete(
        self,
        system: str = "",
        user: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
        **_kwargs,
    ) -> str:
        from openai import OpenAI
        client = OpenAI(base_url=self._base_url + "/v1", api_key="any")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        try:
            model = client.models.list().data[0].id
        except Exception:
            model = "local"
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""


# Imported at module level so tests can patch the names in this module's namespace.
# app.services.task_inference.task_allocate — patch target for task routing tests.
try:
    from app.services.task_inference import TaskNotRegistered, task_allocate
    _HAS_TASK_INFERENCE = True
except ImportError:
    _HAS_TASK_INFERENCE = False

# circuitforge_orch.client.CFOrchClient — patch target for direct-allocate fallback tests.
try:
    from circuitforge_orch.client import CFOrchClient
except ImportError:
    CFOrchClient = None  # type: ignore[assignment,misc]

# circuitforge_core.llm.router.LLMRouter — patch target for local-inference tests.
try:
    from circuitforge_core.llm.router import LLMRouter
except (ImportError, FileNotFoundError):
    LLMRouter = None  # type: ignore[assignment,misc]


def get_meal_plan_router():
    """Return an LLM client for meal plan tasks.

    Returns (router, ctx) where ctx is a context manager the caller holds
    open for the duration of the LLM call. Returns (None, nullcontext(None))
    if no backend is available.
    """
    cf_orch_url = os.environ.get("CF_ORCH_URL")

    if cf_orch_url:
        # Tier 1: task-based routing — coordinator owns model selection.
        if _HAS_TASK_INFERENCE:
            try:
                ctx = task_allocate(
                    "kiwi", "meal_plan",
                    service_hint=_SERVICE_TYPE,
                    ttl_s=_TTL_S,
                )
                alloc = ctx.__enter__()
                return _OrchTextRouter(alloc.url), ctx
            except TaskNotRegistered:
                logger.debug(
                    "kiwi.meal_plan not in coordinator assignments — "
                    "falling back to direct cf-text allocation"
                )
            except Exception as exc:
                logger.debug("task allocation failed, trying direct allocate: %s", exc)

        # Tier 2: direct allocation — hardcoded service type.
        if CFOrchClient is not None:
            try:
                client = CFOrchClient(cf_orch_url)
                ctx = client.allocate(
                    service=_SERVICE_TYPE,
                    ttl_s=_TTL_S,
                    caller=_CALLER,
                )
                alloc = ctx.__enter__()
                if alloc is not None:
                    return _OrchTextRouter(alloc.url), ctx
                ctx.__exit__(None, None, None)  # release allocation before falling through
            except Exception as exc:
                logger.debug("cf-orch cf-text allocation failed, falling back to LLMRouter: %s", exc)

    # Tier 3: local inference — ollama / vllm / openai-compat.
    if LLMRouter is not None:
        try:
            return LLMRouter(), nullcontext(None)
        except FileNotFoundError:
            logger.debug("LLMRouter: no llm.yaml and no LLM env vars — meal plan LLM disabled")
            return None, nullcontext(None)
        except Exception as exc:
            logger.debug("LLMRouter init failed: %s", exc)
            return None, nullcontext(None)
    return None, nullcontext(None)
