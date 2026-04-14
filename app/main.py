#!/usr/bin/env python
# app/main.py

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.services.meal_plan.affiliates import register_kiwi_programs

logger = logging.getLogger(__name__)


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
