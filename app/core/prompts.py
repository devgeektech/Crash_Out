"""
Compact Vidu Q4 Preview prompt builder.

Hard rule: final prompt text must be <= VIDU_PROMPT_MAX_CHARS (2000).
Reference PNGs carry visual identity — character bible blocks are stripped for API calls.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Tuple

from app.core.personas import (
    CHARACTERS,
    STYLE_SHORT,
    VIDU_PROMPT_MAX_CHARS,
    characters_in_scene,
)


def _get_char(cid: str) -> Dict[str, Any]:
    try:
        from app.studio.characters import get_character
        return get_character(cid)
    except Exception:
        return CHARACTERS.get(cid) or {}


def _truncate(text: str, limit: int, *, collapse: bool = True) -> str:
    if collapse:
        text = " ".join((text or "").split())
    else:
        text = text or ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def strip_character_bible(text: str) -> str:
    """
    Remove long CHARACTERS / CHARACTER LOCK sections from human-editable prompts.
    Looks stay locked via Vidu reference images instead.
    """
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(
        r"(?is)\n?\s*\*{0,2}CHARACTER LOCK:\*{0,2}\s*\n.*?(?=\n\s*\*{0,2}TIMELINE)",
        "\n",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)\n?\s*\*{0,2}CHARACTERS?[^\n]*\n.*?(?=\n\s*\*{0,2}TIMELINE|\n\s*AUDIO:|\n\s*\*{0,2}PERFORMANCE|\n\s*\*{0,2}END)",
        "\n",
        cleaned,
    )
    # Collapse excess blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def build_reference_bindings(cast: Sequence[str]) -> Tuple[str, List[str]]:
    """
    Map cast order to Vidu [@reference_image_n] tags.
    Returns (binding_line, cast_ids_in_order).
    Pulls dynamic character overrides from characters/library.json.
    """
    parts = []
    ordered: List[str] = []
    for idx, cid in enumerate(cast, start=1):
        char_data = _get_char(cid)
        c_name = char_data.get("name") or (CHARACTERS.get(cid) or {}).get("name")
        if not c_name:
            continue
        ordered.append(cid)
        parts.append(f"[@reference_image_{idx}]={c_name}")
    if not parts:
        return "", []
    return (
        "Match reference images exactly (no redesign/outfit changes): "
        + ", ".join(parts)
        + ".",
        ordered,
    )


def prepare_api_prompt(
    scene_data: Dict[str, Any],
    cast: Sequence[str] | None = None,
    max_chars: int = VIDU_PROMPT_MAX_CHARS,
) -> str:
    """Prompt text actually sent to Vidu — full editable prompt, unmodified."""
    cast_ids = list(cast) if cast is not None else characters_in_scene(scene_data)
    source = (scene_data.get("source_prompt") or scene_data.get("vidu_prompt") or "").strip()
    if source:
        # Send the complete prompt as edited — no CHARACTER strip / no prepend.
        return source
    return build_scene_prompt(scene_data, cast=cast_ids, max_chars=max_chars)


def format_vidu_prompt(text: str) -> str:
    """Format any raw Vidu prompt into a beautifully structured, readable prompt with camera cuts and sounds."""
    if not text:
        return ""
    text = text.strip()

    import re

    # 1. Header (Style, Scene, Match reference images)
    header_m = re.search(r'^(.*?)(?=\bAction\s*:|\bCamera\s*:|\bDialogue\s*:|\bSFX\s*:|$)', text, re.DOTALL | re.IGNORECASE)
    header = header_m.group(1).strip() if header_m else ''
    
    # Split by Match reference images if present
    ref_m = re.search(r'(Match reference images.*)', header, re.DOTALL | re.IGNORECASE)
    if ref_m:
        style_scene = header[:ref_m.start()].strip()
        refs = ref_m.group(1).strip()
    else:
        style_scene = header
        refs = ''

    if "Scene:" in style_scene:
        parts = re.split(r'\bScene\s*:\s*', style_scene, maxsplit=1)
        if len(parts) == 2:
            style_part = parts[0].strip()
            scene_title = parts[1].strip()
            style_scene = f"{style_part}\nScene: {scene_title}" if style_part else f"Scene: {scene_title}"

    # 2. Action
    act_m = re.search(r'\bAction\s*:\s*(.*?)(?=\bCamera\s*:|\bNative spoken audio|\bDialogue\s*:|\bSFX\s*:|$)', text, re.DOTALL | re.IGNORECASE)
    action = act_m.group(1).strip() if act_m else ''

    # 3. Camera
    cam_m = re.search(r'\bCamera\s*:\s*(.*?)(?=\bNative spoken audio|\bDialogue\s*:|\bSFX\s*:|$)', text, re.DOTALL | re.IGNORECASE)
    camera = cam_m.group(1).strip() if cam_m else ''

    # 4. Dialogue with inline camera movements, gestures, and sounds
    diag_m = re.search(r'\bDialogue:\s*(.*?)(?=(?:\n\s*|(?<!\[)\s+)SFX\s*:|$)', text, re.DOTALL | re.IGNORECASE)
    dialogue_block = ''
    if diag_m:
        diag_text = diag_m.group(1).strip()
        pattern = re.compile(
            r'(?:\[(?:Camera|Shot|Angle)?\s*:?\s*(?P<camera>[^\]]+)\]\s*)?'
            r'(?P<character>[A-Za-z0-9_-]+)\s*:\s*'
            r'(?:\((?P<staging>[^)]+)\)\s*)?'
            r'["\u201c](?P<text>[^"\u201d]+)["\u201d]'
            r'(?:\s*\[(?:SFX|Sound)\s*:\s*(?P<sfx>[^\]]+)\])?',
            re.DOTALL | re.IGNORECASE
        )
        matches = list(pattern.finditer(diag_text))
        if matches:
            formatted_turns = []
            for m in matches:
                char = m.group("character").strip()
                if char.lower() in ("dialogue", "camera", "action", "sfx", "native", "scene"):
                    continue
                cam = (m.group("camera") or "").strip()
                staging = (m.group("staging") or "").strip()
                t_val = (m.group("text") or "").strip()
                s_val = (m.group("sfx") or "").strip()

                turn_str = ""
                if cam:
                    turn_str += f"[{cam}]\n"
                
                staging_str = f"({staging}) " if staging else ""
                turn_str += f'{char.capitalize()}: {staging_str}"{t_val}"'
                if s_val:
                    sfx_clean = s_val if s_val.lower().startswith("sfx:") or s_val.lower().startswith("sound:") else f"SFX: {s_val}"
                    turn_str += f" [{sfx_clean}]"
                formatted_turns.append(turn_str)
            dialogue_block = "Dialogue:\n" + "\n\n".join(formatted_turns)
        else:
            dialogue_block = f"Dialogue:\n{diag_text}"

    # 5. Master SFX (ensure it's not matching an inline [SFX: ...])
    sfx_m = re.search(r'(?:^|\n|(?<!\[)\s+)\bSFX\s*:\s*(?!.*\bSFX\s*:)(.*?)$', text, re.DOTALL | re.IGNORECASE)
    if not sfx_m:
        sfx_m = re.search(r'(?<!\[)\bSFX\s*:\s*([^\[\n]+(?:\.[^\[\n]+)*?)$', text, re.DOTALL | re.IGNORECASE)
    sfx = sfx_m.group(1).strip().rstrip('.') if sfx_m else ''

    sections = []
    if style_scene:
        sections.append(style_scene)
    if refs:
        sections.append(refs)
    if action:
        sections.append(f'Action: {action}')
    if camera:
        sections.append(f'Camera: {camera}\nNative spoken audio in video.')
    elif 'native spoken audio' in text.lower():
        sections.append('Native spoken audio in video.')
    if dialogue_block:
        sections.append(dialogue_block)
    if sfx:
        sections.append(f'SFX: {sfx}.')

    return '\n\n'.join(sections).strip()


def build_scene_prompt(
    scene_data: Dict[str, Any],
    cast: Sequence[str] | None = None,
    max_chars: int = VIDU_PROMPT_MAX_CHARS,
) -> str:
    """
    Build a rich, cinematic, well-structured single-scene Vidu prompt under max_chars (2000).
    Includes per-character camera movements, physical gestures, and sound cues with dialogue.
    """
    source_prompt = (scene_data.get("source_prompt") or "").strip()
    if source_prompt:
        return format_vidu_prompt(source_prompt)

    cast_ids = list(cast) if cast is not None else characters_in_scene(scene_data)
    bind_line, ordered = build_reference_bindings(cast_ids)

    title = scene_data.get("title") or f"Scene {scene_data.get('scene_id', 1)}"
    action = str(scene_data.get("scene_action") or "").strip()
    camera = str(scene_data.get("camera_cue") or "").strip()
    sfx = str(scene_data.get("sfx") or "").strip()
    dialogue = scene_data.get("dialogue") or []

    dialogue_lines: List[str] = []
    for line in dialogue:
        cid = str(line.get("character", "gary")).lower()
        char_data = _get_char(cid)
        name = char_data.get("name") or (CHARACTERS.get(cid) or {}).get("name") or cid.capitalize()
        text = str(line.get("text", "")).strip()
        if not text:
            continue
        cam = str(line.get("camera_cue") or "").strip()
        act = str(line.get("action") or "").strip()
        vtag = str(line.get("voice_tag") or line.get("emotion") or "").strip()
        turn_sfx = str(line.get("sfx") or "").strip()

        turn_parts = []
        if cam:
            cam_clean = cam if cam.startswith("[") else f"[{cam}]"
            turn_parts.append(cam_clean)

        # Remove redundant character name prefix from action if present (e.g. "Gary snaps..." -> "snaps...")
        if act and act.split()[0].lower() in (cid, name.lower()):
            act_words = act.split()[1:]
            act_clean = " ".join(act_words)
        else:
            act_clean = act

        staging_parts = []
        if vtag:
            staging_parts.append(vtag)
        if act_clean and act_clean != vtag:
            staging_parts.append(act_clean.rstrip("."))
        staging_str = f"({', '.join(staging_parts)}) " if staging_parts else ""

        line_str = f'{name}: {staging_str}"{text}"'
        if turn_sfx and not turn_sfx.lower().startswith("sfx:"):
            line_str += f" [SFX: {turn_sfx}]"
        elif turn_sfx:
            line_str += f" [{turn_sfx}]"

        turn_parts.append(line_str)
        dialogue_lines.append("\n".join(turn_parts))

    def assemble(d_lines: List[str]) -> str:
        sections = []

        # 1. Style & Scene
        sections.append(f"{STYLE_SHORT}\nScene: {title}.")

        # 2. Reference Bindings
        if bind_line:
            sections.append(bind_line)

        # 3. Action
        if action:
            sections.append(f"Action: {action}")

        # 4. Camera & Audio
        cam_part = f"Camera: {camera}" if camera else "Camera: Dynamic 9:16 vertical framing."
        sections.append(f"{cam_part}\nNative spoken audio in video.")

        # 5. Dialogue with inline camera movements, gestures, and sounds
        if d_lines:
            dialogue_block = "Dialogue:\n" + "\n\n".join(d_lines)
            sections.append(dialogue_block)

        # 6. SFX
        if sfx:
            sfx_clean = sfx.rstrip(".")
            sections.append(f"SFX: {sfx_clean}.")

        return "\n\n".join(sections).strip()

    prompt = assemble(dialogue_lines)
    # Drop trailing dialogue lines until under budget.
    while len(prompt) > max_chars and dialogue_lines:
        dialogue_lines.pop()
        prompt = assemble(dialogue_lines)

    if len(prompt) > max_chars:
        prompt = _truncate(prompt, max_chars, collapse=False)

    return prompt


def prompt_char_count(prompt: str) -> int:
    return len(prompt or "")


def assert_prompt_budget(prompt: str, max_chars: int = VIDU_PROMPT_MAX_CHARS) -> None:
    if len(prompt) > max_chars:
        raise ValueError(
            f"Vidu prompt exceeds {max_chars} chars (got {len(prompt)})."
        )
