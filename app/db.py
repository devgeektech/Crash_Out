"""
Database connection, session management, and schema initialization for PostgreSQL.
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple

import psycopg2
import psycopg2.extras

logger = logging.getLogger("app.db")

_lock = threading.RLock()
_initialized = False


def database_url() -> str:
    """Return the configured PostgreSQL connection string."""
    return (os.getenv("DATABASE_URL") or "").strip()


def is_postgres() -> bool:
    """Check if PostgreSQL connection URL is configured."""
    return bool(database_url())


class DictCursorWrapper:
    """Wrapper to make PostgreSQL cursor results behave with dictionary/key access."""

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
    """Connection wrapper around psycopg2.connection.

    Converts '?' parameter placeholders to '%s' so existing query patterns
    continue to work seamlessly with psycopg2.
    """

    def __init__(self, raw_conn):
        self._conn = raw_conn
        self._is_pg = True

    def execute(self, query: str, params: Optional[Tuple[Any, ...]] = None):
        # Convert ? placeholders to %s for PostgreSQL
        pg_query = query.replace("?", "%s")
        cur = self._conn.cursor()
        cur.execute(pg_query, params or ())
        return DictCursorWrapper(cur)

    def executescript(self, script: str):
        cur = self._conn.cursor()
        cur.execute(script)
        cur.close()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def _connect_postgres():
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set. PostgreSQL is required.")
    try:
        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    except Exception as exc:
        logger.error("Failed to connect to PostgreSQL at %s: %s", url, exc)
        raise RuntimeError(f"Could not connect to PostgreSQL: {exc}") from exc


@contextmanager
def get_conn() -> Iterator[DBConnectionWrapper]:
    """Yield a PostgreSQL connection context with transaction commit/rollback."""
    with _lock:
        pg_conn = _connect_postgres()
        wrapper = DBConnectionWrapper(pg_conn)
        try:
            yield wrapper
            wrapper.commit()
        except Exception:
            wrapper.rollback()
            raise
        finally:
            wrapper.close()


def init_db() -> None:
    """Create schema and apply all pending migrations with version history in PostgreSQL."""
    global _initialized
    from app.migrations import run_migrations
    applied = run_migrations()
    if applied:
        logger.info("Applied %d database migration(s) on startup.", len(applied))
    else:
        logger.info("PostgreSQL database schema is up to date.")
    _initialized = True


# ---------------------------------------------------------------------------
# Database Helper Functions for Episodes, Pitches & Scripts
# ---------------------------------------------------------------------------

def save_episode_to_db(
    episode_id: str,
    title: str,
    status: str = "DRAFT",
    tokens: int = 0,
    *,
    episode_number: int = 0,
    current_gateway: int = 1,
    cultural_hook: str = "",
    merch_punchline: str = "",
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert or update an episode with Title, Status, and Tokens in PostgreSQL."""
    import json
    payload_json = json.dumps(payload or {})

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO episodes (
                id, title, status, tokens, episode_number, current_gateway,
                cultural_hook, merch_punchline, payload, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, NOW())
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                status = EXCLUDED.status,
                tokens = EXCLUDED.tokens,
                episode_number = EXCLUDED.episode_number,
                current_gateway = EXCLUDED.current_gateway,
                cultural_hook = EXCLUDED.cultural_hook,
                merch_punchline = EXCLUDED.merch_punchline,
                payload = EXCLUDED.payload,
                updated_at = NOW()
            """,
            (episode_id, title, status, int(tokens), int(episode_number), int(current_gateway), cultural_hook, merch_punchline, payload_json),
        )


def save_pitches_to_db(
    episode_id: str,
    pitches: List[Dict[str, Any]],
    selected_pitch_number: Optional[int] = None,
) -> None:
    """
    Save the 5 pitches for an episode in PostgreSQL.
    Sets is_selected to True for the chosen pitch number.
    """
    import json

    with get_conn() as conn:
        conn.execute("DELETE FROM pitches WHERE episode_id = ?", (episode_id,))

        for idx, pitch in enumerate(pitches[:5], start=1):
            p_num = int(pitch.get("pitch_number") or idx)
            is_sel = bool(pitch.get("is_selected") or (selected_pitch_number == p_num))
            title = str(pitch.get("title") or pitch.get("headline") or f"Pitch {p_num}")
            hook = str(pitch.get("hook") or pitch.get("cultural_hook") or "")
            synopsis = str(pitch.get("synopsis") or pitch.get("description") or "")
            target_audience = str(pitch.get("target_audience") or pitch.get("youth_sentiment_summary") or "")
            merch_idea = str(pitch.get("merch_idea") or pitch.get("merch_punchline") or "")
            payload_json = json.dumps(pitch)

            conn.execute(
                """
                INSERT INTO pitches (
                    episode_id, pitch_number, title, hook, synopsis,
                    target_audience, merch_idea, is_selected, payload, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, NOW())
                """,
                (episode_id, p_num, title, hook, synopsis, target_audience, merch_idea, is_sel, payload_json),
            )


def update_selected_pitch(episode_id: str, pitch_number: int) -> None:
    """Update selected pitch to is_selected = True and reset others to False in PostgreSQL."""
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE pitches
            SET is_selected = (pitch_number = ?), updated_at = NOW()
            WHERE episode_id = ?
            """,
            (int(pitch_number), episode_id),
        )


