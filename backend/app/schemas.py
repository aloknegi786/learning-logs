import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator

from .models import Category, Status


class GoalCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: Category
    priority: int = 100


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[Category] = None
    priority: Optional[int] = None
    status: Optional[Status] = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: Optional[str]
    category: Category
    status: Status
    priority: int
    created_at: datetime
    completed_at: Optional[datetime]
    entry_count: int = 0


class StatsOut(BaseModel):
    total: int
    completed: int
    by_category: dict[str, dict[str, int]]


# ---- journal entries (per-goal learning journey: notes + resource links) ----

class JournalEntryCreate(BaseModel):
    content: Optional[str] = Field(None, max_length=10_000)
    link_url: Optional[str] = Field(None, max_length=2048)
    link_label: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def require_content_or_link(self):
        if not (self.content and self.content.strip()) and not (
            self.link_url and self.link_url.strip()
        ):
            raise ValueError("An entry needs at least a note or a link.")
        return self


class JournalEntryUpdate(BaseModel):
    content: Optional[str] = Field(None, max_length=10_000)
    link_url: Optional[str] = Field(None, max_length=2048)
    link_label: Optional[str] = Field(None, max_length=255)


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    content: Optional[str]
    link_url: Optional[str]
    link_label: Optional[str]
    created_at: datetime
    updated_at: datetime


class GoalDetailOut(GoalOut):
    """Goal plus its full learning journal, for a detail/journal view."""

    journal_entries: list[JournalEntryOut] = []


# ---- settings ----

class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    daily_goal_count: int


class SettingsUpdate(BaseModel):
    daily_goal_count: int = Field(..., ge=1, le=20)


# ---- daily selection (today) ----

class TodayOut(BaseModel):
    """Today's picks, plus how they were chosen — surfaced in the UI as a
    small badge (e.g. "AI-picked" vs a fallback method) so it's clear
    whether the 3 AM job's LLM call succeeded that day."""

    source: str  # GenerationSource value
    goals: list[GoalOut]


# ---- activity heatmap ----

class HeatmapDay(BaseModel):
    date: str  # ISO date, e.g. "2026-08-04"
    count: int  # new (first-time) completions that day
    perfect_day: bool  # every goal surfaced that day ended up completed


class HeatmapOut(BaseModel):
    days: list[HeatmapDay]
    current_streak: int
    longest_streak: int
    total_completions: int


class RecentCompletionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    goal_id: Optional[uuid.UUID]
    goal_title: str
    category: Category
    completed_on: date
    completed_at: datetime