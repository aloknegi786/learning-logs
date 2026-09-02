import enum
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    Date,
    Enum,
    ForeignKey,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


class Status(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class GenerationSource(str, enum.Enum):
    LLM = "llm"
    FALLBACK_HISTORY = "fallback_history"
    FALLBACK_ROUND_ROBIN = "fallback_round_robin"


class User(Base):
    """A logged-in account. google_sub (Google's stable per-account
    identifier) is the real anchor — not email, since email can change on
    a Google account but the underlying subject id doesn't. Every other
    table's data is scoped to a user_id pointing here; each user's
    workspace (goals, categories, progress) is fully isolated from every
    other user's."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_sub = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(2048), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Category(Base):
    """A real, user-editable table — not a fixed code-level enum, and not
    global either: each user has their own set (seeded from the standard
    starter curriculum on their first login), so two different users can
    both have a category named "DSA" without conflict — the uniqueness
    constraint is scoped to (user_id, name), not name alone."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_categories_user_name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Goal(Base):
    __tablename__ = "goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    status = Column(Enum(Status, name="status_enum"), default=Status.PENDING, nullable=False)
    # lower number = higher priority = surfaced sooner
    priority = Column(Integer, default=100, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    category_obj = relationship("Category")
    daily_entries = relationship(
        "DailyGoal", back_populates="goal", cascade="all, delete-orphan"
    )
    journal_entries = relationship(
        "JournalEntry",
        back_populates="goal",
        cascade="all, delete-orphan",
        order_by="JournalEntry.created_at.desc()",
    )

    @property
    def category(self) -> str | None:
        # crud eager-loads category_obj (joinedload) wherever goals are
        # listed in bulk, so this never triggers a per-row N+1 query.
        return self.category_obj.name if self.category_obj else None

    @property
    def entry_count(self) -> int:
        # crud.list_goals/get_or_create_today attach a bulk-fetched count via
        # _entry_count_override (one grouped query for the whole list) to
        # avoid an N+1 lazy-load of journal_entries per goal. Falls back to
        # the relationship directly for single-goal fetches (e.g. the goal
        # detail endpoint, which already loads journal_entries in full).
        override = getattr(self, "_entry_count_override", None)
        if override is not None:
            return override
        return len(self.journal_entries)


class JournalEntry(Base):
    """A single entry in a goal's learning journey: your own notes,
    a resource link (blog post, lecture video, docs), or both together.
    A goal can have any number of these over time. No user_id column here
    on purpose — ownership is scoped transitively through goal_id ->
    Goal.user_id, so every query joins through the parent goal rather than
    duplicating the owner on every entry."""

    __tablename__ = "journal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False, index=True)

    content = Column(Text, nullable=True)  # personal notes / reflection
    link_url = Column(String(2048), nullable=True)  # blog post, lecture, docs, etc.
    link_label = Column(String(255), nullable=True)  # e.g. "Lecture: MIT 6.006 - Hashing"

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    goal = relationship("Goal", back_populates="journal_entries")


class DailyGoal(Base):
    """Records which goals were surfaced on which calendar day, so the
    home screen stays stable for the rest of that day instead of reshuffling
    on every request. Populated on the first /api/today request of a new
    day, per user (LLM-picked, or a deterministic fallback — see `source`).

    focus_category/note are snapshotted once per day (same value repeated
    on every row for that surfaced_on date) so a later visit that same day
    — or changing/clearing the focus setting afterward — doesn't retroactively
    change the explanation shown for a day that's already been decided."""

    __tablename__ = "daily_goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False)
    surfaced_on = Column(Date, default=date.today, nullable=False, index=True)
    sort_order = Column(Integer, default=0, nullable=False)  # preserves the LLM's chosen order
    source = Column(
        Enum(GenerationSource, name="generation_source_enum"),
        default=GenerationSource.FALLBACK_ROUND_ROBIN,
        nullable=False,
    )
    focus_category = Column(String(100), nullable=True)  # snapshot of that day's focus, if any
    note = Column(Text, nullable=True)  # e.g. a focus-category shortfall notice

    goal = relationship("Goal", back_populates="daily_entries")


class CompletionEvent(Base):
    """An append-only ledger: exactly one row is ever created per goal, at
    the moment it is FIRST marked completed. Unchecking and rechecking a
    goal (same day or later) never creates a second row — that's what makes
    this safe to drive both the activity heatmap and the LLM's "recent
    activity" context, without double-counting re-toggled goals.

    goal_id is nullable with ON DELETE SET NULL: if the goal itself is later
    deleted, this historical activity record (and the heatmap day it
    contributed to) is preserved. `category` is a plain snapshotted string
    (not a foreign key) for the same reason, extended to categories too: if
    a category later gets renamed or deleted, past activity still shows the
    category name as it was at the time the goal was completed."""

    __tablename__ = "completion_events"
    __table_args__ = (UniqueConstraint("goal_id", name="uq_completion_events_goal_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    goal_id = Column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    goal_title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)

    completed_on = Column(Date, nullable=False, index=True)  # calendar date, for heatmap grouping
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Settings(Base):
    """One row per user (not a global singleton anymore). Created
    lazily/get-or-created the first time a user's settings are read.

    focus_category_id/focus_expires_on implement a temporary category bias
    for daily selection: null means no focus active. When set, it auto-
    expires after 7 days (crud.get_settings lazily clears it once expired —
    no background job needed) or can be cleared manually before that."""

    __tablename__ = "settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False, index=True)
    daily_goal_count = Column(Integer, default=3, nullable=False)
    focus_category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    focus_expires_on = Column(Date, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    focus_category = relationship("Category")

    @property
    def focus_days_remaining(self) -> int | None:
        if not self.focus_expires_on:
            return None
        return max((self.focus_expires_on - date.today()).days, 0)