"""
Jinja + HTMX UI helpers and routes for the Crash Out HITL hub.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("app.ui")

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.agents.agent_0_trend_ingest import trend_ingest_agent
from app.agents.agent_1_scriptwriter import scriptwriter_agent
from app.agents.agent_4_publisher import publisher_agent
from app.agents.agent_5_seeder import seeder_agent
from app.agents.agent_m_orchestrator import orchestrator
from app.core.catalog import (
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
    create_character,
    delete_character,
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
from app.auth.middleware import get_current_user
from app.state import Episode, state_manager

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
STATIC_CSS_PATH = os.path.join(os.path.dirname(__file__), "static", "css", "app.css")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def _static_cache_bust() -> str:
    try:
        return str(int(os.path.getmtime(STATIC_CSS_PATH)))
    except OSError:
        return "1"


def _get_total_credits_used() -> float:
    """Calculate cumulative credits consumed across all episodes."""
    try:
        from app.state import state_manager
        from app.studio.generation import cost_summary

        total = 0.0
        for ep in state_manager.episodes.values():
            total += float(cost_summary(ep).get("total_credits") or 0.0)
        return round(total, 1)
    except Exception:
        return 0.0


def _get_pending_hitl_count(user_id: Optional[int] = None) -> int:
    """Count episodes currently requiring human-in-the-loop sign-off."""
    try:
        from app.agents.agent_m_orchestrator import orchestrator
        return len(orchestrator.get_pending_hitl_assignments(user_id=user_id))
    except Exception:
        return 0


def _get_unread_notifications_count(user_id: Optional[int] = None) -> int:
    """Count unread push/system notifications."""
    try:
        from app.infra.notifications import get_unread_notifications_count
        return get_unread_notifications_count(user_id)
    except Exception:
        return 0


templates.env.globals["static_cache_bust"] = _static_cache_bust
templates.env.globals["get_total_credits_used"] = _get_total_credits_used
templates.env.globals["get_pending_hitl_count"] = _get_pending_hitl_count
templates.env.globals["get_unread_notifications_count"] = _get_unread_notifications_count

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
    from app.studio.generation import cost_summary

    c_summary = cost_summary(ep)
    by_scene_credits = c_summary.get("by_scene") or {}

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
            scene_credits = float(by_scene_credits.get(str(sid), 0.0))
            cards.append(
                {
                    "scene_id": sid,
                    "title": sc.get("title") or f"Clip {sid}",
                    "time_range": sc.get("time_range") or "",
                    "duration_sec": sc.get("duration_sec") or sv.get("duration_sec") or 15,
                    "latency_sec": sv.get("latency_sec"),
                    "vidu_mode": sv.get("vidu_mode"),
                    "credits": scene_credits,
                    "prompt": sc.get("source_prompt") or sc.get("vidu_prompt") or sc.get("visual_prompt") or "",
                    **media,
                }
            )
    else:
        # Record / legacy episodes may have renders without a script package.
        for sid in sorted(by_id.keys()) or [1, 2, 3, 4]:
            sv = by_id.get(sid) or {}
            media = _resolve_scene_playable(ep, sid, sv)
            scene_credits = float(by_scene_credits.get(str(sid), 0.0))
            cards.append(
                {
                    "scene_id": sid,
                    "title": sv.get("title") or f"Clip {sid}",
                    "time_range": sv.get("time_range") or "",
                    "duration_sec": sv.get("duration_sec") or 15,
                    "latency_sec": sv.get("latency_sec"),
                    "vidu_mode": sv.get("vidu_mode"),
                    "credits": scene_credits,
                    "prompt": sv.get("prompt") or sv.get("source_prompt") or sv.get("visual_prompt") or "",
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
    0: "Trend Research & Approve Pitch",
    1: "Trend Research & Approve Pitch",
    2: "Scriptwriter",
    3: "Animation & Rendering",
    4: "Publishing & Merchandising",
    5: "Community & Promotion",
}

# Letter marks shown in the stepper (A0 / A1 / A2 / A4 / A5)
# Stage 3 = Agent 2 (Animation & Rendering); A3 is not a separate stepper chip.
STAGE_MARKS = {
    0: "A0",
    1: "A0",
    2: "A1",
    3: "A2",
    4: "A4",
    5: "A5",
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


def _ensure_episode(user_id: Optional[int] = None) -> Episode:
    ep = state_manager.get_active_episode(user_id=user_id)
    if not ep:
        from app.engines.factory import video_engine_mode

        ep = state_manager.create_episode(
            "Episode 1: The HOA Violation", engine=video_engine_mode(), user_id=user_id
        )
        # Do not auto-score pitches on episode bootstrap — only Create top 5 pitches does.
        ep.available_concepts = trend_ingest_agent.concepts_from_latest_run()
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


def _selected_concept_index(ep: Episode) -> Optional[int]:
    concepts = ep.available_concepts or []
    if not concepts:
        return None
    if ep.selected_concept and not is_empty_concept(ep.selected_concept):
        for i, c in enumerate(concepts):
            if c.get("id") == ep.selected_concept.get("id") or c.get("title") == ep.selected_concept.get(
                "title"
            ):
                return i
    return None


def _resolve_viewing_stage(ep: Episode, viewing_stage: Optional[int]) -> int:
    gw = int(ep.current_gateway or 1)
    if viewing_stage is not None:
        stage = max(0, min(5, viewing_stage))
        if stage in DISABLED_STAGES:
            return min(3, gw)
        # Agent 0 tabs (Trend research / Approve pitch) are always reachable.
        if stage <= 1:
            return stage
        # Prevent jumping ahead to unapproved production stages.
        if stage > gw:
            return gw
        return stage
    # Default landing: Trend research
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
    if active_scene is not None:
        from app.core.prompts import format_vidu_prompt
        raw_p = (active_scene.get("source_prompt") or active_scene.get("vidu_prompt") or "").strip()
        if raw_p:
            active_scene["source_prompt"] = format_vidu_prompt(raw_p)
            active_scene["vidu_prompt"] = active_scene["source_prompt"]
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
    if int(getattr(ep, "current_gateway", 1) or 1) < 3:
        return False
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
    # Only copy script if the episode is already at Gateway 2 or beyond
    if donor.script and not ep.script and int(getattr(ep, "current_gateway", 1) or 1) >= 2:
        ep.script = donor.script
        ep.merch_punchline = donor.merch_punchline or ep.merch_punchline
    return True


def _format_queue_status(ep: Optional[Episode]) -> str:
    """Format step-by-step user-friendly queue status."""
    if not ep:
        return "Not started"
    prod = getattr(ep, "production_status", None) or ""
    gw = int(getattr(ep, "current_gateway", 1) or 1)
    status_raw = str(getattr(ep, "status", "") or "").upper()

    if prod == "published" or status_raw == "COMPLETED" or gw >= 6:
        return "Published"
    if gw == 1 or status_raw == "WAITING_GATEWAY_1" or (not ep.script and gw < 2):
        # Mockup ingest shells have no pitches until Create top 5 pitches.
        if not (ep.available_concepts or []):
            return "Waiting Topic Selection"
        return "Waiting Pitch Approving"
    if gw == 2 or status_raw == "WAITING_GATEWAY_2" or prod == "scripting":
        return "Waiting for Scriptwriting"
    if gw == 3 or status_raw in {"WAITING_GATEWAY_3", "SCRIPT_APPROVED"} or prod == "generating":
        return "Waiting for Video Generation"
    if gw == 4 or status_raw == "WAITING_GATEWAY_4":
        return "Waiting for Merch Sign-Off"
    if gw == 5 or status_raw == "WAITING_GATEWAY_5":
        return "Waiting for Publishing Sign-Off"
    return status_raw.replace("_", " ").title() if status_raw else "Draft"


def _catalog_cards(user_id: Optional[int] = None) -> list:
    cards = []
    for index, item in enumerate(list_catalog_items(user_id=user_id), start=1):
        related = _related_episodes_for_item(item)
        if user_id is not None:
            related = [e for e in related if e.user_id == int(user_id)]
        latest = _pick_best_related_episode(related)
        if latest:
            _attach_local_renders(latest)
        display_title = (
            latest.title
            if latest and (latest.title or "").strip()
            else str(item.get("title") or "Untitled")
        )
        # Determine the true episode ID/number (never overwrite with enumerate index)
        import re
        card_id_num = None
        if latest and getattr(latest, "episode_number", None):
            card_id_num = int(latest.episode_number)
        elif item.get("episode_number"):
            card_id_num = int(item["episode_number"])
        else:
            m = re.search(r'\bEP-(\d+)\b', display_title, re.IGNORECASE)
            if m:
                card_id_num = int(m.group(1))
            else:
                card_id_num = index

        cards.append(
            {
                **item,
                "title": display_title,
                "list_number": card_id_num,
                "id_num": card_id_num,
                "episode": latest,
                "concepts": (latest.available_concepts if latest and latest.available_concepts else None) or concepts_for_catalog(item.get("id")),
                "episode_status": _format_queue_status(latest),
                "gateway": latest.current_gateway if latest else None,
            }
        )
    # Newer catalog entries first (highest ID on top).
    cards.sort(key=lambda c: int(c.get("list_number") or 0), reverse=True)
    return cards


def _studio_queue_cards(user_id: Optional[int] = None) -> list:
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
    for card in _catalog_cards(user_id=user_id):
        ep = card.get("episode")
        if _published(ep):
            continue
        cards.append(card)
        if ep:
            seen_ep_ids.add(ep.id)

    # Draft / scripting / generating episodes that are not represented by a catalog row.
    extras: list = []
    for ep in state_manager.list_episodes_sorted(user_id=user_id):
        if ep.id in seen_ep_ids or _published(ep):
            continue
        prod = normalize_production_status(getattr(ep, "production_status", None))
        ep_num = int(ep.episode_number or 0)
        if not ep_num:
            import re
            m = re.search(r'\bEP-(\d+)\b', ep.title or "", re.IGNORECASE)
            ep_num = int(m.group(1)) if m else 0
        extras.append(
            {
                "id": ep.catalog_id or ep.id,
                "title": ep.title,
                "subtitle": "In studio",
                "duration_label": "—",
                "list_number": ep_num,
                "id_num": ep_num,
                "episode": ep,
                "concepts": ep.available_concepts or (concepts_for_catalog(ep.catalog_id) if ep.catalog_id else []),
                "episode_status": _format_queue_status(ep),
                "gateway": ep.current_gateway,
                "custom": bool(ep.catalog_id and str(ep.catalog_id).startswith("custom_")),
            }
        )

    all_cards = cards + extras

    # Sort newest first: highest episode number / creation time on top
    def _card_sort_key(c: dict) -> tuple:
        ep = c.get("episode")
        created_val = 0.0
        if ep and getattr(ep, "created_at", None):
            try:
                created_val = float(ep.created_at)
            except (ValueError, TypeError):
                created_val = 0.0
        elif c.get("created_at"):
            try:
                created_val = float(c["created_at"])
            except (ValueError, TypeError):
                created_val = 0.0
        list_num = int(c.get("list_number") or (ep.episode_number if ep else 0) or 0)
        return (list_num, created_val)

    all_cards.sort(key=_card_sort_key, reverse=True)
    return all_cards



def _agent0_tab_from_request(request: Request, stage: int) -> str:
    """Agent 0 inner tabs: research | approve | history."""
    if int(stage) == 1:
        return "approve"
    research = (request.query_params.get("research") or "").strip().lower()
    if research in {"history", "trend-history", "28"}:
        return "history"
    if research in {"today", "research", "trend-research"}:
        return "research"
    raw = (request.query_params.get("a0") or request.query_params.get("tab") or "").strip().lower()
    if raw in {"approve", "pitch", "approve-pitch"}:
        return "approve"
    if raw in {"history", "trend-history"}:
        return "history"
    # Hard refresh / episode deep-links: keep Work history if that was the last view.
    from app.trends.research_ui import get_research_view

    if get_research_view(request.session, "today") == "history":
        return "history"
    return "research"


def _research_view_from_request(request: Request) -> str:
    from app.trends.research_ui import get_research_view, remember_research_prefs

    qp = request.query_params.get("research")
    if qp is not None:
        remember_research_prefs(request.session, view=qp)
        return "history" if str(qp).lower() in {"history", "trend-history", "28"} else "today"
    return get_research_view(request.session, "today")


def _work_history_cards(cards: list) -> list:
    """All worked queue/history episodes (newest first when timestamps exist)."""
    rows = list(cards or [])

    def _ts(card: dict) -> float:
        ep = card.get("episode") if isinstance(card, dict) else None
        best = 0.0
        for raw in (
            getattr(ep, "updated_at", None) if ep else None,
            getattr(ep, "created_at", None) if ep else None,
            card.get("updated_at") if isinstance(card, dict) else None,
            card.get("created_at") if isinstance(card, dict) else None,
        ):
            try:
                best = max(best, float(raw or 0))
            except (TypeError, ValueError):
                continue
        return best

    rows.sort(key=_ts, reverse=True)
    return rows


def _history_cards_28d(cards: list) -> list:
    """Back-compat alias — work history is no longer capped at 28 days."""
    return _work_history_cards(cards)


def _research_context_for_request(request: Request) -> Dict[str, Any]:
    from app.auth.middleware import current_user_id
    from app.trends.research_ui import (
        build_research_context,
        get_active_signal_id,
        get_research_filter,
        get_research_query,
        get_selected_signal_ids,
        remember_research_prefs,
    )

    qp_filter = request.query_params.get("filter")
    qp_q = request.query_params.get("q")
    if qp_filter is not None or qp_q is not None:
        remember_research_prefs(
            request.session,
            filter_bucket=qp_filter if qp_filter is not None else None,
            query=qp_q if qp_q is not None else None,
        )
    user_id = current_user_id(request)
    # Persist user picks across refresh; never auto-select — only ids the user toggled.
    selected = get_selected_signal_ids(request.session, user_id=user_id)
    active = get_active_signal_id(request.session)
    filter_bucket = get_research_filter(request.session, qp_filter or "all")
    # Selection UI only on All signals; keep stored picks so refresh/All tab restore them.
    display_selected = selected if str(filter_bucket or "all").lower() == "all" else []
    return build_research_context(
        selected_ids=display_selected,
        active_id=active,
        filter_bucket=filter_bucket,
        query=get_research_query(request.session, qp_q or ""),
        user_id=user_id,
    )


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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
            state_manager.save()
    completed = (ep.current_gateway or 1) >= 6 or (ep.status or "").upper() == "COMPLETED"
    show_completed = completed and viewing_stage is None

    char_id = (char_id or "gary").lower()
    if char_id not in CHARACTERS:
        char_id = "gary"

    catalog_cards = _studio_queue_cards(user_id=user_id)
    from app.trends.mockup_job import get_mockup_job

    mockup_job = get_mockup_job(user_id=user_id)
    mockup_searching = bool(mockup_job.get("running"))
    research_view = _research_view_from_request(request)
    agent0_tab = _agent0_tab_from_request(request, stage)
    if agent0_tab == "history":
        research_view = "history"
    elif agent0_tab == "research" and int(stage) == 0:
        # Keep explicit today from URL/session; do not clobber history.
        if research_view != "history":
            research_view = "today"
    research = (
        _research_context_for_request(request)
        if int(stage) == 0 and agent0_tab == "research" and research_view != "history"
        else {
            "signals": [],
            "selected_count": 0,
            "can_create_pitches": False,
            "max_selected": 1,
            "pitch_btn_mode": "disabled",
            "selected_signal_id": "",
            "has_pitch_for_selection": False,
            "total_count": 0,
            "filter_bucket": "all",
            "query": "",
            "active_signal": None,
            "character_count": 0,
            "mainstream_count": 0,
            "social_count": 0,
        }
    )

    ctx = {
        "request": request,
        "user": get_current_user(request),
        "pending_hitl_count": _get_pending_hitl_count(user_id),
        "unread_notifications_count": _get_unread_notifications_count(user_id),
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
        "catalog_cards": catalog_cards,
        "history_cards": _work_history_cards(catalog_cards),
        "agent0_tab": agent0_tab,
        "research_view": research_view,
        "research": research,
        "mockup_searching": mockup_searching,
        "mockup_job": mockup_job,
        "page": "studio",
        "episode_list": state_manager.list_episodes_sorted(user_id=user_id),
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
    # Keep /studio?stage=N[&scene=][&research=] in the address bar so hard refresh resumes here.
    push_templates = {
        "partials/htmx_workspace.html",
        "partials/script_scene_block.html",
    }
    if viewing_stage is not None and template_name in push_templates:
        scene = kwargs.get("script_scene")
        if scene is None and int(viewing_stage) == 2:
            scene = ctx.get("script_scene")
        ep_obj = ctx.get("ep")
        ep_id = getattr(ep_obj, "id", None) if ep_obj else None
        research_view = ctx.get("research_view")
        response.headers["HX-Push-Url"] = _studio_push_url(
            int(viewing_stage),
            scene,
            ep_id=ep_id,
            research=research_view if int(viewing_stage) == 0 else None,
        )
    return response


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def _shell_context(request: Request, page: str, **extra: Any) -> Dict[str, Any]:
    """Shared chrome context for non-pipeline pages (nav, toast, engine badge)."""
    user = get_current_user(request)
    user_id = user.id if user else None
    ctx = {
        "request": request,
        "user": user,
        "page": page,
        "pending_hitl_count": _get_pending_hitl_count(user_id),
        "unread_notifications_count": _get_unread_notifications_count(user_id),
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
def ui_home(request: Request, timeframe: str = "24h"):
    """Production dashboard — overview of pipeline health, social tracking, and Shopify revenue."""
    from app.core.catalog import list_catalog_items
    from app.studio.analytics import get_social_engagement_metrics, get_shopify_store_metrics

    user = get_current_user(request)
    user_id = user.id if user else None
    snap = studio_dashboard_snapshot(user_id=user_id)
    queue = _studio_queue_cards(user_id=user_id)
    social_data = get_social_engagement_metrics(timeframe=timeframe)
    shopify_data = get_shopify_store_metrics(timeframe=timeframe)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _shell_context(
            request,
            "dashboard",
            dashboard=snap,
            catalog_count=len(queue),
            catalog_cards=queue[:8],
            social_metrics=social_data,
            shopify_metrics=shopify_data,
            selected_timeframe=timeframe,
        ),
    )


def _select_top_queue_item(user_id: Optional[int] = None) -> Optional[Episode]:
    """Select the first (top) Studio queue row so Queue always has an active video."""
    cards = _studio_queue_cards(user_id=user_id)
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


def _studio_push_url(
    stage: int,
    scene: Optional[int] = None,
    ep_id: Optional[str] = None,
    research: Optional[str] = None,
) -> str:
    url = f"/studio?stage={int(stage)}"
    if int(stage) == 2 and scene is not None:
        url += f"&scene={int(scene)}"
    if int(stage) == 0:
        view = str(research or "").strip().lower()
        if view in {"history", "trend-history", "28"}:
            url += "&research=history"
        else:
            url += "&research=today"
        if ep_id:
            url += f"&episode={ep_id}"
    return url


@router.get("/credits", response_class=HTMLResponse)
def ui_credits_page(request: Request):
    """Episode-by-episode credits usage and Video Generations details."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login?next=/credits", status_code=303)

    from app.studio.generation import cost_summary

    breakdown = []
    total = 0.0
    for ep in state_manager.episodes.values():
        if ep.user_id != user.id:
            continue
        c_info = cost_summary(ep)
        ep_total = float(c_info.get("total_credits") or 0.0)
        total += ep_total
        breakdown.append(
            {
                "id": ep.id,
                "title": ep.title or ep.id,
                "episode_number": ep.episode_number,
                "status": getattr(ep, "production_status", None) or getattr(ep, "status", None) or "draft",
                "by_scene": c_info.get("by_scene") or {},
                "total_credits": ep_total,
            }
        )
    breakdown.sort(key=lambda r: (r["total_credits"], r.get("episode_number") or 0), reverse=True)

    return templates.TemplateResponse(
        request,
        "credits.html",
        _shell_context(
            request,
            "credits",
            total_credits=round(total, 1),
            episode_breakdown=breakdown,
        ),
    )


