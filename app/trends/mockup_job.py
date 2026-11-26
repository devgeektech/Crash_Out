"""
Background Mockup ingest job.

Survives page switches: scrape + Work history shell run in a daemon thread.
UI polls status and keeps the Mockup button in Searching until finished.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
# user_key -> job dict
_JOBS: Dict[str, Dict[str, Any]] = {}


def _user_key(user_id: Optional[int]) -> str:
    return f"u:{int(user_id)}" if user_id is not None else "u:anon"


def get_mockup_job(user_id: Optional[int] = None) -> Dict[str, Any]:
    key = _user_key(user_id)
    with _lock:
        job = dict(_JOBS.get(key) or {})
    if not job:
        return {
            "id": "",
            "status": "idle",
            "running": False,
            "message": "",
            "error": "",
            "raw_count": 0,
            "episode_id": "",
            "episode_title": "",
            "started_at": 0.0,
            "finished_at": 0.0,
        }
    status = str(job.get("status") or "idle")
    job["running"] = status == "running"
    return job


def start_mockup_job(*, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Start a background ingest if none is running for this user.
    Returns the current job snapshot (running or newly started).
    """
    key = _user_key(user_id)
    with _lock:
        existing = _JOBS.get(key)
        if existing and existing.get("status") == "running":
            out = dict(existing)
            out["running"] = True
            out["already_running"] = True
            return out

        job_id = f"mockup_{uuid.uuid4().hex[:10]}"
        job: Dict[str, Any] = {
            "id": job_id,
            "status": "running",
            "running": True,
            "already_running": False,
            "message": "Searching for trending topics…",
            "error": "",
            "raw_count": 0,
            "episode_id": "",
            "episode_title": "",
            "layer_bits": "",
            "started_at": time.time(),
            "finished_at": 0.0,
            "user_id": user_id,
        }
        _JOBS[key] = job

    thread = threading.Thread(
        target=_run_mockup_job,
        args=(key, job_id, user_id),
        name=f"agent0-mockup-{job_id}",
        daemon=True,
    )
    thread.start()
    return dict(job)


def ack_mockup_job(user_id: Optional[int] = None) -> None:
    """Clear a finished job after the UI has refreshed."""
    key = _user_key(user_id)
    with _lock:
        job = _JOBS.get(key)
        if not job:
            return
        if job.get("status") in {"done", "error"}:
            _JOBS.pop(key, None)


def _update(key: str, job_id: str, **fields: Any) -> None:
    with _lock:
        job = _JOBS.get(key)
        if not job or job.get("id") != job_id:
            return
        job.update(fields)


def create_research_ingest_shell(
    *,
    user_id: Optional[int],
    raw_count: int,
    run_date: str,
    layer_bits: str = "",
) -> Any:
    """
    Create Work history episode for a fresh ingest (no pitches yet) and make it active
    so Trend Research updates against this episode.
    """
    from app.core.catalog import add_manual_catalog_video
    from app.studio.generation import next_episode_number, set_production_status
    from app.studio.naming import make_studio_episode_name
    from app.state import state_manager

    item = add_manual_catalog_video(
        title=f"Trend Research · {run_date or 'today'}",
        subtitle=f"Agent 0 ingest · {raw_count} raw hits · awaiting topic selection",
        merch="Capitalism broke my dad",
        user_id=user_id,
    )
    target_num = next_episode_number()
    ep = state_manager.create_episode(
        title=make_studio_episode_name(serial_number=target_num),
        engine="vidu",
        catalog_id=str(item["id"]),
        script_key=str(item.get("script_key") or item["id"]),
        episode_number=target_num,
        user_id=user_id,
    )
    ep.available_concepts = []
    ep.selected_concept = None
    set_production_status(ep, "draft")
    state_manager.save()
    state_manager.set_active(ep.id)
    try:
        from app.agents.agent_m_orchestrator import orchestrator

        orchestrator.log(
            ep.id,
            f"Ingest: refreshed {raw_count} signals ({layer_bits}); waiting for topic selection.",
        )
    except Exception:
        pass
    return ep


def _run_mockup_job(key: str, job_id: str, user_id: Optional[int]) -> None:
    try:
        from app.trends.scheduler import run_daily_agent0_job

        _update(key, job_id, message="Scraping Mainstream + Social feeds…")
        # Scrape only here; shell is created below and becomes the active Trend Research episode.
        result = run_daily_agent0_job(create_shell=False)

        raw_count = int(
            (result.get("meta") or {}).get("raw_count")
            or len(result.get("items") or [])
        )
        layers = (result.get("meta") or {}).get("layer_counts") or {}
        run_date = str(result.get("run_date") or "")
        layer_bits = " · ".join(f"{k}:{int(layers.get(k) or 0)}" for k in ("A", "B"))

        _update(
            key,
            job_id,
            message="Saving Work history shell…",
            raw_count=raw_count,
            layer_bits=layer_bits,
        )

        ep = create_research_ingest_shell(
            user_id=user_id,
            raw_count=raw_count,
            run_date=run_date,
            layer_bits=layer_bits,
        )

        toast = (
            f"Trends refreshed · {raw_count} raw hits"
            + (f" ({layer_bits})" if layer_bits else "")
            + f" · listed as {ep.title} · select 5 topics to create pitches"
        )
        _update(
            key,
            job_id,
            status="done",
            running=False,
            message=toast,
            error="",
            raw_count=raw_count,
            layer_bits=layer_bits,
            episode_id=ep.id,
            episode_title=ep.title,
            finished_at=time.time(),
        )
        logger.info("Mockup job %s done: raw=%s ep=%s", job_id, raw_count, ep.id)
    except Exception as exc:
        logger.exception("Mockup job %s failed: %s", job_id, exc)
        _update(
            key,
            job_id,
            status="error",
            running=False,
            message="",
            error=str(exc),
            finished_at=time.time(),
        )
