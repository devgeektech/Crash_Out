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
    """
    parts = []
    ordered: List[str] = []
    for idx, cid in enumerate(cast, start=1):
        c = CHARACTERS.get(cid)
        if not c:
            continue
        ordered.append(cid)
        parts.append(f"[@reference_image_{idx}]={c['name']}")
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


def build_scene_prompt(
    scene_data: Dict[str, Any],
    cast: Sequence[str] | None = None,
    max_chars: int = VIDU_PROMPT_MAX_CHARS,
) -> str:
    """
    Build a single-scene Vidu prompt under max_chars.

    Budget strategy:
      style + refs + action + camera + dialogue + sfx
      Dialogue is trimmed last-in-first-out if over budget.
    """
    # Human-editable full prompt files: send complete text as-is.
    source_prompt = (scene_data.get("source_prompt") or "").strip()
    if source_prompt:
        return source_prompt

    cast_ids = list(cast) if cast is not None else characters_in_scene(scene_data)
    bind_line, ordered = build_reference_bindings(cast_ids)

    title = scene_data.get("title") or f"Scene {scene_data.get('scene_id', 1)}"
    action = scene_data.get("scene_action") or ""
    camera = scene_data.get("camera_cue") or ""
    sfx = scene_data.get("sfx") or ""
    dialogue = scene_data.get("dialogue") or []

    header = (
        f"{STYLE_SHORT} Scene: {title}. {bind_line} "
        f"Action: {action} Camera: {camera} "
        "Native spoken audio in video."
    ).strip()

    dialogue_lines: List[str] = []
    for line in dialogue:
        cid = str(line.get("character", "gary")).lower()
        c = CHARACTERS.get(cid, CHARACTERS["gary"])
        name = c["name"]
        text = str(line.get("text", "")).strip()
        if not text:
            continue
        dialogue_lines.append(f'{name}: "{text}"')

    sfx_line = f"SFX: {sfx}." if sfx else ""

    def assemble(d_lines: List[str]) -> str:
        body = " Dialogue: " + " ".join(d_lines) if d_lines else ""
        prompt = f"{header}{body} {sfx_line}".strip()
        return " ".join(prompt.split())

    prompt = assemble(dialogue_lines)
    # Drop trailing dialogue lines until under budget.
    while len(prompt) > max_chars and dialogue_lines:
        dialogue_lines.pop()
        prompt = assemble(dialogue_lines)

    if len(prompt) > max_chars:
        prompt = _truncate(prompt, max_chars)

    return prompt


def prompt_char_count(prompt: str) -> int:
    return len(prompt or "")


def assert_prompt_budget(prompt: str, max_chars: int = VIDU_PROMPT_MAX_CHARS) -> None:
    if len(prompt) > max_chars:
        raise ValueError(
            f"Vidu prompt exceeds {max_chars} chars (got {len(prompt)})."
        )