@router.get("/agent-m", response_class=HTMLResponse)
@router.get("/orchestrator", response_class=HTMLResponse)
async def ui_agent_m_page(
    request: Request,
    hitl_page: int = 1,
    incidents_page: int = 1,
):
    """Agent M: Master Orchestrator, Temporal telemetry, and HITL Gateway Approvals."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login?next=/agent-m", status_code=303)

    user_id = user.id if user else None
    telemetry = await orchestrator.get_temporal_telemetry()
    overview = orchestrator.get_orchestration_overview(
        user_id=user_id,
        temporal_info=telemetry,
        hitl_page=hitl_page,
        incidents_page=incidents_page,
    )

    return templates.TemplateResponse(
        request,
        "agent_m.html",
        _shell_context(
            request,
            "agent_m",
            overview=overview,
        ),
    )


@router.get("/tasks", response_class=HTMLResponse)
@router.get("/tasks-schedule", response_class=HTMLResponse)
async def ui_tasks_schedule_page(
    request: Request,
    agent_id: str = "all",
    page: int = 1,
    page_size: int = 6,
):
    """Dedicated page for Per-Agent Task Transparency & Schedule (Agent M + Agents 0–5)."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url=f"/login?next=/tasks?agent_id={agent_id}", status_code=303)

    user_id = user.id if user else None
    agent_tasks = orchestrator.get_agent_tasks_transparency(
        user_id=user_id,
        agent_id=agent_id,
        page=page,
        page_size=page_size,
    )

    return templates.TemplateResponse(
        request,
        "tasks_schedule.html",
        _shell_context(
            request,
            "tasks",
            agent_tasks=agent_tasks,
            selected_agent=agent_id,
        ),
    )


