"""
Jinja + HTMX UI helpers and routes for the Crash Out HITL hub.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.agents.agent_0_trend_ingest import trend_ingest_agent
from app.agents.agent_1_scriptwriter import scriptwriter_agent
from app.agents.agent_4_publisher import publisher_agent
from app.agents.agent_5_seeder import seeder_agent
from app.agents.agent_m_orchestrator import orchestrator
from app.catalog import (
    add_manual_catalog_video,
    concepts_for_catalog,
    delete_manual_catalog_video,
    get_catalog_item,
    get_hoa_q4_prompt_episode,
    is_empty_concept,
    list_catalog_items,
    prompt_file_path,
    refresh_hoa_q4_prompt_episode,
    update_custom_scene_prompt,
)
from app.config import CHARACTERS, config
from app.engines.vidu_engine import ViduEngine
from app.paths import (
    OUTPUT_DIR,
    abspath_from_public,
    ensure_episode_output_folder,
    find_existing,
    merged_file_candidates,
    public_url,
    relpath_from_outputs,
    build_episode_folder_name,
    scene_file_candidates,
)
from app.state import Episode, state_manager

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter(tags=["ui"])


def _public_output_url(rel_or_filename: str, file_path: Optional[str] = None) -> str:
    if file_path and os.path.exists(file_path):
        try:
            rel = relpath_from_outputs(file_path)
        except ValueError:
            rel = rel_or_filename.replace("\\", "/").lstrip("/")
        path = file_path
    else:
        rel = rel_or_filename.replace("\\", "/").lstrip("/")
        if rel.startswith("outputs/"):
            rel = rel[len("outputs/") :]
        path = os.path.join(OUTPUT_DIR, rel.replace("/", os.sep))
    url = public_url(rel)
    if path and os.path.exists(path):
        try:
            url = f"{url}?v={int(os.path.getmtime(path))}"
        except OSError:
            pass
    return url


def _episode_folder(ep: Episode) -> str:
    """Resolve folder name without creating directories (UI-safe)."""
    if ep.output_folder:
        return ep.output_folder
    return build_episode_folder_name(ep.id, ep.title or ep.id)


def _scene_file_candidates(ep: Episode, scene_id: int) -> list[str]:
    return scene_file_candidates(
        ep.id, scene_id, folder_name=_episode_folder(ep), title=ep.title
    )


def _resolve_scene_playable(ep: Episode, scene_id: int, sv: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Prefer a local /outputs file so the browser can always play the clip."""
    local_path = (sv or {}).get("local_path") or ""
    video_url = (sv or {}).get("video_url") or ""

    for path in [local_path, *_scene_file_candidates(ep, scene_id)]:
        if path and os.path.exists(path):
            return {
                "has_video": True,
                "playable_url": _public_output_url(relpath_from_outputs(path), path),
                "local_path": path,
                "source": "local",
            }

    if video_url:
        if video_url.startswith("/outputs/"):
            path = abspath_from_public(video_url)
            if os.path.exists(path):
                return {
                    "has_video": True,
                    "playable_url": _public_output_url(relpath_from_outputs(path), path),
                    "local_path": path,
                    "source": "local",
                }
            return {
                "has_video": True,
                "playable_url": video_url,
                "local_path": None,
                "source": "mounted",
            }
        if video_url.startswith("http"):
            return {
                "has_video": True,
                "playable_url": video_url,
                "local_path": None,
                "source": "remote",
            }

    return {
        "has_video": False,
        "playable_url": None,
        "local_path": None,
        "source": None,
    }


def _build_scene_cards(ep: Episode) -> list[Dict[str, Any]]:
    scenes = (ep.script or {}).get("scenes") or []
    by_id: Dict[int, Dict[str, Any]] = {}
    for sv in ep.scene_videos or []:
        try:
            by_id[int(sv.get("scene_id", 0))] = sv
        except (TypeError, ValueError):
            continue

    cards: list[Dict[str, Any]] = []
    for sc in scenes:
        try:
            sid = int(sc.get("scene_id", 0))
        except (TypeError, ValueError):
            continue
        sv = by_id.get(sid) or {}
        media = _resolve_scene_playable(ep, sid, sv)
        cards.append(
            {
                "scene_id": sid,
                "title": sc.get("title") or f"Scene {sid}",
                "time_range": sc.get("time_range") or "",
                "duration_sec": sc.get("duration_sec") or sv.get("duration_sec") or 15,
                "latency_sec": sv.get("latency_sec"),
                "vidu_mode": sv.get("vidu_mode"),
                **media,
            }
        )
    return cards


