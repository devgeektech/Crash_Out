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
# Shared character reference art — outside outputs/ (not episode media).
CHARACTERS_DIR = os.path.join(PROJECT_ROOT, "characters")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CHARACTERS_DIR, exist_ok=True)

_RESERVED_DIR_NAMES = {"clean_characters", "characters"}


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
    path = os.path.join(OUTPUT_DIR, folder_name)
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
    folder = os.path.join(OUTPUT_DIR, folder_name)
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
    return f"{folder_name}/scene_{int(scene_id)}.mp4"


def scene_abspath(folder_name: str, scene_id: int) -> str:
    return os.path.join(episode_dir(folder_name), f"scene_{int(scene_id)}.mp4")


def merged_relpath(folder_name: str) -> str:
    return f"{folder_name}/merged_60s.mp4"


def merged_abspath(folder_name: str) -> str:
    return os.path.join(episode_dir(folder_name), "merged_60s.mp4")


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
