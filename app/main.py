#!/usr/bin/env python
# app/main.py

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Kiwi API...")
    settings.ensure_dirs()
    yield
    logger.info("Kiwi API shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Pantry tracking + leftover recipe suggestions",
    version="0.1.0",
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