def _resolve_master_video(ep: Episode) -> Dict[str, Any]:
    candidates = []
    if ep.merged_video_url and str(ep.merged_video_url).startswith("/outputs/"):
        candidates.append(abspath_from_public(str(ep.merged_video_url)))
    if ep.video_url and str(ep.video_url).startswith("/outputs/"):
        candidates.append(abspath_from_public(str(ep.video_url)))
    candidates.extend(
        merged_file_candidates(
            ep.id, folder_name=_episode_folder(ep), title=ep.title
        )
    )

    for path in candidates:
        if path and os.path.exists(path):
            return {
                "has_video": True,
                "playable_url": _public_output_url(relpath_from_outputs(path), path),
                "merged": True,
            }

    for url in (ep.merged_video_url, ep.video_url):
        if url and str(url).startswith("http"):
            return {"has_video": True, "playable_url": url, "merged": bool(ep.scenes_merged)}

    return {"has_video": False, "playable_url": None, "merged": bool(ep.scenes_merged)}

STAGE_LABELS = {
    0: "Queue",
    1: "Concept",
    2: "Script",
    3: "Video",
    4: "Publish",
    5: "Seeding",
}

# Letter marks shown in the stepper (Q / C / S / V / P / E)
STAGE_MARKS = {
    0: "Q",
    1: "C",
    2: "S",
    3: "V",
    4: "P",
    5: "E",
}

# Gates not ready yet — shown in stepper but not clickable
DISABLED_STAGES = {4, 5}

FAMILY = [
    {"id": "gary", "name": "Gary", "age": 44, "role": "Father"},
    {"id": "linda", "name": "Linda", "age": 42, "role": "Mother"},
    {"id": "chris", "name": "Chris", "age": 15, "role": "Son"},
    {"id": "chloe", "name": "Chloe", "age": 11, "role": "Daughter"},
]

SCENE_BOUNDS = [
    {"id": 1, "start": 0, "label": "Scene 1"},
    {"id": 2, "start": 8, "label": "Scene 2"},
    {"id": 3, "start": 22, "label": "Scene 3"},
    {"id": 4, "start": 38, "label": "Scene 4"},
]


def _ensure_episode() -> Episode:
    ep = state_manager.get_active_episode()
    if not ep:
        ep = state_manager.create_episode("Episode 1: The HOA Violation", engine="vidu")
        ep.available_concepts = trend_ingest_agent.fetch_trending_concepts()
        state_manager.save()
    return ep


def _platform_status() -> Dict[str, Any]:
    vidu = ViduEngine()
    status = vidu.test_connection()
    return {
        "vidu_model": config.vidu_model,
        "vidu_reference_model": config.vidu_reference_model,
        "vidu_has_key": bool(config.vidu_api_key),
        "vidu_connected": bool(status.get("connected")),
        "vidu_authenticated": bool(status.get("authenticated")),
        "vidu_resolution": config.vidu_resolution,
        "vidu_email": config.vidu_email,
    }


def _selected_concept_index(ep: Episode) -> int:
    concepts = ep.available_concepts or []
    if not concepts:
        return 0
    if ep.selected_concept:
        for i, c in enumerate(concepts):
            if c.get("id") == ep.selected_concept.get("id") or c.get("title") == ep.selected_concept.get(
                "title"
            ):
                return i
    return 0


def _resolve_viewing_stage(ep: Episode, viewing_stage: Optional[int]) -> int:
    if viewing_stage is not None:
        stage = max(0, min(5, viewing_stage))
        if stage in DISABLED_STAGES:
            return 3
        return stage
    # Default landing: video queue (before Concept)
    return 0


def _sync_q4_scene_titles(ep: Episode) -> None:
    """Align live Q4 episode titles with catalog clip labels (one-time soft migrate)."""
    if (ep.script_key or "") != "hoa_q4_prompts" or not ep.script:
        return
    scenes = ep.script.get("scenes") or []
    if not scenes:
        return
    catalog_scenes = get_hoa_q4_prompt_episode().get("scenes") or []
    changed = False
    for sc, cat in zip(scenes, catalog_scenes):
        new_title = cat.get("title")
        if new_title and sc.get("title") != new_title:
            # Only rewrite legacy beat labels / missing titles.
            old = str(sc.get("title") or "")
            if old.startswith("Clip ") or old in {
                "Hook & Setup",
                "Conflict & Escalation",
                "The Crack / Breakdown",
                "Merch Punchline & Outro",
                "",
            }:
                sc["title"] = new_title
                changed = True
    if changed:
        state_manager.save()


