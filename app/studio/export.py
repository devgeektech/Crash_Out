"""
Episode export: individual clips, master, zip bundle, optional 16:9 letterbox.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import zipfile
from typing import Any, Dict, List, Optional

import imageio_ffmpeg

from app.paths import OUTPUT_DIR, episode_dir, find_existing, scene_file_candidates
from app.state import Episode


def _episode_folder(ep: Episode) -> str:
    return episode_dir(ep.output_folder or ep.id)


def list_downloadable_assets(ep: Episode) -> List[Dict[str, Any]]:
    folder = _episode_folder(ep)
    assets = []
    for sid in range(1, 5):
        path = find_existing(
            scene_file_candidates(ep.id, sid, folder_name=ep.output_folder, title=ep.title)
        )
        if path and os.path.isfile(path):
            rel = os.path.relpath(path, OUTPUT_DIR).replace("\\", "/")
            assets.append(
                {
                    "kind": "scene",
                    "scene_id": sid,
                    "label": f"Scene {sid}",
                    "path": path,
                    "url": f"/outputs/{rel}",
                    "aspect": "9:16",
                }
            )
    master = os.path.join(folder, "merged_60s.mp4")
    if os.path.isfile(master):
        rel = os.path.relpath(master, OUTPUT_DIR).replace("\\", "/")
        assets.append(
            {
                "kind": "master",
                "label": "Full episode (9:16)",
                "path": master,
                "url": f"/outputs/{rel}",
                "aspect": "9:16",
            }
        )
    wide = os.path.join(folder, "merged_16x9.mp4")
    if os.path.isfile(wide):
        rel = os.path.relpath(wide, OUTPUT_DIR).replace("\\", "/")
        assets.append(
            {
                "kind": "master_16x9",
                "label": "Full episode (16:9)",
                "path": wide,
                "url": f"/outputs/{rel}",
                "aspect": "16:9",
            }
        )
    return assets


def export_16x9_letterbox(ep: Episode) -> Dict[str, Any]:
    """Letterbox 9:16 master into 1920x1080 16:9."""
    folder = _episode_folder(ep)
    src = os.path.join(folder, "merged_60s.mp4")
    if not os.path.isfile(src):
        return {"success": False, "error": "No merged_60s.mp4 — merge scenes first."}
    dest = os.path.join(folder, "merged_16x9.mp4")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    vf = (
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
    )
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        src,
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        dest,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0 or not os.path.isfile(dest):
            return {
                "success": False,
                "error": (proc.stderr or "ffmpeg failed")[-400:],
            }
        rel = os.path.relpath(dest, OUTPUT_DIR).replace("\\", "/")
        return {
            "success": True,
            "path": dest,
            "url": f"/outputs/{rel}",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def export_episode_zip(ep: Episode) -> Dict[str, Any]:
    folder = _episode_folder(ep)
    exports = os.path.join(folder, "exports")
    os.makedirs(exports, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(exports, f"{ep.id}_{stamp}.zip")
    assets = list_downloadable_assets(ep)
    # Include episode.json for provenance
    ep_json = os.path.join(folder, "episode.json")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if os.path.isfile(ep_json):
            zf.write(ep_json, arcname="episode.json")
        for asset in assets:
            path = asset.get("path")
            if path and os.path.isfile(path):
                zf.write(path, arcname=os.path.basename(path))
    rel = os.path.relpath(zip_path, OUTPUT_DIR).replace("\\", "/")
    return {
        "success": True,
        "path": zip_path,
        "url": f"/outputs/{rel}",
        "count": len(assets),
    }