@router.get("/notifications", response_class=HTMLResponse)
async def ui_notifications_page(
    request: Request,
    category: str = "all",
    unread: int = 0,
    page: int = 1,
    page_size: int = 12,
):
    """
    Dedicated notifications & mobile push alerts page displaying HITL approval gates,
    critical errors & SLA incidents, and live publishing confirmations.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url=f"/login?next=/notifications", status_code=303)

    user_id = user.id if user else None
    from app.infra.notifications import list_notifications

    is_unread_only = bool(unread)
    notifs_data = list_notifications(
        user_id=user_id,
        category=None if category.lower() == "all" else category,
        unread_only=is_unread_only,
        page=page,
        page_size=page_size,
    )

    return templates.TemplateResponse(
        request,
        "notifications.html",
        _shell_context(
            request,
            "notifications",
            notifications=notifs_data,
            selected_category=category.lower(),
            unread_only=is_unread_only,
        ),
    )


@router.post("/notifications/{notification_id}/read")
async def ui_notification_mark_read(
    request: Request,
    notification_id: int,
):
    """Mark an individual notification as read."""
    user = get_current_user(request)
    user_id = user.id if user else None
    from app.infra.notifications import mark_notification_read
    mark_notification_read(notification_id, user_id=user_id)

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            '<span class="status-chip status-ok" style="font-size: 0.72rem; padding: 2px 7px;">Read</span>'
        )
    return RedirectResponse(url="/notifications", status_code=303)


@router.post("/notifications/read-all")
async def ui_notifications_mark_all_read(
    request: Request,
):
    """Mark all notifications as read."""
    user = get_current_user(request)
    user_id = user.id if user else None
    from app.infra.notifications import mark_all_notifications_read
    mark_all_notifications_read(user_id=user_id)
    return RedirectResponse(url="/notifications", status_code=303)



@router.get("/ui/agent-m/telemetry", response_class=HTMLResponse)
async def ui_agent_m_telemetry_partial(
    request: Request,
    hitl_page: int = 1,
    incidents_page: int = 1,
):
    """Live partial refresh endpoint for Agent M telemetry, HITL gates, and incident board."""
    user = get_current_user(request)
    user_id = user.id if user else None
    telemetry = await orchestrator.get_temporal_telemetry()
    overview = orchestrator.get_orchestration_overview(
        user_id=user_id,
        temporal_info=telemetry,
        hitl_page=hitl_page,
        incidents_page=incidents_page,
    )

    return templates.TemplateResponse(
        request,
        "partials/agent_m_telemetry.html",
        {
            "request": request,
            "user": user,
            "overview": overview,
        },
    )


@router.get("/ui/agent-m/hitl", response_class=HTMLResponse)
async def ui_agent_m_hitl_partial(
    request: Request,
    page: int = 1,
    incidents_page: int = 1,
):
    """Paginated partial for HITL Assignments list."""
    user = get_current_user(request)
    user_id = user.id if user else None
    telemetry = await orchestrator.get_temporal_telemetry()
    overview = orchestrator.get_orchestration_overview(
        user_id=user_id,
        temporal_info=telemetry,
        hitl_page=page,
        incidents_page=incidents_page,
    )

    return templates.TemplateResponse(
        request,
        "partials/agent_m_hitl_section.html",
        {
            "request": request,
            "user": user,
            "overview": overview,
        },
    )


@router.get("/ui/agent-m/incidents", response_class=HTMLResponse)
async def ui_agent_m_incidents_partial(
    request: Request,
    page: int = 1,
    hitl_page: int = 1,
):
    """Paginated partial for System Error & Incident Log Board."""
    user = get_current_user(request)
    user_id = user.id if user else None
    telemetry = await orchestrator.get_temporal_telemetry()
    overview = orchestrator.get_orchestration_overview(
        user_id=user_id,
        temporal_info=telemetry,
        hitl_page=hitl_page,
        incidents_page=page,
    )

    return templates.TemplateResponse(
        request,
        "partials/agent_m_incidents_section.html",
        {
            "request": request,
            "user": user,
            "overview": overview,
        },
    )


@router.get("/ui/agent-m/agent-tasks", response_class=HTMLResponse)
async def ui_agent_m_tasks_partial(
    request: Request,
    agent_id: str = "all",
    page: int = 1,
    page_size: int = 6,
):
    """Paginated partial for Per-Agent Task Transparency & Schedule."""
    user = get_current_user(request)
    user_id = user.id if user else None
    agent_tasks = orchestrator.get_agent_tasks_transparency(
        user_id=user_id,
        agent_id=agent_id,
        page=page,
        page_size=page_size,
    )

    return templates.TemplateResponse(
        request,
        "partials/agent_m_tasks_section.html",
        {
            "request": request,
            "user": user,
            "agent_tasks": agent_tasks,
        },
    )


@router.post("/agent-m/incidents/{incident_id}/retry", response_class=HTMLResponse)
async def ui_agent_m_retry_incident(
    request: Request,
    incident_id: str,
    hitl_page: int = 1,
    incidents_page: int = 1,
):
    """One-click task retry for failed Vidu rendering, FFmpeg, or API tasks."""
    user = get_current_user(request)
    user_id = user.id if user else None
    actor = user.email if user else "Admin"

    success, message = orchestrator.retry_task(incident_id, actor=actor)
    telemetry = await orchestrator.get_temporal_telemetry()
    overview = orchestrator.get_orchestration_overview(
        user_id=user_id,
        temporal_info=telemetry,
        hitl_page=hitl_page,
        incidents_page=incidents_page,
    )

    template_name = "partials/agent_m_incidents_section.html" if request.headers.get("hx-target") == "system-log-board" else "partials/agent_m_telemetry.html"
    resp = templates.TemplateResponse(
        request,
        template_name,
        {
            "request": request,
            "user": user,
            "overview": overview,
        },
    )
    if not request.headers.get("hx-request"):
        return RedirectResponse(url="/agent-m", status_code=303)
    return resp


@router.post("/agent-m/gateways/{episode_id}/approve", response_class=HTMLResponse)
async def ui_agent_m_approve_gateway(
    request: Request,
    episode_id: str,
    gateway: Optional[int] = None,
    hitl_page: int = 1,
    incidents_page: int = 1,
):
    """Direct approval of an episode gateway from the Agent M supervisor board."""
    user = get_current_user(request)
    user_id = user.id if user else None

    ep = state_manager.episodes.get(episode_id)
    if ep:
        target_gw = int(gateway or ep.current_gateway or 1)
        payload: Dict[str, Any] = {}

        if target_gw == 1:
            concept = ep.selected_concept or (ep.available_concepts[0] if ep.available_concepts else None)
            if not concept:
                from app.agents.agent_0_trend_ingest import trend_ingest_agent
                pitches = trend_ingest_agent.fetch_daily_pitches().get("pitches", [])
                concept = pitches[0] if pitches else {
                    "title": ep.title,
                    "premise": "Suburban satire meltdown",
                    "cultural_hook": "Viral social trend",
                    "characters_involved": ["gary", "linda", "chris", "chloe"],
                }
            payload["selected_concept"] = concept
        elif target_gw == 2:
            payload["script"] = ep.script
        elif target_gw == 3:
            payload["video_url"] = ep.video_url or ep.merged_video_url
        elif target_gw == 4:
            payload["social"] = ep.social_posts
            payload["merch"] = ep.merch_listing
        elif target_gw == 5:
            payload["seeding"] = ep.seeding_drafts

        try:
            orchestrator.approve_gateway(episode_id, target_gw, payload)
        except Exception as exc:
            logger.warning("Agent M approval note for %s (GW %d): %s", episode_id, target_gw, exc)

    telemetry = await orchestrator.get_temporal_telemetry()
    overview = orchestrator.get_orchestration_overview(
        user_id=user_id,
        temporal_info=telemetry,
        hitl_page=hitl_page,
        incidents_page=incidents_page,
    )

    template_name = "partials/agent_m_hitl_section.html" if request.headers.get("hx-target") == "hitl-assignments" else "partials/agent_m_telemetry.html"
    resp = templates.TemplateResponse(
        request,
        template_name,
        {
            "request": request,
            "user": user,
            "overview": overview,
        },
    )
    if not request.headers.get("hx-request"):
        return RedirectResponse(url="/agent-m", status_code=303)
    return resp


@router.post("/agent-m/trigger-agent0")
async def ui_agent_m_trigger_agent0(request: Request):
    """Trigger Agent 0 daily trend ingestion on demand."""
    user = get_current_user(request)
    actor = user.email if user else "Admin"
    try:
        from app.agents.agent_0_trend_ingest import trend_ingest_agent
        trend_ingest_agent.fetch_daily_pitches(force_refresh=True)
        from app.db import log_system_incident
        log_system_incident("AGENT_0_MANUAL_TRIGGER", actor=actor, details={"action": "Manual trend ingestion run"})
    except Exception as exc:
        logger.warning("Manual Agent 0 trigger notice: %s", exc)

    return RedirectResponse(url="/agent-m", status_code=303)


@router.post("/agent-m/test-incident", response_class=HTMLResponse)
async def ui_agent_m_test_incident(
    request: Request,
    hitl_page: int = 1,
    incidents_page: int = 1,
):
    """Generate a test incident for verification of the incident recovery board."""
    user = get_current_user(request)
    user_id = user.id if user else None
    actor = user.email if user else "Admin"

    from app.db import log_system_incident
    episodes = state_manager.list_episodes_sorted(user_id=user_id)
    ep = episodes[0] if episodes else None
    ep_title = ep.title if ep else "Episode 3 - The Strands Hint Breakdown"
    ep_id = ep.id if ep else "ep_test"

    log_system_incident(
        event_type="INCIDENT_VIDU_RENDER_TIMEOUT",
        actor=actor,
        details={
            "task_name": "Scene 3 Vidu Q4 Video Render",
            "category": "Vidu Q4 Preview API",
            "error": "HTTP 504 Gateway Timeout during frame interpolation (retry limit exceeded)",
            "retry_count": 2,
            "episode_id": ep_id,
            "episode_title": ep_title,
            "scene_id": 3,
        },
    )

    telemetry = await orchestrator.get_temporal_telemetry()
    overview = orchestrator.get_orchestration_overview(
        user_id=user_id,
        temporal_info=telemetry,
        hitl_page=hitl_page,
        incidents_page=incidents_page,
    )

    template_name = "partials/agent_m_incidents_section.html" if request.headers.get("hx-target") == "system-log-board" else "partials/agent_m_telemetry.html"
    resp = templates.TemplateResponse(
        request,
        template_name,
        {
            "request": request,
            "user": user,
            "overview": overview,
        },
    )
    if not request.headers.get("hx-request"):
        return RedirectResponse(url="/agent-m", status_code=303)
    return resp


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
            # Graceful fallback: if requested episode is missing/archived, select top queue item
            ep_active = state_manager.get_active_episode()
            if not ep_active:
                _select_top_queue_item()
        queue_select = True
    elif catalog:
        _select_queue_item(catalog)
        queue_select = True

    # Coming from another page / bare Studio link → Queue + top row selected if none active.
    if stage is None:
        stage = 0
        if not queue_select:
            ep_active = state_manager.get_active_episode()
            if not ep_active:
                _select_top_queue_item()
            queue_select = True
    elif stage == 0 and not queue_select:
        ep_active = state_manager.get_active_episode()
        if not ep_active:
            _select_top_queue_item()
        queue_select = True

    ep = state_manager.get_active_episode()

    # Waiting Pitch Approving used to open the pitch-card page. Send that status to Trend Research.
    if stage == 1 and ep and _format_queue_status(ep) == "Waiting Pitch Approving":
        from app.trends.research_ui import remember_research_prefs

        remember_research_prefs(request.session, view="today")
        return RedirectResponse(
            url=f"/studio?stage=0&research=today&episode={ep.id}",
            status_code=303,
        )

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


def _activate_catalog_item(item: Dict[str, Any], user_id: Optional[int] = None) -> Episode:
    from app.studio.naming import make_studio_episode_name

    catalog_id = str(item["id"])
    related = _related_episodes_for_item(item)
    if user_id is not None:
        related = [e for e in related if e.user_id == int(user_id)]
    ep = _pick_best_related_episode(related)
    if ep:
        state_manager.set_active(ep.id)
        ep.catalog_id = catalog_id
        ep.script_key = str(item.get("script_key") or catalog_id)
        if user_id is not None:
            ep.user_id = user_id
        # Keep Episode_Date_Time naming; do not overwrite with catalog marketing titles.
        if not (ep.title or "").strip():
            ep.title = make_studio_episode_name(serial_number=ep.episode_number)
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

    from app.studio.generation import next_episode_number
    target_num = next_episode_number()
    ep = state_manager.create_episode(
        title=make_studio_episode_name(serial_number=target_num),
        engine="vidu",
        catalog_id=catalog_id,
        script_key=str(item.get("script_key") or catalog_id),
        episode_number=target_num,
        user_id=user_id,
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


def _select_queue_item(item_id: str, user_id: Optional[int] = None) -> Episode:
    """Select a queue row only — set active episode, no render hydrate / stage jump."""
    from app.studio.generation import is_final_episode, normalize_production_status

    item = get_catalog_item(item_id)
    if item:
        related = [
            ep
            for ep in _related_episodes_for_item(item)
            if normalize_production_status(getattr(ep, "production_status", None)) != "published"
            and not is_final_episode(ep)
            and (user_id is None or ep.user_id == int(user_id))
        ]
        ep = _pick_best_related_episode(related)
        if ep:
            state_manager.set_active(ep.id)
            if not ep.catalog_id:
                ep.catalog_id = str(item["id"])
                state_manager.save()
            return ep
        # First select of a catalog row: create a draft shell so selection sticks.
        from app.studio.generation import next_episode_number
        from app.studio.naming import make_studio_episode_name

        target_num = next_episode_number()
        ep = state_manager.create_episode(
            title=make_studio_episode_name(serial_number=target_num),
            engine="vidu",
            catalog_id=str(item["id"]),
            script_key=str(item.get("script_key") or item["id"]),
            episode_number=target_num,
            user_id=user_id,
        )
        _apply_catalog_concepts(ep, str(item["id"]))
        state_manager.save()
        return ep

    ep = state_manager.set_active(item_id)
    if not ep or (user_id is not None and ep.user_id != user_id):
        raise HTTPException(status_code=404, detail="Queue item not found")
    return ep


def _stage_for_selected_episode(ep: Episode) -> int:
    """
    Map episode progress → studio stage for Work history Open.
    Matches queue status labels from _format_queue_status.
    """
    gw = int(ep.current_gateway or 1)
    prod = str(getattr(ep, "production_status", None) or "").lower()
    status_raw = str(getattr(ep, "status", "") or "").upper()

    # Published / complete → Video stage (furthest unlocked production view)
    if prod == "published" or status_raw == "COMPLETED" or gw >= 6:
        return 3
    # Merch / Publishing (soon stages still capped at unlocked)
    if gw >= 5 and 5 not in DISABLED_STAGES:
        return 5
    if gw >= 4 and 4 not in DISABLED_STAGES:
        return 4
    # Waiting for Video Generation
    if gw >= 3 or prod == "generating" or status_raw in {"WAITING_GATEWAY_3", "SCRIPT_APPROVED"}:
        return 3
    # Waiting for Scriptwriting
    if gw >= 2 or prod == "scripting" or status_raw == "WAITING_GATEWAY_2" or bool(ep.script):
        return 2
    # Gateway 1: Waiting Topic Selection and Waiting Pitch Approving both open Trend Research.
    return 0


def _render_agent0_workspace(request: Request, *, stage: int = 0, toast: Optional[str] = None, toast_kind: str = "info", error: Optional[str] = None):
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=stage,
        toast=toast,
        toast_kind=toast_kind,
        error=error,
    )


def _render_research_panel(request: Request, *, toast: Optional[str] = None, toast_kind: str = "info") -> HTMLResponse:
    """Fast path: only the Today's research panel (no full studio workspace rebuild)."""
    from app.trends.research_ui import remember_research_prefs

    remember_research_prefs(request.session, view="today")
    research = _research_context_for_request(request)
    response = templates.TemplateResponse(
        request,
        "partials/stages/stage_0_research.html",
        {
            "request": request,
            "research": research,
            "toast": toast,
            "toast_kind": toast_kind,
        },
    )
    return response