def _script_scene_bundle(ep: Episode, script_scene: Optional[int]) -> Dict[str, Any]:
    _sync_q4_scene_titles(ep)
    scenes = (ep.script or {}).get("scenes") or []
    lines = (ep.script or {}).get("dialogue_lines") or []
    ids = [int(sc.get("scene_id", i + 1)) for i, sc in enumerate(scenes)]
    active = int(script_scene or (ids[0] if ids else 1))
    if ids and active not in ids:
        active = ids[0]
    active_scene = next((sc for sc in scenes if int(sc.get("scene_id", 0)) == active), None)
    scene_lines = [ln for ln in lines if int(ln.get("scene_id", 0)) == active]
    clip_ready = False
    for sv in ep.scene_videos or []:
        try:
            sid = int(sv.get("scene_id", 0))
        except (TypeError, ValueError):
            continue
        if sid == active and (sv.get("video_url") or sv.get("local_path")):
            clip_ready = True
            break
    return {
        "script_scene": active,
        "script_scene_ids": ids,
        "active_script_scene": active_scene,
        "active_script_lines": scene_lines,
        "active_script_clip_ready": clip_ready,
    }


def _scene_bounds_for_ep(ep: Episode) -> list:
    scenes = (ep.script or {}).get("scenes") or []
    if not scenes:
        return SCENE_BOUNDS
    bounds = []
    for sc in scenes:
        title = str(sc.get("title") or f"Scene {sc.get('scene_id')}")
        # Prefer "Clip 1" / first two tokens so Q4 titles stay readable in tabs.
        parts = title.split()
        label = " ".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else f"S{sc.get('scene_id')}")
        bounds.append(
            {
                "id": int(sc.get("scene_id", len(bounds) + 1)),
                "start": int(sc.get("time_start_sec", 0)),
                "label": label,
            }
        )
    return bounds


def _related_episodes_for_item(item: Dict[str, Any]) -> list[Episode]:
    catalog_id = item.get("id")
    script_key = item.get("script_key")
    related = []
    for ep in state_manager.episodes.values():
        if catalog_id and ep.catalog_id == catalog_id:
            related.append(ep)
        elif script_key and ep.script_key == script_key:
            related.append(ep)
    return related


def _episode_has_local_renders(ep: Episode) -> bool:
    folder = getattr(ep, "output_folder", None)
    title = getattr(ep, "title", None)
    if find_existing(merged_file_candidates(ep.id, folder_name=folder, title=title)):
        return True
    for sid in range(1, 5):
        if find_existing(scene_file_candidates(ep.id, sid, folder_name=folder, title=title)):
            return True
    if ep.merged_video_url or ep.scenes_merged or (ep.scene_videos or []):
        for sv in ep.scene_videos or []:
            path = (sv or {}).get("local_path") or ""
            if path and os.path.exists(path):
                return True
        if ep.merged_video_url and str(ep.merged_video_url).startswith("/outputs/"):
            path = abspath_from_public(str(ep.merged_video_url))
            if os.path.exists(path):
                return True
    return False


def _episode_render_score(ep: Episode) -> float:
    score = 0.0
    folder = getattr(ep, "output_folder", None)
    title = getattr(ep, "title", None)
    if find_existing(merged_file_candidates(ep.id, folder_name=folder, title=title)):
        score += 200
    if ep.scenes_merged or ep.merged_video_url:
        score += 100
    score += len(ep.scene_videos or []) * 10
    for sid in range(1, 5):
        if find_existing(scene_file_candidates(ep.id, sid, folder_name=folder, title=title)):
            score += 15
    # Prefer mid-pipeline progress (script approved) over a fresh Gate 1 shell.
    if ep.script:
        score += 50
    score += max(0, int(ep.current_gateway or 1) - 1) * 5
    score += (getattr(ep, "updated_at", 0) or 0) / 1e12
    return score


def _pick_best_related_episode(related: list[Episode]) -> Optional[Episode]:
    if not related:
        return None
    return max(related, key=_episode_render_score)


def _attach_local_renders(ep: Episode) -> bool:
    """If scene/master files exist for this episode id, reflect them on the episode."""
    changed = False
    scene_videos = list(ep.scene_videos or [])
    by_id = {}
    for sv in scene_videos:
        try:
            by_id[int(sv.get("scene_id", 0))] = dict(sv)
        except (TypeError, ValueError):
            continue

    folder = getattr(ep, "output_folder", None) or ensure_episode_output_folder(ep)
    for sid in range(1, 5):
        path = find_existing(
            scene_file_candidates(ep.id, sid, folder_name=folder, title=ep.title)
        )
        if not path:
            continue
        rel = relpath_from_outputs(path)
        existing = by_id.get(sid) or {"scene_id": sid}
        if existing.get("local_path") != path or existing.get("status") != "completed":
            existing.update(
                {
                    "scene_id": sid,
                    "local_path": path,
                    "video_url": public_url(rel),
                    "status": "completed",
                }
            )
            by_id[sid] = existing
            changed = True

    if by_id:
        scene_videos = [by_id[k] for k in sorted(by_id)]
        if scene_videos != (ep.scene_videos or []):
            ep.scene_videos = scene_videos
            changed = True

    merged = find_existing(
        merged_file_candidates(ep.id, folder_name=folder, title=ep.title)
    )
    if merged:
        url = public_url(relpath_from_outputs(merged))
        if ep.merged_video_url != url or not ep.scenes_merged:
            ep.merged_video_url = url
            ep.video_url = url
            ep.scenes_merged = True
            changed = True
    return changed


