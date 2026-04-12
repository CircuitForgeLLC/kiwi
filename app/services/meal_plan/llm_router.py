# app/services/meal_plan/llm_router.py
# BSL 1.1 — LLM feature
"""Provide a router-compatible LLM client for meal plan generation tasks.

Cloud (CF_ORCH_URL set):
  Allocates a cf-text service via cf-orch (3B-7B GGUF, ~2GB VRAM).
  Returns an _OrchTextRouter that wraps the cf-text HTTP endpoint
  with a .complete(system, user, **kwargs) interface.

Local / self-hosted (no CF_ORCH_URL):
  Returns an LLMRouter instance which tries ollama, vllm, or any
  backend configured in ~/.config/circuitforge/llm.yaml.

Both paths expose the same interface so llm_timing.py and llm_planner.py
need no knowledge of the backend.
"""
from __future__ import annotations

import logging
import os
from contextlib import nullcontext

logger = logging.getLogger(__name__)

# cf-orch service name and VRAM budget for meal plan LLM tasks.
# These are lighter than recipe_llm (4.0 GB) — cf-text handles them.
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


def get_meal_plan_router():
    """Return an LLM client for meal plan tasks.

    Tries cf-orch cf-text allocation first (cloud); falls back to LLMRouter
    (local ollama/vllm). Returns None if no backend is available.
    """
    cf_orch_url = os.environ.get("CF_ORCH_URL")
    if cf_orch_url:
        try:
            from circuitforge_orch.client import CFOrchClient
            client = CFOrchClient(cf_orch_url)
            ctx = client.allocate(
                service=_SERVICE_TYPE,
                ttl_s=_TTL_S,
                caller=_CALLER,
            )
            alloc = ctx.__enter__()
            if alloc is not None:
                return _OrchTextRouter(alloc.url), ctx
        except Exception as exc:
            logger.debug("cf-orch cf-text allocation failed, falling back to LLMRouter: %s", exc)

    # Local fallback: LLMRouter (ollama / vllm / openai-compat)
    try:
        from circuitforge_core.llm.router import LLMRouter
        return LLMRouter(), nullcontext(None)
    except FileNotFoundError:
        logger.debug("LLMRouter: no llm.yaml and no LLM env vars — meal plan LLM disabled")
        return None, nullcontext(None)
    except Exception as exc:
        logger.debug("LLMRouter init failed: %s", exc)
        return None, nullcontext(None)
