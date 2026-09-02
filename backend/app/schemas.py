import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator

from .models import Status


# ---- auth ----

class GoogleLoginRequest(BaseModel):
    id_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: Optional[str]
    avatar_url: Optional[str]


class LoginResponse(BaseModel):
    """Returned once, right after login. is_new_user drives the frontend's
    welcome message — distinct wording depending on whether this account
    got the standard starter curriculum or (for the app's original owner)
    their real hydrated history — see hydrated."""

    user: UserOut
    is_new_user: bool
    hydrated: bool = False


# ---- categories (real, editable table now) ----

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CategoryUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class GoalCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category_id: uuid.UUID
    priority: int = 100


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    priority: Optional[int] = None
    status: Optional[Status] = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: Optional[str]
    category_id: uuid.UUID
    category: str  # resolved name, for display — see Goal.category property
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
    focus_category: Optional[CategoryOut] = None
    focus_expires_on: Optional[date] = None
    focus_days_remaining: Optional[int] = None


class SettingsUpdate(BaseModel):
    daily_goal_count: int = Field(..., ge=1, le=20)


class FocusCategorySet(BaseModel):
    category_id: uuid.UUID


# ---- daily selection (today) ----

class TodayOut(BaseModel):
    """Today's picks, plus how they were chosen — surfaced in the UI as a
    small badge (e.g. "AI-picked" vs a fallback method) so it's clear
    whether that day's LLM call succeeded. focus_category is set whenever
    a category focus was active for this day's selection (drives the
    "This week's focus" / "For variety" split in the UI); note carries a
    one-off notice, e.g. a focus-category shortfall."""

    source: str  # GenerationSource value
    goals: list[GoalOut]
    focus_category: Optional[str] = None
    note: Optional[str] = None


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
    category: str
    completed_on: date
    completed_at: datetime