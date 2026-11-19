"""
Generation queue, clip history archive, and production-status helpers.
"""
from __future__ import annotations

import os
import shutil
import time
import uuid
from typing import Any, Dict, List, Optional

from app.state import Episode, state_manager

# draft → scripting (concept OK) → generating (script OK) → published (video OK → Episodes)
PRODUCTION_STATUSES = ("draft", "scripting", "generating", "published")
JOB_STATUSES = ("waiting", "processing", "completed", "failed")

_LEGACY_STATUS_MAP = {
    "ready": "draft",
    "review": "generating",
    "approved": "published",
}


def normalize_production_status(value: Optional[str]) -> str:
    raw = (value or "draft").strip().lower()
    raw = _LEGACY_STATUS_MAP.get(raw, raw)
    return raw if raw in PRODUCTION_STATUSES else "draft"


def next_episode_number() -> int:
    nums = [int(getattr(ep, "episode_number", 0) or 0) for ep in state_manager.episodes.values()]
    return (max(nums) if nums else 0) + 1


def is_final_episode(ep: Episode) -> bool:
    """Published shows belong on /episodes (moved out of Studio)."""
    if normalize_production_status(getattr(ep, "production_status", None)) == "published":
        return True
    status = (getattr(ep, "status", "") or "").upper()
    if status == "COMPLETED":
        return True
    return int(getattr(ep, "current_gateway", 1) or 1) >= 6


def list_final_episodes_sorted(user_id: Optional[int] = None) -> List[Episode]:
    """Library list: published episodes only (scoped by user_id if provided)."""
    ensure_episode_numbers()
    migrate_legacy_production_statuses()
    finals = [ep for ep in state_manager.episodes.values() if is_final_episode(ep)]
    if user_id is not None:
        finals = [ep for ep in finals if ep.user_id == int(user_id)]
    return sorted(
        finals,
        key=lambda e: (
            -(int(getattr(e, "episode_number", 0) or 0)),
            -(float(getattr(e, "updated_at", 0) or 0)),
        ),
    )


def mark_episode_final(ep: Episode) -> None:
    """Video confirmed → Published and moved to the Episodes library."""
    ep.status = "COMPLETED"
    ep.current_gateway = max(int(ep.current_gateway or 1), 4)
    set_production_status(ep, "published")
    ep.updated_at = time.time()


def migrate_legacy_production_statuses() -> bool:
    """Rewrite old status labels onto the new draft/scripting/generating/published scale."""
    changed = False
    for ep in state_manager.episodes.values():
        current = (getattr(ep, "production_status", None) or "draft").strip().lower()
        normalized = normalize_production_status(current)
        if current != normalized:
            ep.production_status = normalized
            state_manager.save_episode(ep.id)
            changed = True
    return changed


def active_stage_label(ep: Episode) -> str:
    """Human stage label for dashboard / studio chrome."""
    prod = normalize_production_status(getattr(ep, "production_status", None))
    labels = {
        "draft": "Pitch",
        "scripting": "Script",
        "generating": "Video",
        "published": "Published",
    }
    return labels.get(prod, "Pitch")


def ensure_episode_numbers() -> bool:
    """Assign stable # to any episode missing a number (legacy rows used 0)."""
    episodes = list(state_manager.episodes.values())
    if not episodes:
        return False
    numbered = [ep for ep in episodes if int(getattr(ep, "episode_number", 0) or 0) > 0]
    missing = [ep for ep in episodes if int(getattr(ep, "episode_number", 0) or 0) <= 0]
    if not missing:
        return False
    used = {int(ep.episode_number) for ep in numbered}
    next_num = (max(used) if used else 0) + 1
    # Oldest first so legacy catalog eps get lower numbers.
    missing.sort(key=lambda e: float(getattr(e, "created_at", 0) or getattr(e, "updated_at", 0) or 0))
    changed = False
    for ep in missing:
        while next_num in used:
            next_num += 1
        ep.episode_number = next_num
        used.add(next_num)
        next_num += 1
        state_manager.save_episode(ep.id)
        changed = True
    return changed


def set_production_status(ep: Episode, status: str) -> None:
    status = normalize_production_status(status)
    if status not in PRODUCTION_STATUSES:
        raise ValueError(f"Invalid production_status: {status}")
    ep.production_status = status
    ep.updated_at = time.time()


