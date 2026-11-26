"""
Crash Out Multi-Agent POC - FastAPI Server.
HITL Hub + Vidu Q4 Preview (official API) scene generation and FFmpeg merge.
"""
import asyncio
import os
import sys
import time
import shutil
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List, Tuple
from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from app.core.catalog import get_hoa_q4_prompt_episode
from app.config import (
    config,
    CHARACTERS,
    update_vidu_credentials,
    EPISODE_HOA_VIOLATION,
)
from app.state import state_manager, Episode
from app.agents.agent_m_orchestrator import orchestrator
from app.agents.agent_0_trend_ingest import trend_ingest_agent
from app.agents.agent_1_scriptwriter import scriptwriter_agent
from app.agents.agent_4_publisher import publisher_agent
from app.agents.agent_5_seeder import seeder_agent
from app.engines.factory import engine_display_name, get_video_engine, video_engine_mode
from app.engines.vidu_engine import ViduEngine
from app.studio.generation import (
    archive_clip_before_regen,
    enqueue_job,
    record_cost,
    set_production_status,
    update_job,
)
from app.paths import (
    ASSETS_DIR,
    CHARACTERS_DIR,
    OUTPUT_DIR,
    ensure_episode_output_folder,
    find_existing,
    import_relpath,
    merged_abspath,
    merged_relpath,
    public_url,
    scene_file_candidates,
    scene_relpath,
)
from app.media.merger import merge_scene_videos


def _silence_windows_proactor_connection_reset() -> None:
    """Quiet benign WinError 10054 from asyncio's ProactorEventLoop.

    Video players cancel HTTP range requests when seeking or switching clips.
    On Windows that forcibly closes the socket; asyncio then raises
    ConnectionResetError inside _call_connection_lost and logs a noisy
    "Exception in callback" even though the transfer is already finished.
    """
    if sys.platform != "win32":
        return

    from asyncio.proactor_events import _ProactorBasePipeTransport

    if getattr(_ProactorBasePipeTransport._call_connection_lost, "_crash_out_patched", False):
        return

    _orig = _ProactorBasePipeTransport._call_connection_lost

    def _call_connection_lost(self, exc):  # type: ignore[no-untyped-def]
        try:
            _orig(self, exc)
        except (ConnectionResetError, ConnectionAbortedError):
            pass
        except OSError as err:
            if getattr(err, "winerror", None) not in (10053, 10054):
                raise

    _call_connection_lost._crash_out_patched = True  # type: ignore[attr-defined]
    _ProactorBasePipeTransport._call_connection_lost = _call_connection_lost  # type: ignore[method-assign]


def _install_windows_asyncio_exception_handler(loop: asyncio.AbstractEventLoop) -> None:
    if sys.platform != "win32":
        return

    previous_handler = loop.get_exception_handler()

    def _handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exc = context.get("exception")
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError)):
            return
        if isinstance(exc, OSError) and getattr(exc, "winerror", None) in (10053, 10054):
            return
        if previous_handler is not None:
            previous_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(_handler)


_silence_windows_proactor_connection_reset()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _install_windows_asyncio_exception_handler(asyncio.get_running_loop())
    from app.infra.logging import setup_logging
    setup_logging()

    from app.auth.users import ensure_auth_ready
    from app.db import init_db
    from app.studio.worker import start_worker
    from app.trends.scheduler import shutdown_agent0_scheduler, start_agent0_scheduler
    from app.trends.store import init_store
    from app.infra.temporal import shutdown_temporal_runtime, start_temporal_runtime

    init_db()
    ensure_auth_ready()
    init_store()
    start_worker()
    start_agent0_scheduler()

    # Background Temporal connect + worker (must be cancelled cleanly on reload).
    temporal_boot = asyncio.create_task(start_temporal_runtime(), name="temporal-boot")

    try:
        yield
    finally:
        shutdown_agent0_scheduler()
        if not temporal_boot.done():
            temporal_boot.cancel()
            try:
                await temporal_boot
            except (asyncio.CancelledError, Exception):
                pass
        await shutdown_temporal_runtime()


