"""
Episode-scoped output paths under outputs/<ep_id>_<Episode Name>/.
"""
from __future__ import annotations

import os
import re
from typing import List, Optional, Set
from urllib.parse import quote, unquote

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")
EPISODES_DIR = os.path.join(OUTPUT_DIR, "episodes")
# Shared character reference art — outside outputs/ (not episode media).
CHARACTERS_DIR = os.path.join(PROJECT_ROOT, "characters")
# Optional reusable intro/outro bumpers for final assembly.
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(EPISODES_DIR, exist_ok=True)
os.makedirs(CHARACTERS_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

_RESERVED_DIR_NAMES = {"clean_characters", "characters", "agent0", "episodes", "logs", "system"}


def sanitize_episode_folder_name(title: str) -> str:
    """Human-readable title segment for folder names (Windows-safe)."""
    name = (title or "").strip()
    name = name.replace(":", " -")
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "")
    name = re.sub(r"\s+", " ", name).strip(" .")
    return (name[:150] if name else "") or "Untitled Episode"


def build_episode_folder_name(episode_id: str, title: str) -> str:
    """Canonical folder: ep_1234567890_The HOA Violation."""
    title_part = sanitize_episode_folder_name(title)
    eid = (episode_id or "").strip() or "ep_unknown"
    return f"{eid}_{title_part}"


def episode_dir(folder_name: str) -> str:
    """
    Returns the absolute path to the episode directory, prioritizing outputs/episodes/<folder_name>/.
    Falls back gracefully to legacy outputs/<folder_name>/ if it already exists there.
    """
    if os.path.isabs(folder_name):
        path = folder_name
    elif os.path.isdir(os.path.join(EPISODES_DIR, folder_name)):
        path = os.path.join(EPISODES_DIR, folder_name)
    elif os.path.isdir(os.path.join(OUTPUT_DIR, folder_name)):
        path = os.path.join(OUTPUT_DIR, folder_name)
    else:
        path = os.path.join(EPISODES_DIR, folder_name)
    os.makedirs(path, exist_ok=True)
    return path


def episode_video_dir(folder_name: str) -> str:
    path = os.path.join(episode_dir(folder_name), "video")
    os.makedirs(path, exist_ok=True)
    return path


def episode_audio_dir(folder_name: str) -> str:
    path = os.path.join(episode_dir(folder_name), "audio")
    os.makedirs(path, exist_ok=True)
    return path


def resolve_episode_folder(
    episode_id: str,
    title: str,
    *,
    claimed: Optional[str] = None,
    taken: Optional[Set[str]] = None,
) -> str:
    """
    Stable folder name for an episode: <episode_id>_<Title>.
    If claimed already matches the ep_id_ prefix, keep it; otherwise rebuild.
    """
    canonical = build_episode_folder_name(episode_id, title)
    if claimed:
        # Keep claimed only when it already uses this episode id prefix.
        if claimed == canonical or claimed.startswith(f"{episode_id}_"):
            return claimed
        # Legacy title-only / disambiguated names — migrate to canonical.
    _ = taken  # uniqueness is guaranteed by episode_id prefix
    return canonical


def _folder_belongs_to(folder_name: str, episode_id: str) -> bool:
    folder = episode_dir(folder_name)
    marker = os.path.join(folder, ".episode_id")
    if os.path.isfile(marker):
        try:
            with open(marker, "r", encoding="utf-8") as fh:
                return fh.read().strip() == episode_id
        except OSError:
            return False
    # Empty or only this episode's leftover files.
    return False


def write_episode_marker(folder_name: str, episode_id: str) -> None:
    folder = episode_dir(folder_name)
    marker = os.path.join(folder, ".episode_id")
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write(episode_id)


def scene_relpath(folder_name: str, scene_id: int) -> str:
    abs_p = scene_abspath(folder_name, scene_id)
    return os.path.relpath(abs_p, OUTPUT_DIR).replace("\\", "/")


def scene_abspath(folder_name: str, scene_id: int) -> str:
    ep_dir = episode_dir(folder_name)
    vid_file = os.path.join(ep_dir, "video", f"scene_{int(scene_id)}.mp4")
    if os.path.isfile(vid_file):
        return vid_file
    flat_file = os.path.join(ep_dir, f"scene_{int(scene_id)}.mp4")
    if os.path.isfile(flat_file):
        return flat_file
    # Default location for new writes
    os.makedirs(os.path.join(ep_dir, "video"), exist_ok=True)
    return vid_file


def merged_relpath(folder_name: str) -> str:
    abs_p = merged_abspath(folder_name)
    return os.path.relpath(abs_p, OUTPUT_DIR).replace("\\", "/")


def merged_abspath(folder_name: str) -> str:
    ep_dir = episode_dir(folder_name)
    vid_file = os.path.join(ep_dir, "video", "merged_60s.mp4")
    if os.path.isfile(vid_file):
        return vid_file
    flat_file = os.path.join(ep_dir, "merged_60s.mp4")
    if os.path.isfile(flat_file):
        return flat_file
    os.makedirs(os.path.join(ep_dir, "video"), exist_ok=True)
    return vid_file


def import_relpath(folder_name: str, kind: str = "web_import", ext: str = ".mp4") -> str:
    safe_ext = ext if ext.startswith(".") else f".{ext}"
    return f"{folder_name}/{kind}{safe_ext}"


