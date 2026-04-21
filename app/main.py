#!/usr/bin/env python
# app/main.py

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.services.meal_plan.affiliates import register_kiwi_programs

# Structured key=value log lines — grep/awk-friendly for log-based analytics.
# Without basicConfig, app-level INFO logs are silently dropped.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
logger = logging.getLogger(__name__)

_BROWSE_REFRESH_INTERVAL_H = 24


async def _browse_counts_refresh_loop(corpus_path: str) -> None:
    """Refresh browse counts every 24 h while the container is running."""
    from app.db.store import _COUNT_CACHE
    from app.services.recipe.browse_counts_cache import load_into_memory, refresh

    while True:
        await asyncio.sleep(_BROWSE_REFRESH_INTERVAL_H * 3600)
        try:
            logger.info("browse_counts: starting scheduled refresh...")
            computed = await asyncio.to_thread(
                refresh, corpus_path, settings.BROWSE_COUNTS_PATH
            )
            load_into_memory(settings.BROWSE_COUNTS_PATH, _COUNT_CACHE, corpus_path)
            logger.info("browse_counts: scheduled refresh complete (%d sets)", computed)
        except Exception as exc:
            logger.warning("browse_counts: scheduled refresh failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Kiwi API...")
    settings.ensure_dirs()
    register_kiwi_programs()

    # Start LLM background task scheduler
    from app.tasks.scheduler import get_scheduler
    get_scheduler(settings.DB_PATH)
    logger.info("Task scheduler started.")

    # Initialize community store (no-op if COMMUNITY_DB_URL is not set)
    from app.api.endpoints.community import init_community_store
    init_community_store(settings.COMMUNITY_DB_URL)

    # Browse counts cache — warm in-memory cache from disk, refresh if stale.
    # Uses the corpus path the store will attach to at request time.
    corpus_path = os.environ.get("RECIPE_DB_PATH", str(settings.DB_PATH))
    try:
        from app.db.store import _COUNT_CACHE
        from app.services.recipe.browse_counts_cache import (
            is_stale, load_into_memory, refresh,
        )
        if is_stale(settings.BROWSE_COUNTS_PATH):
            logger.info("browse_counts: cache stale — refreshing in background...")
            asyncio.create_task(
                asyncio.to_thread(refresh, corpus_path, settings.BROWSE_COUNTS_PATH)
            )
        else:
            load_into_memory(settings.BROWSE_COUNTS_PATH, _COUNT_CACHE, corpus_path)
    except Exception as exc:
        logger.warning("browse_counts: startup init failed (live FTS fallback active): %s", exc)

    # Nightly background refresh loop
    asyncio.create_task(_browse_counts_refresh_loop(corpus_path))

    yield

    # Graceful scheduler shutdown
    from app.tasks.scheduler import get_scheduler, reset_scheduler
    get_scheduler(settings.DB_PATH).shutdown(timeout=10.0)
    reset_scheduler()
    logger.info("Kiwi API shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Pantry tracking + leftover recipe suggestions",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    return {"service": "kiwi-api", "docs": "/docs"}