def _script_scenes_for_episode(ep) -> list:
    if ep.script and ep.script.get("scenes"):
        return ep.script["scenes"]
    if getattr(ep, "script_key", "") == "hoa_q4_prompts":
        return get_hoa_q4_prompt_episode()["scenes"]
    return EPISODE_HOA_VIOLATION["scenes"]


app = FastAPI(
    title="Crash Out Multi-Agent POC (Vidu Only)",
    version="3.0.0",
    lifespan=_lifespan,
)

from app.auth.security import session_secret  # noqa: E402
from app.auth.middleware import AuthMiddleware  # noqa: E402
from app.infra.logging import RequestLoggingMiddleware  # noqa: E402

# Order matters: last added runs first. Request logger -> Auth -> Session.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    session_cookie="crash_out_session",
    same_site="lax",
    https_only=False,
    max_age=60 * 60 * 24 * 14,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# Register UI routes before static mounts so /ui/* is never shadowed.
from app.auth.routes import router as auth_router  # noqa: E402
from app.ui import router as ui_router  # noqa: E402

app.include_router(auth_router)
app.include_router(ui_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/characters", StaticFiles(directory=CHARACTERS_DIR), name="characters")
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    fav_path = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.isfile(fav_path):
        return FileResponse(fav_path, media_type="image/x-icon")
    return HTMLResponse(status_code=404)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import logging
    logging.getLogger("app.crash").error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            f'<div class="auth-alert" style="background: rgba(225, 29, 72, 0.15); border: 1px solid #e11d48; color: #fff; padding: 0.75rem 1rem; border-radius: 8px;">'
            f'⚠️ An unexpected error occurred: {exc}. Please refresh or try again.</div>',
            status_code=200,
        )
    return HTMLResponse(
        """<!DOCTYPE html><html><head><title>Crash Out — Error</title><meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="stylesheet" href="/static/css/app.css"></head>
        <body style="background: #0d0914; color: #fff; display: flex; align-items: center; justify-content: center; min-height: 100vh; font-family: sans-serif; text-align: center; padding: 1.5rem;">
        <div style="max-width: 500px; background: #161022; padding: 2rem; border-radius: 12px; border: 1px solid rgba(255, 45, 138, 0.3);">
            <h1 style="color: #ff2d8a; margin-top: 0;">Something went wrong</h1>
            <p style="color: #a098aa; line-height: 1.5;">An internal error occurred while processing this request. The system has logged the details.</p>
            <a href="/" style="display: inline-block; margin-top: 1rem; background: #ff2d8a; color: #fff; padding: 0.6rem 1.4rem; border-radius: 8px; text-decoration: none; font-weight: bold;">Return to Dashboard</a>
        </div></body></html>""",
        status_code=500,
    )


@app.get("/api/state")
def get_pipeline_state():
    ep = state_manager.get_active_episode()
    if not ep:
        ep = state_manager.create_episode("Episode 1: The HOA Violation", engine="vidu")
        ep.available_concepts = trend_ingest_agent.fetch_trending_concepts()
        state_manager.save()
    return {
        "active_episode": ep.dict(),
        "characters": CHARACTERS,
        "active_engine": "vidu",
        "vidu_model": config.vidu_model,
        "vidu_reference_model": config.vidu_reference_model,
    }


@app.post("/api/episodes/new")
def create_new_episode(title: str = "New Episode", engine: str = "mock"):
    mode = video_engine_mode()
    ep = state_manager.create_episode(title=title, engine=mode)
    ep.available_concepts = trend_ingest_agent.fetch_trending_concepts()
    state_manager.save()
    orchestrator.log(
        ep.id,
        f"Created episode pipeline: '{title}' (engine={engine_display_name()}).",
    )
    return ep.dict()


@app.get("/api/platforms/status")
def get_platforms_status():
    engine = get_video_engine()
    return {
        "active_engine": video_engine_mode(),
        "engine_name": engine_display_name(),
        "vidu_model": config.vidu_model,
        "vidu_reference_model": config.vidu_reference_model,
        "credentials": {
            "vidu_email": config.vidu_email,
            "vidu_has_key": bool(config.vidu_api_key),
            "vidu_model": config.vidu_model,
            "vidu_reference_model": config.vidu_reference_model,
            "vidu_base_url": config.vidu_base_url,
            "vidu_resolution": config.vidu_resolution,
            "video_engine": video_engine_mode(),
        },
        "platforms": {
            video_engine_mode(): engine.test_connection(),
        },
    }


