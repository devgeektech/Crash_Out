"""
Agent 0 persistence: Postgres/pgvector when DATABASE_URL is set, else JSON files.

Tables (best-effort create):
  agent0_raw_items, agent0_clusters, agent0_pitch_runs, agent0_episode_topics
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from app.paths import OUTPUT_DIR
from app.trends.schema import normalize_pitch_run, today_run_date

logger = logging.getLogger(__name__)

AGENT0_DIR = os.path.join(OUTPUT_DIR, "agent0")
LATEST_RUN_PATH = os.path.join(AGENT0_DIR, "latest_pitch_run.json")
EPISODE_TOPICS_PATH = os.path.join(AGENT0_DIR, "episode_topics.json")


def _ensure_dir() -> None:
    os.makedirs(AGENT0_DIR, exist_ok=True)


def _database_url() -> str:
    return (os.getenv("DATABASE_URL") or "").strip()


def _pg_conn():
    url = _database_url()
    if not url:
        return None
    try:
        import psycopg2  # type: ignore

        return psycopg2.connect(url)
    except Exception as exc:
        logger.warning("Postgres unavailable (%s); using file store", exc)
        return None


def init_store() -> None:
    """Create tables / extension when Postgres is configured."""
    _ensure_dir()
    conn = _pg_conn()
    if not conn:
        return
    try:
        has_vector = False
        with conn, conn.cursor() as cur:
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                has_vector = True
            except Exception:
                # Extension not installed on system; fall back gracefully to text/JSON storage
                conn.rollback()
                logger.info("pgvector extension not installed in Postgres; using text/JSON embedding fallback")

        with conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS agent0_pitch_runs (
                    id SERIAL PRIMARY KEY,
                    run_date TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS agent0_raw_items (
                    id SERIAL PRIMARY KEY,
                    run_date TEXT NOT NULL,
                    layer TEXT,
                    title TEXT,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            embedding_type = "vector(1536)" if has_vector else "TEXT"
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS agent0_episode_topics (
                    episode_id TEXT PRIMARY KEY,
                    title TEXT,
                    label TEXT,
                    embedding {embedding_type},
                    label_text TEXT,
                    approved_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
        logger.info("Agent 0 Postgres store ready (vector_support=%s)", has_vector)
    except Exception as exc:
        logger.warning("Agent 0 Postgres init failed: %s", exc)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def save_pitch_run(run: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = normalize_pitch_run(
        list(run.get("pitches") or []),
        run_date=str(run.get("run_date") or today_run_date()),
        meta=run.get("meta") if isinstance(run.get("meta"), dict) else {},
    )
    cleaned["generated_at"] = run.get("generated_at") or time.time()
    _ensure_dir()
    with open(LATEST_RUN_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    # dated archive
    archive = os.path.join(AGENT0_DIR, f"pitch_run_{cleaned['run_date']}.json")
    with open(archive, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    conn = _pg_conn()
    if conn:
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO agent0_pitch_runs (run_date, payload) VALUES (%s, %s)",
                    (cleaned["run_date"], json.dumps(cleaned)),
                )
        except Exception as exc:
            logger.warning("Failed to persist pitch run to Postgres: %s", exc)
        finally:
            conn.close()
    return cleaned


def load_latest_pitch_run() -> Optional[Dict[str, Any]]:
    conn = _pg_conn()
    if conn:
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM agent0_pitch_runs ORDER BY created_at DESC LIMIT 1"
                )
                row = cur.fetchone()
                if row and row[0]:
                    payload = row[0]
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    if isinstance(payload, dict) and payload.get("pitches"):
                        return payload
        except Exception as exc:
            logger.debug("Postgres latest run read failed: %s", exc)
        finally:
            conn.close()
    if not os.path.exists(LATEST_RUN_PATH):
        return None
    try:
        with open(LATEST_RUN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("pitches"):
            return data
    except Exception as exc:
        logger.warning("Failed to read latest pitch run: %s", exc)
    return None


def save_raw_items(run_date: str, items: List[Dict[str, Any]]) -> None:
    _ensure_dir()
    path = os.path.join(AGENT0_DIR, f"raw_{run_date}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"run_date": run_date, "count": len(items), "items": items[:300]}, f)
    except Exception as exc:
        logger.debug("raw item file save failed: %s", exc)
    conn = _pg_conn()
    if not conn:
        return
    try:
        with conn, conn.cursor() as cur:
            for it in items[:300]:
                cur.execute(
                    """
                    INSERT INTO agent0_raw_items (run_date, layer, title, payload)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        run_date,
                        str(it.get("layer") or ""),
                        str(it.get("title") or "")[:500],
                        json.dumps(it),
                    ),
                )
    except Exception as exc:
        logger.debug("raw item pg save failed: %s", exc)
    finally:
        conn.close()