@router.get("/ui/agent0/research", response_class=HTMLResponse)
def ui_agent0_research(
    request: Request,
    research: str = "today",
    filter: str = "all",
    q: str = "",
    signal: Optional[str] = None,
    partial: int = 0,
):
    """Trend Research panel (today's signals or 28-day history)."""
    from app.trends.research_ui import remember_research_prefs, set_active_signal

    remember_research_prefs(request.session, view=research, filter_bucket=filter, query=q)
    if signal:
        set_active_signal(request.session, signal)
    view = "history" if str(research).lower() in {"history", "trend-history", "28"} else "today"
    # Checkbox / filter / open interactions only need the research panel.
    if partial or (view == "today" and request.headers.get("hx-target") == "research-root"):
        return _render_research_panel(request)
    return _render_agent0_workspace(request, stage=0)


@router.post("/ui/agent0/signals/{signal_id}/open", response_class=HTMLResponse)
def ui_agent0_open_signal(request: Request, signal_id: str):
    """Open detail and single-select this topic on All signals (no Select button)."""
    from app.auth.middleware import current_user_id
    from app.trends.research_ui import (
        get_research_filter,
        set_active_signal,
        set_selected_signal_ids,
    )

    set_active_signal(request.session, signal_id)
    user_id = current_user_id(request)
    filter_bucket = str(get_research_filter(request.session, "all") or "all").lower()
    if filter_bucket == "all":
        set_selected_signal_ids(request.session, [signal_id], user_id=user_id)
    return _render_research_panel(request)


