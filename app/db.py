"""
Database connection, session management, and schema initialization.
Supports PostgreSQL (via psycopg2) when DATABASE_URL is set, with graceful
fallback to SQLite for zero-config offline development.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.paths import PROJECT_ROOT

logger = logging.getLogger("app.db")

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "app.db")

_lock = threading.RLock()
_initialized = False


def database_url() -> str:
    return (os.getenv("DATABASE_URL") or "").strip()


def is_postgres() -> bool:
    return bool(database_url())


def db_path() -> str:
    override = (os.getenv("APP_DB_PATH") or "").strip()
    return override or DEFAULT_DB_PATH


class DictCursorWrapper:
    """Wrapper to make PostgreSQL cursor results behave like SQLite Rows (dictionary/key access)."""

    def __init__(self, cursor):
        self._cursor = cursor

    def __iter__(self):
        return iter(self._cursor)

    def fetchone(self) -> Optional[Dict[str, Any]]:
        row = self._cursor.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self) -> List[Dict[str, Any]]:
        rows = self._cursor.fetchall()
        return [dict(r) for r in rows]

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> Optional[int]:
        try:
            cur = self._cursor.connection.cursor()
            cur.execute("SELECT LASTVAL()")
            res = cur.fetchone()
            cur.close()
            if res:
                return res[0] if isinstance(res, (tuple, list)) else res.get("lastval")
        except Exception:
            pass
        return None


class DBConnectionWrapper:
    """Unified wrapper around sqlite3.Connection and psycopg2.connection.

    Converts '?' parameter placeholders to '%s' when targeting PostgreSQL,
    so application code can use consistent query patterns.
    """

    def __init__(self, raw_conn, is_pg: bool):
        self._conn = raw_conn
        self._is_pg = is_pg

    def execute(self, query: str, params: Optional[Tuple[Any, ...]] = None):
        if self._is_pg:
            # Convert ? placeholders to %s for PostgreSQL
            pg_query = query.replace("?", "%s")
            cur = self._conn.cursor()
            cur.execute(pg_query, params or ())
            return DictCursorWrapper(cur)
        else:
            return self._conn.execute(query, params or ())

    def executescript(self, script: str):
        if self._is_pg:
            cur = self._conn.cursor()
            cur.execute(script)
            cur.close()
        else:
            self._conn.executescript(script)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def _connect_sqlite() -> sqlite3.Connection:
    path = db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _connect_postgres():
    url = database_url()
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    except Exception as exc:
        logger.warning("PostgreSQL connection to %s failed: %s. Falling back to SQLite.", url, exc)
        return None


@contextmanager
def get_conn() -> Iterator[DBConnectionWrapper]:
    with _lock:
        if is_postgres():
            pg_conn = _connect_postgres()
            if pg_conn is not None:
                wrapper = DBConnectionWrapper(pg_conn, is_pg=True)
                try:
                    yield wrapper
                    wrapper.commit()
                except Exception:
                    wrapper.rollback()
                    raise
                finally:
                    wrapper.close()
                return

        # Fallback / Default SQLite
        raw_sqlite = _connect_sqlite()
        wrapper = DBConnectionWrapper(raw_sqlite, is_pg=False)
        try:
            yield wrapper
            wrapper.commit()
        except Exception:
            wrapper.rollback()
            raise
        finally:
            wrapper.close()


def init_db() -> None:
    """Create auth, settings, and core application schema in PostgreSQL or SQLite."""
    global _initialized
    with get_conn() as conn:
        if conn._is_pg:
            # PostgreSQL Schema
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name VARCHAR(255) NOT NULL DEFAULT '',
                    created_at DOUBLE PRECISION NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    vidu_api_key_enc TEXT NOT NULL DEFAULT '',
                    vidu_email VARCHAR(255) NOT NULL DEFAULT '',
                    vidu_model VARCHAR(100) NOT NULL DEFAULT '',
                    vidu_reference_model VARCHAR(100) NOT NULL DEFAULT '',
                    vidu_resolution VARCHAR(50) NOT NULL DEFAULT '',
                    updated_at DOUBLE PRECISION NOT NULL
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    id VARCHAR(100) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
                    current_gateway INTEGER NOT NULL DEFAULT 1,
                    cultural_hook TEXT DEFAULT '',
                    merch_punchline TEXT DEFAULT '',
                    payload JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS system_audit_logs (
                    id SERIAL PRIMARY KEY,
                    event_type VARCHAR(100) NOT NULL,
                    actor VARCHAR(100) DEFAULT 'system',
                    details JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes(status);
                """
            )
            logger.info("Initialized PostgreSQL application tables (users, user_settings, episodes, audit_logs).")
        else:
            # SQLite Schema
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

                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'DRAFT',
                    current_gateway INTEGER NOT NULL DEFAULT 1,
                    cultural_hook TEXT DEFAULT '',
                    merch_punchline TEXT DEFAULT '',
                    payload TEXT DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                """
            )
            logger.info("Initialized SQLite application tables (users, user_settings, episodes).")

    _initialized = True
