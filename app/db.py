"""
SQLite application database (users, settings).

Uses a local file under data/ so auth works without Postgres.
Agent 0 may still use DATABASE_URL / Postgres separately.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator

from app.paths import PROJECT_ROOT

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "app.db")

_lock = threading.RLock()
_initialized = False


def db_path() -> str:
    override = (os.getenv("APP_DB_PATH") or "").strip()
    return override or DEFAULT_DB_PATH


def _connect() -> sqlite3.Connection:
    path = db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db() -> None:
    """Create auth / settings tables if missing."""
    global _initialized
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                vidu_api_key_enc TEXT NOT NULL DEFAULT '',
                vidu_email TEXT NOT NULL DEFAULT '',
                vidu_model TEXT NOT NULL DEFAULT '',
                vidu_reference_model TEXT NOT NULL DEFAULT '',
                vidu_resolution TEXT NOT NULL DEFAULT '',
                updated_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            """
        )
    _initialized = True