@router.post("/ui/agent0/signals/{signal_id}/toggle", response_class=HTMLResponse)
def ui_agent0_toggle_signal(request: Request, signal_id: str):
    """
    Single-select toggle without remounting the research panel.
    Selection is only allowed on the All signals tab.
    """
    from app.auth.middleware import current_user_id
    from app.trends.research_ui import (
        MAX_SELECTED_SIGNALS,
        get_research_filter,
        get_selected_signal_ids,
        pitch_mode_for_selection,
        toggle_signal_selection,
    )

    user_id = current_user_id(request)
    filter_bucket = str(get_research_filter(request.session, "all") or "all").lower()
    before = set(get_selected_signal_ids(request.session, user_id=user_id))
    if filter_bucket != "all":
        after = list(before)
        toast = "Switch to All signals to select a topic"
        kind = "error"
    else:
        after = toggle_signal_selection(request.session, signal_id, user_id=user_id)
        toast = None
        kind = "info"
        if signal_id in before and signal_id not in after:
            toast = "Selection cleared"
        elif signal_id not in before and signal_id in after:
            toast = "Topic selected"
        elif signal_id not in before and signal_id not in after:
            toast = "Could not select topic"
            kind = "error"

    mode = pitch_mode_for_selection(after, user_id=user_id)
    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = json.dumps(
        {
            "researchSelectionUpdated": {
                "selected": after,
                "max": MAX_SELECTED_SIGNALS,
                "toggled": str(signal_id),
                "pitch_btn_mode": mode,
                "toast": toast,
                "toast_kind": kind,
            }
        }
    )
    return response


@router.post("/ui/agent0/create-pitches", response_class=HTMLResponse)
@router.post("/ui/agent0/create-pitch", response_class=HTMLResponse)
def ui_agent0_create_pitches(request: Request):
    """Create one pitch from the single selected All-signals topic (stay on research)."""
    from app.auth.middleware import current_user_id
    from app.studio.naming import make_studio_episode_name
    from app.trends.research_ui import (
        MAX_SELECTED_SIGNALS,
        create_pitches_from_signal_ids,
        get_selected_signal_ids,
        set_pitch_for_signal,
    )

    user_id = current_user_id(request)
    selected = get_selected_signal_ids(request.session, user_id=user_id)
    if len(selected) != MAX_SELECTED_SIGNALS:
        response = HTMLResponse(content="")
        response.headers["HX-Trigger"] = json.dumps(
            {
                "researchPitchError": {
                    "message": "Select one topic from All signals first.",
                }
            }
        )
        return response

    signal_id = selected[0]
    logger.info("[create-pitch] UI request · signal_id=%s · user_id=%s", signal_id, user_id)
    try:
        result = create_pitches_from_signal_ids(selected)
    except Exception as exc:
        logger.exception("[create-pitch] UI failed · signal_id=%s · error=%s", signal_id, exc)
        response = HTMLResponse(content="")
        response.headers["HX-Trigger"] = json.dumps(
            {"researchPitchError": {"message": str(exc)}}
        )
        return response

    concepts = result.get("concepts") or []
    if not concepts:
        logger.error("[create-pitch] UI · no concept card returned for signal_id=%s", signal_id)
        response = HTMLResponse(content="")
        response.headers["HX-Trigger"] = json.dumps(
            {"researchPitchError": {"message": "Pitch generation returned no card."}}
        )
        return response

    concept = dict(concepts[0])
    episode_name = str(
        concept.get("episode_name") or concept.get("headline") or concept.get("title") or ""
    ).strip()
    # Merch punchline is always the episode name.
    if episode_name:
        concept["episode_name"] = episode_name
        concept["headline"] = episode_name
        concept["title"] = episode_name
        concept["merch_punchline"] = episode_name
        concept["proposed_merch_hook"] = episode_name
        concept["suggested_merch"] = episode_name
    set_pitch_for_signal(signal_id, concept, user_id=user_id)
    logger.info(
        "[create-pitch] UI success · signal_id=%s · episode_name=%s",
        signal_id,
        episode_name[:100],
    )

    run = result.get("run") or {}
    headline = episode_name
    merch = episode_name

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = state_manager.get_active_episode(user_id=user_id)
    reuse_shell = bool(
        ep
        and (user_id is None or ep.user_id == user_id)
        and int(ep.current_gateway or 1) <= 1
        and not ep.script
    )
    if reuse_shell:
        ep.available_concepts = [concept]
        ep.selected_concept = concept
        if headline:
            ep.title = headline[:120]
        if merch:
            ep.merch_punchline = merch
        set_production_status(ep, "draft")
        state_manager.save()
        state_manager.set_active(ep.id)
    else:
        item = add_manual_catalog_video(
            title=headline or "Selected Trend Pitch",
            subtitle=f"Agent 0 selected topic pitch · {run.get('run_date') or ''}",
            merch=merch or "Capitalism broke my dad",
            user_id=user_id,
        )
        from app.studio.generation import next_episode_number

        target_num = next_episode_number()
        ep = state_manager.create_episode(
            title=make_studio_episode_name(serial_number=target_num),
            engine="vidu",
            catalog_id=str(item["id"]),
            script_key=str(item.get("script_key") or item["id"]),
            episode_number=target_num,
            user_id=user_id,
        )
        ep.available_concepts = [concept]
        ep.selected_concept = concept
        set_production_status(ep, "draft")
        state_manager.save()
        state_manager.set_active(ep.id)

    orchestrator.log(ep.id, f"Created pitch from selected research topic {signal_id}.")
    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = json.dumps(
        {
            "researchPitchReady": {
                "signal_id": signal_id,
                "pitch_btn_mode": "view",
                "toast": "Pitch ready",
                "toast_kind": "success",
                "episode_id": ep.id,
            }
        }
    )
    return response


def _pitch_modal_response(
    request: Request,
    *,
    pitch: Dict[str, Any],
    signal_id: str = "",
    ep: Optional[Episode] = None,
) -> HTMLResponse:
    is_approved = bool(
        ep
        and (
            int(ep.current_gateway or 1) >= 2
            or str(ep.status or "").upper() not in {"", "DRAFT", "WAITING_GATEWAY_1"}
        )
    )
    return templates.TemplateResponse(
        request,
        "partials/research_pitch_modal.html",
        {
            "request": request,
            "pitch": pitch,
            "signal_id": signal_id or str((pitch or {}).get("source_signal_id") or ""),
            "is_approved": is_approved,
            "ep": ep,
        },
    )


@router.get("/ui/agent0/pitch-modal", response_class=HTMLResponse)
def ui_agent0_pitch_modal(request: Request, signal_id: str = ""):
    """Popup pitch detail card for the selected All-signals topic."""
    from app.auth.middleware import current_user_id
    from app.trends.research_ui import get_pitch_for_signal, get_selected_signal_ids

    user_id = current_user_id(request)
    sid = str(signal_id or "").strip()
    if not sid:
        selected = get_selected_signal_ids(request.session, user_id=user_id)
        sid = selected[0] if selected else ""
    pitch = get_pitch_for_signal(sid, user_id=user_id) if sid else None
    if not pitch:
        return HTMLResponse(
            '<div class="research-pitch-modal-empty muted">No pitch for this selection yet. Click Create Pitch.</div>'
        )
    user = get_current_user(request)
    ep = state_manager.get_active_episode(user_id=user.id if user else None)
    return _pitch_modal_response(request, pitch=pitch, signal_id=sid, ep=ep)


@router.get("/ui/episodes/{episode_id}/pitch-modal", response_class=HTMLResponse)
def ui_episode_pitch_modal(request: Request, episode_id: str):
    """Work history Pitch column → Episode Pitch popup (same card as View Pitch)."""
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = state_manager.episodes.get(episode_id)
    if not ep or (user_id is not None and ep.user_id != user_id):
        raise HTTPException(status_code=404, detail="Episode not found")
    pitch = None
    if ep.selected_concept and not is_empty_concept(ep.selected_concept):
        pitch = dict(ep.selected_concept)
    elif ep.available_concepts:
        pitch = dict(ep.available_concepts[0] or {})
    if not pitch:
        return HTMLResponse(
            '<div class="research-pitch-modal-empty muted">No pitch on this episode yet.</div>'
        )
    return _pitch_modal_response(
        request,
        pitch=pitch,
        signal_id=str(pitch.get("source_signal_id") or ""),
        ep=ep,
    )


