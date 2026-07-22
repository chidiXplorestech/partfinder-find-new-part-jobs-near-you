"""Minimal account store: SQLite + hashed passwords.

Enough to back the onboarding "Create your account" step: create a user,
sign them in, and enforce a valid email + strong password server-side (never
trust the client alone). Passwords are hashed with Werkzeug (ships with Flask).
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from typing import Any, Dict, Optional

from werkzeug.security import check_password_hash, generate_password_hash

_DB_PATH = os.getenv("ACCOUNTS_DB", os.path.join(os.path.dirname(__file__), "..", "align.db"))
_lock = threading.Lock()

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the users table if it doesn't exist."""
    with _lock, _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT UNIQUE NOT NULL,
                name        TEXT DEFAULT '',
                password    TEXT NOT NULL,
                postcode    TEXT DEFAULT '',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def email_valid(email: str) -> bool:
    return bool(_EMAIL.match((email or "").strip()))


def password_problem(password: str) -> Optional[str]:
    """Return a human message if the password is weak, else ``None``."""
    p = password or ""
    if len(p) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"\d", p):
        return "Password must include a number."
    if not re.search(r"[^A-Za-z0-9]", p):
        return "Password must include a special character."
    if not (re.search(r"[a-z]", p) and re.search(r"[A-Z]", p)):
        return "Password must include upper and lower case letters."
    return None


def create_user(email: str, password: str, name: str = "", postcode: str = "") -> Dict[str, Any]:
    """Create a user. Returns ``{"ok": True, "id"}`` or ``{"ok": False, "error"}``."""
    email = (email or "").strip().lower()
    if not email_valid(email):
        return {"ok": False, "error": "Please enter a valid email address."}
    problem = password_problem(password)
    if problem:
        return {"ok": False, "error": problem}

    init_db()
    with _lock, _conn() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return {"ok": False, "error": "An account with that email already exists. Try logging in."}
        cur = conn.execute(
            "INSERT INTO users (email, name, password, postcode) VALUES (?, ?, ?, ?)",
            (email, (name or "").strip(), generate_password_hash(password), (postcode or "").strip()),
        )
        return {"ok": True, "id": cur.lastrowid}


def authenticate(email: str, password: str) -> Dict[str, Any]:
    """Verify credentials. Returns ``{"ok": True, "id", "name"}`` or an error."""
    email = (email or "").strip().lower()
    init_db()
    with _lock, _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not check_password_hash(row["password"], password):
        return {"ok": False, "error": "Email or password is incorrect."}
    return {"ok": True, "id": row["id"], "name": row["name"]}
