"""Staple library endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.recipe.staple_library import StapleLibrary

router = APIRouter()
_lib = StapleLibrary()


@router.get("/")
async def list_staples(dietary: str | None = None) -> list[dict]:
    staples = _lib.filter_by_dietary(dietary) if dietary else _lib.list_all()
    return [
        {
            "slug": s.slug,
            "name": s.name,
            "description": s.description,
            "dietary_labels": s.dietary_labels,
            "yield_formats": list(s.yield_formats.keys()),
        }
        for s in staples
    ]


@router.get("/{slug}")
async def get_staple(slug: str) -> dict:
    staple = _lib.get(slug)
    if not staple:
        raise HTTPException(status_code=404, detail=f"Staple '{slug}' not found.")
    return {
        "slug": staple.slug,
        "name": staple.name,
        "description": staple.description,
        "dietary_labels": staple.dietary_labels,
        "base_ingredients": staple.base_ingredients,
        "base_method": staple.base_method,
        "base_time_minutes": staple.base_time_minutes,
        "yield_formats": staple.yield_formats,
        "compatible_styles": staple.compatible_styles,
    }
