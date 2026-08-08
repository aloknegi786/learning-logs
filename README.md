# learning_log — Interview Prep Tracker

A personal daily-goals tracker for software engineering interview prep:
CS fundamentals (OOP, OS, Computer Networks, DSA), High-Level Design,
Low-Level Design, and Design Patterns.

Every night at 3 AM, a scheduled job picks tomorrow's set of goals — either
via a free LLM call (Groq) that looks at your recent activity and picks a
well-balanced, sensibly-sequenced set, or via a deterministic fallback if
that fails or isn't configured. Each goal can carry its own learning
journal (your notes, blog/lecture links) alongside a plain done/undone
checkbox. Every completion is tracked in an activity heatmap, GitHub/
LeetCode-style. Everything is stored in PostgreSQL (Supabase).

## Stack
- **Backend**: Python, FastAPI, SQLAlchemy, APScheduler (the 3 AM job)
- **Frontend**: React (Vite), plain CSS
- **Database**: PostgreSQL, hosted on **Supabase** (no local database — the
  app always talks to your cloud instance, including in local dev)
- **LLM (optional)**: [Groq](https://console.groq.com) free tier, for daily
  goal selection only — the rest of the app works fully without it

## Project layout
```
learning-platform/
  backend/
    app/
      main.py         routes
      models.py       SQLAlchemy models (Goal, JournalEntry, DailyGoal,
                       CompletionEvent, Settings)
      schemas.py       Pydantic request/response schemas
      crud.py          DB logic: goals, journal, settings, activity ledger,
                        heatmap aggregation, fallback selection
      llm.py           Groq API call + retry/backoff for daily selection
      scheduler.py      APScheduler job: runs generate_daily_selection at
                        03:00 daily
      seed.py           starter curriculum (run once)
    requirements.txt
    Dockerfile
    .env.example
  frontend/           React app (Vite)
  docker-compose.yml   optional: runs just the backend container
```

## 1. Create your Supabase database
1. Go to [supabase.com](https://supabase.com) → New project (free tier is fine).
2. Once it's provisioned: **Project Settings → Database → Connection string → URI**.
3. Choose the **Transaction pooler** connection (port `6543`).
4. Copy that URI.

## 2. (Optional) Get a free Groq API key
Only needed if you want the 3 AM job to use an LLM for daily selection —
without it, the job (and the same-day safety net) falls back to a
deterministic rule instead, and the rest of the app is unaffected.
1. [console.groq.com/keys](https://console.groq.com/keys) → create a key (no card required).
2. You'll paste it into `.env` in the next step.

## 3. Configure the backend
```bash
cd backend
cp .env.example .env
```
In `.env`:
- `DATABASE_URL`: your Supabase URI, with `postgresql://` changed to
  `postgresql+psycopg2://` and `?sslmode=require` appended
- `GROQ_API_KEY`: optional, from step 2
- `TIMEZONE`: IANA timezone the 3 AM job runs in (defaults to `Asia/Kolkata`)

See the comments in `.env.example` for a worked example.

## 4. Create tables + load the starter curriculum
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m app.seed
```
Creates all tables and loads 30+ starter goals across all 7 categories.
Safe to re-run — it skips categories that already have goals.

## 5. Run the backend
```bash
uvicorn app.main:app --reload
```
API docs at http://localhost:8000/docs. The scheduler starts automatically
with the app (see terminal log: "Scheduler started..."); it'll fire the
daily-selection job at 03:00 in whatever `TIMEZONE` you set. To test it
immediately without waiting, use `POST /api/today/regenerate`.

Or, via Docker (still uses your Supabase `.env`, no local DB container):
```bash
docker compose up -d
docker compose exec backend python -m app.seed   # first time only
```

## 6. Run the frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173.

## Deploying later
Since the database is already cloud-hosted, deploying just means pointing
a hosted backend (Render, Fly.io, Railway, etc.) and a hosted frontend
(Vercel, Netlify) at the same Supabase `DATABASE_URL` — no migration needed
from what you're running locally. Note: the 3 AM job only fires while the
backend process is actually running, so pick a host that keeps it alive
continuously (not one that spins down on idle) if you want the cron to be
reliable.

## API overview
| Method | Path                        | Purpose                                              |
|--------|-----------------------------|-------------------------------------------------------|
| GET    | /api/today                  | Today's picks + how they were chosen (`source`)      |
| POST   | /api/today/regenerate       | Manually re-run selection for today (testing)        |
| GET    | /api/goals                  | All goals (filter by `category`, `status`)            |
| POST   | /api/goals                  | Create a goal                                          |
| GET    | /api/goals/{id}             | Goal detail + its full journal                        |
| PATCH  | /api/goals/{id}             | Update/complete a goal                                 |
| DELETE | /api/goals/{id}             | Remove a goal                                           |
| GET    | /api/goals/{id}/entries     | List a goal's journal entries                           |
| POST   | /api/goals/{id}/entries     | Add a journal entry (note and/or link)                  |
| PATCH  | /api/entries/{id}           | Edit a journal entry                                     |
| DELETE | /api/entries/{id}           | Remove a journal entry                                   |
| GET    | /api/categories             | List of category names                                   |
| GET    | /api/stats                  | Completion stats per category                             |
| GET    | /api/settings                | Current settings (daily goal count)                       |
| PUT    | /api/settings                | Update settings                                            |
| GET    | /api/activity/heatmap       | Per-day completion counts, streaks, perfect-day flags      |

## How daily selection actually works
1. **03:00, every day** (`app/scheduler.py`): if today's selection doesn't
   already exist, it tries the LLM first.
2. **LLM attempt** (`app/llm.py`): sends Groq your last 10 completions (with
   category), your activity over the last ~5 active days, and a shortlist
   of the next 5 pending goals per category — asks it to pick a balanced,
   sensibly-sequenced set sized to your configured daily count. Retries up
   to 3 times with 30s/60s backoff on failure.
3. **Fallback** (if the LLM isn't configured, or fails all 3 attempts):
   if you have any completion history, it picks the next pending goals from
   whichever category(ies) you've most recently been working in; with zero
   history (fresh install), it round-robins evenly across all categories.
4. **Same-day safety net**: if you open the app before the job has ever run
   for today (very first day, a missed cron, server was down at 3 AM), the
   `/api/today` endpoint runs the same fallback logic on the spot so the
   home screen is never empty.
5. Whichever path ran shows up in the UI as a small badge ("AI-picked",
   "Based on recent activity", or "Round robin").

## How the activity heatmap works
A goal contributes to the heatmap **exactly once**, on the day it's first
ever marked complete — an append-only ledger (`CompletionEvent`) records
this separately from the goal's live status, so unchecking and rechecking
a goal (same day or later) never double-counts. A day also gets a distinct
"perfect day" marker if every goal surfaced that day ended up completed.

## What's deliberately kept simple (candidates for the next pass)
- No authentication — assumes a single user (you). The `Settings` table is
  a plain singleton row rather than user-keyed, but isolated cleanly enough
  that adding a `user_id` later shouldn't require a rewrite.
- No editing of an existing goal's title/description from the UI (delete +
  re-add for now); the API already supports `PATCH` for it.
- No drag-and-drop reordering/priority editing from the UI yet.
- The 3 AM job only runs while the backend process is alive — no separate
  worker/queue system; fine for a single-user personal tool, worth revisiting
  if this ever needs to run more reliably unattended.

Good next steps once this is running: add a login, spaced-repetition style
resurfacing of completed topics, and Alembic migrations for schema changes.
