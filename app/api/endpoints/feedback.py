"""Feedback router — provided by circuitforge-core."""
from circuitforge_core.api import make_feedback_router
from app.core.config import settings

router = make_feedback_router(
    repo="Circuit-Forge/kiwi",
    product="kiwi",
    demo_mode_fn=lambda: settings.DEMO_MODE,
)
