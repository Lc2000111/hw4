"""Password hashing and login sessions for Campus Customs.

Passwords are never stored. We store a salted PBKDF2-HMAC-SHA256 hash:

    new accounts:  pbkdf2_sha256$600000$<salt>$<hex digest>
    seed accounts: pbkdf2_sha256$<salt>$<hex digest>   (legacy, 120,000 iterations)

Legacy hashes still verify, and are upgraded to the stronger format the next
time that user logs in successfully.

Sessions: on login we hand the browser a random token in an HttpOnly cookie
and store only the SHA-256 of that token in the `sessions` table, so a leaked
database can't be used to hijack sessions either.
"""

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000          # OWASP's recommendation for PBKDF2-HMAC-SHA256
LEGACY_ITERATIONS = 120_000   # what the seed database used

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128     # caps hashing cost so huge inputs can't slow the server

SESSION_COOKIE = "cc_session"
SESSION_DAYS = 7

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- password hashing ----------

def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)  # unique per user, so identical passwords hash differently
    return f"{ALGORITHM}${ITERATIONS}${salt}${_pbkdf2(password, salt, ITERATIONS)}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) == 4 and parts[0] == ALGORITHM:
        _, iterations, salt, digest = parts
        iterations = int(iterations)
    elif len(parts) == 3 and parts[0] == ALGORITHM:
        _, salt, digest = parts
        iterations = LEGACY_ITERATIONS
    else:
        return False
    # Constant-time compare so response timing doesn't leak how close a guess was.
    return hmac.compare_digest(_pbkdf2(password, salt, iterations), digest)


def needs_rehash(stored: str) -> bool:
    return stored.split("$")[:2] != [ALGORITHM, str(ITERATIONS)]


# Used when the email doesn't exist, so "no such user" takes as long as
# "wrong password" and attackers can't discover which emails are registered.
DUMMY_HASH = hash_password(secrets.token_hex(16))


# ---------- input checks ----------

def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_signup(first_name: str, last_name: str, email: str, password: str, confirm: str) -> str | None:
    """Return a friendly error message, or None if the input is fine."""
    if not first_name.strip() or not last_name.strip():
        return "Please enter your first and last name."
    if len(first_name.strip()) > 50 or len(last_name.strip()) > 50:
        return "Names must be 50 characters or fewer."
    if len(email) > 254 or not EMAIL_RE.match(email):
        return "Please enter a valid email address."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be {MAX_PASSWORD_LENGTH} characters or fewer."
    if password != confirm:
        return "Passwords don't match."
    return None


# ---------- sessions ----------

def ensure_sessions_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, datetime('now', ?))",
        (_token_hash(token), user_id, f"+{SESSION_DAYS} days"),
    )
    return token


def user_id_for_session(conn: sqlite3.Connection, token: str | None) -> int | None:
    if not token:
        return None
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE token_hash = ? AND expires_at > datetime('now')",
        (_token_hash(token),),
    ).fetchone()
    return row[0] if row else None


def delete_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


# ---------- brute-force protection ----------

MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 15 * 60
_failed: dict[str, deque] = defaultdict(deque)


def _recent_failures(key: str) -> deque:
    attempts = _failed[key]
    cutoff = time.monotonic() - LOCKOUT_SECONDS
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    return attempts


def is_locked_out(key: str) -> bool:
    return len(_recent_failures(key)) >= MAX_FAILED_LOGINS


def record_failure(key: str) -> None:
    _recent_failures(key).append(time.monotonic())


def clear_failures(key: str) -> None:
    _failed.pop(key, None)