def public_url(relpath: str) -> str:
    """Build a browser-safe /outputs/... URL (spaces, apostrophes encoded)."""
    parts = relpath.replace("\\", "/").split("/")
    encoded = "/".join(quote(part, safe="()-._~") for part in parts if part != "")
    return f"/outputs/{encoded}"


def abspath_from_public(url: str) -> str:
    """Map /outputs/Name/scene_1.mp4(?v=...) -> absolute filesystem path."""
    rel = unquote(str(url).split("?", 1)[0])
    if rel.startswith("/outputs/"):
        rel = rel[len("/outputs/") :]
    rel = rel.lstrip("/").replace("/", os.sep)
    return os.path.join(OUTPUT_DIR, rel)


def scene_file_candidates(
    episode_id: str,
    scene_id: int,
    *,
    folder_name: Optional[str] = None,
    title: Optional[str] = None,
) -> List[str]:
    """Canonical ep_id_Title folder first, then legacy layouts."""
    sid = int(scene_id)
    paths: List[str] = []
    folders: List[str] = []
    if folder_name:
        folders.append(folder_name)
    canonical = build_episode_folder_name(episode_id, title or "")
    if canonical not in folders:
        folders.append(canonical)
    # Legacy title-only folder (pre ep_id_ prefix).
    if title:
        legacy_title = sanitize_episode_folder_name(title)
        if legacy_title and legacy_title not in folders:
            folders.append(legacy_title)
    for folder in folders:
        # Check inside outputs/episodes/<folder>/video/
        paths.append(os.path.join(EPISODES_DIR, folder, "video", f"scene_{sid}.mp4"))
        paths.append(os.path.join(EPISODES_DIR, folder, "video", f"scene_{sid}.webm"))
        # Check inside outputs/episodes/<folder>/
        paths.append(os.path.join(EPISODES_DIR, folder, f"scene_{sid}.mp4"))
        paths.append(os.path.join(EPISODES_DIR, folder, f"scene_{sid}.webm"))
        # Check inside outputs/<folder>/video/
        paths.append(os.path.join(OUTPUT_DIR, folder, "video", f"scene_{sid}.mp4"))
        paths.append(os.path.join(OUTPUT_DIR, folder, "video", f"scene_{sid}.webm"))
        # Check inside outputs/<folder>/
        paths.append(os.path.join(OUTPUT_DIR, folder, f"scene_{sid}.mp4"))
        paths.append(os.path.join(OUTPUT_DIR, folder, f"scene_{sid}.webm"))
    # Legacy: outputs/<episode_id>/scene_N.mp4
    paths.append(os.path.join(OUTPUT_DIR, episode_id, f"scene_{sid}.mp4"))
    paths.append(os.path.join(OUTPUT_DIR, episode_id, f"scene_{sid}.webm"))
    # Legacy flat: outputs/<episode_id>_scene_N.mp4
    paths.append(os.path.join(OUTPUT_DIR, f"{episode_id}_scene_{sid}.mp4"))
    paths.append(os.path.join(OUTPUT_DIR, f"{episode_id}_scene_{sid}.webm"))
    return paths


def merged_file_candidates(
    episode_id: str,
    *,
    folder_name: Optional[str] = None,
    title: Optional[str] = None,
) -> List[str]:
    paths: List[str] = []
    folders: List[str] = []
    if folder_name:
        folders.append(folder_name)
    canonical = build_episode_folder_name(episode_id, title or "")
    if canonical not in folders:
        folders.append(canonical)
    if title:
        legacy_title = sanitize_episode_folder_name(title)
        if legacy_title and legacy_title not in folders:
            folders.append(legacy_title)
    for folder in folders:
        paths.append(os.path.join(EPISODES_DIR, folder, "video", "merged_60s.mp4"))
        paths.append(os.path.join(EPISODES_DIR, folder, "merged_60s.mp4"))
        paths.append(os.path.join(OUTPUT_DIR, folder, "video", "merged_60s.mp4"))
        paths.append(os.path.join(OUTPUT_DIR, folder, "merged_60s.mp4"))
    paths.append(os.path.join(OUTPUT_DIR, episode_id, "merged_60s.mp4"))
    paths.append(os.path.join(OUTPUT_DIR, f"{episode_id}_merged_60s.mp4"))
    return paths


def find_existing(candidates: List[str]) -> Optional[str]:
    for path in candidates:
        if path and os.path.exists(path) and os.path.getsize(path) > 1000:
            return path
    return None


def relpath_from_outputs(path: str) -> str:
    return os.path.relpath(path, OUTPUT_DIR).replace("\\", "/")


def ensure_episode_output_folder(ep) -> str:
    """Assign + create the named output folder for an Episode-like object."""
    taken: Set[str] = set()
    try:
        from app.state import state_manager

        for other in state_manager.episodes.values():
            if other.id == getattr(ep, "id", None):
                continue
            name = (getattr(other, "output_folder", None) or "").strip()
            if name:
                taken.add(name)
    except Exception:
        pass

    claimed = getattr(ep, "output_folder", None) or None
    folder = resolve_episode_folder(
        ep.id,
        getattr(ep, "title", "") or ep.id,
        claimed=claimed,
        taken=taken,
    )
    if getattr(ep, "output_folder", None) != folder:
        ep.output_folder = folder
    episode_dir(folder)
    write_episode_marker(folder, ep.id)
    return folder
