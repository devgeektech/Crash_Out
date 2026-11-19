"""
Vidu AI video engine — Vidu Q4 Preview (Video) only.

Q4 Preview has no text-to-video. We use:
  POST /ent/v2/reference2video  (character PNGs + prompt <= 2000 chars)
  GET  /ent/v2/tasks/{id}/creations

Each episode = 4 equal ~15s scenes, then FFmpeg merge to 40–60s master.
"""
from __future__ import annotations

import base64
import mimetypes
import os
import time
from typing import Any, Dict, List, Optional

import requests

from app.config import config
from app.engines.base import BaseVideoEngine, VideoJobResult
from app.paths import CHARACTERS_DIR, OUTPUT_DIR, public_url
from app.core.personas import (
    CHARACTERS,
    SCENE_DURATION_SEC,
    VIDU_PROMPT_MAX_CHARS,
    characters_in_scene,
    get_vidu_character_persona_prompt,
)
from app.core.prompts import build_scene_prompt, prepare_api_prompt

CHAR_DIR = CHARACTERS_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CHAR_DIR, exist_ok=True)

POLL_INTERVAL_SEC = 5
Q4_MODEL = "viduq4-preview"
MAX_REFERENCE_IMAGES = 7  # stay well under Q4's 15 + keep request body small


