"""
Character consistency / visual QA checklists + last-frame continuity helpers.
Human review checklists (no CV model). Continuity extracts last frame via FFmpeg.
"""
from __future__ import annotations

import os
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional

import imageio_ffmpeg

from app.paths import episode_dir, find_existing, scene_file_candidates
from app.state import Episode

CONSISTENCY_CHECKS = [
    {"id": "face", "label": "Facial features match reference"},
    {"id": "hair", "label": "Hairstyle matches reference"},
    {"id": "outfit", "label": "Clothing colors / outfit match"},
    {"id": "accessories", "label": "Accessories (watch, Stanley, ring light) correct"},
]

VISUAL_CHECKS = [
    {"id": "hands", "label": "No extra / distorted hands"},
    {"id": "eyes", "label": "Eyes / pupils look correct"},
    {"id": "face_distort", "label": "No face distortions"},
    {"id": "background", "label": "Background stable / expected"},
    {"id": "outfit_change", "label": "No unwanted outfit changes"},
    {"id": "glitches", "label": "No unwanted objects / visual glitches"},
]


def default_qa_bundle(scene_id: int) -> Dict[str, Any]:
    return {
        "scene_id": int(scene_id),
        "updated_at": time.time(),
        "consistency": [
            {"id": c["id"], "label": c["label"], "pass": None, "note": ""}
            for c in CONSISTENCY_CHECKS
        ],
        "visual": [
            {"id": c["id"], "label": c["label"], "pass": None, "note": ""}
            for c in VISUAL_CHECKS
        ],
        "overall": "pending",
    }


def ensure_qa(ep: Episode, scene_id: int) -> Dict[str, Any]:
    qa = dict(ep.qa_checklists or {})
    key = str(int(scene_id))
    if key not in qa:
        qa[key] = default_qa_bundle(scene_id)
        ep.qa_checklists = qa
    return qa[key]


def update_qa(
    ep: Episode,
    scene_id: int,
    *,
    section: str,
    check_id: str,
    passed: Optional[bool],
    note: str = "",
) -> Dict[str, Any]:
    bundle = ensure_qa(ep, scene_id)
    items = bundle.get(section) or []
    for item in items:
        if item.get("id") == check_id:
            item["pass"] = passed
            item["note"] = note
            break
    bundle["updated_at"] = time.time()
    # overall
    flags = [i.get("pass") for i in (bundle.get("consistency") or []) + (bundle.get("visual") or [])]
    if any(f is False for f in flags):
        bundle["overall"] = "flagged"
    elif flags and all(f is True for f in flags):
        bundle["overall"] = "passed"
    else:
        bundle["overall"] = "pending"
    qa = dict(ep.qa_checklists or {})
    qa[str(int(scene_id))] = bundle
    ep.qa_checklists = qa
    return bundle


def extract_last_frame(ep: Episode, scene_id: int) -> Dict[str, Any]:
    """Save last frame of scene_N as continuity ref for scene_N+1."""
    path = find_existing(
        scene_file_candidates(ep.id, int(scene_id), folder_name=ep.output_folder, title=ep.title)
    )
    if not path or not os.path.isfile(path):
        return {"success": False, "error": f"Scene {scene_id} video not found"}
    folder = episode_dir(ep.output_folder or ep.id)
    cont_dir = os.path.join(folder, "continuity")
    os.makedirs(cont_dir, exist_ok=True)
    out = os.path.join(cont_dir, f"scene_{int(scene_id)}_last.png")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    # Seek near end; -sseof -0.1 takes frame near EOF
    cmd = [
        ffmpeg,
        "-y",
        "-sseof",
        "-0.15",
        "-i",
        path,
        "-frames:v",
        "1",
        out,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0 or not os.path.isfile(out):
            return {"success": False, "error": (proc.stderr or "ffmpeg failed")[-300:]}
        frames = dict(ep.continuity_frames or {})
        frames[str(int(scene_id))] = out
        ep.continuity_frames = frames
        return {"success": True, "path": out, "scene_id": int(scene_id)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def continuity_ref_for_next(ep: Episode, next_scene_id: int) -> Optional[str]:
    """Path to previous scene's last frame, if extracted."""
    prev = int(next_scene_id) - 1
    if prev < 1:
        return None
    frames = ep.continuity_frames or {}
    return frames.get(str(prev))
