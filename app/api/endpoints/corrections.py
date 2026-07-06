# app/api/endpoints/corrections.py — user corrections to LLM output for SFT training
from circuitforge_core.api import make_corrections_router

from app.db.session import get_db

router = make_corrections_router(get_db=get_db, product="kiwi")
