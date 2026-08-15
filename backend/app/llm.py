"""LLM-based daily goal selection, using Groq's free-tier API.

Runs synchronously on the first /api/today request of a new calendar day
(see app/daily_selection.py) — not a background cron. Retry settings below
are deliberately short: a person is waiting on this request, so we bound
the worst case tightly rather than patiently retrying like an unattended
job would.
"""
import json
import logging
import os
import time

import requests

from . import crud, models

logger = logging.getLogger("app.llm")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

REQUEST_TIMEOUT = 10  # seconds per call — Groq is normally sub-second; this is a generous cap
ATTEMPTS = 2
RETRY_WAIT = 2  # seconds between the 2 attempts


class LLMSelectionError(Exception):
    """Raised when the LLM call fails after all retries, its response
    can't be turned into a valid selection, or — when a focus category is
    active — it didn't actually honor the ~60-70% focus ratio. Callers
    should catch this and fall back to crud.generate_fallback_selection /
    crud.generate_focus_aware_selection."""


def _build_prompt(shortlist, recent_completions, recent_activity, count, focus_category=None) -> str:
    shortlist_lines = [
        f"- id: {g.id} | category: {category} | title: {g.title}"
        for category, goals in shortlist.items()
        for g in goals
    ]
    shortlist_text = "\n".join(shortlist_lines) or "(no pending goals)"

    recent_lines = [
        f"- {e.completed_on.isoformat()}: {e.goal_title} [{e.category}]"
        for e in recent_completions
    ]
    recent_text = "\n".join(recent_lines) or "(no completion history yet)"

    activity_lines = [
        f"- {day['date']}: " + ", ".join(f"{k}: {v}" for k, v in day["categories"].items())
        for day in recent_activity
    ]
    activity_text = "\n".join(activity_lines) or "(no recent daily activity)"

    focus_instruction = ""
    if focus_category:
        focus_count, _ = crud.compute_focus_split(count)
        focus_instruction = f"""
TODAY'S FOCUS CATEGORY: {focus_category}
The person has set this as their focus for the next few days. Aim for
roughly {focus_count} of the {count} picks to come from "{focus_category}"
specifically (about 60-70% of today's picks), with the rest from other
categories for variety. If "{focus_category}" doesn't have enough candidates
in the list above to hit that, fill the remainder from other categories
instead — never reduce the total count below {count}.
"""

    return f"""You are curating today's study plan for someone preparing for software engineering interviews.

CANDIDATE GOALS (pick only from this list, using their exact id):
{shortlist_text}

THEIR LAST 10 COMPLETED GOALS (most recent first):
{recent_text}

THEIR ACTIVITY OVER THE LAST FEW DAYS (date: category counts):
{activity_text}
{focus_instruction}
Pick exactly {count} goal ids from the candidate list above for today. Aim for a
well-balanced, sensibly-sequenced set of topics — avoid just repeating whatever
category they've done every day in a row, but do build on recent momentum where
it makes sense. Respond with ONLY a JSON object of this exact shape, nothing else:

{{"goal_ids": ["<id1>", "<id2>"]}}
"""


def _call_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        raise LLMSelectionError("GROQ_API_KEY is not set")

    resp = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def generate_with_llm(
    db, count: int, focus_category: str | None = None
) -> list[models.Goal]:
    """Up to 2 attempts, 2s apart. Raises LLMSelectionError if every
    attempt fails, the response can't be validated against the candidate
    shortlist, or — with a focus category active — the picks don't
    actually satisfy the expected focus ratio (deterministic selection
    doesn't need this check, since it's constructed to hit the ratio by
    definition; only the LLM's output needs verifying after the fact)."""
    if not GROQ_API_KEY:
        raise LLMSelectionError("GROQ_API_KEY is not set — skipping LLM, no point retrying")

    shortlist = crud.get_candidate_shortlist(db)
    all_candidates = {str(g.id): g for goals in shortlist.values() for g in goals}

    if not all_candidates:
        raise LLMSelectionError("No pending goals to choose from")

    expected_focus_count = 0
    if focus_category:
        focus_target, _ = crud.compute_focus_split(count)
        expected_focus_count = min(focus_target, len(shortlist.get(focus_category, [])))

    recent_completions = crud.get_recent_completions(db, limit=10)
    recent_activity = crud.get_recent_daily_activity(db, days=5)
    prompt = _build_prompt(shortlist, recent_completions, recent_activity, count, focus_category)

    last_error = None
    for attempt in range(ATTEMPTS):
        try:
            raw = _call_groq(prompt)
            parsed = json.loads(raw)
            goal_ids = parsed.get("goal_ids", [])

            picked, seen = [], set()
            for gid in goal_ids:
                g = all_candidates.get(str(gid))
                if g and g.id not in seen:
                    picked.append(g)
                    seen.add(g.id)

            if not picked:
                raise LLMSelectionError("LLM response contained no valid candidate ids")

            picked = picked[:count]

            if focus_category and expected_focus_count > 0:
                actual_focus_count = sum(1 for g in picked if g.category == focus_category)
                if actual_focus_count < expected_focus_count:
                    raise LLMSelectionError(
                        f"LLM picks didn't satisfy the focus ratio: got {actual_focus_count} "
                        f"from '{focus_category}', expected at least {expected_focus_count}"
                    )

            return picked
        except Exception as e:  # noqa: BLE001 — best-effort external call, any failure should retry/fallback
            last_error = e
            logger.warning("LLM selection attempt %d/%d failed: %s", attempt + 1, ATTEMPTS, e)
            if attempt < ATTEMPTS - 1:
                time.sleep(RETRY_WAIT)

    raise LLMSelectionError(f"LLM selection failed after {ATTEMPTS} attempts: {last_error}")