@router.post("/ui/agent0/approve-pitch", response_class=HTMLResponse)
async def ui_agent0_approve_pitch(request: Request, signal_id: str = Form("")):
    """
    Approve Episode Pitch → generate Scriptwriter package → open A1 Scriptwriter UI.
    Same path as Gate 1 approve; Animation & Rendering UI stays unchanged.
    """
    from app.auth.middleware import current_user_id
    from app.studio.naming import apply_confirmed_pitch_title
    from app.trends.research_ui import get_pitch_for_signal, get_selected_signal_ids, remember_research_prefs
    from app.trends.schema import is_sensitive_pitch
    from app.trends.store import remember_episode_topic

    user = get_current_user(request)
    user_id = user.id if user else current_user_id(request)
    sid = str(signal_id or "").strip()
    if not sid:
        selected = get_selected_signal_ids(request.session, user_id=user_id)
        sid = selected[0] if selected else ""
    pitch = get_pitch_for_signal(sid, user_id=user_id) if sid else None
    ep = state_manager.get_active_episode(user_id=user_id)
    if not ep:
        ep = _ensure_episode(user_id=user_id)
    if not pitch and ep and (ep.available_concepts or []):
        pitch = dict((ep.available_concepts or [None])[0] or {})
    if not pitch or is_empty_concept(pitch):
        return _render_agent0_workspace(request, stage=0, error="No pitch to approve for this selection.")

    ep.available_concepts = [pitch]
    ep.selected_concept = pitch
    episode_name = str(
        pitch.get("episode_name") or pitch.get("headline") or pitch.get("title") or ""
    ).strip()
    if episode_name:
        ep.title = episode_name[:120]
        ep.merch_punchline = episode_name
    elif pitch.get("proposed_merch_hook") or pitch.get("suggested_merch") or pitch.get("merch_punchline"):
        ep.merch_punchline = str(
            pitch.get("merch_punchline")
            or pitch.get("proposed_merch_hook")
            or pitch.get("suggested_merch")
            or ""
        )
    state_manager.save()

    try:
        if is_sensitive_pitch(pitch):
            orchestrator.log(
                ep.id,
                f"SENSITIVE_REVIEW pitch approved by human: {pitch.get('headline') or pitch.get('title')}",
            )
        orchestrator.approve_gateway(ep.id, 1, {"selected_concept": pitch})
        script_key = pitch.get("script_key") or ep.script_key or "hoa_violation"
        ep.script_key = script_key
        orchestrator.log(ep.id, f"Agent 1 loading script package '{script_key}'...")
        script_data = scriptwriter_agent.generate_script(ep.selected_concept)
        passed, qa_msg = orchestrator.validate_script_qa(script_data)
        orchestrator.log(ep.id, qa_msg)
        if not passed:
            return _render_agent0_workspace(request, stage=0, error=qa_msg)
        ep.script = script_data
        ep.merch_punchline = (
            script_data.get("merch_punchline_trigger")
            or pitch.get("merch_punchline")
            or pitch.get("proposed_merch_hook")
            or pitch.get("suggested_merch")
            or ep.merch_punchline
        )
        ep.status = "WAITING_GATEWAY_2"
        ep.current_gateway = 2
        set_production_status(ep, "scripting")
        apply_confirmed_pitch_title(ep, episode_name)
        remember_episode_topic(
            ep.id,
            title=ep.title,
            label=episode_name or ep.title,
        )
        state_manager.save()
    except Exception as exc:
        logger.exception("Approve pitch → script generation failed: %s", exc)
        return _render_agent0_workspace(request, stage=0, error=str(exc))

    # Leave Today's research mode so the agent bar reflects this episode's status.
    remember_research_prefs(request.session, view="history")
    _remember_studio_ui(ep, 2, 1, persist=False)
    state_manager.save()
    response = render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=2,
        script_scene=1,
        toast="Script ready · Scriptwriter unlocked",
        toast_kind="success",
    )
    response.headers["HX-Push-Url"] = f"/studio?stage=2&scene=1&episode={ep.id}"
    return response

def _mockup_button_html(*, searching: bool) -> str:
    label = "Searching..." if searching else "Mockup"
    disabled = " disabled" if searching else ""
    searching_cls = " is-searching" if searching else ""
    return (
        f'<button id="research-mockup-btn" type="button" '
        f'class="btn btn-primary btn-sm{searching_cls}"'
        f'{disabled} '
        f'hx-post="/ui/queue/mockup?research=today" '
        f'hx-target="#research-mockup-btn" '
        f'hx-swap="outerHTML" '
        f'hx-disabled-elt="this" '
        f'data-mockup-btn="1" '
        f'title="Scrape Mainstream (A) + Social Proof (B) in the background and refresh today\'s signals">'
        f"{label}</button>"
    )


@router.post("/ui/queue/mockup", response_class=HTMLResponse)
def ui_mockup_queue_scheduler(request: Request):
    """
    Start Agent 0 Mockup ingest in a background thread and return immediately.
    Job keeps running if the user switches pages; UI polls until done then refreshes.
    """
    import json as _json

    from app.trends.mockup_job import start_mockup_job
    from app.trends.research_ui import remember_research_prefs

    remember_research_prefs(request.session, view="today")
    user = get_current_user(request)
    user_id = user.id if user else None
    job = start_mockup_job(user_id=user_id)
    response = HTMLResponse(_mockup_button_html(searching=True))
    response.headers["HX-Trigger"] = _json.dumps(
        {
            "mockupSearchStarted": {
                "id": job.get("id") or "",
                "already_running": bool(job.get("already_running")),
                "message": job.get("message") or "Searching for Trending Topics...",
            }
        }
    )
    return response


@router.get("/ui/queue/mockup/status")
def ui_mockup_status(request: Request):
    """Poll background Mockup ingest status (survives page navigation)."""
    from app.trends.mockup_job import ack_mockup_job, get_mockup_job

    user = get_current_user(request)
    user_id = user.id if user else None
    job = get_mockup_job(user_id=user_id)
    status = str(job.get("status") or "idle")
    # After the client refreshes on done/error, clear so the next Mockup can start.
    if status in {"done", "error"} and (request.query_params.get("ack") or "").strip() in {
        "1",
        "true",
        "yes",
    }:
        ack_mockup_job(user_id=user_id)
        job = get_mockup_job(user_id=user_id)
    return JSONResponse(
        {
            "id": job.get("id") or "",
            "status": job.get("status") or "idle",
            "running": bool(job.get("running")),
            "message": job.get("message") or "",
            "error": job.get("error") or "",
            "raw_count": int(job.get("raw_count") or 0),
            "episode_id": job.get("episode_id") or "",
            "episode_title": job.get("episode_title") or "",
        }
    )


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
    user = get_current_user(request)
    user_id = user.id if user else None
    try:
        item = add_manual_catalog_video(title=title, subtitle=subtitle, user_id=user_id)
        ep = _activate_catalog_item(item, user_id=user_id)
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
    """Delete a queue video or active episode."""
    item = get_catalog_item(catalog_id)
    ep_by_id = state_manager.episodes.get(catalog_id)
    title = (item.get("title") if item else (ep_by_id.title if ep_by_id else catalog_id))

    if not item and not ep_by_id:
        # Check if catalog_id matches any episode catalog_id
        matching_ep = next((e for e in state_manager.episodes.values() if e.catalog_id == catalog_id), None)
        if not matching_ep:
            return render(
                request,
                "partials/htmx_workspace.html",
                viewing_stage=0,
                error="Video not found.",
            )

    delete_manual_catalog_video(catalog_id)
    for ep_id, ep in list(state_manager.episodes.items()):
        if ep.catalog_id == catalog_id or ep.id == catalog_id:
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
        toast=f"Deleted '{title}'",
        toast_kind="ok",
    )


@router.post("/ui/queue/{item_id}/rename", response_class=HTMLResponse)
@router.post("/ui/catalog/{item_id}/rename", response_class=HTMLResponse)
def ui_rename_queue_video(request: Request, item_id: str, title: str = Form(...)):
    """Rename a queue item / episode from the Agent 0 table."""
    new_title = (title or "").strip()
    if not new_title:
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=0,
            error="Title cannot be empty.",
        )

    # 1. Check if item_id is a direct episode
    ep = state_manager.episodes.get(item_id)
    if not ep:
        # Check if item_id matches an episode's catalog_id
        ep = next((e for e in state_manager.episodes.values() if e.catalog_id == item_id), None)

    if ep:
        state_manager.rename_episode(ep.id, new_title)

    # 2. Also update in catalog if custom catalog item exists
    from app.core.catalog import _load_custom_catalog, _save_custom_catalog
    items = _load_custom_catalog()
    changed = False
    for it in items:
        if it.get("id") == item_id or (ep and it.get("id") == ep.catalog_id):
            it["title"] = new_title
            changed = True
            break
    if changed:
        _save_custom_catalog(items)

    state_manager.save()
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
        toast=f"Renamed to '{new_title}'",
        toast_kind="ok",
    )


@router.post("/ui/queue/{item_id}/select", response_class=HTMLResponse)
@router.post("/ui/catalog/{item_id}/select", response_class=HTMLResponse)
def ui_select_queue_video(request: Request, item_id: str):
    """Row click: select only — stay on Studio queue, do not open/load stages."""
    from app.trends.research_ui import remember_research_prefs

    user = get_current_user(request)
    user_id = user.id if user else None
    _select_queue_item(item_id, user_id=user_id)
    remember_research_prefs(request.session, view="history")
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
    )


@router.post("/ui/episodes/{episode_id}/select", response_class=HTMLResponse)
def ui_select_episode(request: Request, episode_id: str):
    """Select an existing episode in the Studio queue (no pipeline load)."""
    from app.trends.research_ui import remember_research_prefs

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = state_manager.episodes.get(episode_id)
    if not ep or (user_id is not None and ep.user_id != user_id):
        raise HTTPException(status_code=404, detail="Episode not found")
    state_manager.set_active(episode_id)
    remember_research_prefs(request.session, view="history")
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
    )


@router.post("/ui/episodes/{episode_id}/research", response_class=HTMLResponse)
def ui_open_episode_research(request: Request, episode_id: str):
    """Work history Open → activate THIS episode and open its Trend Research page."""
    from app.trends.research_ui import remember_research_prefs

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = state_manager.episodes.get(episode_id)
    if not ep or (user_id is not None and ep.user_id != user_id):
        raise HTTPException(status_code=404, detail="Episode not found")
    state_manager.set_active(episode_id)
    remember_research_prefs(request.session, view="today")
    _remember_studio_ui(ep, 0)
    response = render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
        toast=f"Trend Research · {ep.title}",
        toast_kind="ok",
    )
    response.headers["HX-Push-Url"] = f"/studio?stage=0&research=today&episode={ep.id}"
    return response


@router.post("/ui/catalog/{catalog_id}/research", response_class=HTMLResponse)
def ui_open_catalog_research(request: Request, catalog_id: str):
    """Work history Open for catalog-only rows → Trend Research for that item."""
    from app.trends.research_ui import remember_research_prefs

    user = get_current_user(request)
    user_id = user.id if user else None
    item = get_catalog_item(catalog_id)
    if not item:
        raise HTTPException(status_code=404, detail="Video not found in catalog")
    ep = _activate_catalog_item(item, user_id=user_id)
    remember_research_prefs(request.session, view="today")
    _remember_studio_ui(ep, 0)
    response = render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=0,
        toast=f"Trend Research · {ep.title}",
        toast_kind="ok",
    )
    response.headers["HX-Push-Url"] = f"/studio?stage=0&research=today&episode={ep.id}"
    return response


