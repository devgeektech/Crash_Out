"""
Daily Agent 0 cadence — 06:00 America/New_York via APScheduler.

Enable with AGENT0_SCHEDULE_ENABLED=true (default false in local POC).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_scheduler = None


def _enabled() -> bool:
    import os

    return (os.getenv("AGENT0_SCHEDULE_ENABLED", "false") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def run_daily_agent0_job() -> dict:
    """Fetch Top-5 pitches and optionally dispatch to Telegram."""
    from app.trends.pipeline import fetch_daily_pitch_run
    from app.trends.telegram_dispatch import dispatch_pitch_run

    logger.info("Agent 0 scheduled run starting")
    run = fetch_daily_pitch_run(force_refresh=True)
    dispatch_pitch_run(run)
    logger.info(
        "Agent 0 scheduled run complete: %s pitches (mode=%s)",
        len(run.get("pitches") or []),
        (run.get("meta") or {}).get("mode"),
    )
    return run


def start_agent0_scheduler() -> Optional[Any]:
    """Start background scheduler once. Safe to call multiple times."""
    global _scheduler
    if not _enabled():
        logger.info("Agent 0 scheduler disabled (set AGENT0_SCHEDULE_ENABLED=true to enable)")
        return None
    if _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed; Agent 0 cron unavailable")
        return None

    hour = 6
    minute = 0
    try:
        import os

        hour = int(os.getenv("AGENT0_SCHEDULE_HOUR", "6"))
        minute = int(os.getenv("AGENT0_SCHEDULE_MINUTE", "0"))
    except ValueError:
        pass

    sched = BackgroundScheduler(timezone="America/New_York")
    sched.add_job(
        run_daily_agent0_job,
        CronTrigger(hour=hour, minute=minute, timezone="America/New_York"),
        id="agent0_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _scheduler = sched
    logger.info(
        "Agent 0 scheduler started — daily %02d:%02d America/New_York",
        hour,
        minute,
    )
    return sched


def shutdown_agent0_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
    except Exception as exc:
        logger.debug("scheduler shutdown: %s", exc)
    _scheduler = None
