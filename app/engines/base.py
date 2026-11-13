"""
Base abstract class for the Vidu video generation engine.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel


class VideoJobResult(BaseModel):
    engine: str
    job_id: str
    status: str  # completed | processing | queued | failed
    video_url: Optional[str] = None
    local_path: Optional[str] = None
    latency_sec: float = 0.0
    cost_estimate_usd: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class BaseVideoEngine(ABC):
    def __init__(self, name: str, platform_id: str):
        self.name = name
        self.platform_id = platform_id

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """Verify API connectivity and authentication credentials."""
        pass

    @abstractmethod
    def generate_scene_video(
        self,
        scene_data: Dict[str, Any],
        output_filename: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> VideoJobResult:
        """Generate a timed scene video with native audio."""
        pass

    @abstractmethod
    def get_specs(self) -> Dict[str, Any]:
        """Return engine capabilities and configuration."""
        pass
