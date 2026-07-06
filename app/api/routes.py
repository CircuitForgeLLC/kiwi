from fastapi import APIRouter

from app.api.endpoints import (
    export,
    feedback,
    feedback_attach,
    health,
    household,
    imitate,
    inventory,
    meal_plans,
    ocr,
    orch_usage,
    receipts,
    recipes,
    saved_recipes,
    session,
    settings,
    shopping,
    staples,
)
from app.api.endpoints.community import router as community_router
from app.api.endpoints.corrections import router as corrections_router
from app.api.endpoints.mastodon_oauth import router as mastodon_router
from app.api.endpoints.recipe_scan import router as recipe_scan_router
from app.api.endpoints.recipe_tags import router as recipe_tags_router

api_router = APIRouter()

api_router.include_router(session.router,        prefix="/session",        tags=["session"])
api_router.include_router(health.router,         prefix="/health",         tags=["health"])
api_router.include_router(receipts.router,       prefix="/receipts",       tags=["receipts"])
api_router.include_router(ocr.router,            prefix="/receipts",       tags=["ocr"])
api_router.include_router(export.router,                                   tags=["export"])
api_router.include_router(inventory.router,      prefix="/inventory",      tags=["inventory"])
api_router.include_router(saved_recipes.router,  prefix="/recipes/saved",  tags=["saved-recipes"])
# recipe_scan_router registered BEFORE recipes.router so /recipes/scan and /recipes/user
# take priority over /recipes/{recipe_id} (which would otherwise match them as int IDs).
api_router.include_router(recipe_scan_router,    prefix="/recipes",        tags=["recipe-scan"])
api_router.include_router(recipes.router,        prefix="/recipes",        tags=["recipes"])
api_router.include_router(settings.router,       prefix="/settings",       tags=["settings"])
api_router.include_router(staples.router,        prefix="/staples",        tags=["staples"])
api_router.include_router(feedback.router,        prefix="/feedback",       tags=["feedback"])
api_router.include_router(feedback_attach.router, prefix="/feedback",       tags=["feedback"])
api_router.include_router(household.router,      prefix="/household",      tags=["household"])
api_router.include_router(imitate.router,        prefix="/imitate",        tags=["imitate"])
api_router.include_router(meal_plans.router,     prefix="/meal-plans",     tags=["meal-plans"])
api_router.include_router(orch_usage.router,     prefix="/orch-usage",     tags=["orch-usage"])
api_router.include_router(shopping.router,       prefix="/shopping",       tags=["shopping"])
api_router.include_router(community_router)
api_router.include_router(recipe_tags_router)
api_router.include_router(corrections_router,    prefix="/corrections",    tags=["corrections"])
api_router.include_router(mastodon_router)
