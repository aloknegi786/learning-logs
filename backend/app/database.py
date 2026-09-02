import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy backend/.env.example to backend/.env "
        "and fill in your Supabase connection string."
    )

# pool_pre_ping avoids "server closed the connection" errors, and
# Supabase's pooled connection (port 6543) can drop idle connections too.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---- legacy database (owner-hydration only) ----
# Read-only in practice: the app never writes here. Points at the old,
# pre-multi-tenant Supabase project so the owner's real existing data can
# be copied into their new account on first login. Optional — most users
# (and most deployments) will never need this configured at all.
LEGACY_DATABASE_URL = os.getenv("LEGACY_DATABASE_URL")

LegacySessionLocal = None
if LEGACY_DATABASE_URL:
    legacy_engine = create_engine(LEGACY_DATABASE_URL, pool_pre_ping=True)
    LegacySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=legacy_engine)


def get_legacy_db():
    if not LegacySessionLocal:
        raise RuntimeError("LEGACY_DATABASE_URL is not configured")
    db = LegacySessionLocal()
    try:
        yield db
    finally:
        db.close()