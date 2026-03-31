# app/api/endpoints/health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health_check():
    return {"status": "ok", "service": "kiwi-api"}


@router.get("/ping")
async def ping():
    return {"ping": "pong"}
