"""
Daily Agent 0 cadence — 06:00 EST (America/New_York) via APScheduler.

Scrapes Mainstream + Social feeds into today's research board.
Pitch cards are NOT generated here — only after the user selects topics
and clicks Create top 5 pitches.

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


def run_daily_agent0_job(*, create_shell: bool = False, user_id: Optional[int] = None) -> dict:
    """
    Scrape layers into today's raw research feed (no pitch cards).

    When create_shell=True (scheduled runs), also mint a Work history episode shell
    and set it active so Trend Research follows the new ingest.
    Mockup job creates its own shell after calling this with create_shell=False.
    """
    from app.trends.pipeline import fetch_daily_raw_ingest
    from app.trends.research_ui import clear_raw_feed_cache

    logger.info("Agent 0 scheduled raw ingest starting")
    result = fetch_daily_raw_ingest()
    clear_raw_feed_cache()
    raw_count = int(
        (result.get("meta") or {}).get("raw_count")
        or len(result.get("items") or [])
    )
    logger.info(
        "Agent 0 scheduled raw ingest complete: %s items (mode=%s)",
        raw_count,
        (result.get("meta") or {}).get("mode"),
    )
    if create_shell:
        from app.trends.mockup_job import create_research_ingest_shell

        layers = (result.get("meta") or {}).get("layer_counts") or {}
        layer_bits = " · ".join(f"{k}:{int(layers.get(k) or 0)}" for k in ("A", "B"))
        ep = create_research_ingest_shell(
            user_id=user_id,
            raw_count=raw_count,
            run_date=str(result.get("run_date") or ""),
            layer_bits=layer_bits,
        )
        result = dict(result)
        result["episode_id"] = ep.id
        result["episode_title"] = ep.title
        logger.info("Agent 0 scheduled shell episode=%s", ep.id)
    return result


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
    timezone = "America/New_York"
    try:
        import os

        hour = int(os.getenv("AGENT0_SCHEDULE_HOUR", "6"))
        minute = int(os.getenv("AGENT0_SCHEDULE_MINUTE", "0"))
        timezone = (os.getenv("AGENT0_SCHEDULE_TIMEZONE", "America/New_York") or "America/New_York").strip()
    except ValueError:
        pass

    sched = BackgroundScheduler(timezone=timezone)
    sched.add_job(
        lambda: run_daily_agent0_job(create_shell=True),
        CronTrigger(hour=hour, minute=minute, timezone=timezone),
        id="agent0_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _scheduler = sched
    logger.info(
        "Agent 0 scheduler started — daily %02d:%02d %s (raw ingest only)",
        hour,
        minute,
        timezone,
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
