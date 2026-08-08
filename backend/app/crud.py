from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, schemas

DEFAULT_DAILY_GOAL_COUNT = 3


def create_goal(db: Session, goal: schemas.GoalCreate) -> models.Goal:
    db_goal = models.Goal(**goal.model_dump())
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal


def attach_entry_counts(db: Session, goals: list[models.Goal]) -> list[models.Goal]:
    """One grouped query for the whole list, instead of lazy-loading
    journal_entries per goal (which is what Goal.entry_count would do on
    its own — an N+1 that shows up on every /api/goals and /api/today call)."""
    if not goals:
        return goals
    ids = [g.id for g in goals]
    rows = (
        db.query(models.JournalEntry.goal_id, func.count(models.JournalEntry.id))
        .filter(models.JournalEntry.goal_id.in_(ids))
        .group_by(models.JournalEntry.goal_id)
        .all()
    )
    counts = dict(rows)
    for g in goals:
        g._entry_count_override = counts.get(g.id, 0)
    return goals


def list_goals(
    db: Session,
    category: str | None = None,
    status: str | None = None,
):
    q = db.query(models.Goal)
    if category:
        q = q.filter(models.Goal.category == category)
    if status:
        q = q.filter(models.Goal.status == status)
    goals = q.order_by(models.Goal.priority.asc(), models.Goal.created_at.asc()).all()
    return attach_entry_counts(db, goals)


def get_goal(db: Session, goal_id):
    return db.query(models.Goal).filter(models.Goal.id == goal_id).first()


