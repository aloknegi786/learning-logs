"""What happens the moment a brand-new User row is created (see
main.py's /api/auth/google handler): either the standard starter
curriculum (everyone else), or — for the app's original single-user
owner, identified by OWNER_EMAIL — a one-time hydration of their real
historical data from the old, pre-multi-tenant database.

The legacy database has an OLDER schema (no user_id columns anywhere,
categories were globally unique by name, etc.) — reading it with the
current models.py's ORM classes would fail, since those now describe the
new shape. So the legacy side is read with plain SQL instead of the ORM;
only the writes into the new database go through the ORM.
"""
import logging
import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models
from .database import LegacySessionLocal

logger = logging.getLogger("app.provisioning")

OWNER_EMAIL = os.getenv("OWNER_EMAIL")

CURRICULUM: dict[str, list[str]] = {
    "OOP": [
        "Explain the 4 pillars: encapsulation, abstraction, inheritance, polymorphism",
        "Compare composition vs inheritance, with examples",
        "SOLID principles — write a short example violating & fixing each",
        "Abstract classes vs interfaces — when to use which",
        "Method overloading vs overriding",
    ],
    "Operating Systems": [
        "Process vs thread, and context switching cost",
        "Deadlock: 4 necessary conditions + prevention strategies",
        "Virtual memory, paging, and page replacement algorithms (LRU, FIFO)",
        "Scheduling algorithms: FCFS, SJF, Round Robin, Priority",
        "Mutex vs semaphore vs monitor",
    ],
    "Computer Networks": [
        "TCP vs UDP — handshake, reliability, use cases",
        "What happens when you type a URL into a browser (full flow)",
        "HTTP vs HTTPS, and how TLS handshake works",
        "DNS resolution steps",
        "Load balancing algorithms (round robin, least connections, consistent hashing)",
    ],
    "Data Structures & Algorithms": [
        "Arrays & Strings: two-pointer and sliding window patterns",
        "Linked Lists: reverse, detect cycle, merge two sorted lists",
        "Trees: BFS/DFS traversals, height, LCA",
        "Graphs: BFS/DFS, topological sort, Dijkstra's algorithm",
        "Dynamic Programming: 0/1 knapsack, longest common subsequence",
        "Heaps & Priority Queues: top-K problems",
        "Binary Search on answer space",
    ],
    "High Level Design": [
        "Design a URL shortener (TinyURL)",
        "Design a rate limiter",
        "Design a scalable chat application (WhatsApp-like)",
        "Design a news feed system (Twitter/Instagram)",
        "Design a distributed cache",
        "CAP theorem and how it shapes real system trade-offs",
    ],
    "Low Level Design": [
        "Design a parking lot system (classes, relationships)",
        "Design a tic-tac-toe / chess game engine",
        "Design an elevator control system",
        "Design a library management system",
        "Design a splitwise-style expense sharing system",
    ],
    "Design Patterns": [
        "Singleton pattern — implementation & pitfalls (thread safety)",
        "Factory & Abstract Factory patterns",
        "Observer pattern (pub/sub)",
        "Strategy pattern",
        "Decorator pattern",
        "Builder pattern",
    ],
}

EXTRA_CATEGORIES = ["Other"]


def is_owner(email: str) -> bool:
    return bool(OWNER_EMAIL) and email.strip().lower() == OWNER_EMAIL.strip().lower()


def seed_default_curriculum_for_user(db: Session, user_id) -> None:
    """The standard starter set every new (non-owner) user gets on their
    first login — the same curriculum backend/app/seed.py uses to
    initialize a fresh dev database, just scoped to one user's workspace
    instead of being global."""
    for name, titles in CURRICULUM.items():
        cat = models.Category(user_id=user_id, name=name)
        db.add(cat)
        db.flush()  # assigns cat.id without a full commit, so goals can reference it
        for i, title in enumerate(titles):
            db.add(models.Goal(user_id=user_id, title=title, category_id=cat.id, priority=100 + i))
    for name in EXTRA_CATEGORIES:
        db.add(models.Category(user_id=user_id, name=name))
    db.commit()


def hydrate_owner_from_legacy(db: Session, new_user_id) -> bool:
    """Copies categories/goals/journal_entries/completion_events from the
    legacy (pre-auth) database into this brand-new user's workspace,
    preserving original row ids — UUIDs are globally unique, so copying
    them across databases as-is can't collide. All-or-nothing: wrapped in
    a single transaction on the NEW database's side — if anything fails
    partway, nothing commits, so a retry (the next login attempt, since
    the User row itself is only committed by the caller after this
    returns) starts clean rather than leaving a half-populated account.
    daily_goals and settings are deliberately NOT copied — daily_goals
    regenerates naturally on the next Today visit, settings starts at the
    app default (per explicit instruction).

    Returns True if hydration ran, False if LEGACY_DATABASE_URL isn't
    configured (nothing to hydrate from — a no-op for every deployment
    that isn't specifically the app's own migration)."""
    if not LegacySessionLocal:
        return False

    legacy_db = LegacySessionLocal()
    try:
        categories = legacy_db.execute(text("SELECT id, name, created_at FROM categories")).all()
        goals = legacy_db.execute(
            text(
                "SELECT id, title, description, category_id, status, priority, "
                "created_at, completed_at FROM goals"
            )
        ).all()
        entries = legacy_db.execute(
            text(
                "SELECT id, goal_id, content, link_url, link_label, created_at, "
                "updated_at FROM journal_entries"
            )
        ).all()
        events = legacy_db.execute(
            text(
                "SELECT id, goal_id, goal_title, category, completed_on, completed_at "
                "FROM completion_events"
            )
        ).all()

        for c in categories:
            db.add(models.Category(id=c.id, user_id=new_user_id, name=c.name, created_at=c.created_at))
        db.flush()

        for g in goals:
            db.add(
                models.Goal(
                    id=g.id,
                    user_id=new_user_id,
                    title=g.title,
                    description=g.description,
                    category_id=g.category_id,
                    status=g.status,
                    priority=g.priority,
                    created_at=g.created_at,
                    completed_at=g.completed_at,
                )
            )
        db.flush()

        for e in entries:
            db.add(
                models.JournalEntry(
                    id=e.id,
                    goal_id=e.goal_id,
                    content=e.content,
                    link_url=e.link_url,
                    link_label=e.link_label,
                    created_at=e.created_at,
                    updated_at=e.updated_at,
                )
            )

        for ev in events:
            db.add(
                models.CompletionEvent(
                    id=ev.id,
                    user_id=new_user_id,
                    goal_id=ev.goal_id,
                    goal_title=ev.goal_title,
                    category=ev.category,
                    completed_on=ev.completed_on,
                    completed_at=ev.completed_at,
                )
            )

        db.commit()
        logger.info(
            "Owner hydration succeeded: %d categories, %d goals, %d journal entries, %d completion events",
            len(categories), len(goals), len(entries), len(events),
        )
        return True
    except Exception:
        db.rollback()
        logger.exception("Owner hydration failed — rolled back, nothing partially committed")
        raise
    finally:
        legacy_db.close()