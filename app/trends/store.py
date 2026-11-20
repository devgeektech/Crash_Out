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
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.paths import OUTPUT_DIR
from app.trends.schema import normalize_pitch_run, today_run_date

logger = logging.getLogger(__name__)

AGENT0_DIR = os.path.join(OUTPUT_DIR, "agent0")
AGENT0_RAW_DIR = os.path.join(AGENT0_DIR, "raw")
AGENT0_PITCHES_DIR = os.path.join(AGENT0_DIR, "pitches")
AGENT0_TOPICS_DIR = os.path.join(AGENT0_DIR, "topics")

LATEST_RUN_PATH = os.path.join(AGENT0_DIR, "latest_pitch_run.json")
EPISODE_TOPICS_PATH = os.path.join(AGENT0_TOPICS_DIR, "episode_topics.json")
LEGACY_EPISODE_TOPICS_PATH = os.path.join(AGENT0_DIR, "episode_topics.json")


def _ensure_dir() -> None:
    os.makedirs(AGENT0_DIR, exist_ok=True)
    os.makedirs(AGENT0_RAW_DIR, exist_ok=True)
    os.makedirs(AGENT0_PITCHES_DIR, exist_ok=True)
    os.makedirs(AGENT0_TOPICS_DIR, exist_ok=True)


def prune_agent0_history(retention_days: int = 7) -> int:
    """
    Remove raw scrapes and pitch archives older than retention_days.
    Preserves latest_pitch_run.json and topic definitions.
    """
    deleted_count = 0
    cutoff = time.time() - (retention_days * 86400)
    for folder in (AGENT0_RAW_DIR, AGENT0_PITCHES_DIR, AGENT0_DIR):
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            # Only prune dated archives like raw_*.json and pitch_run_*.json
            if not (fname.startswith("raw_") or fname.startswith("pitch_run_")):
                continue
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(folder, fname)
            if os.path.isfile(fpath):
                try:
                    if os.path.getmtime(fpath) < cutoff:
                        os.remove(fpath)
                        deleted_count += 1
                except Exception as exc:
                    logger.debug("Failed pruning %s: %s", fpath, exc)
    if deleted_count > 0:
        logger.info("Agent 0 storage prune: cleaned %d historical files older than %d days", deleted_count, retention_days)
    return deleted_count


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
            # Dedicated table for generated pitch uniqueness & validation
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS generated_pitches (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    run_date TEXT NOT NULL,
                    rank INT,
                    headline TEXT NOT NULL,
                    youth_sentiment_summary TEXT,
                    crash_out_angle TEXT NOT NULL,
                    proposed_merch_hook TEXT,
                    sensitivity_flag TEXT DEFAULT 'SAFE',
                    consensus_score FLOAT DEFAULT 0.0,
                    sources JSONB,
                    score_breakdown JSONB,
                    embedding {embedding_type},
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            if has_vector:
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_pitches_embedding 
                    ON generated_pitches USING hnsw (embedding vector_cosine_ops)
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
    
    # 1. Update active pointer for dashboard
    with open(LATEST_RUN_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
        
    # 2. Save dated and timestamped archives into pitches/
    time_str = datetime.now().strftime("%H%M%S")
    dated_archive = os.path.join(AGENT0_PITCHES_DIR, f"pitch_run_{cleaned['run_date']}.json")
    snapshot_archive = os.path.join(AGENT0_PITCHES_DIR, f"pitch_run_{cleaned['run_date']}_{time_str}.json")
    
    with open(dated_archive, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    with open(snapshot_archive, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
        
    # Keep legacy root dated archive for backward compatibility
    legacy_archive = os.path.join(AGENT0_DIR, f"pitch_run_{cleaned['run_date']}.json")
    try:
        with open(legacy_archive, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    # Prune historical files older than 7 days
    try:
        prune_agent0_history(retention_days=7)
    except Exception as exc:
        logger.debug("History prune error: %s", exc)

    conn = _pg_conn()
    if conn:
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO agent0_pitch_runs (run_date, payload) VALUES (%s, %s)",
                    (cleaned["run_date"], json.dumps(cleaned)),
                )
                # Also store individual pitches into generated_pitches
                for p in cleaned.get("pitches") or []:
                    emb = p.get("embedding")
                    vec = emb if (isinstance(emb, list) and len(emb) == 1536) else None
                    cur.execute(
                        """
                        INSERT INTO generated_pitches 
                        (run_date, rank, headline, youth_sentiment_summary, crash_out_angle, 
                         proposed_merch_hook, sensitivity_flag, consensus_score, sources, score_breakdown, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            cleaned["run_date"],
                            p.get("rank"),
                            p.get("headline") or "",
                            p.get("youth_sentiment_summary") or "",
                            p.get("crash_out_angle") or "",
                            p.get("proposed_merch_hook") or "",
                            p.get("sensitivity_flag") or "SAFE",
                            p.get("consensus_score") or 0.0,
                            json.dumps(p.get("sources") or {}),
                            json.dumps(p.get("score_breakdown") or {}),
                            vec,
                        ),
                    )
        except Exception as exc:
            logger.warning("Failed to persist pitch run to Postgres: %s", exc)
        finally:
            conn.close()
    return cleaned


def find_similar_pitches(
    embedding: List[float],
    *,
    threshold: float = 0.82,
    limit: int = 5,
    days: int = 60,
) -> List[Dict[str, Any]]:
    """
    Search historical pitches using pgvector cosine similarity (<=> operator).
    Returns pitches with similarity (1 - distance) >= threshold.
    """
    if not embedding or len(embedding) != 1536:
        return []
    conn = _pg_conn()
    if not conn:
        return []
    similar: List[Dict[str, Any]] = []
    try:
        with conn, conn.cursor() as cur:
            # Note: 1 - (embedding <=> vec) is cosine similarity
            cur.execute(
                """
                SELECT 
                    id, headline, crash_out_angle, run_date,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM generated_pitches
                WHERE embedding IS NOT NULL
                  AND created_at >= NOW() - (%s || ' days')::interval
                  AND 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector ASC
                LIMIT %s;
                """,
                (embedding, str(int(days)), embedding, threshold, embedding, limit),
            )
            for row in cur.fetchall() or []:
                similar.append({
                    "id": str(row[0]),
                    "headline": row[1],
                    "crash_out_angle": row[2],
                    "run_date": row[3],
                    "similarity": round(float(row[4]), 4),
                })
    except Exception as exc:
        logger.debug("pgvector similarity search failed: %s", exc)
    finally:
        conn.close()
    return similar


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
    time_str = datetime.now().strftime("%H%M%S")
    dated_path = os.path.join(AGENT0_RAW_DIR, f"raw_{run_date}.json")
    snapshot_path = os.path.join(AGENT0_RAW_DIR, f"raw_{run_date}_{time_str}.json")
    payload = {"run_date": run_date, "count": len(items), "items": items[:300]}
    try:
        with open(dated_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        # Keep legacy root dated copy for backward compatibility
        legacy_path = os.path.join(AGENT0_DIR, f"raw_{run_date}.json")
        with open(legacy_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
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
    for path in (EPISODE_TOPICS_PATH, LEGACY_EPISODE_TOPICS_PATH):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
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