def save_scripts_to_db(episode_id: str, scenes: List[Dict[str, Any]]) -> None:
    """
    Store all scripts for the 4 video scenes for the given episode in PostgreSQL.
    """
    import json

    with get_conn() as conn:
        for idx, scene in enumerate(scenes[:4], start=1):
            v_num = int(scene.get("video_number") or scene.get("scene_id") or idx)
            title = str(scene.get("scene_title") or scene.get("title") or f"Scene {v_num}")
            character = str(scene.get("character") or scene.get("character_id") or "")
            dialogue = str(scene.get("dialogue") or scene.get("dialogue_text") or scene.get("text") or "")
            visual = str(scene.get("visual_prompt") or scene.get("prompt") or scene.get("video_prompt") or "")
            audio = str(scene.get("audio_prompt") or scene.get("audio") or "")
            duration = int(scene.get("duration_sec") or scene.get("duration") or 15)
            payload_json = json.dumps(scene)

            conn.execute(
                """
                INSERT INTO scripts (
                    episode_id, video_number, scene_title, character, dialogue,
                    visual_prompt, audio_prompt, duration_sec, payload, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, NOW())
                ON CONFLICT (episode_id, video_number) DO UPDATE SET
                    scene_title = EXCLUDED.scene_title,
                    character = EXCLUDED.character,
                    dialogue = EXCLUDED.dialogue,
                    visual_prompt = EXCLUDED.visual_prompt,
                    audio_prompt = EXCLUDED.audio_prompt,
                    duration_sec = EXCLUDED.duration_sec,
                    payload = EXCLUDED.payload,
                    updated_at = NOW()
                """,
                (episode_id, v_num, title, character, dialogue, visual, audio, duration, payload_json),
            )



def log_system_incident(
    event_type: str,
    actor: str = "system",
    details: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Insert a structured system audit or incident log entry in PostgreSQL."""
    import json

    try:
        details_json = json.dumps(details or {})
        with get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO system_audit_logs (event_type, actor, details, created_at)
                VALUES (?, ?, ?::jsonb, NOW())
                RETURNING id
                """,
                (event_type, actor, details_json),
            )
            row = cursor.fetchone()
            log_id = row.get("id") if row else None

            # Automatically dispatch real-time mobile push alert for critical errors / incidents
            try:
                evt_upper = event_type.upper()
                if (evt_upper.startswith(("ERROR", "FAIL", "INCIDENT")) 
                    and evt_upper not in {"INCIDENT_RESOLVED", "INCIDENT_RETRIED"}):
                    from app.infra.notifications import notify_critical_error
                    det = details or {}
                    notify_critical_error(
                        task_name=str(det.get("task_name") or event_type),
                        error_message=str(det.get("error") or det.get("message") or "System execution incident"),
                        episode_id=det.get("episode_id"),
                        category=str(det.get("category") or "System Incident"),
                        retry_count=int(det.get("retry_count") or 0),
                    )
            except Exception:
                pass

            return log_id
    except Exception as exc:
        logger.warning("Could not record system audit log in PostgreSQL: %s", exc)
        return None


def list_system_audit_logs(
    limit: int = 50,
    event_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve recent system audit and incident log entries from PostgreSQL."""
    try:
        with get_conn() as conn:
            if event_type:
                cursor = conn.execute(
                    """
                    SELECT id, event_type, actor, details, created_at
                    FROM system_audit_logs
                    WHERE event_type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (event_type, int(limit)),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, event_type, actor, details, created_at
                    FROM system_audit_logs
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                )
            return cursor.fetchall()
    except Exception as exc:
        logger.warning("Could not list system audit logs: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Notification Persistence Helpers
# ---------------------------------------------------------------------------

def get_unread_notifications_count(user_id: Optional[int] = None) -> int:
    """Retrieve count of unread notifications from PostgreSQL."""
    try:
        from app.infra.notifications import get_unread_notifications_count as _get_unread
        return _get_unread(user_id=user_id)
    except Exception as exc:
        logger.warning("Could not get unread notifications count: %s", exc)
        return 0


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    init_db()
    print("PostgreSQL tables initialized successfully.")