def add_revision_note(
    ep: Episode,
    note: str,
    *,
    author: str = "",
    status: Optional[str] = None,
) -> Dict[str, Any]:
    entry = {
        "id": f"note_{uuid.uuid4().hex[:8]}",
        "at": time.time(),
        "author": (author or "").strip(),
        "episode_title": ep.title,
        "episode_number": ep.episode_number,
        "note": (note or "").strip(),
        "status": status or ep.production_status,
    }
    notes = list(ep.revision_notes or [])
    notes.append(entry)
    ep.revision_notes = notes
    return entry


def save_script_version(ep: Episode, *, label: str = "") -> Dict[str, Any]:
    if not ep.script:
        raise ValueError("No script to version")
    versions = list(ep.script_versions or [])
    entry = {
        "id": f"sv_{uuid.uuid4().hex[:8]}",
        "saved_at": time.time(),
        "label": label or f"Version {len(versions) + 1}",
        "script": ep.script,
    }
    versions.append(entry)
    ep.script_versions = versions[-50:]
    return entry


def _history_dir(ep: Episode) -> str:
    from app.paths import episode_dir

    folder = ep.output_folder or ep.id
    path = os.path.join(episode_dir(folder), "history")
    os.makedirs(path, exist_ok=True)
    return path


def archive_clip_before_regen(
    ep: Episode,
    scene_id: int,
    *,
    prompt: str = "",
    engine: str = "mock",
) -> Optional[Dict[str, Any]]:
    """Move existing scene_N.mp4 into history/ and record metadata."""
    from app.paths import find_existing, scene_file_candidates

    sid = int(scene_id)
    path = find_existing(
        scene_file_candidates(ep.id, sid, folder_name=ep.output_folder, title=ep.title)
    )
    history = dict(ep.clip_history or {})
    key = str(sid)
    versions = list(history.get(key) or [])
    version_num = len(versions) + 1

    archived_rel = None
    if path and os.path.isfile(path):
        dest_name = f"scene_{sid}_v{version_num}.mp4"
        dest = os.path.join(_history_dir(ep), dest_name)
        try:
            shutil.copy2(path, dest)
            archived_rel = f"{ep.output_folder}/history/{dest_name}"
        except OSError:
            archived_rel = None

    entry = {
        "version": version_num,
        "prompt": (prompt or "")[:4000],
        "path": archived_rel,
        "created_at": time.time(),
        "engine": engine,
    }
    versions.append(entry)
    history[key] = versions
    ep.clip_history = history
    return entry


