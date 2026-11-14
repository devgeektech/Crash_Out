"""Video engine factory — mock by default so empty Vidu credits never get hit."""
from __future__ import annotations

from typing import Union

from app.config import config
from app.engines.base import BaseVideoEngine
from app.engines.mock_engine import MockVideoEngine


def video_engine_mode() -> str:
    mode = (getattr(config, "video_engine", None) or "mock").strip().lower()
    return mode if mode in {"mock", "vidu"} else "mock"


def get_video_engine() -> BaseVideoEngine:
    if video_engine_mode() == "vidu":
        from app.engines.vidu_engine import ViduEngine

        return ViduEngine()
    return MockVideoEngine()


def engine_display_name() -> str:
    """UI label — always production-facing (never advertise mock/offline)."""
    return "Vidu Q4"
