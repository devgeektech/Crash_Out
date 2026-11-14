"""
Editable character library overlay on top of personas.CHARACTERS.
Persists to characters/library.json; images stay as *_9x16.png.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from typing import Any, Dict, List, Optional

from app.paths import CHARACTERS_DIR
from app.personas import CHARACTERS

LIBRARY_PATH = os.path.join(CHARACTERS_DIR, "library.json")
CHAR_IDS = ("gary", "linda", "chris", "chloe")


def _seed_entry(char_id: str) -> Dict[str, Any]:
    base = CHARACTERS.get(char_id) or {}
    voice = dict(base.get("voice") or {})
    return {
        "id": char_id,
        "name": base.get("name") or char_id.title(),
        "age": base.get("age"),
        "role": base.get("role") or "",
        "archetype": base.get("archetype") or "",
        "description": base.get("psychological_profile") or "",
        "personality": base.get("mannerisms") or "",
        "visual_prompt": base.get("visual_prompt") or base.get("visual_short") or "",
        "image_file": f"{char_id}_9x16.png",
        "voice": {
            "tone": voice.get("tone") or "",
            "speed": voice.get("speed") or "1.0x",
            "pitch": voice.get("pitch") or "medium",
            "delivery": voice.get("delivery") or voice.get("audio_tag") or "",
            "sample_file": voice.get("sample_file") or "",
        },
        "updated_at": time.time(),
    }


def _default_library() -> Dict[str, Any]:
    return {
        "version": 1,
        "updated_at": time.time(),
        "characters": {cid: _seed_entry(cid) for cid in CHAR_IDS},
    }


def load_library() -> Dict[str, Any]:
    if not os.path.isfile(LIBRARY_PATH):
        data = _default_library()
        save_library(data)
        return data
    try:
        with open(LIBRARY_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        data = _default_library()
    chars = data.setdefault("characters", {})
    for cid in CHAR_IDS:
        if cid not in chars:
            chars[cid] = _seed_entry(cid)
    return data


def save_library(data: Dict[str, Any]) -> None:
    data["updated_at"] = time.time()
    os.makedirs(CHARACTERS_DIR, exist_ok=True)
    tmp = LIBRARY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, LIBRARY_PATH)


def list_characters() -> List[Dict[str, Any]]:
    lib = load_library()
    out = []
    for cid in CHAR_IDS:
        entry = dict(lib["characters"].get(cid) or _seed_entry(cid))
        entry["image_url"] = f"/characters/{entry.get('image_file') or f'{cid}_9x16.png'}"
        out.append(entry)
    return out


def get_character(char_id: str) -> Dict[str, Any]:
    cid = (char_id or "").lower()
    lib = load_library()
    entry = dict(lib["characters"].get(cid) or _seed_entry(cid))
    entry["image_url"] = f"/characters/{entry.get('image_file') or f'{cid}_9x16.png'}"
    return entry


def update_character(char_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    cid = (char_id or "").lower()
    if cid not in CHAR_IDS:
        raise ValueError(f"Unknown character: {char_id}")
    lib = load_library()
    entry = dict(lib["characters"].get(cid) or _seed_entry(cid))
    for key in (
        "name",
        "role",
        "archetype",
        "description",
        "personality",
        "visual_prompt",
    ):
        if key in patch and patch[key] is not None:
            entry[key] = str(patch[key])
    if "voice" in patch and isinstance(patch["voice"], dict):
        voice = dict(entry.get("voice") or {})
        for vk, vv in patch["voice"].items():
            if vv is not None:
                voice[str(vk)] = str(vv)
        entry["voice"] = voice
    entry["updated_at"] = time.time()
    lib["characters"][cid] = entry
    save_library(lib)
    return get_character(cid)


def save_character_image(char_id: str, src_path: str, *, ext: str = ".png") -> str:
    cid = (char_id or "").lower()
    if cid not in CHAR_IDS:
        raise ValueError(f"Unknown character: {char_id}")
    safe_ext = ext if ext.startswith(".") else f".{ext}"
    if safe_ext.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        safe_ext = ".png"
    dest_name = f"{cid}_9x16{safe_ext if safe_ext == '.png' else '.png'}"
    # Always store as *_9x16.png for Vidu/mock path consistency.
    dest_name = f"{cid}_9x16.png"
    dest = os.path.join(CHARACTERS_DIR, dest_name)
    shutil.copyfile(src_path, dest)
    lib = load_library()
    entry = dict(lib["characters"].get(cid) or _seed_entry(cid))
    entry["image_file"] = dest_name
    entry["updated_at"] = time.time()
    lib["characters"][cid] = entry
    save_library(lib)
    return dest_name


def character_prompt_overlay(char_id: str) -> Optional[str]:
    """Return library visual/personality text for prompt assembly."""
    entry = get_character(char_id)
    bits = [
        entry.get("visual_prompt") or "",
        entry.get("personality") or "",
        entry.get("description") or "",
    ]
    text = " ".join(b for b in bits if b).strip()
    return text or None