def enqueue_job(ep: Episode, scene_id: int) -> Dict[str, Any]:
    """Add a waiting job; refuse if same scene already waiting/processing."""
    sid = int(scene_id)
    jobs = list(ep.generation_jobs or [])
    for job in jobs:
        if int(job.get("scene_id") or 0) == sid and job.get("status") in {
            "waiting",
            "processing",
        }:
            raise ValueError(f"Scene {sid} already has an in-flight generation job")
    job = {
        "id": f"job_{uuid.uuid4().hex[:10]}",
        "scene_id": sid,
        "status": "waiting",
        "error": None,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    jobs.append(job)
    ep.generation_jobs = jobs[-100:]
    return job


def update_job(
    ep: Episode,
    job_id: str,
    *,
    status: str,
    error: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    jobs = list(ep.generation_jobs or [])
    for job in jobs:
        if job.get("id") == job_id:
            job["status"] = status
            job["error"] = error
            job["updated_at"] = time.time()
            ep.generation_jobs = jobs
            return job
    return None


def find_job(ep: Episode, job_id: str) -> Optional[Dict[str, Any]]:
    for job in ep.generation_jobs or []:
        if job.get("id") == job_id:
            return job
    return None


def _normalize_credits(engine: str, credits: float = 0.0) -> float:
    """Count Vidu clip generations as credits; local preview gens use 0."""
    try:
        value = float(credits or 0)
    except (TypeError, ValueError):
        value = 0.0
    if value > 0:
        return value
    eng = (engine or "").lower()
    if eng in {"mock", "local-preview", "local"}:
        return 0.0
    # Live Vidu engines (name may be "vidu" or "Vidu AI …")
    if "vidu" in eng:
        return 1.0
    return 0.0


def record_cost(
    ep: Episode,
    *,
    scene_id: int,
    engine: str,
    estimated_usd: float = 0.0,
    credits: float = 0.0,
) -> None:
    ledger = list(ep.cost_ledger or [])
    used = _normalize_credits(engine, credits)
    ledger.append(
        {
            "scene_id": int(scene_id),
            "engine": engine,
            "credits": used,
            # Kept for older episode.json rows; UI uses credits only.
            "estimated_usd": float(estimated_usd or 0),
            "at": time.time(),
        }
    )
    ep.cost_ledger = ledger[-200:]


def cost_summary(ep: Episode) -> Dict[str, Any]:
    ledger = list(ep.cost_ledger or [])
    total_credits = 0.0
    by_scene: Dict[str, float] = {}
    for row in ledger:
        engine = str(row.get("engine") or "")
        raw = row.get("credits")
        if raw is None and float(row.get("estimated_usd") or 0) > 0:
            # Legacy dollar rows → treat each as 1 credit for display continuity.
            used = 1.0 if engine == "vidu" else 0.0
        else:
            used = _normalize_credits(engine, float(raw or 0))
        total_credits += used
        sid = str(row.get("scene_id"))
        by_scene[sid] = by_scene.get(sid, 0.0) + used
    counts: Dict[str, int] = {}
    for row in ledger:
        sid = str(row.get("scene_id"))
        counts[sid] = counts.get(sid, 0) + 1
    regenerations = sum(max(0, n - 1) for n in counts.values())
    # Enrich ledger copy for UI
    display_ledger = []
    for row in reversed(ledger[-30:]):
        engine = str(row.get("engine") or "")
        raw = row.get("credits")
        if raw is None and float(row.get("estimated_usd") or 0) > 0:
            used = 1.0 if engine == "vidu" else 0.0
        else:
            used = _normalize_credits(engine, float(raw or 0))
        display_ledger.append({**row, "credits": used})
    return {
        "total_credits": round(total_credits, 2),
        "total_usd": 0.0,  # dollars not tracked in UI
        "entries": len(ledger),
        "by_scene": by_scene,
        "regenerations": regenerations,
        "ledger": display_ledger,
    }


def studio_dashboard_snapshot(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Aggregate production metrics for the top-level dashboard (scoped by user_id if provided)."""
    migrate_legacy_production_statuses()
    ensure_episode_numbers()
    episodes = state_manager.list_episodes_sorted(user_id=user_id)
    by_prod: Dict[str, int] = {s: 0 for s in PRODUCTION_STATUSES}
    jobs_waiting = 0
    jobs_failed = 0
    credits_total = 0.0
    notes: List[Dict[str, Any]] = []
    studio_eps: List[Episode] = []
    for ep in episodes:
        prod = normalize_production_status(getattr(ep, "production_status", None))
        ep.production_status = prod
        by_prod[prod] = by_prod.get(prod, 0) + 1
        if prod != "published":
            studio_eps.append(ep)
        for job in ep.generation_jobs or []:
            st = (job.get("status") or "").lower()
            if st == "waiting":
                jobs_waiting += 1
            elif st == "failed":
                jobs_failed += 1
        credits_total += float(cost_summary(ep).get("total_credits") or 0)
        for n in ep.revision_notes or []:
            notes.append(
                {
                    **n,
                    "episode_id": ep.id,
                    "episode_title": n.get("episode_title") or ep.title,
                    "episode_number": n.get("episode_number") or ep.episode_number,
                }
            )
    notes.sort(key=lambda n: float(n.get("at") or 0), reverse=True)
    active = state_manager.get_active_episode(user_id=user_id)
    if active and normalize_production_status(active.production_status) == "published":
        # Prefer an in-studio show for the active card when possible.
        active_studio = next((e for e in studio_eps if e.id == active.id), None)
        active = active_studio or (studio_eps[0] if studio_eps else active)

    # Compute agent-specific counts for the client dashboard overview
    waiting_gw1 = sum(1 for ep in episodes if int(getattr(ep, "current_gateway", 1) or 1) == 1 and not ep.script)
    scripting_gw2 = sum(1 for ep in episodes if int(getattr(ep, "current_gateway", 1) or 1) == 2 or (ep.script and not getattr(ep, "scene_videos", None)))
    rendering_gw3 = sum(1 for ep in episodes if int(getattr(ep, "current_gateway", 1) or 1) == 3 or (ep.scene_videos and not getattr(ep, "scenes_merged", False)))
    publishing_gw4 = sum(1 for ep in episodes if int(getattr(ep, "current_gateway", 1) or 1) in (4, 5) or getattr(ep, "scenes_merged", False) and normalize_production_status(ep.production_status) != "published")
    total_ideas_count = sum(len(ep.available_concepts or []) for ep in episodes) or (len(episodes) * 5)

    active_info = None
    if active:
        prod = normalize_production_status(active.production_status)
        active_info = {
            "episode": active,
            "status": prod,
            "stage_label": active_stage_label(active),
            "is_published": prod == "published",
            "steps": [
                {
                    "id": "draft",
                    "label": "Pitch",
                    "done": prod in ("scripting", "generating", "published"),
                    "current": prod == "draft",
                },
                {
                    "id": "scripting",
                    "label": "Script",
                    "done": prod in ("generating", "published"),
                    "current": prod == "scripting",
                },
                {
                    "id": "generating",
                    "label": "Video",
                    "done": prod == "published",
                    "current": prod == "generating",
                },
                {
                    "id": "published",
                    "label": "Published",
                    "done": prod == "published",
                    "current": prod == "published",
                },
            ],
        }

    return {
        "episode_count": len(episodes),
        "studio_count": len(studio_eps),
        "by_production": {s: by_prod.get(s, 0) for s in PRODUCTION_STATUSES},
        "jobs_waiting": jobs_waiting,
        "jobs_failed": jobs_failed,
        "credits_total": round(credits_total, 2),
        "recent_episodes": [
            ep
            for ep in sorted(
                [e for e in episodes if normalize_production_status(e.production_status) == "published"],
                key=lambda e: (
                    -(int(getattr(e, "episode_number", 0) or 0)),
                    -(float(getattr(e, "updated_at", 0) or 0)),
                ),
            )
        ][:12],
        "recent_notes": notes[:4],
        "active_episode": active,
        "active_info": active_info,
        "published_count": by_prod.get("published", 0),
        "scripting_count": by_prod.get("scripting", 0),
        "generating_count": by_prod.get("generating", 0),
        "draft_count": by_prod.get("draft", 0),
        "agent_stats": {
            "agent_0_ideas_total": total_ideas_count,
            "agent_0_waiting_approval": waiting_gw1,
            "agent_1_scripts_ready": len([e for e in episodes if e.script]),
            "agent_1_in_review": scripting_gw2,
            "agent_3_rendering": rendering_gw3,
            "agent_3_clips_rendered": sum(len(e.scene_videos or []) for e in episodes),
            "agent_4_in_publishing": publishing_gw4,
            "agent_5_seeding_ready": by_prod.get("published", 0),
        },
    }


def restore_script_version(ep: Episode, version_id: str) -> Dict[str, Any]:
    for ver in ep.script_versions or []:
        if ver.get("id") == version_id:
            ep.script = ver.get("script")
            return ver
    raise ValueError("Script version not found")


def restore_clip_version(ep: Episode, scene_id: int, version: int) -> Dict[str, Any]:
    """Copy an archived history clip back to scene_N.mp4."""
    from app.paths import OUTPUT_DIR, episode_dir, public_url

    key = str(int(scene_id))
    versions = list((ep.clip_history or {}).get(key) or [])
    entry = next((v for v in versions if int(v.get("version") or 0) == int(version)), None)
    if not entry:
        raise ValueError("Clip history version not found")
    rel = entry.get("path")
    if not rel:
        raise ValueError("History file path missing")
    src_path = os.path.join(OUTPUT_DIR, str(rel).replace("/", os.sep))
    if not os.path.isfile(src_path):
        raise ValueError(f"History file missing: {rel}")
    folder = ep.output_folder or ep.id
    dest = os.path.join(episode_dir(folder), f"scene_{int(scene_id)}.mp4")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src_path, dest)
    url = public_url(f"{folder}/scene_{int(scene_id)}.mp4")
    found = False
    for sc in ep.scene_videos or []:
        if int(sc.get("scene_id") or 0) == int(scene_id):
            sc["local_path"] = dest
            sc["video_url"] = url
            sc["restored_from_version"] = int(version)
            found = True
            break
    if not found:
        ep.scene_videos = list(ep.scene_videos or []) + [
            {
                "scene_id": int(scene_id),
                "local_path": dest,
                "video_url": url,
                "status": "completed",
                "restored_from_version": int(version),
            }
        ]
    return {"scene_id": int(scene_id), "version": int(version), "video_url": url, "path": dest}
