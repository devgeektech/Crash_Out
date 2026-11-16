"""
Official Vidu video model IDs for settings dropdowns.

Source: https://platform.vidu.com/docs/overview/model-map
Crash Out generation primarily uses reference2video / img2video.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

# (api_id, label)
VIDU_VIDEO_MODELS: List[Tuple[str, str]] = [
    ("viduq4-preview", "Vidu Q4 Preview — viduq4-preview"),
    ("viduq3-pro", "Vidu Q3 Pro — viduq3-pro"),
    ("viduq3-mix", "Vidu Q3 Mix — viduq3-mix"),
    ("viduq3-drama", "Vidu Q3 Drama — viduq3-drama"),
    ("viduq3-ad", "Vidu Q3 Ad — viduq3-ad"),
    ("viduq3-turbo", "Vidu Q3 Turbo — viduq3-turbo"),
    ("viduq2-pro", "Vidu Q2 Pro — viduq2-pro"),
    ("viduq2", "Vidu Q2 — viduq2"),
    ("viduq2-turbo", "Vidu Q2 Turbo — viduq2-turbo"),
    ("viduq1", "Vidu Q1 — viduq1"),
    ("viduq1-classic", "Vidu Q1 Classic — viduq1-classic"),
    ("vidu2.0", "Vidu 2.0 — vidu2.0"),
]

# Models that support reference-to-video per Vidu model map
VIDU_REFERENCE_MODELS: List[Tuple[str, str]] = [
    ("viduq4-preview", "Vidu Q4 Preview — viduq4-preview"),
    ("viduq3-mix", "Vidu Q3 Mix — viduq3-mix"),
    ("viduq3-drama", "Vidu Q3 Drama — viduq3-drama"),
    ("viduq3-ad", "Vidu Q3 Ad — viduq3-ad"),
    ("viduq3-turbo", "Vidu Q3 Turbo — viduq3-turbo"),
    ("viduq2-pro", "Vidu Q2 Pro — viduq2-pro"),
    ("viduq2", "Vidu Q2 — viduq2"),
    ("viduq1", "Vidu Q1 — viduq1"),
    ("vidu2.0", "Vidu 2.0 — vidu2.0"),
]

VIDU_RESOLUTIONS: List[Tuple[str, str]] = [
    ("540p", "540p"),
    ("720p", "720p"),
    ("1080p", "1080p"),
    ("2K", "2K"),
    ("4K", "4K"),
]


def options_with_current(
    options: Sequence[Tuple[str, str]],
    current: str,
) -> List[Tuple[str, str]]:
    """Ensure a saved custom value still appears in the select list."""
    value = (current or "").strip()
    ids = {oid for oid, _ in options}
    if value and value not in ids:
        return [(value, f"Custom — {value}"), *options]
    return list(options)
