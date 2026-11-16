"""Studio queue episode naming: Episode_Date_Time → Episode_Date_Time - Title after pitch confirm."""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any, Optional

_STAMP_RE = re.compile(r"^Episode_\d{8}_\d{6}$")


def make_studio_episode_name(*, when: Optional[float] = None) -> str:
    """Queue name before pitch confirmation: Episode_YYYYMMDD_HHMMSS."""
    dt = datetime.fromtimestamp(when if when is not None else time.time())
    return f"Episode_{dt.strftime('%Y%m%d')}_{dt.strftime('%H%M%S')}"


def studio_base_name(title: Optional[str]) -> str:
    """Extract Episode_Date_Time base from a title (with or without ' - Pitch')."""
    text = (title or "").strip()
    if not text:
        return make_studio_episode_name()
    if " - " in text:
        head = text.split(" - ", 1)[0].strip()
        if _STAMP_RE.match(head):
            return head
    if _STAMP_RE.match(text):
        return text
    # Legacy / catalog titles: mint a fresh stamp for queue convention.
    return make_studio_episode_name()


def is_pre_pitch_studio_name(title: Optional[str]) -> bool:
    return bool(_STAMP_RE.match((title or "").strip()))


def apply_confirmed_pitch_title(ep: Any, pitch_title: str) -> str:
    """
    After Gateway 1 pitch confirm:
    Episode_Date_Time - {pitch title}
    """
    base = studio_base_name(getattr(ep, "title", None))
    clean = re.sub(r"\s+", " ", (pitch_title or "").strip())
    # Avoid nesting if already confirmed with same pitch.
    if clean and getattr(ep, "title", "") == f"{base} - {clean}":
        return ep.title
    new_title = f"{base} - {clean}" if clean else base
    ep.title = new_title
    return new_title


def display_studio_title(ep: Any) -> str:
    """Title shown in Studio queue / meta everywhere."""
    return str(getattr(ep, "title", None) or make_studio_episode_name())