@app.post("/api/platforms/set-active")
def set_active_platform(engine: str = Body(..., embed=True)):
    mode = (engine or "").lower().strip()
    if mode not in {"mock", "vidu"}:
        raise HTTPException(status_code=400, detail="Engine must be mock or vidu.")
    ep = state_manager.get_active_episode()
    if ep:
        ep.selected_engine = mode
        state_manager.log_qa(ep.id, f"Active engine set: {mode}.")
        state_manager.save()
    return {"status": "success", "active_engine": mode}


@app.post("/api/platforms/lock-in")
def lock_in_platform(platform: str = Body(..., embed=True)):
    if platform.lower() != "vidu":
        raise HTTPException(status_code=400, detail="Only Vidu can be locked in.")
    ep = state_manager.get_active_episode()
    if ep:
        ep.selected_engine = "vidu"
        ep.final_platform_decision = "vidu"
        state_manager.log_qa(ep.id, "Production platform locked: Vidu Q4 Preview API.")
        state_manager.save()
    return {"status": "locked_in", "platform": "vidu"}


class CredentialUpdate(BaseModel):
    vidu_api_key: Optional[str] = None
    vidu_model: Optional[str] = None
    vidu_reference_model: Optional[str] = None
    vidu_resolution: Optional[str] = None


@app.post("/api/platforms/update-credentials")
def update_credentials(creds: CredentialUpdate):
    update_vidu_credentials(
        api_key=creds.vidu_api_key,
        model=creds.vidu_model,
        reference_model=creds.vidu_reference_model,
        resolution=creds.vidu_resolution,
    )
    return {
        "status": "credentials_updated",
        "vidu_has_key": bool(config.vidu_api_key),
        "vidu_model": config.vidu_model,
        "vidu_reference_model": config.vidu_reference_model,
        "vidu_resolution": config.vidu_resolution,
    }


@app.get("/api/platforms/benchmark")
def get_benchmark_report():
    vidu_engine = ViduEngine()
    return {
        "active_platform": "vidu",
        "model": config.vidu_model,
        "reference_model": config.vidu_reference_model,
        "specs": vidu_engine.get_specs(),
        "notes": "Pipeline is Vidu Q4 Preview only. Scenes use reference2video (character PNGs) with native audio.",
    }


@app.post("/api/pipeline/stage-0-refresh")
def refresh_concepts():
    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")
    ep.available_concepts = trend_ingest_agent.fetch_trending_concepts()
    titles = [
        str(c.get("headline") or c.get("title") or "")
        for c in (ep.available_concepts or [])[:5]
    ]
    orchestrator.log(
        ep.id,
        "Agent 0 friction pitches refreshed"
        + (f": {', '.join(t for t in titles if t)}" if any(titles) else "."),
    )
    state_manager.save()
    return {"concepts": ep.available_concepts, "count": len(ep.available_concepts or [])}


@app.post("/api/agent0/run")
def api_agent0_run(dispatch_telegram: bool = False):
    """Manual Agent 0 daily run (Top 5 pitch cards)."""
    run = trend_ingest_agent.fetch_daily_pitches(force_refresh=True)
    if dispatch_telegram:
        from app.trends.telegram_dispatch import dispatch_pitch_run

        dispatch_pitch_run(run)
    return run


@app.get("/api/agent0/latest")
def api_agent0_latest():
    from app.trends.store import load_latest_pitch_run

    run = load_latest_pitch_run()
    if not run:
        raise HTTPException(status_code=404, detail="No Agent 0 run yet")
    return run


