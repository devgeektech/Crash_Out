"""Studio queue episode naming: EP-serialnumber-date → EP-serialnumber-date - Title after pitch confirm."""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any, Optional

# Supports new format (EP-1-20261118) and legacy format (Episode_20261118_153318)
_STAMP_RE = re.compile(r"^(?:EP-\d+-\d{8}|Episode_\d{8}_\d{6})$")


def make_studio_episode_name(*, serial_number: Optional[int] = None, when: Optional[float] = None) -> str:
    """Queue name before pitch confirmation: EP-<serialnumber>-<YYYYMMDD>."""
    from app.studio.generation import next_episode_number

    dt = datetime.fromtimestamp(when if when is not None else time.time())
    num = serial_number if serial_number is not None else next_episode_number()
    return f"EP-{num}-{dt.strftime('%Y%m%d')}"


def studio_base_name(title: Optional[str], *, serial_number: Optional[int] = None) -> str:
    """Extract EP-serialnumber-date or Episode_Date_Time base from a title."""
    text = (title or "").strip()
    if not text:
        return make_studio_episode_name(serial_number=serial_number)
    if " - " in text:
        head = text.split(" - ", 1)[0].strip()
        if _STAMP_RE.match(head):
            return head
    if _STAMP_RE.match(text):
        return text
    # Legacy / catalog titles: mint a fresh stamp for queue convention.
    return make_studio_episode_name(serial_number=serial_number)


def is_pre_pitch_studio_name(title: Optional[str]) -> bool:
    return bool(_STAMP_RE.match((title or "").strip()))


def apply_confirmed_pitch_title(ep: Any, pitch_title: str) -> str:
    """
    After Gateway 1 pitch confirm:
    EP-{num}-{date} - {pitch title}
    """
    ep_num = getattr(ep, "episode_number", None)
    base = studio_base_name(getattr(ep, "title", None), serial_number=ep_num)
    clean = re.sub(r"\s+", " ", (pitch_title or "").strip())
    # Avoid nesting if already confirmed with same pitch.
    if clean and getattr(ep, "title", "") == f"{base} - {clean}":
        return ep.title
    new_title = f"{base} - {clean}" if clean else base
    ep.title = new_title
    return new_title


def display_studio_title(ep: Any) -> str:
    """Title shown in Studio queue / meta everywhere."""
    ep_num = getattr(ep, "episode_number", None)
    return str(getattr(ep, "title", None) or make_studio_episode_name(serial_number=ep_num))