def _hydrate_renders_from_siblings(ep: Episode) -> bool:
    """Copy playable scene/master refs from a sibling episode that already rendered."""
    _attach_local_renders(ep)
    if _episode_has_local_renders(ep) and (ep.scene_videos or ep.merged_video_url):
        return False

    siblings = [
        other
        for other in state_manager.episodes.values()
        if other.id != ep.id
        and (
            (ep.catalog_id and other.catalog_id == ep.catalog_id)
            or (ep.script_key and other.script_key == ep.script_key)
        )
    ]
    donor = _pick_best_related_episode(siblings)
    if not donor or _episode_render_score(donor) < 10:
        return False

    _attach_local_renders(donor)
    if not (donor.scene_videos or donor.merged_video_url):
        return False

    ep.scene_videos = list(donor.scene_videos or [])
    ep.merged_video_url = donor.merged_video_url
    ep.video_url = donor.video_url or donor.merged_video_url
    ep.scenes_merged = bool(donor.scenes_merged or donor.merged_video_url)
    if donor.script and not ep.script:
        ep.script = donor.script
        ep.merch_punchline = donor.merch_punchline or ep.merch_punchline
    return True


def _catalog_cards() -> list:
    cards = []
    for index, item in enumerate(list_catalog_items(), start=1):
        related = _related_episodes_for_item(item)
        latest = _pick_best_related_episode(related)
        if latest:
            _attach_local_renders(latest)
        cards.append(
            {
                **item,
                "list_number": index,
                "episode": latest,
                "episode_status": (latest.status.replace("_", " ").title() if latest else "Not started"),
                "gateway": latest.current_gateway if latest else None,
                "has_master": bool(
                    latest
                    and (
                        latest.merged_video_url
                        or latest.scenes_merged
                        or _episode_has_local_renders(latest)
                    )
                ),
            }
        )
    # Newer catalog entries first (highest number on top).
    cards.sort(key=lambda c: int(c.get("list_number") or 0), reverse=True)
    return cards


