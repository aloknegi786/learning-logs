import os
import uuid
from datetime import date

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import engine, get_db, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Interview Prep Tracker API", version="0.3.0")

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return crud.list_categories(db)


@app.post("/api/categories", response_model=schemas.CategoryOut)
def create_category(data: schemas.CategoryCreate, db: Session = Depends(get_db)):
    cat = crud.create_category(db, data)
    if not cat:
        raise HTTPException(status_code=409, detail="A category with this name already exists")
    return cat


@app.patch("/api/categories/{category_id}", response_model=schemas.CategoryOut)
def update_category(category_id: uuid.UUID, data: schemas.CategoryUpdate, db: Session = Depends(get_db)):
    try:
        cat = crud.update_category(db, category_id, data)
    except ValueError:
        raise HTTPException(status_code=409, detail="A category with this name already exists")
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


@app.delete("/api/categories/{category_id}")
def delete_category(category_id: uuid.UUID, db: Session = Depends(get_db)):
    deleted, in_use = crud.delete_category(db, category_id)
    if not deleted:
        if in_use > 0:
            raise HTTPException(
                status_code=400,
                detail=f"{in_use} goal(s) still use this category — reassign or delete them first",
            )
        raise HTTPException(status_code=404, detail="Category not found")
    return {"deleted": True}


@app.post("/api/goals", response_model=schemas.GoalOut)
def create_goal(goal: schemas.GoalCreate, db: Session = Depends(get_db)):
    created = crud.create_goal(db, goal)
    if not created:
        raise HTTPException(status_code=404, detail="Category not found")
    return created


@app.get("/api/goals", response_model=list[schemas.GoalOut])
def list_goals(
    category: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return crud.list_goals(db, category, status)


@app.get("/api/goals/{goal_id}", response_model=schemas.GoalDetailOut)
def get_goal_detail(goal_id: uuid.UUID, db: Session = Depends(get_db)):
    goal = crud.get_goal(db, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.patch("/api/goals/{goal_id}", response_model=schemas.GoalOut)
def update_goal(goal_id: uuid.UUID, updates: schemas.GoalUpdate, db: Session = Depends(get_db)):
    try:
        updated = crud.update_goal(db, goal_id, updates)
    except ValueError:
        raise HTTPException(status_code=404, detail="Category not found")
    if not updated:
        raise HTTPException(status_code=404, detail="Goal not found")
    return updated


@app.delete("/api/goals/{goal_id}")
def delete_goal(goal_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = crud.delete_goal(db, goal_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"deleted": True}


# ---- journal entries (per-goal learning journey: notes + resource links) ----

@app.get("/api/goals/{goal_id}/entries", response_model=list[schemas.JournalEntryOut])
def list_journal_entries(goal_id: uuid.UUID, db: Session = Depends(get_db)):
    if not crud.get_goal(db, goal_id):
        raise HTTPException(status_code=404, detail="Goal not found")
    return crud.list_journal_entries(db, goal_id)


@app.post("/api/goals/{goal_id}/entries", response_model=schemas.JournalEntryOut)
def create_journal_entry(
    goal_id: uuid.UUID, entry: schemas.JournalEntryCreate, db: Session = Depends(get_db)
):
    created = crud.create_journal_entry(db, goal_id, entry)
    if not created:
        raise HTTPException(status_code=404, detail="Goal not found")
    return created


@app.patch("/api/entries/{entry_id}", response_model=schemas.JournalEntryOut)
def update_journal_entry(
    entry_id: uuid.UUID, updates: schemas.JournalEntryUpdate, db: Session = Depends(get_db)
):
    updated = crud.update_journal_entry(db, entry_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")
    return updated


@app.delete("/api/entries/{entry_id}")
def delete_journal_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    ok = crud.delete_journal_entry(db, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"deleted": True}


# ---- today's picks (generated on the first visit of each calendar day) ----

@app.get("/api/today", response_model=schemas.TodayOut)
def get_today(db: Session = Depends(get_db)):
    """First request of a new day triggers generation right here (tries
    the LLM, falls back if needed — see app/daily_selection.py). Every
    later request that same day just returns what was already picked."""
    goals, source, focus_category, note = crud.get_or_create_today(db)
    return {"source": source, "goals": goals, "focus_category": focus_category, "note": note}


@app.post("/api/today/regenerate", response_model=schemas.TodayOut)
def regenerate_today(db: Session = Depends(get_db)):
    """Manual trigger for testing: clears today's existing selection (if
    any) and re-runs the same LLM-then-fallback logic a fresh day would."""
    today = date.today()
    db.query(models.DailyGoal).filter(models.DailyGoal.surfaced_on == today).delete()
    db.commit()
    goals, source, focus_category, note = crud.get_or_create_today(db)
    return {"source": source, "goals": goals, "focus_category": focus_category, "note": note}


@app.get("/api/stats", response_model=schemas.StatsOut)
def get_stats(db: Session = Depends(get_db)):
    return crud.get_stats(db)


# ---- settings ----

@app.get("/api/settings", response_model=schemas.SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return crud.get_settings(db)


@app.put("/api/settings", response_model=schemas.SettingsOut)
def update_settings(updates: schemas.SettingsUpdate, db: Session = Depends(get_db)):
    return crud.update_settings(db, updates)


@app.post("/api/settings/focus", response_model=schemas.SettingsOut)
def set_focus(data: schemas.FocusCategorySet, db: Session = Depends(get_db)):
    settings = crud.set_focus_category(db, data.category_id)
    if not settings:
        raise HTTPException(status_code=404, detail="Category not found")
    return settings


@app.delete("/api/settings/focus", response_model=schemas.SettingsOut)
def clear_focus(db: Session = Depends(get_db)):
    return crud.clear_focus_category(db)


# ---- activity heatmap ----

@app.get("/api/activity/heatmap", response_model=schemas.HeatmapOut)
def get_heatmap(days: int = 365, db: Session = Depends(get_db)):
    return crud.get_heatmap_data(db, days=days)


@app.get("/api/activity/recent", response_model=list[schemas.RecentCompletionOut])
def get_recent_completions(limit: int = 5, db: Session = Depends(get_db)):
    return crud.get_recent_completions(db, limit=limit)