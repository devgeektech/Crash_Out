"""Optional Telegram dispatch for daily Top-5 pitch cards."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from app.config import config

logger = logging.getLogger(__name__)


def format_pitch_message(run: Dict[str, Any]) -> str:
    run_date = run.get("run_date") or ""
    lines = [f"CRASH OUT Agent 0 — {run_date}", "Top friction-intersection pitches:", ""]
    for pitch in (run.get("pitches") or [])[:5]:
        rank = pitch.get("rank")
        score = pitch.get("consensus_score")
        flag = pitch.get("sensitivity_flag") or "SAFE"
        headline = pitch.get("headline") or ""
        merch = pitch.get("proposed_merch_hook") or ""
        lines.append(f"{rank}. [{score}/10 · {flag}] {headline}")
        if merch:
            lines.append(f"   Merch: {merch}")
        lines.append("")
    lines.append("Approve in Studio → Gate 1")
    return "\n".join(lines).strip()


def dispatch_pitch_run(run: Dict[str, Any]) -> bool:
    token = (getattr(config, "telegram_bot_token", None) or "").strip()
    chat_id = (getattr(config, "telegram_chat_id", None) or "").strip()
    if not token or not chat_id:
        logger.info("Telegram dispatch skipped (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID unset)")
        return False
    text = format_pitch_message(run)
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:3900]},
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning("Telegram dispatch failed %s: %s", resp.status_code, resp.text[:200])
            return False
        logger.info("Telegram dispatch sent for run %s", run.get("run_date"))
        return True
    except Exception as exc:
        logger.warning("Telegram dispatch error: %s", exc)
        return False
