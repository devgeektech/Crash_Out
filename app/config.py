"""
Crash Out configuration — Vidu Q4 Preview credentials + persona re-exports.
"""
import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv, set_key

from app.personas import (  # noqa: F401 — re-exported for existing imports
    CHARACTERS,
    EPISODE_HOA_VIOLATION,
    SCENE_COUNT,
    SCENE_DURATION_SEC,
    EPISODE_DURATION_SEC,
    VIDU_PROMPT_MAX_CHARS,
    get_vidu_system_style_prefix,
    get_vidu_character_persona_prompt,
)

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_PATH)


class PlatformCredentials(BaseModel):
    vidu_email: str = os.getenv("VIDU_EMAIL", "")
    vidu_api_key: str = os.getenv("VIDU_API_KEY", "")
    vidu_base_url: str = os.getenv("VIDU_BASE_URL", "https://api.vidu.com")
    vidu_model: str = os.getenv("VIDU_MODEL", "viduq4-preview")
    vidu_reference_model: str = os.getenv("VIDU_REFERENCE_MODEL", "viduq4-preview")
    vidu_resolution: str = os.getenv("VIDU_RESOLUTION", "720p")
    vidu_poll_timeout_sec: int = int(os.getenv("VIDU_POLL_TIMEOUT_SEC", "600"))
    vidu_prompt_max_chars: int = int(
        os.getenv("VIDU_PROMPT_MAX_CHARS", str(VIDU_PROMPT_MAX_CHARS))
    )

    # Agent 0 — live trend ingestion (all optional; public Reddit + pytrends work without keys)
    reddit_client_id: str = os.getenv("REDDIT_CLIENT_ID", "")
    reddit_client_secret: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    reddit_user_agent: str = os.getenv(
        "REDDIT_USER_AGENT", "CrashOutPOC/1.0 (Agent0 Trend Ingest)"
    )
    news_api_key: str = os.getenv("NEWS_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    video_aspect_ratio: str = "9:16"
    scene_duration_seconds: int = SCENE_DURATION_SEC
    total_scenes: int = SCENE_COUNT
    # Fixed attached script runtime (~55s); keep 60 as merge target ceiling.
    total_duration_seconds: int = 55
    fps: int = 24
    active_video_engine: str = "vidu"


config = PlatformCredentials()


def update_vidu_credentials(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    reference_model: Optional[str] = None,
    resolution: Optional[str] = None,
) -> None:
    """Update in-memory config and persist selected values to .env."""
    if api_key is not None:
        cleaned = api_key.strip()
        config.vidu_api_key = cleaned
        set_key(ENV_PATH, "VIDU_API_KEY", cleaned)
    if model is not None:
        cleaned = model.strip()
        config.vidu_model = cleaned
        set_key(ENV_PATH, "VIDU_MODEL", cleaned)
    if reference_model is not None:
        cleaned = reference_model.strip()
        config.vidu_reference_model = cleaned
        set_key(ENV_PATH, "VIDU_REFERENCE_MODEL", cleaned)
    if resolution is not None:
        cleaned = resolution.strip()
        config.vidu_resolution = cleaned
        set_key(ENV_PATH, "VIDU_RESOLUTION", cleaned)