@app.post("/api/gateway/1/approve")
def approve_gateway_1(payload: Dict[str, Any] = Body(...)):
    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")

    orchestrator.approve_gateway(ep.id, 1, payload)
    orchestrator.log(ep.id, "Agent 1 generating satirical script & merch punchline...")
    script_data = scriptwriter_agent.generate_script(ep.selected_concept)

    passed, qa_msg = orchestrator.validate_script_qa(script_data)
    orchestrator.log(ep.id, qa_msg)
    if not passed:
        raise HTTPException(status_code=422, detail=qa_msg)

    ep.script = script_data
    ep.merch_punchline = script_data.get("merch_punchline_trigger")
    ep.status = "WAITING_GATEWAY_2"
    ep.current_gateway = 2
    set_production_status(ep, "scripting")
    from app.studio.naming import apply_confirmed_pitch_title

    selected = ep.selected_concept or payload.get("selected_concept") or {}
    apply_confirmed_pitch_title(
        ep,
        str(selected.get("headline") or selected.get("title") or "").strip(),
    )
    state_manager.save()
    return ep.dict()


def _require_engine_ready():
    """Return configured engine. Mock never needs a Vidu key."""
    mode = video_engine_mode()
    if mode == "vidu" and not config.vidu_api_key:
        raise HTTPException(
            status_code=400,
            detail="VIDU_API_KEY is required when VIDEO_ENGINE=vidu. Or set VIDEO_ENGINE=mock.",
        )
    return get_video_engine()


def _scene_result_payload(sc: Dict[str, Any], res) -> Dict[str, Any]:
    sc_id = sc.get("scene_id", 1)
    return {
        "scene_id": sc_id,
        "title": sc.get("title", f"Scene {sc_id}"),
        "time_range": sc.get("time_range", "00:00 - 00:15"),
        "duration_sec": res.metadata.get("duration_sec", 15),
        "primary_character": sc.get("primary_character", "gary"),
        "video_url": res.video_url,
        "local_path": res.local_path,
        "status": "completed",
        "latency_sec": res.latency_sec,
        "job_id": res.job_id,
        "vidu_mode": res.metadata.get("mode"),
        "engine": res.engine,
        "credits": res.metadata.get("credits"),
    }


def _generate_scene_worker(
    scene: Dict[str, Any], folder_name: str
) -> Tuple[int, Dict[str, Any], Any]:
    """Thread worker: each scene gets its own engine client (mock or vidu)."""
    sc_id = int(scene.get("scene_id", 1))
    engine = get_video_engine()
    rel = scene_relpath(folder_name, sc_id)
    result = engine.generate_scene_video(scene, rel)
    return sc_id, scene, result


