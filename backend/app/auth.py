"""Google OAuth verification + our own session (httpOnly cookie, JWT).

Flow:
1. Frontend gets a Google ID token via Google Identity Services (the
   "Sign in with Google" button) — no client secret involved on our side,
   this is signature verification only.
2. POST /api/auth/google sends that token here.
3. verify_google_token checks it against Google's public signing keys and
   confirms it was issued for OUR app (audience = GOOGLE_CLIENT_ID).
4. main.py finds-or-creates the User from the verified payload, then this
   module issues OUR OWN session JWT (separate secret/expiry from
   Google's token entirely) as an httpOnly cookie.
5. Every later request carries that cookie; get_current_user decodes it
   and loads the User row — this is the dependency added to every
   user-scoped route in main.py.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, Depends, HTTPException, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from . import models
from .database import get_db

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
SESSION_DAYS = 30
COOKIE_NAME = "session"

# SameSite=None requires Secure, and Secure cookies require HTTPS — which
# localhost dev doesn't have. COOKIE_SECURE=false (set in local .env) flips
# both together so the cookie still works over plain http://localhost.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = "none" if COOKIE_SECURE else "lax"


class AuthConfigError(Exception):
    """Raised when required env vars (GOOGLE_CLIENT_ID / JWT_SECRET) are missing."""


def verify_google_token(token: str) -> dict:
    """Returns the verified Google payload (sub, email, name, picture).
    Raises ValueError (from the google-auth library) if the token is
    invalid, expired, or wasn't issued for this app."""
    if not GOOGLE_CLIENT_ID:
        raise AuthConfigError("GOOGLE_CLIENT_ID is not configured")
    return id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)


def create_session_token(user_id) -> str:
    if not JWT_SECRET:
        raise AuthConfigError("JWT_SECRET is not configured")
    payload = {
        "sub": str(user_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> str:
    """Returns the user_id string. Raises jwt.PyJWTError on invalid/expired tokens."""
    if not JWT_SECRET:
        raise AuthConfigError("JWT_SECRET is not configured")
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return payload["sub"]


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=SESSION_DAYS * 24 * 3600,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME, path="/", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE
    )


def get_current_user(
    session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    """The dependency every user-scoped route uses. 401s cleanly if the
    cookie is missing, invalid, expired, or points at a user that no
    longer exists — the frontend treats any 401 as "show the login screen"."""
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        user_id = uuid.UUID(decode_session_token(session))
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user