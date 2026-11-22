"""
auth.py — YojanaMitra Authentication Module

Provides:
  - SQLite user database (users table + saved_schemes + conversation_history)
  - Password hashing via bcrypt (passlib)
  - JWT access tokens (python-jose)
  - FastAPI dependency: get_current_user (raises 401 on invalid/missing token)
  - Pydantic models: RegisterRequest, LoginRequest, TokenResponse, UserOut

Design principles:
  - Passwords are NEVER stored; only bcrypt hash stored.
  - Tokens are short-lived (ACCESS_TOKEN_EXPIRE_MINUTES).
  - DB file is data/users.db (separate from vector_store.db).
  - Module degrades gracefully: if import fails the rest of the app is unaffected.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

# ── Configuration ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "users.db"

SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "CHANGE_ME_IN_DOT_ENV_THIS_IS_INSECURE_DEFAULT")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ── Crypto ─────────────────────────────────────────────────────────────────────
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


# ── Database ───────────────────────────────────────────────────────────────────
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables on first run. Safe to call multiple times."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                email       TEXT NOT NULL UNIQUE COLLATE NOCASE,
                hashed_pw   TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS saved_schemes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                scheme_id   TEXT NOT NULL,
                saved_at    TEXT NOT NULL,
                UNIQUE(user_id, scheme_id)
            );

            CREATE TABLE IF NOT EXISTS conversation_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role        TEXT NOT NULL CHECK(role IN ('user','model')),
                text        TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_saved_schemes_user ON saved_schemes(user_id);
            CREATE INDEX IF NOT EXISTS idx_convo_user ON conversation_history(user_id);
        """)


# ── Pydantic models ────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    created_at: str


# ── CRUD helpers ───────────────────────────────────────────────────────────────
def get_user_by_email(email: str) -> sqlite3.Row | None:
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)
        ).fetchone()


def create_user(name: str, email: str, plain_password: str) -> dict:
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    hashed = hash_password(plain_password)
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO users (id, name, email, hashed_pw, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, email, hashed, now),
        )
    return {"id": user_id, "name": name, "email": email, "created_at": now}


# ── JWT ────────────────────────────────────────────────────────────────────────
def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    """Return user_id from a valid token; raise HTTPException 401 otherwise."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise ValueError("missing sub")
        return user_id
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── FastAPI dependency ─────────────────────────────────────────────────────────
def get_current_user(token: str | None = Depends(_oauth2_scheme)) -> dict:
    """
    Dependency that extracts and validates the JWT Bearer token.
    Returns the user row dict, or raises 401.
    Use as:  user = Depends(get_current_user)
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_token(token)
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return dict(row)


def get_optional_user(token: str | None = Depends(_oauth2_scheme)) -> dict | None:
    """Like get_current_user but returns None instead of raising 401."""
    if not token:
        return None
    try:
        return get_current_user(token)
    except HTTPException:
        return None


# ── Saved schemes helpers ──────────────────────────────────────────────────────
def get_saved_schemes(user_id: str) -> list[str]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT scheme_id FROM saved_schemes WHERE user_id = ? ORDER BY saved_at DESC",
            (user_id,),
        ).fetchall()
    return [r["scheme_id"] for r in rows]


def save_scheme(user_id: str, scheme_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO saved_schemes (user_id, scheme_id, saved_at) VALUES (?, ?, ?)",
            (user_id, scheme_id, now),
        )


def unsave_scheme(user_id: str, scheme_id: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "DELETE FROM saved_schemes WHERE user_id = ? AND scheme_id = ?",
            (user_id, scheme_id),
        )


# ── Conversation history helpers ───────────────────────────────────────────────
def save_conversation_turn(user_id: str, role: str, text: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO conversation_history (user_id, role, text, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, text[:3000], now),
        )
        # Trim to keep only the last 100 turns per user
        conn.execute("""
            DELETE FROM conversation_history
            WHERE user_id = ? AND id NOT IN (
                SELECT id FROM conversation_history
                WHERE user_id = ?
                ORDER BY id DESC LIMIT 100
            )
        """, (user_id, user_id))


def get_conversation_history(user_id: str, limit: int = 20) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT role, text FROM conversation_history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{"role": r["role"], "text": r["text"]} for r in reversed(rows)]


def clear_conversation_history(user_id: str) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM conversation_history WHERE user_id = ?", (user_id,))


# Initialise DB at import time
init_db()
