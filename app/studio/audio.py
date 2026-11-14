"""
Vidu-native audio helpers.

Spoken dialogue is generated inside Vidu with each clip (`audio: true`).
Character voice fields are prompt direction / audio tags — not a separate TTS API.
Dialogue timing rows sync script timestamps into editable prompt-friendly rows.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.studio.characters import get_character, list_characters
from app.state import Episode


def voice_library_snapshot() -> List[Dict[str, Any]]:
    """Vidu audio-direction tags from the character library."""
    out = []
    for c in list_characters():
        voice = dict(c.get("voice") or {})
        out.append(
            {
                "character_id": c["id"],
                "name": c.get("name"),
                "tone": voice.get("tone") or "",
                "pitch": voice.get("pitch") or "medium",
                "speed": voice.get("speed") or "1.0x",
                "delivery": voice.get("delivery") or voice.get("audio_tag") or "",
            }
        )
    return out


def sync_dialogue_timing_from_script(ep: Episode) -> List[Dict[str, Any]]:
    """Build editable timing rows from script dialogue (for Vidu timeline prompts)."""
    rows: List[Dict[str, Any]] = []
    for sc in (ep.script or {}).get("scenes") or []:
        sid = int(sc.get("scene_id") or 0)
        for i, line in enumerate(sc.get("dialogue") or []):
            char_id = (line.get("character") or "gary").lower()
            voice = get_character(char_id).get("voice") or {}
            rows.append(
                {
                    "id": f"dlg_{sid}_{i}",
                    "scene_id": sid,
                    "character": char_id,
                    "text": line.get("text") or "",
                    "time_start": float(line.get("time_start") or 0),
                    "time_end": float(line.get("time_end") or 0),
                    "pause_after_sec": float(line.get("pause_after_sec") or 0.15),
                    "audio_tag": voice.get("delivery") or voice.get("audio_tag") or "",
                    "speed": voice.get("speed") or "1.0x",
                }
            )
    ep.dialogue_timing = rows
    return rows


def update_dialogue_timing_row(ep: Episode, row_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rows = list(ep.dialogue_timing or [])
    if not rows:
        rows = sync_dialogue_timing_from_script(ep)
    for row in rows:
        if row.get("id") == row_id:
            for k in ("time_start", "time_end", "pause_after_sec"):
                if k in patch and patch[k] is not None:
                    row[k] = float(patch[k])
            if "speed" in patch and patch["speed"] is not None:
                row["speed"] = str(patch["speed"])
            if "text" in patch and patch["text"] is not None:
                row["text"] = str(patch["text"])
                _mirror_text_to_script(ep, row)
            ep.dialogue_timing = rows
            return row
    return None


def _mirror_text_to_script(ep: Episode, row: Dict[str, Any]) -> None:
    if not ep.script:
        return
    sid = int(row.get("scene_id") or 0)
    for sc in ep.script.get("scenes") or []:
        if int(sc.get("scene_id") or 0) != sid:
            continue
        for i, line in enumerate(sc.get("dialogue") or []):
            if f"dlg_{sid}_{i}" == row.get("id"):
                line["text"] = row.get("text") or ""
                line["time_start"] = row.get("time_start")
                line["time_end"] = row.get("time_end")
                line["pause_after_sec"] = row.get("pause_after_sec")
                return
