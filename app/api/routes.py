from fastapi import APIRouter
from app.api.endpoints import health, receipts, export, inventory, ocr, recipes, settings, staples

api_router = APIRouter()

api_router.include_router(health.router,     prefix="/health",    tags=["health"])
api_router.include_router(receipts.router,   prefix="/receipts",  tags=["receipts"])
api_router.include_router(ocr.router,        prefix="/receipts",  tags=["ocr"])
api_router.include_router(export.router,                          tags=["export"])
api_router.include_router(inventory.router,  prefix="/inventory", tags=["inventory"])
api_router.include_router(recipes.router,    prefix="/recipes",   tags=["recipes"])
api_router.include_router(settings.router,   prefix="/settings",  tags=["settings"])
api_router.include_router(staples.router,    prefix="/staples",   tags=["staples"])