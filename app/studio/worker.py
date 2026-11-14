"""
Background generation worker — process waiting jobs without keeping the browser open.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_thread: Optional[threading.Thread] = None
_stop = threading.Event()
_notifications: List[Dict[str, Any]] = []


def _push_notify(ep_id: str, message: str, *, kind: str = "ok") -> None:
    with _lock:
        _notifications.append(
            {
                "id": f"n_{int(time.time() * 1000)}",
                "episode_id": ep_id,
                "message": message,
                "kind": kind,
                "at": time.time(),
                "read": False,
            }
        )
        del _notifications[:-50]


def list_notifications(*, unread_only: bool = False) -> List[Dict[str, Any]]:
    with _lock:
        items = list(_notifications)
    if unread_only:
        return [n for n in items if not n.get("read")]
    return items


def mark_notifications_read() -> None:
    with _lock:
        for n in _notifications:
            n["read"] = True


def _run_scene_job(ep_id: str, job_id: str, scene_id: int) -> None:
    from app.engines.factory import engine_display_name, get_video_engine, video_engine_mode
    from app.studio.generation import (
        archive_clip_before_regen,
        record_cost,
        set_production_status,
        update_job,
    )
    from app.paths import ensure_episode_output_folder, scene_relpath
    from app.state import state_manager

    ep = state_manager.episodes.get(ep_id)
    if not ep:
        return
    scenes = (ep.script or {}).get("scenes") or []
    target = next((sc for sc in scenes if int(sc.get("scene_id", 0)) == scene_id), None)
    if not target:
        update_job(ep, job_id, status="failed", error="Scene not in script")
        state_manager.save_episode(ep_id)
        _push_notify(ep_id, f"Scene {scene_id} missing from script", kind="error")
        return

    update_job(ep, job_id, status="processing")
    set_production_status(ep, "generating")
    state_manager.save_episode(ep_id)

    mode = video_engine_mode()
    prompt = target.get("vidu_prompt") or target.get("source_prompt") or ""
    archive_clip_before_regen(ep, scene_id, prompt=prompt, engine=mode)
    folder = ensure_episode_output_folder(ep)
    engine = get_video_engine()
    rel = scene_relpath(folder, scene_id)
    try:
        res = engine.generate_scene_video(target, rel)
        if res.status != "completed":
            update_job(ep, job_id, status="failed", error=res.error or "failed")
            state_manager.save_episode(ep_id)
            _push_notify(ep_id, f"Scene {scene_id} failed: {res.error}", kind="error")
            return
        updated = False
        for sc_info in ep.scene_videos or []:
            if int(sc_info.get("scene_id", 0)) == scene_id:
                sc_info.update(
                    {
                        "video_url": res.video_url,
                        "local_path": res.local_path,
                        "duration_sec": res.metadata.get("duration_sec", 15),
                        "latency_sec": res.latency_sec,
                        "job_id": res.job_id,
                        "vidu_mode": res.metadata.get("mode"),
                        "engine": res.engine,
                        "status": "completed",
                    }
                )
                updated = True
                break
        if not updated:
            ep.scene_videos = list(ep.scene_videos or []) + [
                {
                    "scene_id": scene_id,
                    "title": target.get("title", f"Scene {scene_id}"),
                    "video_url": res.video_url,
                    "local_path": res.local_path,
                    "status": "completed",
                    "engine": res.engine,
                    "job_id": res.job_id,
                }
            ]
        try:
            credits_used = float(res.metadata.get("credits_used") or 0)
        except (TypeError, ValueError):
            credits_used = 0.0
        record_cost(
            ep,
            scene_id=scene_id,
            engine=res.engine,
            estimated_usd=float(res.cost_estimate_usd or 0),
            credits=credits_used,
        )
        update_job(ep, job_id, status="completed")
        ep.video_engine_used = engine_display_name()
        state_manager.save_episode(ep_id)
        _push_notify(ep_id, f"Scene {scene_id} ready ({engine_display_name()})", kind="ok")
    except Exception as exc:
        logger.exception("Background scene job failed")
        update_job(ep, job_id, status="failed", error=str(exc))
        state_manager.save_episode(ep_id)
        _push_notify(ep_id, f"Scene {scene_id} failed: {exc}", kind="error")


def _process_once() -> None:
    from app.state import state_manager

    jobs_to_run = []
    for ep in list(state_manager.episodes.values()):
        for job in list(ep.generation_jobs or []):
            if job.get("status") == "waiting":
                jobs_to_run.append((ep.id, job.get("id"), int(job.get("scene_id") or 1)))

    for ep_id, job_id, scene_id in jobs_to_run:
        if not job_id:
            continue
        _run_scene_job(ep_id, job_id, scene_id)


def _loop() -> None:
    while not _stop.is_set():
        try:
            _process_once()
        except Exception:
            logger.exception("Worker loop error")
        _stop.wait(2.0)


def start_worker() -> None:
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="crashout-gen-worker", daemon=True)
        _thread.start()
        logger.info("Background generation worker started")


def enqueue_background(ep, scene_id: int) -> Dict[str, Any]:
    from app.studio.generation import enqueue_job
    from app.state import state_manager

    job = enqueue_job(ep, int(scene_id))
    state_manager.save_episode(ep.id)
    start_worker()
    return job
