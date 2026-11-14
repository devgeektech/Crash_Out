"""
Reusable prompt templates: character + scene + camera + dialogue combine.
Stored in characters/prompt_templates.json (shared studio asset).
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from app.studio.characters import get_character
from app.paths import CHARACTERS_DIR

TEMPLATES_PATH = os.path.join(CHARACTERS_DIR, "prompt_templates.json")

DEFAULT_TEMPLATES = [
    {
        "id": "kitchen_crashout",
        "name": "Kitchen Crash-Out",
        "scene_type": "kitchen",
        "camera": "9:16 vertical, snappy cuts, close-ups on stress-watch then wide kitchen",
        "scene_instructions": (
            "Suburban kitchen; white cabinets, marble island. Escalate from decorum to crash-out. "
            "No text overlays. Flat vector cutout, bold outlines."
        ),
        "dialogue_hint": "Short overlapping family arguments; Chloe may livestream.",
    },
    {
        "id": "driveway_optics",
        "name": "Driveway Optics Crisis",
        "scene_type": "driveway",
        "camera": "9:16, wide driveway then close on Linda's Stanley / Gary's face flush",
        "scene_instructions": (
            "Suburban driveway / HOA sightline. Status anxiety and neighbor optics. "
            "Keep character looks locked to refs."
        ),
        "dialogue_hint": "Linda optics panic; Gary tariff rant; kids rate engagement.",
    },
    {
        "id": "continuity_cut",
        "name": "Continuity Cut (from prior frame)",
        "scene_type": "continuity",
        "camera": "Match previous clip final frame; continue action without redesign",
        "scene_instructions": (
            "Continue DIRECTLY from previous clip final frame. Identical kitchen layout, "
            "outfits, faces. No extras."
        ),
        "dialogue_hint": "Pick up mid-argument; escalate.",
    },
]


def _default() -> Dict[str, Any]:
    return {"version": 1, "updated_at": time.time(), "templates": DEFAULT_TEMPLATES}


def load_templates() -> Dict[str, Any]:
    if not os.path.isfile(TEMPLATES_PATH):
        data = _default()
        save_templates(data)
        return data
    try:
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not data.get("templates"):
            data["templates"] = list(DEFAULT_TEMPLATES)
        return data
    except Exception:
        return _default()


def save_templates(data: Dict[str, Any]) -> None:
    data["updated_at"] = time.time()
    os.makedirs(CHARACTERS_DIR, exist_ok=True)
    tmp = TEMPLATES_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, TEMPLATES_PATH)


def list_templates() -> List[Dict[str, Any]]:
    return list(load_templates().get("templates") or [])


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    for t in list_templates():
        if t.get("id") == template_id:
            return dict(t)
    return None


def upsert_template(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = load_templates()
    templates = list(data.get("templates") or [])
    tid = (payload.get("id") or f"tpl_{int(time.time())}").strip()
    entry = {
        "id": tid,
        "name": payload.get("name") or tid,
        "scene_type": payload.get("scene_type") or "general",
        "camera": payload.get("camera") or "",
        "scene_instructions": payload.get("scene_instructions") or "",
        "dialogue_hint": payload.get("dialogue_hint") or "",
    }
    replaced = False
    for i, t in enumerate(templates):
        if t.get("id") == tid:
            templates[i] = entry
            replaced = True
            break
    if not replaced:
        templates.append(entry)
    data["templates"] = templates
    save_templates(data)
    return entry


def combine_prompt(
    *,
    template_id: str,
    character_ids: List[str],
    dialogue_lines: Optional[List[Dict[str, Any]]] = None,
    extra: str = "",
) -> str:
    """Assemble character + scene + camera + dialogue into one prompt draft."""
    tpl = get_template(template_id) or DEFAULT_TEMPLATES[0]
    char_blocks = []
    for cid in character_ids:
        c = get_character(cid)
        char_blocks.append(
            f"{c.get('name')} ({cid}): {c.get('visual_prompt') or c.get('description') or ''}"
        )
    dialogue_bits = []
    for line in dialogue_lines or []:
        cid = (line.get("character") or "gary").lower()
        voice = get_character(cid).get("voice") or {}
        tag = (line.get("voice_tag") or voice.get("delivery") or voice.get("audio_tag") or "").strip()
        who = tag or f"{(line.get('character') or 'gary').capitalize()}:"
        if tag and not who.endswith(":"):
            who = f"{who}:"
        text = line.get("text") or ""
        ts = line.get("time_start")
        te = line.get("time_end")
        timing = f" [{ts}-{te}s]" if ts is not None else ""
        dialogue_bits.append(f'{who}{timing} "{text}"')
    voice_notes = []
    for cid in character_ids:
        c = get_character(cid)
        v = c.get("voice") or {}
        tag = (v.get("delivery") or v.get("audio_tag") or "").strip()
        tone = (v.get("tone") or "").strip()
        if tag or tone:
            voice_notes.append(f"{c.get('name')}: {tag} {tone}".strip())
    parts = [
        "15s, 9:16 vertical satirical 2D sitcom CRASH OUT. Native dialogue audio in-clip.",
        tpl.get("scene_instructions") or "",
        f"CAMERA: {tpl.get('camera') or ''}",
        "CHARACTERS:\n" + "\n".join(char_blocks),
    ]
    if voice_notes:
        parts.append("VIDU AUDIO DIRECTION:\n" + "\n".join(voice_notes))
    if dialogue_bits:
        parts.append("DIALOGUE (spoken by Vidu):\n" + "\n".join(dialogue_bits))
    elif tpl.get("dialogue_hint"):
        parts.append(f"DIALOGUE HINT: {tpl.get('dialogue_hint')}")
    if extra.strip():
        parts.append(extra.strip())
    return "\n\n".join(p for p in parts if p).strip()