class ViduEngine(BaseVideoEngine):
    def __init__(self):
        super().__init__(name="Vidu AI (Q4 Preview Video)", platform_id="vidu")
        self.base_url = config.vidu_base_url.rstrip("/")
        self.api_key = (config.vidu_api_key or "").strip()
        self.account_email = config.vidu_email
        self.model = (config.vidu_model or Q4_MODEL).strip() or Q4_MODEL
        self.reference_model = (
            (config.vidu_reference_model or self.model).strip() or self.model
        )
        self.resolution = config.vidu_resolution
        self.aspect_ratio = config.video_aspect_ratio
        self.poll_timeout_sec = config.vidu_poll_timeout_sec
        self.prompt_max_chars = int(
            getattr(config, "vidu_prompt_max_chars", VIDU_PROMPT_MAX_CHARS)
        )

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise RuntimeError(
                "VIDU_API_KEY is missing. Add it in .env or studio settings."
            )
        return {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.api_key}",
            "User-Agent": "CrashOut-Pipeline/3.1-Q4",
        }

    def test_connection(self) -> Dict[str, Any]:
        start = time.time()
        if not self.api_key:
            return {
                "connected": False,
                "platform": "Vidu AI",
                "model": self.model,
                "authenticated": False,
                "latency_sec": 0.0,
                "message": "No VIDU_API_KEY configured.",
                "prompt_max_chars": self.prompt_max_chars,
            }
        try:
            res = requests.get(
                f"{self.base_url}/ent/v2/tasks/healthcheck-probe/creations",
                headers=self._get_headers(),
                timeout=10,
            )
            latency = round(time.time() - start, 3)
            authenticated = res.status_code not in (401, 403)
            return {
                "connected": True,
                "platform": "Vidu AI",
                "model": self.model,
                "reference_model": self.reference_model,
                "status_code": res.status_code,
                "authenticated": authenticated,
                "latency_sec": latency,
                "prompt_max_chars": self.prompt_max_chars,
                "scene_duration_sec": SCENE_DURATION_SEC,
                "account": self.account_email,
                "message": (
                    f"Vidu Q4 Preview reachable. Auth "
                    f"{'OK' if authenticated else 'FAILED'}."
                ),
            }
        except Exception as exc:
            return {
                "connected": False,
                "platform": "Vidu AI",
                "model": self.model,
                "authenticated": False,
                "latency_sec": round(time.time() - start, 3),
                "error": str(exc),
                "message": "Could not reach Vidu API.",
            }

    def build_vidu_prompt(
        self, character_id: str, scene_action: str = "", script_text: str = ""
    ) -> str:
        return get_vidu_character_persona_prompt(character_id, script_text)[
            : self.prompt_max_chars
        ]

    def build_scene_prompt(self, scene_data: Dict[str, Any]) -> str:
        # Editable source prompts are sent complete (no strip / no truncate).
        source = (scene_data.get("source_prompt") or "").strip()
        if source:
            return source
        cast = characters_in_scene(scene_data)
        prompt = prepare_api_prompt(
            scene_data, cast=cast, max_chars=self.prompt_max_chars
        ) or scene_data.get("vidu_prompt") or build_scene_prompt(
            scene_data, cast=cast, max_chars=self.prompt_max_chars
        )
        return prompt[: self.prompt_max_chars]

    def _resolve_character_image(self, character_id: str) -> Optional[str]:
        cid = character_id.lower()
        candidates = [
            os.path.join(CHAR_DIR, f"{cid}_9x16.png"),
            # Legacy fallbacks (pre-dedupe) + static pack.
            os.path.join(CHAR_DIR, f"{cid}.png"),
            os.path.join(CHAR_DIR, f"{cid}_full.png"),
            os.path.join(CHAR_DIR, f"{cid}_avatar.png"),
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "static",
                "assets",
                "characters",
                f"{cid}.png",
            ),
        ]
        for path in candidates:
            if path and os.path.exists(path) and os.path.getsize(path) > 1000:
                return path
        return None

    def _image_to_data_uri(self, image_path: str) -> str:
        mime, _ = mimetypes.guess_type(image_path)
        if mime not in {"image/png", "image/jpeg", "image/jpg", "image/webp"}:
            mime = "image/png"
        with open(image_path, "rb") as fh:
            encoded = base64.b64encode(fh.read()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _collect_reference_images(self, scene_data: Dict[str, Any]) -> List[str]:
        """Only attach characters present in this 15s scene (order = prompt bindings)."""
        cast = characters_in_scene(scene_data)[:MAX_REFERENCE_IMAGES]
        images: List[str] = []
        for cid in cast:
            path = self._resolve_character_image(cid)
            if path:
                images.append(self._image_to_data_uri(path))
        return images

    def _create_task(
        self,
        prompt: str,
        duration: int,
        images: List[str],
    ) -> Dict[str, Any]:
        if not images:
            raise RuntimeError(
                "Vidu Q4 Preview requires character reference images. "
                "Expected PNGs in characters/."
            )

        # Send prompt as-is (no strip / no hard truncate) — user-editable full text.
        prompt = prompt or ""

        duration = max(3, min(int(duration), 16))
        headers = self._get_headers()
        endpoint = f"{self.base_url}/ent/v2/reference2video"
        payload: Dict[str, Any] = {
            "model": self.reference_model,
            "prompt": prompt,
            "images": images[:MAX_REFERENCE_IMAGES],
            "duration": duration,
            "aspect_ratio": self.aspect_ratio,
            "resolution": self.resolution,
            "audio": True,
        }
        mode = "reference2video"

        resp = requests.post(endpoint, headers=headers, json=payload, timeout=120)
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Vidu {mode} create failed HTTP {resp.status_code}: {resp.text[:500]}"
            )

        data = resp.json()
        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            raise RuntimeError(f"Vidu create response missing task_id: {data}")
        data["_mode"] = mode
        data["_endpoint"] = endpoint
        data["_model"] = payload.get("model")
        data["_prompt_chars"] = len(prompt)
        return data

    def _poll_task(self, task_id: str) -> Dict[str, Any]:
        headers = self._get_headers()
        url = f"{self.base_url}/ent/v2/tasks/{task_id}/creations"
        deadline = time.time() + self.poll_timeout_sec

        while time.time() < deadline:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code not in (200, 201):
                raise RuntimeError(
                    f"Vidu poll failed HTTP {resp.status_code}: {resp.text[:500]}"
                )
            data = resp.json()
            state = str(data.get("state", "")).lower()
            if state == "success":
                return data
            if state == "failed":
                raise RuntimeError(
                    f"Vidu task {task_id} failed: {data.get('err_code') or data}"
                )
            time.sleep(POLL_INTERVAL_SEC)

        raise TimeoutError(
            f"Vidu task {task_id} timed out after {self.poll_timeout_sec}s"
        )

    def _download_video(self, remote_url: str, output_filename: str) -> str:
        # Supports nested episode paths like "ep_123/scene_1.mp4".
        rel = output_filename.replace("\\", "/").lstrip("/")
        local_path = os.path.join(OUTPUT_DIR, rel.replace("/", os.sep))
        parent = os.path.dirname(local_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with requests.get(remote_url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with open(local_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        fh.write(chunk)
        if os.path.getsize(local_path) < 10000:
            raise RuntimeError(f"Downloaded Vidu video looks empty: {local_path}")
        return local_path

    def generate_scene_video(
        self,
        scene_data: Dict[str, Any],
        output_filename: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> VideoJobResult:
        options = options or {}
        start = time.time()
        duration = int(
            options.get("duration")
            or scene_data.get("vidu_duration_sec")
            or scene_data.get("duration_sec")
            or SCENE_DURATION_SEC
        )
        duration = max(3, min(duration, 16))
        images = self._collect_reference_images(scene_data)
        prompt = options.get("prompt") or self.build_scene_prompt(scene_data)
        rel_output = output_filename.replace("\\", "/").lstrip("/")

        try:
            created = self._create_task(prompt, duration, images=images)
            task_id = created.get("task_id") or created.get("id")
            result = self._poll_task(str(task_id))
            creations = result.get("creations") or []
            if not creations or not creations[0].get("url"):
                raise RuntimeError(
                    f"Vidu task {task_id} succeeded but returned no video URL"
                )

            remote_url = creations[0]["url"]
            local_path = self._download_video(remote_url, rel_output)
            latency = round(time.time() - start, 2)

            return VideoJobResult(
                engine=self.name,
                job_id=str(task_id),
                status="completed",
                video_url=public_url(rel_output),
                local_path=local_path,
                latency_sec=latency,
                metadata={
                    "model": created.get("_model") or self.reference_model,
                    "mode": created.get("_mode"),
                    "native_audio": True,
                    "duration_sec": max(3, min(duration, 16)),
                    "credits": result.get("credits"),
                    "credits_used": 1,
                    "remote_url": remote_url,
                    "cover_url": creations[0].get("cover_url"),
                    "reference_image_count": len(images),
                    "prompt_chars": len(prompt),
                    "prompt_max_chars": self.prompt_max_chars,
                    "prompt_preview": prompt[:280],
                    "cast": characters_in_scene(scene_data),
                },
            )
        except Exception as exc:
            return VideoJobResult(
                engine=self.name,
                job_id=f"failed_{int(time.time())}",
                status="failed",
                latency_sec=round(time.time() - start, 2),
                error=str(exc),
                metadata={
                    "model": self.reference_model,
                    "native_audio": True,
                    "duration_sec": duration,
                    "reference_image_count": len(images),
                    "prompt_chars": len(prompt),
                    "prompt_max_chars": self.prompt_max_chars,
                },
            )

    def get_specs(self) -> Dict[str, Any]:
        return {
            "platform": "Vidu AI",
            "series": "Vidu Q4 Preview (Video)",
            "api_base": self.base_url,
            "model": self.model,
            "reference_model": self.reference_model,
            "prompt_max_chars": self.prompt_max_chars,
            "episode_layout": f"{config.total_scenes} x {SCENE_DURATION_SEC}s -> {config.total_duration_seconds}s",
            "endpoints": {
                "reference2video": "POST /ent/v2/reference2video",
                "poll": "GET /ent/v2/tasks/{id}/creations",
            },
            "aspect_ratio": self.aspect_ratio,
            "resolution": self.resolution,
            "native_audio_enabled": True,
            "characters": list(CHARACTERS.keys()),
            "api_key_configured": bool(self.api_key),
        }