def build_context(
    request: Request,
    viewing_stage: Optional[int] = None,
    *,
    toast: Optional[str] = None,
    toast_kind: str = "info",
    char_id: str = "gary",
    script_scene: Optional[int] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    ep = _ensure_episode()
    # Re-link local / sibling renders so Video stage can show already-generated clips.
    if _attach_local_renders(ep) or _hydrate_renders_from_siblings(ep):
        state_manager.save()
    stage = _resolve_viewing_stage(ep, viewing_stage)
    # Keep Concept cards in sync with catalog copy (longer premises, etc.).
    if stage == 1 and ep.catalog_id:
        fresh = concepts_for_catalog(str(ep.catalog_id))
        if fresh:
            ep.available_concepts = fresh
            if not ep.selected_concept or is_empty_concept(ep.selected_concept):
                ep.selected_concept = next((c for c in fresh if not is_empty_concept(c)), ep.selected_concept)
            state_manager.save()
    completed = (ep.current_gateway or 1) >= 6 or (ep.status or "").upper() == "COMPLETED"
    show_completed = completed and viewing_stage is None

    char_id = (char_id or "gary").lower()
    if char_id not in CHARACTERS:
        char_id = "gary"

    ctx = {
        "request": request,
        "ep": ep,
        "viewing_stage": stage,
        "show_completed": show_completed,
        "stage_labels": STAGE_LABELS,
        "stage_marks": STAGE_MARKS,
        "disabled_stages": DISABLED_STAGES,
        "family": FAMILY,
        "scene_bounds": _scene_bounds_for_ep(ep),
        "platform": _platform_status(),
        "selected_concept_index": _selected_concept_index(ep),
        "active_char": char_id,
        "active_char_meta": CHARACTERS.get(char_id, {}),
        "toast": error or toast,
        "toast_kind": "error" if error else toast_kind,
        "scene_cards": _build_scene_cards(ep),
        "master_video": _resolve_master_video(ep),
        "catalog_cards": _catalog_cards(),
        "page": "studio",
        # Always define Gate 2 tab vars before bundle merge (avoids Jinja UndefinedError)
        "script_scene": 1,
        "script_scene_ids": [],
        "active_script_scene": None,
        "active_script_lines": [],
        "active_script_clip_ready": False,
    }
    ctx.update(_script_scene_bundle(ep, script_scene))
    return ctx


def render(
    request: Request,
    template_name: str,
    viewing_stage: Optional[int] = None,
    **kwargs: Any,
) -> HTMLResponse:
    ctx = build_context(request, viewing_stage, **kwargs)
    # Starlette 1.x: TemplateResponse(request, name, context)
    # Pass a plain dict copy so every template key is present.
    return templates.TemplateResponse(request, template_name, dict(ctx))


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def ui_home(request: Request, stage: Optional[int] = None):
    """Studio landing — video queue (stage 0) sits before Concept."""
    return render(request, "studio.html", viewing_stage=0 if stage is None else stage)


@router.get("/studio", response_class=HTMLResponse)
def ui_studio(request: Request, stage: Optional[int] = None):
    return render(request, "studio.html", viewing_stage=0 if stage is None else stage)


def _apply_catalog_concepts(ep: Episode, catalog_id: str) -> None:
    concepts = concepts_for_catalog(catalog_id)
    ep.available_concepts = concepts
    real = next((c for c in concepts if not is_empty_concept(c)), None)
    ep.selected_concept = real
    if real and real.get("script_key"):
        ep.script_key = str(real["script_key"])


def _activate_catalog_item(item: Dict[str, Any]) -> Episode:
    catalog_id = str(item["id"])
    related = _related_episodes_for_item(item)
    ep = _pick_best_related_episode(related)
    if ep:
        state_manager.set_active(ep.id)
        ep.catalog_id = catalog_id
        ep.script_key = str(item.get("script_key") or catalog_id)
        # Keep the catalog title unless this episode already has renders under another name.
        if not _episode_has_local_renders(ep):
            ep.title = str(item.get("title") or ep.title)
        elif not ep.title:
            ep.title = str(item.get("title") or ep.title)
        # Refresh concept cards, but do not rewind an already-approved episode.
        already_past_gate1 = bool(ep.script) or int(ep.current_gateway or 1) >= 2
        if not already_past_gate1:
            _apply_catalog_concepts(ep, catalog_id)
        else:
            # Keep concept list fresh for UI, preserve selected_concept + script progress.
            concepts = concepts_for_catalog(catalog_id)
            if concepts:
                ep.available_concepts = concepts
        _hydrate_renders_from_siblings(ep)
        state_manager.save()
        orchestrator.log(ep.id, f"Selected queue video '{item.get('title')}'.")
        return ep

    ep = state_manager.create_episode(
        title=str(item.get("title") or "Untitled video"),
        engine="vidu",
        catalog_id=catalog_id,
        script_key=str(item.get("script_key") or catalog_id),
    )
    _apply_catalog_concepts(ep, catalog_id)
    state_manager.save()
    orchestrator.log(ep.id, f"Selected queue video '{item.get('title')}' → Gate 1.")
    return ep


def _activate_catalog_video(catalog_id: str) -> Episode:
    item = get_catalog_item(catalog_id)
    if not item:
        raise HTTPException(status_code=404, detail="Video not found in catalog")
    return _activate_catalog_item(item)


def _stage_for_selected_episode(ep: Episode) -> int:
    gw = int(ep.current_gateway or 1)
    if gw >= 6:
        return 3
    stage = max(1, min(3, gw))
    return stage


@router.post("/ui/queue/add", response_class=HTMLResponse)
@router.post("/ui/catalog/add", response_class=HTMLResponse)
def ui_add_catalog_video(
    request: Request,
    title: str = Form(""),
    subtitle: str = Form(""),
):
    """Manually add a video to the queue (newest on top)."""
    if not (title or "").strip():
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=0,
            error="Title is required to add a video.",
        )
    try:
        item = add_manual_catalog_video(title=title, subtitle=subtitle)
        ep = _activate_catalog_item(item)
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=0,
            error=f"Could not add video: {exc}",
        )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
        toast=f"Added · {ep.title}",
        toast_kind="ok",
    )


@router.post("/ui/queue/{catalog_id}/delete", response_class=HTMLResponse)
@router.post("/ui/catalog/{catalog_id}/delete", response_class=HTMLResponse)
def ui_delete_catalog_video(request: Request, catalog_id: str):
    """Delete a manually added queue video (built-ins are protected)."""
    item = get_catalog_item(catalog_id)
    if not item:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=0,
            error="Video not found.",
        )
    if not item.get("custom"):
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=0,
            error="Built-in videos cannot be deleted.",
        )

    delete_manual_catalog_video(catalog_id)
    for ep_id, ep in list(state_manager.episodes.items()):
        if ep.catalog_id == catalog_id:
            del state_manager.episodes[ep_id]
            if state_manager.active_episode_id == ep_id:
                state_manager.active_episode_id = None

    if not state_manager.get_active_episode() and state_manager.episodes:
        state_manager.active_episode_id = next(iter(state_manager.episodes))
    state_manager.save()
    _ensure_episode()

    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
        toast=f"Deleted · {item.get('title') or catalog_id}",
        toast_kind="ok",
    )


