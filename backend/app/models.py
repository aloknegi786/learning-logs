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


class Category(str, enum.Enum):
    OOP = "OOP"
    OS = "Operating Systems"
    CN = "Computer Networks"
    DSA = "Data Structures & Algorithms"
    HLD = "High Level Design"
    LLD = "Low Level Design"
    DESIGN_PATTERNS = "Design Patterns"
    AGENTS = "Agents & Multi-Agent Systems"
    OTHER = "Other"


class Status(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class GenerationSource(str, enum.Enum):
    LLM = "llm"
    FALLBACK_HISTORY = "fallback_history"
    FALLBACK_ROUND_ROBIN = "fallback_round_robin"


class Goal(Base):
    __tablename__ = "goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(Enum(Category, name="category_enum"), nullable=False)
    status = Column(Enum(Status, name="status_enum"), default=Status.PENDING, nullable=False)
    # lower number = higher priority = surfaced sooner
    priority = Column(Integer, default=100, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

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
    A goal can have any number of these over time."""

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
    on every request. Populated by the 3 AM generation job (LLM-picked, or
    a deterministic fallback — see `source`), with a same-day safety net in
    the /api/today endpoint in case the job hasn't run yet."""

    __tablename__ = "daily_goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False)
    surfaced_on = Column(Date, default=date.today, nullable=False, index=True)
    sort_order = Column(Integer, default=0, nullable=False)  # preserves the LLM's chosen order
    source = Column(
        Enum(GenerationSource, name="generation_source_enum"),
        default=GenerationSource.FALLBACK_ROUND_ROBIN,
        nullable=False,
    )

    goal = relationship("Goal", back_populates="daily_entries")


class CompletionEvent(Base):
    """An append-only ledger: exactly one row is ever created per goal, at
    the moment it is FIRST marked completed. Unchecking and rechecking a
    goal (same day or later) never creates a second row — that's what makes
    this safe to drive both the activity heatmap and the LLM's "recent
    activity" context, without double-counting re-toggled goals.

    goal_id is nullable with ON DELETE SET NULL: if the goal itself is later
    deleted, this historical activity record (and the heatmap day it
    contributed to) is preserved — category/title are snapshotted at
    completion time for exactly this reason."""

    __tablename__ = "completion_events"
    __table_args__ = (UniqueConstraint("goal_id", name="uq_completion_events_goal_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id = Column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    goal_title = Column(String(255), nullable=False)
    category = Column(Enum(Category, name="category_enum"), nullable=False)

    completed_on = Column(Date, nullable=False, index=True)  # calendar date, for heatmap grouping
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Settings(Base):
    """Single-row app settings. Deliberately a plain table (not tied to a
    user id) since this is a single-user tool today — but isolated here
    rather than scattered as env vars, so it's easy to key by user_id later
    without touching the rest of the schema."""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)
    daily_goal_count = Column(Integer, default=3, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)