def remember_episode_topic(
    episode_id: str,
    *,
    title: str,
    label: str,
    embedding: Optional[List[float]] = None,
) -> None:
    _ensure_dir()
    topics = _load_episode_topics_file()
    topics[episode_id] = {
        "episode_id": episode_id,
        "title": title,
        "label": label,
        "label_text": label,
        "embedding": embedding,
        "approved_at": time.time(),
    }
    # Keep 90 days-ish by count
    if len(topics) > 200:
        ordered = sorted(topics.items(), key=lambda kv: float(kv[1].get("approved_at") or 0))
        topics = dict(ordered[-200:])
    with open(EPISODE_TOPICS_PATH, "w", encoding="utf-8") as f:
        json.dump(topics, f, indent=2)

    conn = _pg_conn()
    if not conn:
        return
    try:
        with conn, conn.cursor() as cur:
            if embedding and len(embedding) in (1536, 3072):
                # Only write vector when dimension matches common OpenAI sizes; else label only
                dim = len(embedding)
                if dim == 1536:
                    cur.execute(
                        """
                        INSERT INTO agent0_episode_topics (episode_id, title, label, label_text, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (episode_id) DO UPDATE
                        SET title=EXCLUDED.title, label=EXCLUDED.label, label_text=EXCLUDED.label_text,
                            embedding=EXCLUDED.embedding, approved_at=NOW()
                        """,
                        (episode_id, title, label, label, embedding),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO agent0_episode_topics (episode_id, title, label, label_text)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (episode_id) DO UPDATE
                        SET title=EXCLUDED.title, label=EXCLUDED.label, label_text=EXCLUDED.label_text,
                            approved_at=NOW()
                        """,
                        (episode_id, title, label, label),
                    )
            else:
                cur.execute(
                    """
                    INSERT INTO agent0_episode_topics (episode_id, title, label, label_text)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (episode_id) DO UPDATE
                    SET title=EXCLUDED.title, label=EXCLUDED.label, label_text=EXCLUDED.label_text,
                        approved_at=NOW()
                    """,
                    (episode_id, title, label, label),
                )
    except Exception as exc:
        logger.debug("episode topic pg save failed: %s", exc)
    finally:
        conn.close()


def _load_episode_topics_file() -> Dict[str, Any]:
    if not os.path.exists(EPISODE_TOPICS_PATH):
        return {}
    try:
        with open(EPISODE_TOPICS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_prior_topic_embeddings(days: int = 30) -> List[Tuple[str, List[float]]]:
    """
    Return list of (label_or_id, embedding_or_empty) for 30-day dedupe.
    Empty embedding means cluster.py should Jaccard on the label string.
    """
    cutoff = time.time() - days * 86400
    results: List[Tuple[str, List[float]]] = []

    conn = _pg_conn()
    if conn:
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT episode_id, label_text, embedding
                    FROM agent0_episode_topics
                    WHERE approved_at >= NOW() - (%s || ' days')::interval
                    """,
                    (str(int(days)),),
                )
                for episode_id, label_text, embedding in cur.fetchall() or []:
                    vec: List[float] = []
                    if embedding is not None:
                        try:
                            vec = list(embedding)
                        except Exception:
                            vec = []
                    results.append((str(label_text or episode_id), vec))
        except Exception as exc:
            logger.debug("prior topic pg read failed: %s", exc)
        finally:
            conn.close()
        if results:
            return results

    for episode_id, row in _load_episode_topics_file().items():
        if float(row.get("approved_at") or 0) < cutoff:
            continue
        emb = row.get("embedding") or []
        if not isinstance(emb, list):
            emb = []
        label = str(row.get("label") or row.get("label_text") or row.get("title") or episode_id)
        results.append((label, [float(x) for x in emb] if emb else []))
    return results
