"""Studio queue episode naming: EP_YYYY-MM-DD → EP_YYYY-MM-DD - Title after pitch confirm."""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any, Optional, Tuple

# Current: EP_2026-11-23
# Legacy: EP-18-20261123, Episode_20261118_153318
_STAMP_CURRENT_RE = re.compile(r"^EP_\d{4}-\d{2}-\d{2}$")
_STAMP_LEGACY_EP_RE = re.compile(r"^EP-(\d+)-(\d{8})$", re.IGNORECASE)
_STAMP_LEGACY_EPISODE_RE = re.compile(r"^Episode_(\d{8})_\d{6}$", re.IGNORECASE)
_STAMP_RE = re.compile(
    r"^(?:EP_\d{4}-\d{2}-\d{2}|EP-\d+-\d{8}|Episode_\d{8}_\d{6})$",
    re.IGNORECASE,
)


def _ymd_dashed(yyyymmdd: str) -> str:
    raw = (yyyymmdd or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw


def make_studio_episode_name(*, serial_number: Optional[int] = None, when: Optional[float] = None) -> str:
    """Queue name before pitch confirmation: EP_YYYY-MM-DD.

    ``serial_number`` is accepted for call-site compatibility but is not part of the title;
    the numeric ID stays on the episode record / queue ID column.
    """
    del serial_number  # kept for API compatibility
    dt = datetime.fromtimestamp(when if when is not None else time.time())
    return f"EP_{dt.strftime('%Y-%m-%d')}"


def _split_title(title: Optional[str]) -> Tuple[str, str]:
    text = (title or "").strip()
    if " - " in text:
        head, rest = text.split(" - ", 1)
        return head.strip(), rest.strip()
    return text, ""


def normalize_episode_title(title: Optional[str], *, serial_number: Optional[int] = None) -> str:
    """
    Rewrite legacy stamps to EP_YYYY-MM-DD (keeps optional `` - pitch title`` suffix).
    """
    head, pitch = _split_title(title)
    if not head:
        return make_studio_episode_name(serial_number=serial_number)

    if _STAMP_CURRENT_RE.match(head):
        base = head
    else:
        m_ep = _STAMP_LEGACY_EP_RE.match(head)
        if m_ep:
            base = f"EP_{_ymd_dashed(m_ep.group(2))}"
        else:
            m_old = _STAMP_LEGACY_EPISODE_RE.match(head)
            if m_old:
                base = f"EP_{_ymd_dashed(m_old.group(1))}"
            elif _STAMP_RE.match(head):
                base = head
            else:
                # Non-stamp catalog/custom title — leave unchanged.
                return (title or "").strip()

    return f"{base} - {pitch}" if pitch else base


def studio_base_name(title: Optional[str], *, serial_number: Optional[int] = None) -> str:
    """Extract EP_YYYY-MM-DD base from a title (normalizes legacy stamps)."""
    normalized = normalize_episode_title(title, serial_number=serial_number)
    head, _ = _split_title(normalized)
    if _STAMP_CURRENT_RE.match(head) or _STAMP_RE.match(head):
        if _STAMP_CURRENT_RE.match(head):
            return head
        # Normalize legacy head if somehow still present
        return normalize_episode_title(head, serial_number=serial_number)
    return make_studio_episode_name(serial_number=serial_number)


def is_pre_pitch_studio_name(title: Optional[str]) -> bool:
    head, pitch = _split_title(title)
    if pitch:
        return False
    return bool(_STAMP_RE.match(head) or _STAMP_CURRENT_RE.match(head))


def apply_confirmed_pitch_title(ep: Any, pitch_title: str) -> str:
    """
    After Gateway 1 pitch confirm:
    EP_YYYY-MM-DD - {pitch title}
    """
    ep_num = getattr(ep, "episode_number", None)
    base = studio_base_name(getattr(ep, "title", None), serial_number=ep_num)
    clean = re.sub(r"\s+", " ", (pitch_title or "").strip())
    if clean and getattr(ep, "title", "") == f"{base} - {clean}":
        return ep.title
    new_title = f"{base} - {clean}" if clean else base
    ep.title = new_title
    return new_title


def display_studio_title(ep: Any) -> str:
    """Title shown in Studio queue / meta everywhere (legacy stamps normalized)."""
    ep_num = getattr(ep, "episode_number", None)
    raw = getattr(ep, "title", None) or make_studio_episode_name(serial_number=ep_num)
    return normalize_episode_title(str(raw), serial_number=ep_num)
