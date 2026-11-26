"""Studio queue episode naming: EP_YYYY-Mon-DD → EP_YYYY-Mon-DD (2) for same-day episodes."""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any, Iterable, Optional

# English month abbreviations (locale-independent).
_MONTH_ABBR = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

# New: EP_2026-Nov-23 / EP_2026-Nov-23 (2)
# Previous: EP-1-20261118
# Legacy: Episode_20261118_153318
_STAMP_RE = re.compile(
    r"^(?:"
    r"EP_\d{4}-[A-Za-z]{3}-\d{2}(?: \(\d+\))?"
    r"|EP-\d+-\d{8}"
    r"|Episode_\d{8}_\d{6}"
    r")$"
)

# Match day stamp + optional sequence from a full title (with or without pitch suffix).
_DAY_SEQ_RE = re.compile(
    r"^EP_(\d{4}-[A-Za-z]{3}-\d{2})(?: \((\d+)\))?(?: - .*)?$",
    re.IGNORECASE,
)


def episode_day_stamp(*, when: Optional[float] = None) -> str:
    """Canonical day stamp: EP_2026-Nov-23."""
    dt = datetime.fromtimestamp(when if when is not None else time.time())
    return f"EP_{dt.year}-{_MONTH_ABBR[dt.month - 1]}-{dt.day:02d}"


def _day_key_and_seq(title: Optional[str]) -> Optional[tuple[str, int]]:
    """Parse (EP_YYYY-Mon-DD, sequence) from a title. Bare stamp => seq 1."""
    text = (title or "").strip()
    if not text:
        return None
    m = _DAY_SEQ_RE.match(text)
    if not m:
        return None
    day_key = f"EP_{m.group(1)}"
    # Normalize month casing to Title case (Nov, not NOV/nov).
    parts = day_key.split("-")
    if len(parts) == 3:
        day_key = f"{parts[0]}-{parts[1].title()}-{parts[2]}"
    seq = int(m.group(2)) if m.group(2) else 1
    return day_key, seq


def _existing_titles(existing_titles: Optional[Iterable[str]] = None) -> list[str]:
    if existing_titles is not None:
        return [str(t or "") for t in existing_titles]
    try:
        from app.state import state_manager

        return [str(getattr(ep, "title", "") or "") for ep in state_manager.episodes.values()]
    except Exception:
        return []


def make_studio_episode_name(
    *,
    serial_number: Optional[int] = None,
    when: Optional[float] = None,
    existing_titles: Optional[Iterable[str]] = None,
) -> str:
    """
    Queue name: EP_YYYY-Mon-DD for the first episode of the day,
    then EP_YYYY-Mon-DD (2), (3), … for later episodes the same day.

    serial_number is accepted for call-site compatibility but is not part of the title.
    """
    del serial_number  # kept for API compatibility with existing callers
    base = episode_day_stamp(when=when)
    used: set[int] = set()
    for title in _existing_titles(existing_titles):
        parsed = _day_key_and_seq(title)
        if parsed and parsed[0] == base:
            used.add(parsed[1])
    if 1 not in used:
        return base
    n = 2
    while n in used:
        n += 1
    return f"{base} ({n})"


def studio_base_name(title: Optional[str], *, serial_number: Optional[int] = None) -> str:
    """Extract day stamp (with optional same-day sequence) from a title."""
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
    EP_YYYY-Mon-DD [(N)] - {pitch title}
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
