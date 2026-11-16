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


def parse_speed_hint(value: Any, default: float = 1.0) -> float:
    """Normalize legacy '1.15x' / strings into a 0–2 speed multiplier."""
    raw = str(value or "").strip().lower().replace("x", "")
    try:
        num = float(raw) if raw else float(default)
    except (TypeError, ValueError):
        num = float(default)
    return max(0.0, min(2.0, round(num, 2)))


def format_speed_hint(value: Any, default: float = 1.0) -> str:
    # Snap to 0.25 steps within 0–2; always show two decimals (default 1.00).
    stepped = round(parse_speed_hint(value, default) * 4) / 4
    stepped = max(0.0, min(2.0, stepped))
    return f"{stepped:.2f}"


PITCH_HINTS = ("low", "medium", "high")


def normalize_pitch_hint(value: Any, default: str = "medium") -> str:
    raw = str(value or default).strip().lower()
    return raw if raw in PITCH_HINTS else default


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
            "speed": format_speed_hint(voice.get("speed") or 1.0),
            "pitch": normalize_pitch_hint(voice.get("pitch") or "medium"),
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


def _cache_bust(path: str, *markers: Any) -> str:
    """Append ?v= so replaced images/audio show immediately (same filename)."""
    stamp = ""
    for m in markers:
        if m is None or m == "":
            continue
        try:
            stamp = str(int(float(m)))
        except (TypeError, ValueError):
            stamp = str(m)
        break
    if not stamp and path:
        abs_path = path if os.path.isabs(path) else os.path.join(CHARACTERS_DIR, os.path.basename(path))
        try:
            stamp = str(int(os.path.getmtime(abs_path)))
        except OSError:
            stamp = "1"
    return f"{path}?v={stamp}" if stamp else path


def _with_media_urls(entry: Dict[str, Any]) -> Dict[str, Any]:
    cid = entry.get("id") or ""
    out = dict(entry)
    voice = dict(out.get("voice") or {})
    voice["speed"] = format_speed_hint(voice.get("speed") or 1.0)
    voice["pitch"] = normalize_pitch_hint(voice.get("pitch") or "medium")
    out["voice"] = voice
    image_file = out.get("image_file") or f"{cid}_9x16.png"
    updated = out.get("updated_at")
    out["image_url"] = _cache_bust(f"/characters/{image_file}", updated)
    sample = str(voice.get("sample_file") or "").strip()
    if sample:
        out["audio_url"] = _cache_bust(f"/characters/{sample}", updated)
    else:
        out["audio_url"] = ""
    return out


def list_characters() -> List[Dict[str, Any]]:
    lib = load_library()
    out = []
    for cid in CHAR_IDS:
        entry = dict(lib["characters"].get(cid) or _seed_entry(cid))
        out.append(_with_media_urls(entry))
    return out


def get_character(char_id: str) -> Dict[str, Any]:
    cid = (char_id or "").lower()
    lib = load_library()
    entry = dict(lib["characters"].get(cid) or _seed_entry(cid))
    return _with_media_urls(entry)


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
            if vv is None:
                continue
            if str(vk) == "speed":
                voice["speed"] = format_speed_hint(vv)
            elif str(vk) == "pitch":
                voice["pitch"] = normalize_pitch_hint(vv)
            else:
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


_AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".webm", ".aac", ".mp4"}


def save_character_audio(char_id: str, src_path: str, *, ext: str = ".mp3") -> str:
    """Persist a voice reference sample for Vidu (characters/{id}_voice_sample.ext)."""
    cid = (char_id or "").lower()
    if cid not in CHAR_IDS:
        raise ValueError(f"Unknown character: {char_id}")
    safe_ext = (ext if ext.startswith(".") else f".{ext}").lower()
    if safe_ext == ".mpeg":
        safe_ext = ".mp3"
    if safe_ext not in _AUDIO_EXTS:
        raise ValueError("Unsupported audio type — use mp3, wav, m4a, ogg, or webm")
    dest_name = f"{cid}_voice_sample{safe_ext}"
    dest = os.path.join(CHARACTERS_DIR, dest_name)
    # Drop previous sample if extension changed.
    lib = load_library()
    entry = dict(lib["characters"].get(cid) or _seed_entry(cid))
    voice = dict(entry.get("voice") or {})
    old = str(voice.get("sample_file") or "").strip()
    if old and old != dest_name:
        old_path = os.path.join(CHARACTERS_DIR, old)
        if os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass
    shutil.copyfile(src_path, dest)
    voice["sample_file"] = dest_name
    entry["voice"] = voice
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