@router.post("/ui/catalog/{catalog_id}/select", response_class=HTMLResponse)
def ui_select_catalog_video(request: Request, catalog_id: str):
    """Row click: select only — stay on the Queue."""
    ep = _activate_catalog_video(catalog_id)
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
        toast=f"Selected · {ep.title}",
        toast_kind="ok",
    )


@router.post("/ui/catalog/{catalog_id}/open", response_class=HTMLResponse)
@router.post("/ui/catalog/{catalog_id}/gate1", response_class=HTMLResponse)
def ui_open_catalog_video(request: Request, catalog_id: str):
    """Open catalog video and resume at the furthest approved stage."""
    ep = _activate_catalog_video(catalog_id)
    stage = _stage_for_selected_episode(ep)
    gate_label = {1: "Concept", 2: "Script", 3: "Video"}.get(stage, f"Stage {stage}")
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=stage,
        toast=f"{gate_label} · {ep.title}",
        toast_kind="ok",
    )


@router.get("/ui/workspace", response_class=HTMLResponse)
def ui_workspace(request: Request, stage: Optional[int] = None, char: str = "gary"):
    return render(request, "partials/htmx_workspace.html", viewing_stage=stage, char_id=char)


@router.get("/ui/stage/{stage_num}", response_class=HTMLResponse)
def ui_stage(
    request: Request,
    stage_num: int,
    char: str = "gary",
    scene: Optional[int] = None,
):
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=stage_num,
        char_id=char,
        script_scene=scene,
    )


@router.get("/ui/script/scene/{scene_id}", response_class=HTMLResponse)
def ui_script_scene(request: Request, scene_id: int):
    """Gate 2: swap only the active scene panel + tab strip."""
    return render(
        request,
        "partials/script_scene_block.html",
        viewing_stage=2,
        script_scene=scene_id,
    )


@router.post("/ui/script/scene/{scene_id}/generate", response_class=HTMLResponse)
def ui_generate_script_scene_clip(request: Request, scene_id: int):
    """Generate a single Vidu clip for the active script scene, then open Video stage."""
    from app.main import generate_single_scene

    ep = _ensure_episode()
    if not ep.script or not (ep.script.get("scenes") or []):
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=2,
            script_scene=scene_id,
            error="No script loaded. Approve a concept first.",
        )

    try:
        generate_single_scene({"scene_id": scene_id})
    except HTTPException as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=2,
            script_scene=scene_id,
            error=str(exc.detail),
        )
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=2,
            script_scene=scene_id,
            error=str(exc),
        )

    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        script_scene=scene_id,
        toast=f"Scene {scene_id} clip ready",
        toast_kind="ok",
    )


@router.post("/ui/script/scene/{scene_id}/save", response_class=HTMLResponse)
def ui_save_script_scene(
    request: Request,
    scene_id: int,
    source_prompt: str = Form(""),
):
    """Persist editable scene prompt (autosave or Save). Full prompt is stored as written."""
    ep = _ensure_episode()
    scenes = (ep.script or {}).get("scenes") or []
    scene = next((sc for sc in scenes if int(sc.get("scene_id", 0)) == scene_id), None)
    if not scene:
        return HTMLResponse('<span class="badge badge-warn">Scene not found</span>', status_code=404)

    scene["source_prompt"] = source_prompt
    scene["vidu_prompt"] = source_prompt

    fname = scene.get("source_prompt_file")
    if fname:
        path = prompt_file_path(str(fname))
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(source_prompt)
            refresh_hoa_q4_prompt_episode()
        except OSError:
            pass

    if ep.catalog_id and str(ep.catalog_id).startswith("custom_"):
        update_custom_scene_prompt(str(ep.catalog_id), scene_id, source_prompt)

    state_manager.save()
    orchestrator.log(ep.id, f"Script scene {scene_id} prompt updated ({len(source_prompt)} chars).")

    # Autosave targets status chip only — char badge updates live in the browser.
    hx_target = (request.headers.get("hx-target") or "").lstrip("#")
    if hx_target == "script-save-status":
        return HTMLResponse("Saved")

    return render(
        request,
        "partials/script_scene_block.html",
        viewing_stage=2,
        script_scene=scene_id,
        toast="Scene saved",
        toast_kind="ok",
    )