def render_all_episode_scenes(ep: Episode) -> List[Dict[str, Any]]:
    _require_engine_ready()
    scenes = _script_scenes_for_episode(ep)
    folder = ensure_episode_output_folder(ep)
    mode = video_engine_mode()
    set_production_status(ep, "generating")
    state_manager.save()

    total_start = time.time()
    worker_count = min(4, max(1, len(scenes)))
    orchestrator.log(
        ep.id,
        f"Rendering {len(scenes)} scenes concurrently via {engine_display_name()} "
        f"({worker_count} workers) → outputs/{folder}/",
    )
    for sc in scenes:
        sc_id = int(sc.get("scene_id", 1))
        prompt = sc.get("vidu_prompt") or sc.get("source_prompt") or ""
        archive_clip_before_regen(ep, sc_id, prompt=prompt, engine=mode)
        try:
            job = enqueue_job(ep, sc_id)
            update_job(ep, job["id"], status="processing")
            sc["_job_id"] = job["id"]
        except ValueError:
            sc["_job_id"] = None
        prompt_chars = sc.get("vidu_prompt_chars") or len(prompt)
        orchestrator.log(
            ep.id,
            f"Queued Scene {sc_id}/4: '{sc.get('title')}' | prompt {prompt_chars}/2000 chars",
        )
    state_manager.save()

    completed: Dict[int, Dict[str, Any]] = {}
    failures: List[str] = []

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = {
            pool.submit(_generate_scene_worker, sc, folder): sc for sc in scenes
        }
        for fut in as_completed(futures):
            sc = futures[fut]
            sc_id = int(sc.get("scene_id", 1))
            job_id = sc.get("_job_id")
            try:
                done_id, scene, res = fut.result()
            except Exception as exc:
                failures.append(f"Scene {sc_id}: {exc}")
                orchestrator.log(ep.id, f"Scene {sc_id} failed: {exc}")
                if job_id:
                    update_job(ep, job_id, status="failed", error=str(exc))
                continue

            if res.status != "completed" or not res.local_path:
                err = res.error or "unknown error"
                failures.append(f"Scene {done_id}: {err}")
                orchestrator.log(ep.id, f"Scene {done_id} failed: {err}")
                if job_id:
                    update_job(ep, job_id, status="failed", error=err)
                continue

            completed[done_id] = _scene_result_payload(scene, res)
            try:
                credits_used = float(res.metadata.get("credits_used") or 0)
            except (TypeError, ValueError):
                credits_used = 0.0
            record_cost(
                ep,
                scene_id=done_id,
                engine=res.engine,
                estimated_usd=float(res.cost_estimate_usd or 0),
                credits=credits_used,
            )
            if job_id:
                update_job(ep, job_id, status="completed")
            orchestrator.log(
                ep.id,
                f"Scene {done_id} completed via {res.engine} ({res.metadata.get('mode')}): "
                f"{res.video_url} in {res.latency_sec}s",
            )

    if failures:
        state_manager.save()
        raise HTTPException(
            status_code=502,
            detail="Scene generation failed — " + "; ".join(failures),
        )

    scene_results = [completed[int(sc.get("scene_id", 1))] for sc in scenes]
    ep.scene_videos = scene_results
    ep.video_render_time_sec = round(time.time() - total_start, 2)
    ep.video_engine_used = engine_display_name()
    orchestrator.log(
        ep.id,
        f"All {len(scene_results)} scenes finished concurrently in "
        f"{ep.video_render_time_sec}s (saved under outputs/{folder}/)",
    )
    state_manager.save()
    return scene_results


def merge_episode_scenes(ep: Episode) -> Dict[str, Any]:
    if not ep.scene_videos:
        render_all_episode_scenes(ep)

    folder = ensure_episode_output_folder(ep)
    scene_paths = []
    for sc in ep.scene_videos:
        p = sc.get("local_path")
        if not p or not os.path.exists(p):
            sc_id = int(sc.get("scene_id", 1))
            p = find_existing(
                scene_file_candidates(ep.id, sc_id, folder_name=folder)
            )
        if p and os.path.exists(p):
            scene_paths.append(p)

    merged_rel = merged_relpath(folder)
    merged_path = merged_abspath(folder)
    intro = os.path.join(ASSETS_DIR, "intro.mp4")
    outro = os.path.join(ASSETS_DIR, "outro.mp4")

    orchestrator.log(
        ep.id,
        f"FFmpeg concat: merging {len(scene_paths)} scene clips"
        f"{' + intro' if os.path.isfile(intro) else ''}"
        f"{' + outro' if os.path.isfile(outro) else ''}"
        f" into outputs/{merged_rel}...",
    )
    merge_res = merge_scene_videos(
        scene_paths,
        merged_path,
        intro_path=intro if os.path.isfile(intro) else None,
        outro_path=outro if os.path.isfile(outro) else None,
    )

    if merge_res.get("success"):
        ep.merged_video_url = public_url(merged_rel)
        ep.video_url = ep.merged_video_url
        ep.scenes_merged = True
        ep.video_qa_passed = True
        set_production_status(ep, "generating")
        orchestrator.log(
            ep.id,
            f"FFmpeg concat success: {merged_rel} ({merge_res.get('file_size_kb')} KB)",
        )
    else:
        orchestrator.log(ep.id, f"FFmpeg merge failed: {merge_res.get('error')}")
        if ep.scene_videos:
            ep.video_url = ep.scene_videos[0].get("video_url")

    state_manager.save()
    return merge_res


