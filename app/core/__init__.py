"""Core domain models, personas, prompts, and catalog definitions."""
from app.core.personas import (
    CHARACTERS,
    EPISODE_DURATION_SEC,
    EPISODE_HOA_VIOLATION,
    SCENE_COUNT,
    SCENE_DURATION_SEC,
    VIDU_PROMPT_MAX_CHARS,
    get_vidu_character_persona_prompt,
    get_vidu_system_style_prefix,
)
from app.core.prompts import (
    build_scene_prompt,
    prepare_api_prompt,
    prompt_char_count,
)
from app.core.catalog import (
    VIDEO_CATALOG,
    add_manual_catalog_video,
    concepts_for_catalog,
    delete_manual_catalog_video,
    get_catalog_item,
    get_hoa_q4_prompt_episode,
    list_catalog_items,
    refresh_hoa_q4_prompt_episode,
    update_catalog_concept,
    update_custom_scene_prompt,
)

__all__ = [
    "CHARACTERS",
    "EPISODE_DURATION_SEC",
    "EPISODE_HOA_VIOLATION",
    "SCENE_COUNT",
    "SCENE_DURATION_SEC",
    "VIDU_PROMPT_MAX_CHARS",
    "get_vidu_character_persona_prompt",
    "get_vidu_system_style_prefix",
    "build_scene_prompt",
    "prepare_api_prompt",
    "prompt_char_count",
    "VIDEO_CATALOG",
    "add_manual_catalog_video",
    "concepts_for_catalog",
    "delete_manual_catalog_video",
    "get_catalog_item",
    "get_hoa_q4_prompt_episode",
    "list_catalog_items",
    "refresh_hoa_q4_prompt_episode",
    "update_catalog_concept",
    "update_custom_scene_prompt",
]