@router.post("/ui/episodes/{episode_id}/studio", response_class=HTMLResponse)
def ui_open_episode_in_studio(request: Request, episode_id: str):
    """Work history Open → resume at the episode's current status stage."""
    from app.trends.research_ui import remember_research_prefs

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = state_manager.episodes.get(episode_id)
    if not ep or (user_id is not None and ep.user_id != user_id):
        raise HTTPException(status_code=404, detail="Episode not found")
    state_manager.set_active(episode_id)
    stage = _stage_for_selected_episode(ep)
    if stage <= 1:
        remember_research_prefs(request.session, view="today")
    _remember_studio_ui(ep, stage)
    status_label = _format_queue_status(ep)
    gate_label = {
        0: "Trend Research",
        1: "Approve Pitch",
        2: "Script",
        3: "Video",
        4: "Publish",
        5: "Seeding",
    }.get(stage, f"Stage {stage}")
    response = render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=stage,
        toast=f"{gate_label} · {status_label}",
        toast_kind="ok",
    )
    if stage == 0:
        response.headers["HX-Push-Url"] = f"/studio?stage=0&research=today&episode={ep.id}"
    else:
        response.headers["HX-Push-Url"] = f"/studio?stage={stage}&episode={ep.id}"
    return response


@router.post("/ui/catalog/{catalog_id}/open", response_class=HTMLResponse)
@router.post("/ui/catalog/{catalog_id}/gate1", response_class=HTMLResponse)
def ui_open_catalog_video(request: Request, catalog_id: str):
    """Work history Open for catalog rows → current status stage."""
    from app.trends.research_ui import remember_research_prefs

    user = get_current_user(request)
    user_id = user.id if user else None
    item = get_catalog_item(catalog_id)
    if not item:
        raise HTTPException(status_code=404, detail="Video not found in catalog")
    ep = _activate_catalog_item(item, user_id=user_id)
    stage = _stage_for_selected_episode(ep)
    if stage <= 1:
        remember_research_prefs(request.session, view="today")
    _remember_studio_ui(ep, stage)
    status_label = _format_queue_status(ep)
    gate_label = {
        0: "Trend Research",
        1: "Approve Pitch",
        2: "Script",
        3: "Video",
        4: "Publish",
        5: "Seeding",
    }.get(stage, f"Stage {stage}")
    response = render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=stage,
        toast=f"{gate_label} · {status_label}",
        toast_kind="ok",
    )
    if stage == 0:
        response.headers["HX-Push-Url"] = f"/studio?stage=0&research=today&episode={ep.id}"
    else:
        response.headers["HX-Push-Url"] = f"/studio?stage={stage}&episode={ep.id}"
    return response


@router.post("/ui/episodes/{episode_id}/pitches", response_class=HTMLResponse)
def ui_open_episode_pitches(request: Request, episode_id: str):
    """Open pitch page directly for an episode (Stage 1 concept cards)."""
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = state_manager.episodes.get(episode_id)
    if not ep or (user_id is not None and ep.user_id != user_id):
        raise HTTPException(status_code=404, detail="Episode not found")
    state_manager.set_active(episode_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    _remember_studio_ui(ep, 1)
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=1,
        toast=f"Pitches · {ep.title}",
        toast_kind="ok",
    )


@router.post("/ui/catalog/{catalog_id}/pitches", response_class=HTMLResponse)
def ui_open_catalog_pitches(request: Request, catalog_id: str):
    """Open pitch page directly for a catalog video (Stage 1 concept cards)."""
    ep = _activate_catalog_video(catalog_id)
    _remember_studio_ui(ep, 1)
    return render(
        request,
        "partials/htmx_workspace.html",
        viewing_stage=1,
        toast=f"Pitches · {ep.title}",
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
    if stage_num == 1 and _format_queue_status(ep) == "Waiting Pitch Approving":
        from app.trends.research_ui import remember_research_prefs

        remember_research_prefs(request.session, view="today")
        stage_num = 0
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    """Persist editable scene prompt (autosave or Save). Parses and synchronizes dialogue and directions."""
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
    scenes = (ep.script or {}).get("scenes") or []
    scene = next((sc for sc in scenes if int(sc.get("scene_id", 0)) == scene_id), None)
    if not scene:
        return HTMLResponse('<span class="badge badge-warn">Scene not found</span>', status_code=404)

    from app.core.prompts import format_vidu_prompt
    clean_prompt = format_vidu_prompt(source_prompt.strip())
    scene["source_prompt"] = clean_prompt
    scene["vidu_prompt"] = clean_prompt
    scene["vidu_prompt_chars"] = len(clean_prompt)

    # Bidirectional sync: Parse dialogue, action, camera, and sfx from prompt text
    import re
    diag_match = re.search(r'Dialogue:\s*(.*?)(?=(?:\n\s*|(?<!\[)\s+)SFX\s*:|$)', clean_prompt, re.DOTALL | re.IGNORECASE)
    if diag_match:
        pattern = re.compile(
            r'(?:\[(?:Camera|Shot|Angle)?\s*:?\s*(?P<camera>[^\]]+)\]\s*)?'
            r'(?P<character>[A-Za-z0-9_-]+)\s*:\s*'
            r'(?:\((?P<staging>[^)]+)\)\s*)?'
            r'["\u201c](?P<text>[^"\u201d]+)["\u201d]'
            r'(?:\s*\[(?:SFX|Sound)\s*:\s*(?P<sfx>[^\]]+)\])?',
            re.DOTALL | re.IGNORECASE
        )
        matches = list(pattern.finditer(diag_match.group(1)))
        if matches:
            old_dialogue = scene.get("dialogue") or []
            new_dialogue = []
            for idx, m in enumerate(matches):
                p_char = m.group("character").strip()
                if p_char.lower() in ("dialogue", "camera", "action", "sfx", "native", "scene"):
                    continue
                p_text = (m.group("text") or "").strip()
                p_cam = (m.group("camera") or "").strip()
                p_staging = (m.group("staging") or "").strip()
                p_sfx = (m.group("sfx") or "").strip()

                existing = old_dialogue[idx] if idx < len(old_dialogue) else {}
                entry = dict(existing)
                entry["character"] = p_char.lower()
                entry["text"] = p_text
                if p_cam:
                    entry["camera_cue"] = p_cam
                if p_sfx:
                    entry["sfx"] = p_sfx
                if p_staging:
                    parts = [p.strip() for p in p_staging.split(",") if p.strip()]
                    if len(parts) >= 2:
                        entry["voice_tag"] = parts[0]
                        entry["action"] = ", ".join(parts[1:])
                    else:
                        entry["action"] = parts[0]
                new_dialogue.append(entry)
            if new_dialogue:
                scene["dialogue"] = new_dialogue

    act_match = re.search(r'Action:\s*(.*?)(?=\n\s*Camera:|\s+Camera:|\n\s*Native|\s+Native|\n\s*Dialogue:|\s+Dialogue:|$)', clean_prompt, re.DOTALL | re.IGNORECASE)
    if act_match:
        scene["scene_action"] = act_match.group(1).strip()

    cam_match = re.search(r'Camera:\s*(.*?)(?=\n\s*Native|\s+Native|\n\s*Dialogue:|\s+Dialogue:|$)', clean_prompt, re.DOTALL | re.IGNORECASE)
    if cam_match:
        scene["camera_cue"] = cam_match.group(1).strip()

    sfx_match = re.search(r'SFX:\s*(.*?)$', clean_prompt, re.DOTALL | re.IGNORECASE)
    if sfx_match:
        scene["sfx"] = sfx_match.group(1).strip()

    fname = scene.get("source_prompt_file")
    if fname:
        path = prompt_file_path(str(fname))
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(clean_prompt)
            refresh_hoa_q4_prompt_episode()
        except OSError:
            pass

    if ep.catalog_id and str(ep.catalog_id).startswith("custom_"):
        update_custom_scene_prompt(str(ep.catalog_id), scene_id, clean_prompt)

    state_manager.save()
    orchestrator.log(ep.id, f"Script scene {scene_id} prompt updated ({len(clean_prompt)} chars).")

    hx_target = (request.headers.get("hx-target") or "").lstrip("#")
    if hx_target == "script-save-status":
        return HTMLResponse("Saved")

    return render(
        request,
        "partials/script_scene_block.html",
        viewing_stage=2,
        script_scene=scene_id,
        toast="Scene saved & synchronized",
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
    """
    Manually triggers the Agent 0 daily ingest (06:00 EST job): scrape feeds only.
    Pitch cards are created later from selected Trend Research topics.
    """
    from app.trends.scheduler import run_daily_agent0_job
    from app.trends.research_ui import clear_raw_feed_cache, remember_research_prefs

    remember_research_prefs(request.session, view="today")
    try:
        result = run_daily_agent0_job()
        clear_raw_feed_cache()
        raw_count = int(
            (result.get("meta") or {}).get("raw_count")
            or len(result.get("items") or [])
        )
        toast = f"Signals refreshed · {raw_count} raw hits · select 5 topics to create pitches"
        response = render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=0,
            toast=toast,
            toast_kind="ok",
        )
        response.headers["HX-Push-Url"] = "/studio?stage=0&research=today"
        return response
    except Exception as exc:
        logger.exception("Mock scheduler raw ingest failed: %s", exc)
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=0,
            error=f"Mock scheduler error: {exc}",
        )