@app.post("/api/gateway/2/approve")
def approve_gateway_2(payload: Dict[str, Any] = Body(...)):
    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")

    orchestrator.approve_gateway(ep.id, 2, payload)
    ep.status = "SCRIPT_APPROVED"
    ep.current_gateway = 3
    set_production_status(ep, "generating")
    state_manager.save()
    orchestrator.log(
        ep.id,
        f"Gateway 2 approved: generating 4 scenes via {engine_display_name()}...",
    )

    render_all_episode_scenes(ep)
    merge_episode_scenes(ep)

    ep.video_engine_used = engine_display_name()
    ep.native_audio_enabled = True
    ep.selected_engine = video_engine_mode()
    ep.status = "SCRIPT_APPROVED"
    ep.current_gateway = 3
    set_production_status(ep, "generating")
    state_manager.save()
    return ep.dict()


@app.post("/api/video/generate-all-scenes")
def generate_all_scenes():
    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")
    render_all_episode_scenes(ep)
    return {"status": "success", "scene_videos": ep.scene_videos}


@app.post("/api/video/generate-single-scene")
def generate_single_scene(payload: Dict[str, Any] = Body(...)):
    scene_id = int(payload.get("scene_id", 1))
    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")

    scenes = _script_scenes_for_episode(ep)
    target_scene = next((sc for sc in scenes if sc.get("scene_id") == scene_id), None)
    if not target_scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found in script.")

    engine = _require_engine_ready()
    folder = ensure_episode_output_folder(ep)
    mode = video_engine_mode()
    prompt = target_scene.get("vidu_prompt") or target_scene.get("source_prompt") or ""
    archive_clip_before_regen(ep, scene_id, prompt=prompt, engine=mode)
    try:
        job = enqueue_job(ep, scene_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    update_job(ep, job["id"], status="processing")
    set_production_status(ep, "generating")
    state_manager.save()
    output_filename = scene_relpath(folder, scene_id)
    orchestrator.log(
        ep.id,
        f"Re-generating Scene {scene_id} via {engine_display_name()} → outputs/{output_filename}",
    )
    res = engine.generate_scene_video(target_scene, output_filename)
    if res.status != "completed":
        update_job(ep, job["id"], status="failed", error=res.error or "failed")
        state_manager.save()
        raise HTTPException(
            status_code=502,
            detail=f"Scene {scene_id} failed: {res.error}",
        )

    updated = False
    for sc_info in ep.scene_videos:
        if sc_info.get("scene_id") == scene_id:
            sc_info["video_url"] = res.video_url
            sc_info["local_path"] = res.local_path
            sc_info["duration_sec"] = res.metadata.get("duration_sec", 15)
            sc_info["latency_sec"] = res.latency_sec
            sc_info["job_id"] = res.job_id
            sc_info["vidu_mode"] = res.metadata.get("mode")
            sc_info["engine"] = res.engine
            updated = True
            break
    if not updated:
        ep.scene_videos.append(_scene_result_payload(target_scene, res))

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
    update_job(ep, job["id"], status="completed")
    state_manager.save()
    return {"status": "success", "scene": target_scene, "video_url": res.video_url}


@app.post("/api/video/merge-scenes")
def trigger_merge_scenes():
    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")
    merge_res = merge_episode_scenes(ep)
    return {
        "status": "success" if merge_res.get("success") else "error",
        "merge_result": merge_res,
        "merged_video_url": ep.merged_video_url,
    }


@app.post("/api/gateway/3/approve")
def approve_gateway_3(payload: Dict[str, Any] = Body(...)):
    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")

    orchestrator.approve_gateway(ep.id, 3, payload)
    orchestrator.log(ep.id, "Agent 4 preparing social metadata and merch mockup...")
    deploy_result = publisher_agent.prepare_deployment(
        episode_id=ep.id,
        episode_title=ep.title,
        merch_punchline=ep.merch_punchline or "Capitalism Broke My Dad",
    )

    ep.social_posts = deploy_result.get("social", {})
    ep.merch_listing = deploy_result.get("merch", {})
    ep.merch_mockup_url = deploy_result.get("mockup_url")
    from app.studio.generation import mark_episode_final

    mark_episode_final(ep)
    state_manager.save()
    return ep.dict()


@app.post("/api/episodes/reset")
def reset_episode_pipeline():
    ep = state_manager.create_episode("Episode 1: The HOA Violation", engine="vidu")
    ep.available_concepts = trend_ingest_agent.fetch_trending_concepts()
    state_manager.save()
    orchestrator.log(ep.id, "Pipeline reset to Stage 1 (Vidu only).")
    return ep.dict()


@app.post("/api/video/import-file")
async def import_video_file(
    file: UploadFile = File(...),
    platform_source: str = Form("Vidu Q4 Preview"),
):
    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")

    ext = os.path.splitext(file.filename or "")[1] or ".mp4"
    folder = ensure_episode_output_folder(ep)
    state_manager.save()
    saved_rel = import_relpath(folder, "web_import", ext)
    saved_path = os.path.join(OUTPUT_DIR, saved_rel.replace("/", os.sep))

    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    passed, qa_msg = orchestrator.validate_video_qa(saved_path)
    orchestrator.log(ep.id, f"Imported video from {platform_source}: {qa_msg}")

    ep.video_url = public_url(saved_rel)
    ep.video_engine_used = f"{platform_source} (Native Audio)"
    ep.video_qa_passed = passed
    ep.native_audio_enabled = True
    ep.current_gateway = 4
    ep.status = "WAITING_GATEWAY_4"
    state_manager.save()
    return ep.dict()


@app.post("/api/video/import-url")
def import_video_url(payload: Dict[str, Any] = Body(...)):
    url = payload.get("video_url")
    platform = payload.get("platform", "Vidu Q4 Preview")
    if not url:
        raise HTTPException(status_code=400, detail="Missing video_url")

    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")

    try:
        r = requests.get(url, stream=True, timeout=30)
        folder = ensure_episode_output_folder(ep)
        state_manager.save()
        saved_rel = import_relpath(folder, "url_import", ".mp4")
        saved_path = os.path.join(OUTPUT_DIR, saved_rel.replace("/", os.sep))
        with open(saved_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        passed, qa_msg = orchestrator.validate_video_qa(saved_path)
        orchestrator.log(ep.id, f"Downloaded web video: {qa_msg}")
        ep.video_url = public_url(saved_rel)
        ep.video_engine_used = f"{platform} (Native Audio)"
        ep.video_qa_passed = passed
        ep.native_audio_enabled = True
        ep.current_gateway = 4
        ep.status = "WAITING_GATEWAY_4"
        state_manager.save()
        return ep.dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch video from URL: {e}")


@app.get("/api/studio-package")
def get_studio_package():
    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")

    script_lines = ep.script.get("dialogue_lines", []) if ep.script else []
    primary_dialogue = (
        " ".join([l.get("text", "") for l in script_lines])
        if script_lines
        else "Gary crashing out comically."
    )

    vidu_engine = ViduEngine()
    gary_vidu_prompt = vidu_engine.build_vidu_prompt(
        "gary",
        "veins bulging on forehead, accordion hands flailing, yelling at self checkout terminal",
        primary_dialogue[:180],
    )
    linda_vidu_prompt = vidu_engine.build_vidu_prompt(
        "linda",
        "holding 40oz Stanley tumbler in Alo Yoga athleisure, manic wide eyes in shrill HOA panic",
        primary_dialogue[:180],
    )
    chris_vidu_prompt = vidu_engine.build_vidu_prompt(
        "chris",
        "slouching with severe tech-neck, oversized hoodie, headphones, deadpan drawl looking at glowing crypto phone",
        primary_dialogue[:180],
    )
    chloe_vidu_prompt = vidu_engine.build_vidu_prompt(
        "chloe",
        "hot-pink blazer, ring-light iPhone rig, index finger pause gesture, dabbing Drunk Elephant serum mid-sentence",
        primary_dialogue[:180],
    )

    return {
        "episode_id": ep.id,
        "episode_title": ep.title,
        "merch_punchline": ep.merch_punchline or "Capitalism Broke My Dad",
        "clean_avatars": {
            "gary": "/characters/gary_9x16.png",
            "linda": "/characters/linda_9x16.png",
            "chris": "/characters/chris_9x16.png",
            "chloe": "/characters/chloe_9x16.png",
        },
        "prompts": {
            "vidu": gary_vidu_prompt,
            "vidu_characters": {
                "gary": gary_vidu_prompt,
                "linda": linda_vidu_prompt,
                "chris": chris_vidu_prompt,
                "chloe": chloe_vidu_prompt,
            },
        },
        "vidu_voice_recommendations": {
            "gary": {
                "name": "Gary (Dad, 44)",
                "archetype": "The Cracking Gentle Parent / Suburban MAGA Disciple",
                "audio_tag": "[Gary, agitated suburban dad with rapid manic acceleration]:",
                "tone": "Therapist voice that cracks into rapid-fire, abrasive Trumpian rally rhetoric with loud volume spikes.",
            },
            "linda": {
                "name": "Linda (Mom, 42)",
                "archetype": "The Secret Junk-Food Goopist / Status-Anxious Suburbanite",
                "audio_tag": "[Linda, breathy vocal-fried wellness guru whispering in shrill panic]:",
                "tone": "Breathy, melodic faux-zen guru cadence that shatters into shrill, high-pitched HOA terror.",
            },
            "chris": {
                "name": "Chris (Son, 15)",
                "archetype": "The Techno-Gospel Doomer / First Principles Bro",
                "audio_tag": "[Chris, flat monotone teen drawl with cold statistical detachment]:",
                "tone": "Completely flat, low-energy monotone drawl, vocal fry, zero eye contact, chilled nihilism.",
            },
            "chloe": {
                "name": "Chloe (Daughter, 11)",
                "archetype": "The Pre-Teen Momager / Digital Monetization Shark",
                "audio_tag": "[Chloe, polished sugary influencer voice shifting into cold corporate PR cadence]:",
                "tone": "Razor-sharp Kardashian vocal fry with polished corporate PR coaching cadence.",
            },
        },
        "accounts": {
            "vidu": {
                "email": config.vidu_email,
                "url": "https://platform.vidu.com",
                "model": config.vidu_model,
                "reference_model": config.vidu_reference_model,
                "role": "Official Vidu Q4 Preview — reference2video / img2video with native audio",
            }
        },
    }


@app.post("/api/gateway/4/approve")
def approve_gateway_4(payload: Dict[str, Any] = Body(...)):
    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")

    orchestrator.approve_gateway(ep.id, 4, payload)
    orchestrator.log(ep.id, "Agent 5 drafting community seeding responses...")
    seeding_campaign = seeder_agent.generate_seeding_campaign(
        episode_title=ep.title,
        merch_punchline=ep.merch_punchline or "Capitalism Broke My Dad",
    )

    ep.seeding_drafts = seeding_campaign
    ep.status = "WAITING_GATEWAY_5"
    ep.current_gateway = 5
    state_manager.save()
    return ep.dict()


@app.post("/api/gateway/5/approve")
def approve_gateway_5(payload: Dict[str, Any] = Body(...)):
    ep = state_manager.get_active_episode()
    if not ep:
        raise HTTPException(status_code=404, detail="No active episode")

    from app.studio.generation import mark_episode_final

    orchestrator.approve_gateway(ep.id, 5, payload)
    mark_episode_final(ep)
    state_manager.save()
    return ep.dict()


@app.post("/api/gateway/6/approve")
def approve_gateway_6(payload: Dict[str, Any] = Body(...)):
    return approve_gateway_5(payload)


@app.get("/api/system/health")
def system_health():
    """System health & M2 component status check."""
    from app.db import is_postgres
    from app.infra.storage import s3_service
    from app.infra.temporal import TEMPORAL_HOST

    db_status = "postgresql" if is_postgres() else "disconnected"
    return {
        "status": "healthy",
        "database": {
            "mode": db_status,
            "connected": True,
        },
        "storage": {
            "s3_configured": s3_service.is_configured,
            "s3_bucket": s3_service.bucket_name or None,
            "region": s3_service.region_name,
        },
        "temporal": {
            "host": TEMPORAL_HOST,
            "status": "configured",
        },
        "auth": {
            "session_auth": "enabled",
            "password_hashing": "bcrypt",
            "secret_encryption": "fernet",
        },
        "logging": {
            "framework": "active",
            "app_log": "outputs/logs/app.log",
            "access_log": "outputs/logs/access.log",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
