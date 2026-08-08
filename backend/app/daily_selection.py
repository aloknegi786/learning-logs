"""Decides today's goal selection: tries the LLM first, falls back to
deterministic selection on failure. Called once — the first time
/api/today is hit on a new calendar day (see main.py) — not on a
schedule. Kept separate from crud.py to avoid a circular import (llm.py
already imports crud.py for its context-gathering helpers).
"""
import logging

from . import crud, models
from .llm import LLMSelectionError, generate_with_llm

logger = logging.getLogger("app.daily_selection")


def generate_for_today(db) -> tuple[list["models.Goal"], "models.GenerationSource"]:
    settings = crud.get_settings(db)
    count = settings.daily_goal_count

    try:
        picked = generate_with_llm(db, count)
        return picked, models.GenerationSource.LLM
    except LLMSelectionError as e:
        logger.warning("LLM generation failed, using fallback: %s", e)
        picked = crud.generate_fallback_selection(db, count)
        has_history = len(crud.get_recent_completions(db, limit=1)) > 0
        source = (
            models.GenerationSource.FALLBACK_HISTORY
            if has_history
            else models.GenerationSource.FALLBACK_ROUND_ROBIN
        )
        return picked, source