from fastapi import APIRouter
from app.api.endpoints import health, receipts, export, inventory, ocr

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(receipts.router, prefix="/receipts", tags=["receipts"])
api_router.include_router(ocr.router, prefix="/receipts", tags=["ocr"])  # OCR endpoints under /receipts
api_router.include_router(export.router, tags=["export"])  # No prefix, uses /export in the router
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])