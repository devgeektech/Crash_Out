"""
Platform specifications for Vidu Q4 Preview Crash Out production.
"""
from typing import Dict, Any


PLATFORM_BENCHMARKS = {
    "vidu": {
        "platform_name": "Vidu AI",
        "tagline": "Official Vidu Q4 Preview Video API — reference/image to video with native audio",
        "model_version": "viduq4-preview",
        "recommended_role": "Full episode 2D animation with native synchronized audio",
        "api": {
            "base_url": "https://api.vidu.com",
            "auth": "Authorization: Token {VIDU_API_KEY}",
            "reference2video": "POST /ent/v2/reference2video",
            "img2video": "POST /ent/v2/img2video",
            "poll": "GET /ent/v2/tasks/{id}/creations",
        },
        "metrics": {
            "max_scene_duration_sec": 16,
            "episode_layout": "4 x 15s scenes -> 60s master",
            "max_video_resolution": "540p / 720p / 1080p / 2K / 4K",
            "aspect_ratios": ["9:16", "16:9", "1:1", "3:4", "4:3"],
            "supported_audio": ["Native audio track in video (speech + SFX)"],
            "reference_images": "1–15",
        },
        "pros": [
            "Q4 Preview reference consistency across character stills",
            "Native audio generation inside the video container",
            "9:16 vertical aspect supported on reference2video",
            "15s scene length fits within 3–16s duration limits",
        ],
        "cons": [
            "No text-to-video on Q4 Preview — character reference images are required",
        ],
    }
}


def get_benchmark_comparison() -> Dict[str, Any]:
    return {
        "platforms": PLATFORM_BENCHMARKS,
        "recommendation": "vidu",
        "rationale": "Crash Out is standardized exclusively on Vidu Q4 Preview Video.",
    }
