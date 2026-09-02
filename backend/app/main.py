import os
import uuid
from datetime import date, datetime

from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import auth, crud, models, provisioning, schemas
from .database import engine, get_db, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Interview Prep Tracker API", version="1.0.0")

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # required for the httpOnly session cookie to work cross-origin
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---- auth ----

@app.post("/api/auth/google", response_model=schemas.LoginResponse)
def login_with_google(data: schemas.GoogleLoginRequest, response: Response, db: Session = Depends(get_db)):
    try:
        payload = auth.verify_google_token(data.id_token)
    except (ValueError, auth.AuthConfigError) as e:
        raise HTTPException(status_code=401, detail=f"Google sign-in failed: {e}")

    google_sub = payload["sub"]
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Google account has no email")

    user = db.query(models.User).filter(models.User.google_sub == google_sub).first()
    is_new_user = False
    hydrated = False

    if user:
        user.last_login_at = datetime.utcnow()
        user.name = payload.get("name") or user.name
        user.avatar_url = payload.get("picture") or user.avatar_url
        db.commit()
        db.refresh(user)
    else:
        is_new_user = True
        user = models.User(
            google_sub=google_sub,
            email=email,
            name=payload.get("name"),
            avatar_url=payload.get("picture"),
        )
        db.add(user)
        db.flush()  # assigns user.id without committing yet — provisioning below can still fail safely

        if provisioning.is_owner(email):
            hydrated = provisioning.hydrate_owner_from_legacy(db, user.id)
        if not hydrated:
            provisioning.seed_default_curriculum_for_user(db, user.id)

        db.commit()
        db.refresh(user)

    token = auth.create_session_token(user.id)
    auth.set_session_cookie(response, token)
    return {"user": user, "is_new_user": is_new_user, "hydrated": hydrated}


@app.post("/api/auth/logout")
def logout(response: Response):
    auth.clear_session_cookie(response)
    return {"logged_out": True}