def record_completion_event(db: Session, goal: models.Goal) -> None:
    """Append-only: only ever inserts once per goal, on its first-ever
    completion. Safe to call every time a goal is marked completed —
    re-completions after an uncheck are silently ignored."""
    already_recorded = (
        db.query(models.CompletionEvent)
        .filter(models.CompletionEvent.goal_id == goal.id)
        .first()
    )
    if already_recorded:
        return
    event = models.CompletionEvent(
        goal_id=goal.id,
        goal_title=goal.title,
        category=goal.category,
        completed_on=date.today(),
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # race condition safety net — the unique constraint on goal_id
        # already protects us, just swallow the duplicate quietly.
        db.rollback()


def update_goal(db: Session, goal_id, updates: schemas.GoalUpdate):
    db_goal = get_goal(db, goal_id)
    if not db_goal:
        return None
    data = updates.model_dump(exclude_unset=True)
    newly_completed = (
        data.get("status") == models.Status.COMPLETED
        and db_goal.status != models.Status.COMPLETED
    )
    if newly_completed:
        db_goal.completed_at = func.now()
    if data.get("status") == models.Status.PENDING:
        db_goal.completed_at = None
    for key, value in data.items():
        setattr(db_goal, key, value)
    db.commit()
    db.refresh(db_goal)
    if newly_completed:
        record_completion_event(db, db_goal)
    return db_goal


def delete_goal(db: Session, goal_id) -> bool:
    db_goal = get_goal(db, goal_id)
    if not db_goal:
        return False
    db.delete(db_goal)
    db.commit()
    return True


def _round_robin_pick(pending_goals: list[models.Goal], count: int) -> list[models.Goal]:
    """Pick goals cycling across categories so a single subject doesn't
    dominate a day, falling back to plain priority order within a category."""
    by_category: dict[str, list[models.Goal]] = {}
    for g in pending_goals:
        by_category.setdefault(g.category, []).append(g)
    for bucket in by_category.values():
        bucket.sort(key=lambda g: (g.priority, g.created_at))

    picked: list[models.Goal] = []
    categories = list(by_category.keys())
    i = 0
    while len(picked) < count and categories:
        cat = categories[i % len(categories)]
        bucket = by_category[cat]
        if bucket:
            picked.append(bucket.pop(0))
        if not bucket:
            categories.remove(cat)
            i = 0
            continue
        i += 1
    return picked


def get_stats(db: Session) -> dict:
    goals = db.query(models.Goal).all()
    total = len(goals)
    completed = sum(1 for g in goals if g.status == models.Status.COMPLETED)

    by_category: dict[str, dict[str, int]] = {}
    for g in goals:
        cat = g.category.value if hasattr(g.category, "value") else g.category
        bucket = by_category.setdefault(cat, {"total": 0, "completed": 0})
        bucket["total"] += 1
        if g.status == models.Status.COMPLETED:
            bucket["completed"] += 1

    return {"total": total, "completed": completed, "by_category": by_category}


# ---- journal entries (per-goal learning journey) ----

def list_journal_entries(db: Session, goal_id) -> list[models.JournalEntry]:
    return (
        db.query(models.JournalEntry)
        .filter(models.JournalEntry.goal_id == goal_id)
        .order_by(models.JournalEntry.created_at.desc())
        .all()
    )


def create_journal_entry(
    db: Session, goal_id, entry: schemas.JournalEntryCreate
) -> models.JournalEntry | None:
    if not get_goal(db, goal_id):
        return None
    db_entry = models.JournalEntry(goal_id=goal_id, **entry.model_dump())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


def get_journal_entry(db: Session, entry_id) -> models.JournalEntry | None:
    return (
        db.query(models.JournalEntry)
        .filter(models.JournalEntry.id == entry_id)
        .first()
    )


def update_journal_entry(
    db: Session, entry_id, updates: schemas.JournalEntryUpdate
) -> models.JournalEntry | None:
    db_entry = get_journal_entry(db, entry_id)
    if not db_entry:
        return None
    for key, value in updates.model_dump(exclude_unset=True).items():
        setattr(db_entry, key, value)
    db.commit()
    db.refresh(db_entry)
    return db_entry


def delete_journal_entry(db: Session, entry_id) -> bool:
    db_entry = get_journal_entry(db, entry_id)
    if not db_entry:
        return False
    db.delete(db_entry)
    db.commit()
    return True


# ---- settings ----

def get_settings(db: Session) -> models.Settings:
    settings = db.query(models.Settings).filter(models.Settings.id == 1).first()
    if not settings:
        settings = models.Settings(id=1, daily_goal_count=DEFAULT_DAILY_GOAL_COUNT)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(db: Session, updates: schemas.SettingsUpdate) -> models.Settings:
    settings = get_settings(db)
    settings.daily_goal_count = updates.daily_goal_count
    db.commit()
    db.refresh(settings)
    return settings


# ---- daily selection: candidate pool + LLM/fallback context ----

def get_candidate_shortlist(db: Session, per_category: int = 5) -> dict[str, list[models.Goal]]:
    """Next N pending goals per category, in priority order — the shortlist
    the LLM (or the fallback logic) actually picks from, rather than
    handing it the entire backlog."""
    pending = (
        db.query(models.Goal)
        .filter(models.Goal.status == models.Status.PENDING)
        .order_by(models.Goal.priority.asc(), models.Goal.created_at.asc())
        .all()
    )
    by_category: dict[str, list[models.Goal]] = {}
    for g in pending:
        cat = g.category.value if hasattr(g.category, "value") else g.category
        bucket = by_category.setdefault(cat, [])
        if len(bucket) < per_category:
            bucket.append(g)
    return by_category


def get_recent_completions(db: Session, limit: int = 10) -> list[models.CompletionEvent]:
    return (
        db.query(models.CompletionEvent)
        .order_by(models.CompletionEvent.completed_at.desc())
        .limit(limit)
        .all()
    )


def get_recent_daily_activity(db: Session, days: int = 5) -> list[dict]:
    """Last N *distinct dates* that have any completions, each with a
    per-category breakdown — e.g. [{"date": "2026-08-03", "categories":
    {"DSA": 2, "High Level Design": 1}}, ...], most recent first."""
    since = date.today() - timedelta(days=days * 3)  # generous window in case of gaps
    events = (
        db.query(models.CompletionEvent)
        .filter(models.CompletionEvent.completed_on >= since)
        .order_by(models.CompletionEvent.completed_on.desc())
        .all()
    )
    by_date: dict[date, dict[str, int]] = {}
    for e in events:
        cat = e.category.value if hasattr(e.category, "value") else e.category
        day_bucket = by_date.setdefault(e.completed_on, {})
        day_bucket[cat] = day_bucket.get(cat, 0) + 1

    ordered_dates = sorted(by_date.keys(), reverse=True)[:days]
    return [
        {"date": d.isoformat(), "categories": by_date[d]}
        for d in ordered_dates
    ]


# ---- daily selection: fallback (no LLM / LLM failed) ----

def generate_fallback_selection(db: Session, count: int) -> list[models.Goal]:
    """Deterministic fallback used when the LLM call fails after retries,
    or when there's nothing to send it yet:
    - if any completion history exists, prefer the next pending goals from
      the category (or categories) most recently worked in, then fill any
      remaining slots via round robin across everything else;
    - if there's no history at all, plain round robin across all categories.
    """
    pending = (
        db.query(models.Goal)
        .filter(models.Goal.status == models.Status.PENDING)
        .order_by(models.Goal.priority.asc(), models.Goal.created_at.asc())
        .all()
    )
    if not pending:
        return []

    recent = get_recent_completions(db, limit=10)
    if not recent:
        return _round_robin_pick(pending, count)

    # most-recently-worked-in categories first, most recent occurrence wins
    recent_categories: list[str] = []
    for e in recent:
        cat = e.category.value if hasattr(e.category, "value") else e.category
        if cat not in recent_categories:
            recent_categories.append(cat)

    picked: list[models.Goal] = []
    remaining = list(pending)

    for cat in recent_categories:
        if len(picked) >= count:
            break
        for g in list(remaining):
            if len(picked) >= count:
                break
            g_cat = g.category.value if hasattr(g.category, "value") else g.category
            if g_cat == cat:
                picked.append(g)
                remaining.remove(g)

    if len(picked) < count:
        picked.extend(_round_robin_pick(remaining, count - len(picked)))

    return picked[:count]


def apply_daily_selection(
    db: Session,
    target_date: date,
    goals: list[models.Goal],
    source: models.GenerationSource,
) -> list[models.Goal]:
    """Idempotent: if daily_goals rows already exist for target_date, this
    is a no-op (returns the existing selection instead)."""
    existing = (
        db.query(models.DailyGoal)
        .filter(models.DailyGoal.surfaced_on == target_date)
        .all()
    )
    if existing:
        goal_ids = [e.goal_id for e in existing]
        found = db.query(models.Goal).filter(models.Goal.id.in_(goal_ids)).all()
        order = {gid: idx for idx, gid in enumerate(goal_ids)}
        found.sort(key=lambda g: order[g.id])
        return found

    for idx, g in enumerate(goals):
        db.add(
            models.DailyGoal(
                goal_id=g.id, surfaced_on=target_date, sort_order=idx, source=source
            )
        )
    db.commit()
    return goals


def get_today_source(db: Session, target_date: date) -> str:
    row = (
        db.query(models.DailyGoal)
        .filter(models.DailyGoal.surfaced_on == target_date)
        .first()
    )
    if not row:
        return models.GenerationSource.FALLBACK_ROUND_ROBIN.value
    return row.source.value if hasattr(row.source, "value") else row.source


def get_or_create_today(db: Session) -> tuple[list[models.Goal], str]:
    """The sole trigger for daily selection: runs on the first /api/today
    request of a new calendar day (no more 3 AM cron — see
    app/daily_selection.py for the LLM-then-fallback logic, and llm.py's
    module docstring for why its retries are short: a person is waiting
    on this request)."""
    today = date.today()
    existing = (
        db.query(models.DailyGoal)
        .filter(models.DailyGoal.surfaced_on == today)
        .order_by(models.DailyGoal.sort_order.asc())
        .all()
    )
    if existing:
        goal_ids = [e.goal_id for e in existing]
        goals = db.query(models.Goal).filter(models.Goal.id.in_(goal_ids)).all()
        order = {gid: idx for idx, gid in enumerate(goal_ids)}
        goals.sort(key=lambda g: order[g.id])
        return attach_entry_counts(db, goals), get_today_source(db, today)

    from .daily_selection import generate_for_today  # local import: avoids a
    # circular import with llm.py (which imports crud.py at module load time)

    picked, source = generate_for_today(db)
    saved = apply_daily_selection(db, today, picked, source)
    return attach_entry_counts(db, saved), source.value


# ---- activity heatmap ----

def get_heatmap_data(db: Session, days: int = 365) -> dict:
    start = date.today() - timedelta(days=days - 1)

    events = (
        db.query(models.CompletionEvent)
        .filter(models.CompletionEvent.completed_on >= start)
        .all()
    )
    counts_by_date: dict[date, int] = {}
    for e in events:
        counts_by_date[e.completed_on] = counts_by_date.get(e.completed_on, 0) + 1

    daily_rows = (
        db.query(models.DailyGoal)
        .filter(models.DailyGoal.surfaced_on >= start)
        .all()
    )
    surfaced_by_date: dict[date, list] = {}
    for row in daily_rows:
        surfaced_by_date.setdefault(row.surfaced_on, []).append(row.goal_id)

    all_goal_ids = {gid for ids in surfaced_by_date.values() for gid in ids}
    status_by_id: dict = {}
    if all_goal_ids:
        status_by_id = dict(
            db.query(models.Goal.id, models.Goal.status)
            .filter(models.Goal.id.in_(all_goal_ids))
            .all()
        )

    perfect_by_date: dict[date, bool] = {}
    for d, goal_ids in surfaced_by_date.items():
        if not goal_ids:
            continue
        perfect_by_date[d] = all(
            status_by_id.get(gid) == models.Status.COMPLETED for gid in goal_ids
        )

    days_out = []
    cursor = start
    today = date.today()
    while cursor <= today:
        days_out.append(
            {
                "date": cursor.isoformat(),
                "count": counts_by_date.get(cursor, 0),
                "perfect_day": perfect_by_date.get(cursor, False),
            }
        )
        cursor += timedelta(days=1)

    current_streak = 0
    cursor = today
    active_dates = set(counts_by_date.keys())
    while cursor in active_dates:
        current_streak += 1
        cursor -= timedelta(days=1)

    longest_streak = 0
    run = 0
    for day in days_out:
        if day["count"] > 0:
            run += 1
            longest_streak = max(longest_streak, run)
        else:
            run = 0

    total_completions = db.query(models.CompletionEvent).count()

    return {
        "days": days_out,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "total_completions": total_completions,
    }