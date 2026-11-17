"""
Jinja + HTMX UI helpers and routes for the Crash Out HITL hub.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("app.ui")

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
    update_catalog_concept,
    update_custom_scene_prompt,
)
from app.config import CHARACTERS, config
from app.studio.characters import (
    format_speed_hint,
    get_character,
    list_characters,
    normalize_pitch_hint,
    save_character_audio,
    save_character_image,
    update_character,
)
from app.studio.audio import (
    sync_dialogue_timing_from_script,
    update_dialogue_timing_row,
    voice_library_snapshot,
)
from app.studio.export import export_16x9_letterbox, export_episode_zip, list_downloadable_assets
from app.studio.generation import (
    PRODUCTION_STATUSES,
    add_revision_note,
    cost_summary,
    find_job,
    list_final_episodes_sorted,
    mark_episode_final,
    restore_clip_version,
    restore_script_version,
    save_script_version,
    studio_dashboard_snapshot,
    set_production_status,
    update_job,
)
from app.studio.prompt_library import combine_prompt, list_templates, upsert_template
from app.studio.qa import ensure_qa, extract_last_frame, update_qa
from app.studio.worker import enqueue_background, list_notifications, mark_notifications_read
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
from app.auth_middleware import get_current_user
from app.state import Episode, state_manager

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
STATIC_CSS_PATH = os.path.join(os.path.dirname(__file__), "static", "css", "app.css")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def _static_cache_bust() -> str:
    try:
        return str(int(os.path.getmtime(STATIC_CSS_PATH)))
    except OSError:
        return "1"


templates.env.globals["static_cache_bust"] = _static_cache_bust

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
    if scenes:
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
    else:
        # Record / legacy episodes may have renders without a script package.
        for sid in sorted(by_id.keys()) or [1, 2, 3, 4]:
            sv = by_id.get(sid) or {}
            media = _resolve_scene_playable(ep, sid, sv)
            cards.append(
                {
                    "scene_id": sid,
                    "title": sv.get("title") or f"Scene {sid}",
                    "time_range": sv.get("time_range") or "",
                    "duration_sec": sv.get("duration_sec") or 15,
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
    1: "Pitch",
    2: "Script",
    3: "Video",
    4: "Publish",
    5: "Seeding",
}

# Letter marks shown in the stepper (Q / P / S / V / Pb / E)
STAGE_MARKS = {
    0: "Q",
    1: "P",
    2: "S",
    3: "V",
    4: "Pb",
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
        from app.engines.factory import video_engine_mode

        ep = state_manager.create_episode(
            "Episode 1: The HOA Violation", engine=video_engine_mode()
        )
        ep.available_concepts = trend_ingest_agent.fetch_trending_concepts()
        state_manager.save()
    return ep


def _platform_status() -> Dict[str, Any]:
    from app.engines.factory import engine_display_name, get_video_engine, video_engine_mode

    engine = get_video_engine()
    status = engine.test_connection()
    return {
        "video_engine": video_engine_mode(),
        "engine_name": engine_display_name(),
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
    # Default landing: video queue (before Pitch)
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
        display_title = (
            latest.title
            if latest and (latest.title or "").strip()
            else str(item.get("title") or "Untitled")
        )
        cards.append(
            {
                **item,
                "title": display_title,
                "list_number": index,
                "episode": latest,
                "episode_status": (latest.status.replace("_", " ").title() if latest else "Not started"),
                "gateway": latest.current_gateway if latest else None,
            }
        )
    # Newer catalog entries first (highest number on top).
    cards.sort(key=lambda c: int(c.get("list_number") or 0), reverse=True)
    return cards


def _studio_queue_cards() -> list:
    """Studio queue only: in-progress catalog rows + orphan studio episodes (never published)."""
    from app.studio.generation import is_final_episode, normalize_production_status

    def _published(ep: Optional[Episode]) -> bool:
        if not ep:
            return False
        if normalize_production_status(getattr(ep, "production_status", None)) == "published":
            return True
        return is_final_episode(ep)

    cards: list = []
    seen_ep_ids: set[str] = set()
    for card in _catalog_cards():
        ep = card.get("episode")
        if _published(ep):
            continue
        cards.append(card)
        if ep:
            seen_ep_ids.add(ep.id)

    # Draft / scripting / generating episodes that are not represented by a catalog row.
    extras: list = []
    for ep in state_manager.list_episodes_sorted():
        if ep.id in seen_ep_ids or _published(ep):
            continue
        prod = normalize_production_status(getattr(ep, "production_status", None))
        extras.append(
            {
                "id": ep.catalog_id or ep.id,
                "title": ep.title,
                "subtitle": "In studio",
                "duration_label": "—",
                "list_number": int(ep.episode_number or 0),
                "episode": ep,
                "episode_status": (prod or "draft").replace("_", " ").title(),
                "gateway": ep.current_gateway,
                "custom": bool(ep.catalog_id and str(ep.catalog_id).startswith("custom_")),
            }
        )
    extras.sort(key=lambda c: int(c.get("list_number") or 0), reverse=True)
    return cards + extras


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
    stage = _resolve_viewing_stage(ep, viewing_stage)
    # Queue selection must stay light — only hydrate when entering pipeline stages.
    if stage != 0:
        if _attach_local_renders(ep) or _hydrate_renders_from_siblings(ep):
            state_manager.save()
    # Load Gate 1 cards once; edits are owned by the episode (Refresh replaces them).
    if stage == 1 and ep.catalog_id and not (ep.available_concepts or []):
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
        "user": get_current_user(request),
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
        "catalog_cards": _studio_queue_cards(),
        "page": "studio",
        "episode_list": state_manager.list_episodes_sorted(),
        "production_statuses": list(PRODUCTION_STATUSES),
        "generation_jobs": list(reversed(ep.generation_jobs or []))[:20],
        "revision_notes": list(reversed(list(ep.revision_notes or [])))[:20],
        "clip_history": ep.clip_history or {},
        "library_characters": list_characters(),
        "script_versions": list(reversed(ep.script_versions or []))[:20],
        "prompt_templates": list_templates(),
        "cost_summary": cost_summary(ep),
        "export_assets": list_downloadable_assets(ep),
        "voice_library": voice_library_snapshot(),
        "dialogue_timing": ep.dialogue_timing or [],
        "notifications": list_notifications(unread_only=True),
        "qa_scene": ensure_qa(ep, script_scene or 1),
        "continuity_frames": ep.continuity_frames or {},
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
    response = templates.TemplateResponse(request, template_name, dict(ctx))
    # Keep /studio?stage=N[&scene=] in the address bar so hard refresh resumes here.
    push_templates = {
        "partials/htmx_workspace.html",
        "partials/script_scene_block.html",
    }
    if viewing_stage is not None and template_name in push_templates:
        scene = kwargs.get("script_scene")
        if scene is None and int(viewing_stage) == 2:
            scene = ctx.get("script_scene")
        response.headers["HX-Push-Url"] = _studio_push_url(int(viewing_stage), scene)
    return response


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def _shell_context(request: Request, page: str, **extra: Any) -> Dict[str, Any]:
    """Shared chrome context for non-pipeline pages (nav, toast, engine badge)."""
    ctx = {
        "request": request,
        "user": get_current_user(request),
        "page": page,
        "platform": _platform_status(),
        "toast": extra.pop("toast", None),
        "toast_kind": extra.pop("toast_kind", "info"),
        "viewing_stage": extra.pop("viewing_stage", 0),
        # Safe defaults so base/partials never hit UndefinedError
        "revision_notes": [],
        "production_statuses": PRODUCTION_STATUSES,
        "library_characters": [],
        "episode_list": [],
    }
    ctx.update(extra)
    return ctx


@router.get("/", response_class=HTMLResponse)
def ui_home(request: Request):
    """Production dashboard — overview of pipeline health and recent work."""
    from app.catalog import list_catalog_items

    snap = studio_dashboard_snapshot()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _shell_context(
            request,
            "dashboard",
            dashboard=snap,
            catalog_count=len(_studio_queue_cards()),
            catalog_cards=_studio_queue_cards()[:8],
        ),
    )


def _select_top_queue_item() -> Optional[Episode]:
    """Select the first (top) Studio queue row so Queue always has an active video."""
    cards = _studio_queue_cards()
    if not cards:
        return None
    top = cards[0]
    ep = top.get("episode")
    if ep is not None and getattr(ep, "id", None):
        selected = state_manager.set_active(ep.id)
        if selected:
            return selected
    item_id = str(top.get("id") or "").strip()
    if not item_id:
        return None
    try:
        return _select_queue_item(item_id)
    except HTTPException:
        return None


def _remember_studio_ui(
    ep: Episode,
    stage: Optional[int],
    scene: Optional[int] = None,
    *,
    persist: bool = True,
) -> None:
    """Persist last Studio stage/scene so hard refresh can restore it."""
    if stage is None:
        return
    ep.studio_ui_stage = int(stage)
    if scene is not None:
        ep.studio_ui_scene = int(scene)
    ep.updated_at = time.time()
    if persist:
        state_manager.save()


def _studio_push_url(stage: int, scene: Optional[int] = None) -> str:
    url = f"/studio?stage={int(stage)}"
    if int(stage) == 2 and scene is not None:
        url += f"&scene={int(scene)}"
    return url


@router.get("/studio", response_class=HTMLResponse)
def ui_studio(
    request: Request,
    stage: Optional[int] = None,
    scene: Optional[int] = None,
    episode: Optional[str] = None,
    catalog: Optional[str] = None,
):
    """HITL production studio.

    Bare ``/studio`` (nav / other pages) always opens Queue with the top video
    selected. Pass ``stage=`` to keep a pipeline tab on hard refresh.
    ``episode`` / ``catalog`` selects that queue item (still Queue unless
    ``stage`` is also provided).
    """
    queue_select = False
    if episode:
        if not state_manager.set_active(episode):
            raise HTTPException(status_code=404, detail="Episode not found")
        queue_select = True
    elif catalog:
        _select_queue_item(catalog)
        queue_select = True

    # Coming from another page / bare Studio link → Queue + top row selected.
    if stage is None:
        stage = 0
        if not queue_select:
            _select_top_queue_item()
            queue_select = True
    elif stage == 0 and not queue_select:
        _select_top_queue_item()
        queue_select = True

    ep = state_manager.get_active_episode()

    if scene is None and stage == 2 and ep and getattr(ep, "studio_ui_scene", None):
        scene = int(ep.studio_ui_scene)

    if ep:
        _remember_studio_ui(ep, stage, scene if stage == 2 else None)

    return render(request, "studio.html", viewing_stage=stage, script_scene=scene)


@router.get("/queue", response_class=HTMLResponse)
def ui_queue_redirect(request: Request):
    """Legacy URL — Queue was renamed to Studio."""
    return RedirectResponse(url="/studio?stage=0", status_code=303)


def _apply_catalog_concepts(ep: Episode, catalog_id: str) -> None:
    concepts = concepts_for_catalog(catalog_id)
    ep.available_concepts = concepts
    real = next((c for c in concepts if not is_empty_concept(c)), None)
    ep.selected_concept = real
    if real and real.get("script_key"):
        ep.script_key = str(real["script_key"])


def _activate_catalog_item(item: Dict[str, Any]) -> Episode:
    from app.studio.naming import make_studio_episode_name

    catalog_id = str(item["id"])
    related = _related_episodes_for_item(item)
    ep = _pick_best_related_episode(related)
    if ep:
        state_manager.set_active(ep.id)
        ep.catalog_id = catalog_id
        ep.script_key = str(item.get("script_key") or catalog_id)
        # Keep Episode_Date_Time naming; do not overwrite with catalog marketing titles.
        if not (ep.title or "").strip():
            ep.title = make_studio_episode_name()
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
        orchestrator.log(ep.id, f"Selected queue video '{ep.title}'.")
        return ep

    ep = state_manager.create_episode(
        title=make_studio_episode_name(),
        engine="vidu",
        catalog_id=catalog_id,
        script_key=str(item.get("script_key") or catalog_id),
    )
    _apply_catalog_concepts(ep, catalog_id)
    state_manager.save()
    orchestrator.log(ep.id, f"Selected queue video '{ep.title}' → Gate 1.")
    return ep


def _activate_catalog_video(catalog_id: str) -> Episode:
    item = get_catalog_item(catalog_id)
    if not item:
        raise HTTPException(status_code=404, detail="Video not found in catalog")
    return _activate_catalog_item(item)


def _select_queue_item(item_id: str) -> Episode:
    """Select a queue row only — set active episode, no render hydrate / stage jump."""
    from app.studio.generation import is_final_episode, normalize_production_status

    item = get_catalog_item(item_id)
    if item:
        related = [
            ep
            for ep in _related_episodes_for_item(item)
            if normalize_production_status(getattr(ep, "production_status", None)) != "published"
            and not is_final_episode(ep)
        ]
        ep = _pick_best_related_episode(related)
        if ep:
            state_manager.set_active(ep.id)
            if not ep.catalog_id:
                ep.catalog_id = str(item["id"])
                state_manager.save()
            return ep
        # First select of a catalog row: create a draft shell so selection sticks.
        from app.studio.naming import make_studio_episode_name

        ep = state_manager.create_episode(
            title=make_studio_episode_name(),
            engine="vidu",
            catalog_id=str(item["id"]),
            script_key=str(item.get("script_key") or item["id"]),
        )
        _apply_catalog_concepts(ep, str(item["id"]))
        state_manager.save()
        return ep

    ep = state_manager.set_active(item_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return ep


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


@router.post("/ui/queue/{item_id}/select", response_class=HTMLResponse)
@router.post("/ui/catalog/{item_id}/select", response_class=HTMLResponse)
def ui_select_queue_video(request: Request, item_id: str):
    """Row click: select only — stay on Studio queue, do not open/load stages."""
    ep = _select_queue_item(item_id)
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
        toast=f"Selected · {ep.title}",
        toast_kind="ok",
    )


@router.post("/ui/episodes/{episode_id}/select", response_class=HTMLResponse)
def ui_select_episode(request: Request, episode_id: str):
    """Select an existing episode in the Studio queue (no pipeline load)."""
    ep = state_manager.set_active(episode_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
        toast=f"Selected · {ep.title}",
        toast_kind="ok",
    )


@router.post("/ui/episodes/{episode_id}/studio", response_class=HTMLResponse)
def ui_open_episode_in_studio(request: Request, episode_id: str):
    """Arrow/open: activate episode and resume at furthest approved stage."""
    ep = state_manager.set_active(episode_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    stage = _stage_for_selected_episode(ep)
    gate_label = {1: "Pitch", 2: "Script", 3: "Video"}.get(stage, f"Stage {stage}")
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=stage,
        toast=f"{gate_label} · {ep.title}",
        toast_kind="ok",
    )


@router.post("/ui/catalog/{catalog_id}/open", response_class=HTMLResponse)
@router.post("/ui/catalog/{catalog_id}/gate1", response_class=HTMLResponse)
def ui_open_catalog_video(request: Request, catalog_id: str):
    """Arrow/open: activate catalog video and resume at furthest approved stage."""
    ep = _activate_catalog_video(catalog_id)
    stage = _stage_for_selected_episode(ep)
    gate_label = {1: "Pitch", 2: "Script", 3: "Video"}.get(stage, f"Stage {stage}")
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
    ep = _ensure_episode()
    if scene is None and stage_num == 2 and getattr(ep, "studio_ui_scene", None):
        scene = int(ep.studio_ui_scene)
    _remember_studio_ui(ep, stage_num, scene if stage_num == 2 else None)
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
    ep = _ensure_episode()
    _remember_studio_ui(ep, 2, scene_id)
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
            error="No script loaded. Approve a pitch first.",
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
@router.post("/ui/scheduler/mock-run", response_class=HTMLResponse)
def ui_mock_scheduler_run(request: Request):
    """Manually triggers the Agent 0 daily scheduler (which normally runs daily at 6:00 AM UTC)."""
    from app.trends.scheduler import run_daily_agent0_job
    from app.db import save_pitches_to_db

    ep = _ensure_episode()
    try:
        run_res = run_daily_agent0_job()
        pitches = run_res.get("pitches") or []
        if pitches:
            ep.available_concepts = pitches
            try:
                save_pitches_to_db(ep.id, pitches)
            except Exception as dberr:
                logger.debug("Failed to persist scheduler pitches to DB: %s", dberr)
    except Exception as exc:
        logger.warning("Mock scheduler run fallback: %s", exc)
        ep.available_concepts = trend_ingest_agent.fetch_trending_concepts()

    titles = [
        str(c.get("headline") or c.get("title") or "")
        for c in (ep.available_concepts or [])[:5]
    ]
    detail = ", ".join(t for t in titles if t) or "5 pitches"
    orchestrator.log(
        ep.id,
        f"Mock Scheduler manually executed (06:00 UTC job) → Top pitches: {detail}",
    )
    state_manager.save()
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=1,
        toast="Mock Scheduler executed (6:00 AM UTC job ran)",
        toast_kind="ok",
    )


def _split_source_csv(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _apply_concept_edits(
    concept: Dict[str, Any],
    *,
    headline: str,
    youth_sentiment_summary: str,
    crash_out_angle: str,
    proposed_merch_hook: str,
    tone: str = "",
    conflict: str = "",
    synopsis: str = "",
    mainstream_sources: str = "",
    youth_sources: str = "",
    touch_sources: bool = False,
) -> Dict[str, Any]:
    updated = dict(concept or {})
    title = (headline or "").strip()
    youth = (youth_sentiment_summary or "").strip()
    angle = (crash_out_angle or "").strip()
    merch = (proposed_merch_hook or "").strip()
    tone_val = (tone or "").strip()
    conflict_val = (conflict or "").strip()
    synopsis_val = (synopsis or "").strip()
    updated["headline"] = title
    updated["title"] = title
    updated["youth_sentiment_summary"] = youth
    updated["cultural_hook"] = youth
    updated["crash_out_angle"] = angle
    updated["premise"] = angle
    updated["synopsis"] = synopsis_val or angle
    updated["conflict"] = conflict_val or angle
    updated["tone"] = tone_val
    updated["proposed_merch_hook"] = merch
    updated["suggested_merch"] = merch
    if touch_sources:
        mainstream = _split_source_csv(mainstream_sources)
        youth_list = _split_source_csv(youth_sources)
        updated["sources"] = {
            "mainstream": mainstream,
            "youth_social": youth_list,
        }
        updated["source_trends"] = (mainstream + youth_list)[:4]
    if title:
        updated["empty"] = False
    elif updated.get("manual"):
        updated["empty"] = True
    return updated


@router.post("/ui/concepts/{index}/update", response_class=HTMLResponse)
def ui_update_concept(
    request: Request,
    index: int,
    headline: str = Form(""),
    youth_sentiment_summary: str = Form(""),
    crash_out_angle: str = Form(""),
    proposed_merch_hook: str = Form(""),
    tone: str = Form(""),
    conflict: str = Form(""),
    synopsis: str = Form(""),
    mainstream_sources: str = Form(""),
    youth_sources: str = Form(""),
    action: str = Form("save"),
):
    ep = _ensure_episode()
    concepts = list(ep.available_concepts or [])
    if index < 0 or index >= len(concepts):
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=1,
            error="Invalid pitch card",
        )
    # Pitch card UI: Title / youth sentiment / crash-out / merch are editable; sources stay read-only.
    updated = _apply_concept_edits(
        concepts[index],
        headline=headline,
        youth_sentiment_summary=youth_sentiment_summary,
        crash_out_angle=crash_out_angle,
        proposed_merch_hook=proposed_merch_hook,
        tone=tone,
        conflict=conflict,
        synopsis=synopsis,
        mainstream_sources=mainstream_sources,
        youth_sources=youth_sources,
        touch_sources=False,
    )
    concepts[index] = updated
    ep.available_concepts = concepts

    # Persist primary manual card back into custom catalog.
    if ep.catalog_id and str(ep.catalog_id).startswith("custom_") and index == 0:
        update_catalog_concept(str(ep.catalog_id), updated)

    select = (action or "save").strip().lower() == "select"
    if select:
        if is_empty_concept(updated):
            return render(
                request,
                "partials/htmx_workspace.html",
                viewing_stage=1,
                error="Add a headline before selecting this card",
            )
        ep.selected_concept = updated
        if updated.get("script_key"):
            ep.script_key = str(updated["script_key"])
    elif ep.selected_concept:
        # Keep selected_concept in sync when editing the active card.
        same_id = ep.selected_concept.get("id") and ep.selected_concept.get("id") == updated.get("id")
        same_idx = _selected_concept_index(ep) == index
        if same_id or same_idx:
            ep.selected_concept = updated

    state_manager.save()
    # Inline card autosave: keep focus (no workspace remount). Select still reloads.
    if not select and (
        (request.headers.get("HX-Request") or "").lower() == "true"
        and "workspace" not in (request.headers.get("HX-Target") or "")
    ):
        return HTMLResponse("")
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=1,
        toast="Pitch selected" if select else "Pitch saved",
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
            error="Invalid pitch selection",
        )
    chosen = concepts[index]
    if is_empty_concept(chosen):
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=1,
            error="Add a headline before selecting this card",
        )
    ep.selected_concept = chosen
    if chosen.get("script_key"):
        ep.script_key = str(chosen["script_key"])
    state_manager.save()
    return render(request, "partials/htmx_workspace.html", viewing_stage=1)


@router.post("/ui/gateway/1/approve", response_class=HTMLResponse)
def ui_approve_gateway_1(request: Request):
    from app.trends.schema import is_sensitive_pitch
    from app.trends.store import remember_episode_topic

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
            error="Select a pitch first",
        )
    ep.selected_concept = selected

    try:
        if is_sensitive_pitch(selected):
            orchestrator.log(
                ep.id,
                f"SENSITIVE_REVIEW pitch approved by human: {selected.get('headline') or selected.get('title')}",
            )
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
        ep.merch_punchline = script_data.get("merch_punchline_trigger") or selected.get(
            "proposed_merch_hook"
        ) or selected.get("suggested_merch")
        ep.status = "WAITING_GATEWAY_2"
        ep.current_gateway = 2
        set_production_status(ep, "scripting")
        from app.studio.naming import apply_confirmed_pitch_title

        pitch_label = str(selected.get("headline") or selected.get("title") or "").strip()
        apply_confirmed_pitch_title(ep, pitch_label)
        remember_episode_topic(
            ep.id,
            title=ep.title,
            label=pitch_label or ep.title,
        )
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

    _remember_studio_ui(ep, 2, 1, persist=False)
    state_manager.save()
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=2,
        script_scene=1,
        toast="Pitch approved · status Scripting",
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
        script_scene=getattr(ep, "studio_ui_scene", None),
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
        set_production_status(ep, "generating")
        state_manager.save()
        orchestrator.log(ep.id, "Gateway 2 approved: generating 4 Vidu scenes...")
        render_all_episode_scenes(ep)
        merge_episode_scenes(ep)
        ep.video_engine_used = f"Vidu AI ({config.vidu_model} / {config.vidu_reference_model})"
        ep.native_audio_enabled = True
        ep.selected_engine = "vidu"
        ep.status = "SCRIPT_APPROVED"
        ep.current_gateway = 3
        set_production_status(ep, "generating")
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

    _remember_studio_ui(ep, 3, persist=False)
    state_manager.save()
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
        # Video confirmed → Published and moved to Episodes library.
        mark_episode_final(ep)
        state_manager.save()
    except Exception as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error=str(exc),
        )
    return RedirectResponse(url=f"/episodes/{ep.id}", status_code=303)


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
        mark_episode_final(ep)
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
        toast="Episode complete — moved to Episodes",
        toast_kind="ok",
    )


# ---------------------------------------------------------------------------
# Episodes dashboard + character library + production workflow
# ---------------------------------------------------------------------------


@router.get("/episodes", response_class=HTMLResponse)
def ui_episodes_page(request: Request):
    """Finished library only — in-progress work stays in Studio."""
    _ensure_episode()
    return templates.TemplateResponse(
        request,
        "episodes.html",
        _shell_context(
            request,
            "episodes",
            episodes=list_final_episodes_sorted(),
            active_id=state_manager.active_episode_id,
        ),
    )


@router.get("/episodes/{episode_id}", response_class=HTMLResponse)
def ui_episode_record(request: Request, episode_id: str):
    """Read-only record view (video archive) — does not open Studio."""
    from app.studio.generation import is_final_episode

    ep = state_manager.episodes.get(episode_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    if not is_final_episode(ep):
        # In-progress shows belong in Studio, not the records library.
        return RedirectResponse(url="/studio?stage=0", status_code=303)

    if _attach_local_renders(ep) or _hydrate_renders_from_siblings(ep):
        state_manager.save_episode(ep.id)

    return templates.TemplateResponse(
        request,
        "episode_record.html",
        _shell_context(
            request,
            "episodes",
            ep=ep,
            scene_cards=_build_scene_cards(ep),
            master_video=_resolve_master_video(ep),
        ),
    )


@router.post("/ui/episodes/create", response_class=HTMLResponse)
def ui_episodes_create(request: Request, title: str = Form("New Episode")):
    from app.engines.factory import video_engine_mode

    ep = state_manager.create_episode(
        title=(title or "New Episode").strip() or "New Episode",
        engine=video_engine_mode(),
    )
    ep.available_concepts = trend_ingest_agent.fetch_trending_concepts()
    state_manager.save()
    orchestrator.log(ep.id, f"Created episode #{ep.episode_number}: {ep.title}")
    return RedirectResponse(url="/studio?stage=0", status_code=303)


@router.post("/ui/episodes/{episode_id}/open", response_class=HTMLResponse)
def ui_episodes_open(request: Request, episode_id: str):
    """Legacy POST open → record page (not Studio)."""
    ep = state_manager.episodes.get(episode_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    return RedirectResponse(url=f"/episodes/{episode_id}", status_code=303)


@router.post("/ui/episodes/{episode_id}/duplicate", response_class=HTMLResponse)
def ui_episodes_duplicate(request: Request, episode_id: str):
    clone = state_manager.duplicate_episode(episode_id)
    if not clone:
        raise HTTPException(status_code=404, detail="Episode not found")
    orchestrator.log(clone.id, f"Duplicated from {episode_id} → #{clone.episode_number}")
    return RedirectResponse(url="/episodes", status_code=303)


@router.post("/ui/episodes/{episode_id}/rename", response_class=HTMLResponse)
def ui_episodes_rename(request: Request, episode_id: str, title: str = Form(...)):
    from app.studio.generation import is_final_episode

    ep = state_manager.rename_episode(episode_id, title)
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    # Studio renames stay in Studio; published records return to the library view.
    if is_final_episode(ep):
        return RedirectResponse(url=f"/episodes/{episode_id}", status_code=303)
    stage = getattr(ep, "studio_ui_stage", None)
    if stage is None:
        stage = 0
    return RedirectResponse(url=f"/studio?stage={int(stage)}", status_code=303)


@router.post("/ui/episodes/{episode_id}/autosave", response_class=HTMLResponse)
def ui_episodes_autosave(
    request: Request,
    episode_id: str,
    title: Optional[str] = Form(None),
):
    ep = state_manager.episodes.get(episode_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    if title is not None and title.strip():
        ep.title = title.strip()
    state_manager.save_episode(episode_id)
    return HTMLResponse('<span class="autosave-ok">Saved</span>')


@router.post("/ui/production/status", response_class=HTMLResponse)
def ui_production_status(request: Request, status: str = Form(...)):
    ep = _ensure_episode()
    try:
        set_production_status(ep, status)
        state_manager.save()
    except ValueError as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=0,
            error=str(exc),
        )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
        toast=f"Status → {status}",
        toast_kind="ok",
    )


@router.post("/ui/production/note", response_class=HTMLResponse)
def ui_production_note(
    request: Request,
    note: str = Form(...),
):
    ep = _ensure_episode()
    add_revision_note(ep, note, author="")
    state_manager.save()
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
        toast="Note saved",
        toast_kind="ok",
    )


@router.post("/ui/script/version", response_class=HTMLResponse)
def ui_script_version(request: Request, label: str = Form("")):
    ep = _ensure_episode()
    scene = getattr(ep, "studio_ui_scene", None)
    try:
        save_script_version(ep, label=label)
        state_manager.save()
    except ValueError as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=2,
            script_scene=scene,
            error=str(exc),
        )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=2,
        script_scene=scene,
        toast="Script version saved",
        toast_kind="ok",
    )


@router.post("/ui/jobs/{job_id}/retry", response_class=HTMLResponse)
def ui_job_retry(request: Request, job_id: str):
    from app.main import generate_single_scene

    ep = _ensure_episode()
    job = find_job(ep, job_id)
    if not job:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error="Job not found",
        )
    if job.get("status") not in {"failed", "completed"}:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error="Only failed/completed jobs can be retried",
        )
    # Clear in-flight lock by marking old job failed-done, then re-run scene.
    update_job(ep, job_id, status="failed", error="superseded by retry")
    state_manager.save()
    scene_id = int(job.get("scene_id") or 1)
    try:
        generate_single_scene({"scene_id": scene_id})
    except HTTPException as exc:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=3,
            error=str(exc.detail),
        )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast=f"Retried scene {scene_id}",
        toast_kind="ok",
    )


@router.get("/characters", response_class=HTMLResponse)
def ui_characters_page(request: Request, char_id: str = "gary"):
    cid = (char_id or "gary").lower()
    return templates.TemplateResponse(
        request,
        "characters.html",
        _shell_context(
            request,
            "characters",
            characters=list_characters(),
            active=get_character(cid),
            library_characters=list_characters(),
        ),
    )


@router.post("/ui/characters/{char_id}/save", response_class=HTMLResponse)
def ui_characters_save(
    request: Request,
    char_id: str,
    name: str = Form(""),
    role: str = Form(""),
    archetype: str = Form(""),
    description: str = Form(""),
    personality: str = Form(""),
    visual_prompt: str = Form(""),
    voice_tone: str = Form(""),
    voice_speed: str = Form(""),
    voice_pitch: str = Form(""),
    voice_delivery: str = Form(""),
):
    try:
        update_character(
            char_id,
            {
                "name": name,
                "role": role,
                "archetype": archetype,
                "description": description,
                "personality": personality,
                "visual_prompt": visual_prompt,
                "voice": {
                    "tone": voice_tone,
                    "speed": format_speed_hint(voice_speed),
                    "pitch": normalize_pitch_hint(voice_pitch),
                    "delivery": voice_delivery,
                },
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url=f"/characters?char_id={char_id}", status_code=303)


@router.post("/ui/characters/{char_id}/image", response_class=HTMLResponse)
async def ui_characters_image(
    request: Request,
    char_id: str,
    image: UploadFile = File(...),
):
    import tempfile

    suffix = os.path.splitext(image.filename or "")[1] or ".png"
    raw = await image.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        save_character_image(char_id, tmp_path, ext=suffix)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    return RedirectResponse(url=f"/characters?char_id={char_id}", status_code=303)


@router.post("/ui/characters/{char_id}/audio", response_class=HTMLResponse)
async def ui_characters_audio(
    request: Request,
    char_id: str,
    audio: UploadFile = File(...),
):
    import tempfile

    suffix = os.path.splitext(audio.filename or "")[1] or ".mp3"
    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty audio file")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        save_character_audio(char_id, tmp_path, ext=suffix)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    return RedirectResponse(url=f"/characters?char_id={char_id}", status_code=303)


# ---------------------------------------------------------------------------
# Script versions, dialogue edit, templates, history restore, export, audio, QA
# ---------------------------------------------------------------------------


@router.post("/ui/script/version/{version_id}/restore", response_class=HTMLResponse)
def ui_script_version_restore(request: Request, version_id: str):
    ep = _ensure_episode()
    try:
        restore_script_version(ep, version_id)
        state_manager.save()
    except ValueError as exc:
        return render(request, "partials/htmx_workspace.html", viewing_stage=2, error=str(exc))
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=2,
        toast="Script version restored",
        toast_kind="ok",
    )


@router.post("/ui/script/scene/{scene_id}/line/{line_index}", response_class=HTMLResponse)
def ui_script_line_save(
    request: Request,
    scene_id: int,
    line_index: int,
    text: str = Form(""),
    time_start: float = Form(0),
    time_end: float = Form(0),
    character: str = Form("gary"),
):
    ep = _ensure_episode()
    scenes = (ep.script or {}).get("scenes") or []
    scene = next((sc for sc in scenes if int(sc.get("scene_id", 0)) == scene_id), None)
    if not scene:
        return render(request, "partials/htmx_workspace.html", viewing_stage=2, error="Scene not found")
    lines = list(scene.get("dialogue") or [])
    if line_index < 0 or line_index >= len(lines):
        return render(request, "partials/htmx_workspace.html", viewing_stage=2, error="Line not found")
    lines[line_index]["text"] = text
    lines[line_index]["time_start"] = float(time_start)
    lines[line_index]["time_end"] = float(time_end)
    lines[line_index]["character"] = (character or "gary").lower()
    scene["dialogue"] = lines
    state_manager.save()
    return render(
        request,
        "partials/script_scene_block.html",
        viewing_stage=2,
        script_scene=scene_id,
        toast="Dialogue saved",
        toast_kind="ok",
    )


@router.post("/ui/templates/apply", response_class=HTMLResponse)
def ui_templates_apply(
    request: Request,
    template_id: str = Form(...),
    scene_id: int = Form(1),
    characters: str = Form("gary,linda,chris,chloe"),
):
    ep = _ensure_episode()
    cast = [c.strip().lower() for c in characters.split(",") if c.strip()]
    scenes = (ep.script or {}).get("scenes") or []
    scene = next((sc for sc in scenes if int(sc.get("scene_id", 0)) == int(scene_id)), None)
    dialogue = (scene or {}).get("dialogue") or []
    prompt = combine_prompt(template_id=template_id, character_ids=cast, dialogue_lines=dialogue)
    if scene is not None:
        scene["source_prompt"] = prompt
        scene["vidu_prompt"] = prompt
        state_manager.save()
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=2,
        script_scene=int(scene_id),
        toast="Template applied to scene prompt",
        toast_kind="ok",
    )


@router.post("/ui/templates/save", response_class=HTMLResponse)
def ui_templates_save(
    request: Request,
    template_id: str = Form(""),
    name: str = Form(""),
    scene_type: str = Form("general"),
    camera: str = Form(""),
    scene_instructions: str = Form(""),
    dialogue_hint: str = Form(""),
):
    upsert_template(
        {
            "id": template_id or None,
            "name": name,
            "scene_type": scene_type,
            "camera": camera,
            "scene_instructions": scene_instructions,
            "dialogue_hint": dialogue_hint,
        }
    )
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=2,
        toast="Template saved",
        toast_kind="ok",
    )


@router.post("/ui/clips/{scene_id}/restore/{version}", response_class=HTMLResponse)
def ui_clip_restore(request: Request, scene_id: int, version: int):
    ep = _ensure_episode()
    try:
        restore_clip_version(ep, scene_id, version)
        state_manager.save()
    except ValueError as exc:
        return render(request, "partials/htmx_workspace.html", viewing_stage=3, error=str(exc))
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast=f"Restored scene {scene_id} v{version}",
        toast_kind="ok",
    )


@router.post("/ui/jobs/enqueue/{scene_id}", response_class=HTMLResponse)
def ui_jobs_enqueue(request: Request, scene_id: int):
    ep = _ensure_episode()
    try:
        enqueue_background(ep, scene_id)
    except ValueError as exc:
        return render(request, "partials/htmx_workspace.html", viewing_stage=3, error=str(exc))
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast=f"Scene {scene_id} queued in background",
        toast_kind="ok",
    )


@router.post("/ui/notifications/read", response_class=HTMLResponse)
def ui_notifications_read(request: Request):
    mark_notifications_read()
    return render(request, "partials/htmx_workspace.html", viewing_stage=3, toast="Notifications cleared")


@router.post("/ui/export/zip", response_class=HTMLResponse)
def ui_export_zip(request: Request):
    ep = _ensure_episode()
    res = export_episode_zip(ep)
    if not res.get("success"):
        return render(request, "partials/htmx_workspace.html", viewing_stage=3, error=res.get("error"))
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast=f"Zip ready: {res.get('url')}",
        toast_kind="ok",
    )


@router.post("/ui/export/16x9", response_class=HTMLResponse)
def ui_export_16x9(request: Request):
    ep = _ensure_episode()
    res = export_16x9_letterbox(ep)
    if not res.get("success"):
        return render(request, "partials/htmx_workspace.html", viewing_stage=3, error=res.get("error"))
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast="16:9 export ready",
        toast_kind="ok",
    )


@router.post("/ui/audio/timing/sync", response_class=HTMLResponse)
def ui_audio_timing_sync(request: Request):
    ep = _ensure_episode()
    sync_dialogue_timing_from_script(ep)
    state_manager.save()
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=2,
        toast="Dialogue timing synced for Vidu prompts",
        toast_kind="ok",
    )


@router.post("/ui/audio/timing/{row_id}", response_class=HTMLResponse)
def ui_audio_timing_row(
    request: Request,
    row_id: str,
    time_start: float = Form(0),
    time_end: float = Form(0),
    pause_after_sec: float = Form(0.15),
    speed: str = Form("1.0x"),
    text: str = Form(""),
):
    ep = _ensure_episode()
    row = update_dialogue_timing_row(
        ep,
        row_id,
        {
            "time_start": time_start,
            "time_end": time_end,
            "pause_after_sec": pause_after_sec,
            "speed": speed,
            "text": text,
        },
    )
    if not row:
        return render(request, "partials/htmx_workspace.html", viewing_stage=2, error="Timing row not found")
    state_manager.save()
    return render(request, "partials/htmx_workspace.html", viewing_stage=2, toast="Timing updated", toast_kind="ok")


@router.post("/ui/qa/{scene_id}", response_class=HTMLResponse)
def ui_qa_update(
    request: Request,
    scene_id: int,
    section: str = Form(...),
    check_id: str = Form(...),
    passed: str = Form("true"),
    note: str = Form(""),
):
    ep = _ensure_episode()
    flag = None if passed == "pending" else (passed.lower() == "true")
    update_qa(ep, scene_id, section=section, check_id=check_id, passed=flag, note=note)
    state_manager.save()
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        script_scene=scene_id,
        toast="QA updated",
        toast_kind="ok",
    )


@router.post("/ui/continuity/{scene_id}/extract", response_class=HTMLResponse)
def ui_continuity_extract(request: Request, scene_id: int):
    ep = _ensure_episode()
    res = extract_last_frame(ep, scene_id)
    if not res.get("success"):
        return render(request, "partials/htmx_workspace.html", viewing_stage=3, error=res.get("error"))
    state_manager.save()
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=3,
        toast=f"Last frame saved for scene {scene_id}",
        toast_kind="ok",
    )