@app.get("/api/auth/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# ---- categories (real, per-user editable table) ----

@app.get("/api/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    return crud.list_categories(db, current_user.id)


@app.post("/api/categories", response_model=schemas.CategoryOut)
def create_category(
    data: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    cat = crud.create_category(db, current_user.id, data)
    if not cat:
        raise HTTPException(status_code=409, detail="A category with this name already exists")
    return cat


@app.patch("/api/categories/{category_id}", response_model=schemas.CategoryOut)
def update_category(
    category_id: uuid.UUID,
    data: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        cat = crud.update_category(db, current_user.id, category_id, data)
    except ValueError:
        raise HTTPException(status_code=409, detail="A category with this name already exists")
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


@app.delete("/api/categories/{category_id}")
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    deleted, in_use = crud.delete_category(db, current_user.id, category_id)
    if not deleted:
        if in_use > 0:
            raise HTTPException(
                status_code=400,
                detail=f"{in_use} goal(s) still use this category — reassign or delete them first",
            )
        raise HTTPException(status_code=404, detail="Category not found")
    return {"deleted": True}


# ---- goals ----

@app.post("/api/goals", response_model=schemas.GoalOut)
def create_goal(
    goal: schemas.GoalCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    created = crud.create_goal(db, current_user.id, goal)
    if not created:
        raise HTTPException(status_code=404, detail="Category not found")
    return created


@app.get("/api/goals", response_model=list[schemas.GoalOut])
def list_goals(
    category: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.list_goals(db, current_user.id, category, status)


@app.get("/api/goals/{goal_id}", response_model=schemas.GoalDetailOut)
def get_goal_detail(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    goal = crud.get_goal(db, current_user.id, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.patch("/api/goals/{goal_id}", response_model=schemas.GoalOut)
def update_goal(
    goal_id: uuid.UUID,
    updates: schemas.GoalUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        updated = crud.update_goal(db, current_user.id, goal_id, updates)
    except ValueError:
        raise HTTPException(status_code=404, detail="Category not found")
    if not updated:
        raise HTTPException(status_code=404, detail="Goal not found")
    return updated


@app.delete("/api/goals/{goal_id}")
def delete_goal(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    ok = crud.delete_goal(db, current_user.id, goal_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"deleted": True}


# ---- journal entries (per-goal learning journey: notes + resource links) ----

@app.get("/api/goals/{goal_id}/entries", response_model=list[schemas.JournalEntryOut])
def list_journal_entries(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not crud.get_goal(db, current_user.id, goal_id):
        raise HTTPException(status_code=404, detail="Goal not found")
    return crud.list_journal_entries(db, current_user.id, goal_id)


@app.post("/api/goals/{goal_id}/entries", response_model=schemas.JournalEntryOut)
def create_journal_entry(
    goal_id: uuid.UUID,
    entry: schemas.JournalEntryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    created = crud.create_journal_entry(db, current_user.id, goal_id, entry)
    if not created:
        raise HTTPException(status_code=404, detail="Goal not found")
    return created


@app.patch("/api/entries/{entry_id}", response_model=schemas.JournalEntryOut)
def update_journal_entry(
    entry_id: uuid.UUID,
    updates: schemas.JournalEntryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    updated = crud.update_journal_entry(db, current_user.id, entry_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")
    return updated


@app.delete("/api/entries/{entry_id}")
def delete_journal_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    ok = crud.delete_journal_entry(db, current_user.id, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"deleted": True}


# ---- today's picks (generated on the first visit of each calendar day) ----

@app.get("/api/today", response_model=schemas.TodayOut)
def get_today(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """First request of a new day (per user) triggers generation right
    here (tries the LLM, falls back if needed — see app/daily_selection.py).
    Every later request that same day just returns what was already picked."""
    goals, source, focus_category, note = crud.get_or_create_today(db, current_user.id)
    return {"source": source, "goals": goals, "focus_category": focus_category, "note": note}


@app.post("/api/today/regenerate", response_model=schemas.TodayOut)
def regenerate_today(
    db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)
):
    """Manual trigger for testing: clears today's existing selection (if
    any) and re-runs the same LLM-then-fallback logic a fresh day would."""
    today = date.today()
    db.query(models.DailyGoal).filter(
        models.DailyGoal.surfaced_on == today, models.DailyGoal.user_id == current_user.id
    ).delete()
    db.commit()
    goals, source, focus_category, note = crud.get_or_create_today(db, current_user.id)
    return {"source": source, "goals": goals, "focus_category": focus_category, "note": note}


@app.get("/api/stats", response_model=schemas.StatsOut)
def get_stats(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    return crud.get_stats(db, current_user.id)


# ---- settings ----

@app.get("/api/settings", response_model=schemas.SettingsOut)
def get_settings(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    return crud.get_settings(db, current_user.id)


@app.put("/api/settings", response_model=schemas.SettingsOut)
def update_settings(
    updates: schemas.SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.update_settings(db, current_user.id, updates)


@app.post("/api/settings/focus", response_model=schemas.SettingsOut)
def set_focus(
    data: schemas.FocusCategorySet,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    settings = crud.set_focus_category(db, current_user.id, data.category_id)
    if not settings:
        raise HTTPException(status_code=404, detail="Category not found")
    return settings


@app.delete("/api/settings/focus", response_model=schemas.SettingsOut)
def clear_focus(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    return crud.clear_focus_category(db, current_user.id)


# ---- activity heatmap ----

@app.get("/api/activity/heatmap", response_model=schemas.HeatmapOut)
def get_heatmap(
    days: int = 365,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.get_heatmap_data(db, current_user.id, days=days)


@app.get("/api/activity/recent", response_model=list[schemas.RecentCompletionOut])
def get_recent_completions(
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return crud.get_recent_completions(db, current_user.id, limit=limit)