@router.get("/ui/character/{char_id}", response_class=HTMLResponse)
def ui_character(request: Request, char_id: str):
    return render(request, "partials/character_panel.html", viewing_stage=3, char_id=char_id)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


@router.post("/ui/episode/reset", response_class=HTMLResponse)
def ui_reset_episode(request: Request):
    """Return to the video queue (stage 0)."""
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
        toast="Back to video queue",
        toast_kind="ok",
    )


@router.post("/ui/concepts/refresh", response_class=HTMLResponse)
def ui_refresh_concepts(request: Request):
    ep = _ensure_episode()
    ep.available_concepts = trend_ingest_agent.fetch_trending_concepts()
    titles = [str(c.get("title") or "") for c in (ep.available_concepts or [])[:3]]
    hooks = []
    for c in (ep.available_concepts or [])[:3]:
        trends = c.get("source_trends") or []
        if trends:
            hooks.append(str(trends[0]))
    detail = ", ".join(titles) if titles else "3 concepts"
    orchestrator.log(
        ep.id,
        f"Agent 0 ingested 3 new trending cultural topics: {detail}"
        + (f" (signals: {', '.join(hooks[:3])})" if hooks else ""),
    )
    state_manager.save()
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=1,
        toast="Concepts refreshed",
        toast_kind="ok",
    )


@router.post("/ui/concepts/select", response_class=HTMLResponse)
def ui_select_concept(request: Request, index: int = Form(...)):
    ep = _ensure_episode()
    concepts = ep.available_concepts or []
    if index < 0 or index >= len(concepts):
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=1,
            error="Invalid concept selection",
        )
    chosen = concepts[index]
    if is_empty_concept(chosen):
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=1,
            error="That concept slot is empty",
        )
    ep.selected_concept = chosen
    if chosen.get("script_key"):
        ep.script_key = str(chosen["script_key"])
    state_manager.save()
    return render(request, "partials/htmx_workspace.html", viewing_stage=1)


@router.post("/ui/gateway/1/approve", response_class=HTMLResponse)
def ui_approve_gateway_1(request: Request):
    ep = _ensure_episode()
    concepts = ep.available_concepts or []
    selected = ep.selected_concept
    if is_empty_concept(selected):
        selected = next((c for c in concepts if not is_empty_concept(c)), None)
    if not selected:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=1,
            error="Select a concept first",
        )

    try:
        orchestrator.approve_gateway(ep.id, 1, {"selected_concept": selected})
        script_key = selected.get("script_key") or ep.script_key or "hoa_violation"
        ep.script_key = script_key
        orchestrator.log(ep.id, f"Agent 1 loading script package '{script_key}'...")
        script_data = scriptwriter_agent.generate_script(ep.selected_concept)
        passed, qa_msg = orchestrator.validate_script_qa(script_data)
        orchestrator.log(ep.id, qa_msg)
        if not passed:
            raise HTTPException(status_code=422, detail=qa_msg)
        ep.script = script_data
        ep.merch_punchline = script_data.get("merch_punchline_trigger")
        ep.status = "WAITING_GATEWAY_2"
        ep.current_gateway = 2
        state_manager.save()
    except HTTPException as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=1,
            error=str(exc.detail),
        )
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=1,
            error=str(exc),
        )

    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=2,
        toast="Concept approved · script ready",
        toast_kind="ok",
    )


@router.post("/ui/merch/update", response_class=HTMLResponse)
def ui_update_merch(request: Request, punchline: str = Form(...)):
    ep = _ensure_episode()
    cleaned = punchline.strip()
    if cleaned:
        ep.merch_punchline = cleaned
        if ep.script:
            ep.script["merch_punchline_trigger"] = cleaned
        state_manager.save()
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=2,
        toast="Merch line updated",
        toast_kind="ok",
    )


@router.post("/ui/gateway/2/approve", response_class=HTMLResponse)
def ui_approve_gateway_2(request: Request):
    from app.main import merge_episode_scenes, render_all_episode_scenes

    ep = _ensure_episode()
    try:
        orchestrator.approve_gateway(ep.id, 2, {"script": ep.script})
        # Keep SCRIPT_APPROVED visible after Generate Video (do not overwrite with WAITING_GATEWAY_3).
        ep.status = "SCRIPT_APPROVED"
        ep.current_gateway = 3
        state_manager.save()
        orchestrator.log(ep.id, "Gateway 2 approved: generating 4 Vidu scenes...")
        render_all_episode_scenes(ep)
        merge_episode_scenes(ep)
        ep.video_engine_used = f"Vidu AI ({config.vidu_model} / {config.vidu_reference_model})"
        ep.native_audio_enabled = True
        ep.selected_engine = "vidu"
        ep.status = "SCRIPT_APPROVED"
        ep.current_gateway = 3
        state_manager.save()
    except HTTPException as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=2,
            error=str(exc.detail),
        )
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=2,
            error=str(exc),
        )

    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast="Video generated · scenes ready",
        toast_kind="ok",
    )


