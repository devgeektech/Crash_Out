"""
Offline mock video engine — never calls Vidu.
Produces a short 9:16 placeholder MP4 via FFmpeg lavfi.
"""
from __future__ import annotations

import os
import subprocess
import time
import uuid
from typing import Any, Dict, Optional

import imageio_ffmpeg

from app.engines.base import BaseVideoEngine, VideoJobResult
from app.paths import OUTPUT_DIR, public_url
from app.personas import SCENE_DURATION_SEC


class MockVideoEngine(BaseVideoEngine):
    def __init__(self):
        super().__init__(name="Mock Video Engine", platform_id="mock")
        self.duration_sec = SCENE_DURATION_SEC

    def test_connection(self) -> Dict[str, Any]:
        return {
            "connected": True,
            "platform": "Vidu Q4",
            "model": "local-preview",
            "authenticated": True,
            "latency_sec": 0.0,
            "message": "Studio engine ready.",
            "prompt_max_chars": 2000,
        }

    def get_specs(self) -> Dict[str, Any]:
        return {
            "engine": "mock",
            "aspect_ratio": "9:16",
            "resolution": "720x1280",
            "duration_sec": self.duration_sec,
            "credits": False,
        }

    def generate_scene_video(
        self,
        scene_data: Dict[str, Any],
        output_filename: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> VideoJobResult:
        start = time.time()
        sc_id = int(scene_data.get("scene_id") or 1)
        title = str(scene_data.get("title") or f"Scene {sc_id}")
        duration = int(
            (options or {}).get("duration_sec")
            or scene_data.get("duration_sec")
            or self.duration_sec
        )
        duration = max(3, min(duration, 16))

        abs_path = output_filename
        if not os.path.isabs(abs_path):
            abs_path = os.path.join(OUTPUT_DIR, output_filename.replace("/", os.sep))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        label = title.replace(":", " -").replace("'", "")[:48]
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        # Solid vertical placeholder + silent audio (no network).
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x1e293b:s=720x1280:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=mono:sample_rate=44100",
            "-vf",
            (
                f"drawtext=text='MOCK SCENE {sc_id}':fontsize=48:fontcolor=white:"
                f"x=(w-text_w)/2:y=(h-text_h)/2-40,"
                f"drawtext=text='{label}':fontsize=28:fontcolor=0xf8fafc:"
                f"x=(w-text_w)/2:y=(h-text_h)/2+40"
            ),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            "-t",
            str(duration),
            abs_path,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0 or not os.path.isfile(abs_path):
                # Fallback without drawtext (some FFmpeg builds lack libfreetype).
                cmd_plain = [
                    ffmpeg,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=0x334155:s=720x1280:d={duration}",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=mono:sample_rate=44100",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-shortest",
                    "-t",
                    str(duration),
                    abs_path,
                ]
                proc2 = subprocess.run(cmd_plain, capture_output=True, text=True, timeout=60)
                if proc2.returncode != 0 or not os.path.isfile(abs_path):
                    err = (proc2.stderr or proc.stderr or "mock ffmpeg failed")[-400:]
                    return VideoJobResult(
                        engine="mock",
                        job_id=f"mock_fail_{uuid.uuid4().hex[:8]}",
                        status="failed",
                        latency_sec=round(time.time() - start, 2),
                        error=err,
                    )
        except Exception as exc:
            return VideoJobResult(
                engine="mock",
                job_id=f"mock_fail_{uuid.uuid4().hex[:8]}",
                status="failed",
                latency_sec=round(time.time() - start, 2),
                error=str(exc),
            )

        rel = os.path.relpath(abs_path, OUTPUT_DIR).replace("\\", "/")
        return VideoJobResult(
            engine="mock",
            job_id=f"mock_{uuid.uuid4().hex[:10]}",
            status="completed",
            video_url=public_url(rel),
            local_path=abs_path,
            latency_sec=round(time.time() - start, 2),
            cost_estimate_usd=0.0,
            metadata={
                "mode": "mock",
                "duration_sec": duration,
                "credits": 0,
                "scene_id": sc_id,
            },
        )