def _split_source_csv(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _apply_concept_edits(
    concept: Dict[str, Any],
    *,
    headline: str = "",
    episode_name: str = "",
    youth_sentiment_summary: str = "",
    comedy_angle: str = "",
    crash_out_angle: str = "",
    possible_storyline: str = "",
    proposed_merch_hook: str = "",
    merch_punchline: str = "",
    episode_potential: str = "",
    character_involvement: str = "",
    tone: str = "",
    conflict: str = "",
    synopsis: str = "",
    mainstream_sources: str = "",
    youth_sources: str = "",
    touch_sources: bool = False,
) -> Dict[str, Any]:
    updated = dict(concept or {})
    title = (episode_name or headline or "").strip()
    # Merch punchline stays identical to episode name.
    merch = title or (merch_punchline or proposed_merch_hook or "").strip()
    comedy = (comedy_angle or youth_sentiment_summary or "").strip()
    storyline = (possible_storyline or crash_out_angle or "").strip()
    potential = (episode_potential or "").strip()
    characters = (character_involvement or "").strip()
    tone_val = (tone or "").strip()
    conflict_val = (conflict or "").strip()
    synopsis_val = (synopsis or "").strip()

    updated["episode_name"] = title
    updated["headline"] = title
    updated["title"] = title
    updated["merch_punchline"] = merch
    updated["proposed_merch_hook"] = merch
    updated["suggested_merch"] = merch
    updated["comedy_angle"] = comedy
    updated["youth_sentiment_summary"] = comedy
    updated["cultural_hook"] = comedy
    updated["possible_storyline"] = storyline
    updated["crash_out_angle"] = storyline
    updated["premise"] = storyline
    updated["synopsis"] = synopsis_val or storyline
    updated["conflict"] = conflict_val or storyline
    updated["episode_potential"] = potential
    updated["character_involvement"] = characters
    updated["tone"] = tone_val
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
    episode_name: str = Form(""),
    youth_sentiment_summary: str = Form(""),
    comedy_angle: str = Form(""),
    crash_out_angle: str = Form(""),
    possible_storyline: str = Form(""),
    proposed_merch_hook: str = Form(""),
    merch_punchline: str = Form(""),
    episode_potential: str = Form(""),
    character_involvement: str = Form(""),
    tone: str = Form(""),
    conflict: str = Form(""),
    synopsis: str = Form(""),
    mainstream_sources: str = Form(""),
    youth_sources: str = Form(""),
    action: str = Form("save"),
):
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
    # If Gateway 1 is already approved, lock pitches from edits
    if int(ep.current_gateway or 1) >= 2 or bool(ep.script):
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=1,
            error="Pitch already approved and locked.",
        )
    concepts = list(ep.available_concepts or [])
    if index < 0 or index >= len(concepts):
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=1,
            error="Invalid pitch card",
        )
    updated = _apply_concept_edits(
        concepts[index],
        headline=headline,
        episode_name=episode_name,
        youth_sentiment_summary=youth_sentiment_summary,
        comedy_angle=comedy_angle,
        crash_out_angle=crash_out_angle,
        possible_storyline=possible_storyline,
        proposed_merch_hook=proposed_merch_hook,
        merch_punchline=merch_punchline,
        episode_potential=episode_potential,
        character_involvement=character_involvement,
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
    # If Gateway 1 is already approved, prevent selecting another pitch
    if int(ep.current_gateway or 1) >= 2 or bool(ep.script):
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=1,
            error="Pitch already approved and locked.",
        )
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

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
    selected = ep.selected_concept
    if not selected or is_empty_concept(selected):
        return render(
            request,
            "partials/htmx_workspace.html",
            viewing_stage=1,
            error="Please select one of the pitches first before approving",
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    _ensure_episode(user_id=user_id)
    return templates.TemplateResponse(
        request,
        "episodes.html",
        _shell_context(
            request,
            "episodes",
            episodes=list_final_episodes_sorted(user_id=user_id),
            active_id=state_manager.active_episode_id,
        ),
    )


@router.get("/episodes/{episode_id}", response_class=HTMLResponse)
def ui_episode_record(request: Request, episode_id: str):
    """Read-only record view (video archive) — does not open Studio."""
    from app.studio.generation import is_final_episode

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = state_manager.episodes.get(episode_id)
    if not ep or (user_id is not None and ep.user_id != user_id):
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

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = state_manager.create_episode(
        title=(title or "New Episode").strip() or "New Episode",
        engine=video_engine_mode(),
        user_id=user_id,
    )
    ep.available_concepts = trend_ingest_agent.fetch_trending_concepts()
    state_manager.save()
    orchestrator.log(ep.id, f"Created episode #{ep.episode_number}: {ep.title}")
    return RedirectResponse(url="/studio?stage=0", status_code=303)


@router.post("/ui/episodes/{episode_id}/open", response_class=HTMLResponse)
def ui_episodes_open(request: Request, episode_id: str):
    """Legacy POST open → record page (not Studio)."""
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = state_manager.episodes.get(episode_id)
    if not ep or (user_id is not None and ep.user_id != user_id):
        raise HTTPException(status_code=404, detail="Episode not found")
    return RedirectResponse(url=f"/episodes/{episode_id}", status_code=303)


@router.post("/ui/episodes/{episode_id}/duplicate", response_class=HTMLResponse)
def ui_episodes_duplicate(request: Request, episode_id: str):
    user = get_current_user(request)
    user_id = user.id if user else None
    clone = state_manager.duplicate_episode(episode_id, user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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

    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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


@router.post("/ui/characters/new", response_class=HTMLResponse)
async def ui_characters_create(
    request: Request,
    name: str = Form(...),
    role: str = Form(""),
    archetype: str = Form(""),
    description: str = Form(""),
    personality: str = Form(""),
    visual_prompt: str = Form(""),
    voice_tone: str = Form(""),
    voice_speed: str = Form("1.00"),
    voice_pitch: str = Form("medium"),
    voice_delivery: str = Form(""),
    image: UploadFile = File(...),
    audio: UploadFile = File(...),
):
    try:
        if not image or not image.filename:
            raise ValueError("Reference portrait image is mandatory.")
        if not audio or not audio.filename:
            raise ValueError("Voice audio sample is mandatory.")

        raw_img = await image.read()
        if not raw_img:
            raise ValueError("Uploaded image file is empty.")
        raw_aud = await audio.read()
        if not raw_aud:
            raise ValueError("Uploaded audio file is empty.")

        new_char = create_character(
            name=name,
            role=role,
            archetype=archetype,
            description=description,
            personality=personality,
            visual_prompt=visual_prompt,
            voice_tone=voice_tone,
            voice_speed=voice_speed,
            voice_pitch=voice_pitch,
            voice_delivery=voice_delivery,
        )
        cid = new_char["id"]

        import tempfile
        ext_img = os.path.splitext(image.filename)[1] or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext_img) as tf:
            tf.write(raw_img)
            tmp_img = tf.name
        try:
            save_character_image(cid, tmp_img, ext=ext_img)
        finally:
            if os.path.exists(tmp_img):
                os.remove(tmp_img)

        ext_aud = os.path.splitext(audio.filename)[1] or ".mp3"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext_aud) as tf:
            tf.write(raw_aud)
            tmp_aud = tf.name
        try:
            save_character_audio(cid, tmp_aud, ext=ext_aud)
        finally:
            if os.path.exists(tmp_aud):
                os.remove(tmp_aud)

        return RedirectResponse(url=f"/characters?char_id={cid}", status_code=303)
    except Exception as exc:
        logger.exception("Failed to create character: %s", exc)
        return templates.TemplateResponse(
            request,
            "characters.html",
            _shell_context(
                request,
                "characters",
                characters=list_characters(),
                active=get_character("gary"),
                library_characters=list_characters(),
                toast=f"{exc}",
                toast_kind="error",
            ),
        )


@router.post("/ui/characters/{char_id}/delete", response_class=HTMLResponse)
def ui_characters_delete(request: Request, char_id: str):
    cid = (char_id or "").lower()
    delete_character(cid)
    remaining = list_characters()
    target_id = remaining[0]["id"] if remaining else "gary"
    return RedirectResponse(url=f"/characters?char_id={target_id}", status_code=303)


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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    voice_tag: str = Form(""),
    camera_cue: str = Form(""),
    action: str = Form(""),
    sfx: str = Form(""),
):
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
    scenes = (ep.script or {}).get("scenes") or []
    scene = next((sc for sc in scenes if int(sc.get("scene_id", 0)) == scene_id), None)
    if not scene:
        return render(request, "partials/htmx_workspace.html", viewing_stage=2, error="Scene not found")
    lines = list(scene.get("dialogue") or [])
    if line_index < 0 or line_index >= len(lines):
        return render(request, "partials/htmx_workspace.html", viewing_stage=2, error="Line not found")
    lines[line_index]["text"] = text.strip()
    if voice_tag:
        lines[line_index]["voice_tag"] = voice_tag.strip()
    if camera_cue:
        lines[line_index]["camera_cue"] = camera_cue.strip()
    if action:
        lines[line_index]["action"] = action.strip()
    if sfx:
        lines[line_index]["sfx"] = sfx.strip()
    lines[line_index]["character"] = (character or "gary").lower().strip()
    scene["dialogue"] = lines

    # Synchronize Vidu prompt text automatically
    from app.core.prompts import build_scene_prompt, prompt_char_count
    new_prompt = build_scene_prompt(scene)
    scene["source_prompt"] = new_prompt
    scene["vidu_prompt"] = new_prompt
    scene["vidu_prompt_chars"] = prompt_char_count(new_prompt)

    state_manager.save()
    return render(
        request,
        "partials/script_scene_block.html",
        viewing_stage=2,
        script_scene=scene_id,
        toast="Dialogue line updated & prompt synced",
        toast_kind="ok",
    )


@router.post("/ui/templates/apply", response_class=HTMLResponse)
def ui_templates_apply(
    request: Request,
    template_id: str = Form(...),
    scene_id: int = Form(1),
    characters: str = Form("gary,linda,chris,chloe"),
):
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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
    user = get_current_user(request)
    user_id = user.id if user else None
    ep = _ensure_episode(user_id=user_id)
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