@router.post("/ui/video/generate-all", response_class=HTMLResponse)
def ui_generate_all_scenes(request: Request):
    from app.main import render_all_episode_scenes

    ep = _ensure_episode()
    try:
        render_all_episode_scenes(ep)
    except HTTPException as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error=str(exc.detail),
        )
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error=str(exc),
        )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast="All scenes generated",
        toast_kind="ok",
    )


@router.post("/ui/video/generate-scene/{scene_id}", response_class=HTMLResponse)
def ui_generate_scene(request: Request, scene_id: int):
    from app.main import generate_single_scene

    try:
        generate_single_scene({"scene_id": scene_id})
    except HTTPException as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error=str(exc.detail),
        )
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error=str(exc),
        )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast=f"Scene {scene_id} regenerated",
        toast_kind="ok",
    )


@router.post("/ui/video/merge", response_class=HTMLResponse)
def ui_merge_scenes(request: Request):
    from app.main import merge_episode_scenes

    ep = _ensure_episode()
    try:
        merge_res = merge_episode_scenes(ep)
        if not merge_res.get("success"):
            raise HTTPException(status_code=500, detail=merge_res.get("error") or "Merge failed")
    except HTTPException as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error=str(exc.detail),
        )
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error=str(exc),
        )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast="Master cut merged",
        toast_kind="ok",
    )


@router.post("/ui/video/lock-vidu", response_class=HTMLResponse)
def ui_lock_vidu(request: Request):
    ep = _ensure_episode()
    ep.selected_engine = "vidu"
    ep.final_platform_decision = "vidu"
    state_manager.log_qa(ep.id, "Production platform locked: Vidu Q4 Preview API.")
    state_manager.save()
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast="Vidu confirmed",
        toast_kind="ok",
    )


@router.post("/ui/video/import", response_class=HTMLResponse)
async def ui_import_video(
    request: Request,
    file: UploadFile = File(...),
):
    from app.main import import_video_file

    try:
        await import_video_file(file=file, platform_source="Vidu Q4 Preview")
    except HTTPException as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error=str(exc.detail),
        )
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error=str(exc),
        )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast="Video imported",
        toast_kind="ok",
    )


@router.post("/ui/gateway/3/approve", response_class=HTMLResponse)
def ui_approve_gateway_3(request: Request):
    ep = _ensure_episode()
    try:
        orchestrator.approve_gateway(ep.id, 3, {"video_url": ep.video_url or ep.merged_video_url})
        orchestrator.log(ep.id, "Agent 4 preparing social metadata and merch mockup...")
        deploy_result = publisher_agent.prepare_deployment(
            episode_id=ep.id,
            episode_title=ep.title,
            merch_punchline=ep.merch_punchline or "Capitalism Broke My Dad",
        )
        ep.social_posts = deploy_result.get("social", {})
        ep.merch_listing = deploy_result.get("merch", {})
        ep.merch_mockup_url = deploy_result.get("mockup_url")
        ep.status = "WAITING_GATEWAY_4"
        ep.current_gateway = 4
        state_manager.save()
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error=str(exc),
        )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=4,
        toast="Video approved",
        toast_kind="ok",
    )


@router.post("/ui/gateway/4/approve", response_class=HTMLResponse)
def ui_approve_gateway_4(request: Request):
    ep = _ensure_episode()
    try:
        orchestrator.approve_gateway(ep.id, 4, {"social": ep.social_posts, "merch": ep.merch_listing})
        orchestrator.log(ep.id, "Agent 5 drafting community seeding responses...")
        seeding_campaign = seeder_agent.generate_seeding_campaign(
            episode_title=ep.title,
            merch_punchline=ep.merch_punchline or "Capitalism Broke My Dad",
        )
        ep.seeding_drafts = seeding_campaign
        ep.status = "WAITING_GATEWAY_5"
        ep.current_gateway = 5
        state_manager.save()
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=4,
            error=str(exc),
        )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=5,
        toast="Publish package approved",
        toast_kind="ok",
    )


@router.post("/ui/gateway/5/approve", response_class=HTMLResponse)
def ui_approve_gateway_5(request: Request):
    ep = _ensure_episode()
    try:
        orchestrator.approve_gateway(ep.id, 5, {"seeding": ep.seeding_drafts})
        ep.status = "COMPLETED"
        ep.current_gateway = 6
        state_manager.save()
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=5,
            error=str(exc),
        )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=5,
        toast="Episode complete",
        toast_kind="ok",
    )

