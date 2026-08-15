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


def generate_for_today(
    db,
) -> tuple[list["models.Goal"], "models.GenerationSource", str | None, str | None]:
    """Returns (goals, source, focus_category, note)."""
    settings = crud.get_settings(db)  # lazily clears an expired focus, if any
    count = settings.daily_goal_count
    focus_category = settings.focus_category.name if settings.focus_category else None

    note = None
    if focus_category:
        expected = min(
            crud.compute_focus_split(count)[0],
            crud.get_focus_candidate_count(db, focus_category),
        )
        target = crud.compute_focus_split(count)[0]
        if expected < target:
            note = (
                f"Not enough pending goals in {focus_category} — filled the rest of "
                f"today's picks normally."
            )

    try:
        picked = generate_with_llm(db, count, focus_category=focus_category)
        return picked, models.GenerationSource.LLM, focus_category, note
    except LLMSelectionError as e:
        logger.warning("LLM generation failed, using fallback: %s", e)

        if focus_category:
            picked, _, _ = crud.generate_focus_aware_selection(db, count, focus_category)
        else:
            picked = crud.generate_fallback_selection(db, count)

        has_history = len(crud.get_recent_completions(db, limit=1)) > 0
        source = (
            models.GenerationSource.FALLBACK_HISTORY
            if has_history
            else models.GenerationSource.FALLBACK_ROUND_ROBIN
        )
        return picked, source, focus_category, note