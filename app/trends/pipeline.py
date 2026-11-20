"""
Agent 0 pipeline: Layer A/B/C fetch → cluster → friction score → Top 5 pitches.
Always returns concepts adapted from pitches (Gate 1 compatible).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.db import log_system_incident
from app.trends.cache import load_cached_concepts, save_cached_concepts
from app.trends.cluster import cluster_items
from app.trends.friction import score_clusters
from app.trends.schema import (
    empty_pitch_run,
    normalize_pitch_run,
    pitches_to_concepts,
    today_run_date,
)
from app.trends.sources import collect_all_trends
from app.trends.store import (
    load_latest_pitch_run,
    load_prior_topic_embeddings,
    save_pitch_run,
    save_raw_items,
)

logger = logging.getLogger(__name__)


def fetch_daily_pitch_run(*, force_refresh: bool = True) -> Dict[str, Any]:
    """
    Full Agent 0 run → Top 5 pitch cards (client schema).
    No static mock fallbacks. Automated 3-retry handling via Agent M with manual retry requirement.
    """
    run_date = today_run_date()
    meta: Dict[str, Any] = {
        "mode": "unknown",
        "raw_count": 0,
        "cluster_count": 0,
        "layer_counts": {"A": 0, "B": 0, "C": 0},
    }
    pipeline_error = None
    try:
        raw = collect_all_trends()
        meta["raw_count"] = len(raw)
        for it in raw:
            layer = str(it.get("layer") or "?").upper()
            if layer in meta["layer_counts"]:
                meta["layer_counts"][layer] += 1
        save_raw_items(run_date, raw)

        prior = load_prior_topic_embeddings(days=30)
        clusters = cluster_items(raw, prior_embeddings=prior)
        meta["cluster_count"] = len(clusters)

        if clusters:
            pitches = score_clusters(clusters, run_date=run_date)
            if len(pitches) >= 1:
                meta["mode"] = "live"
                run = normalize_pitch_run(pitches, run_date=run_date, meta=meta)
                save_pitch_run(run)
                logger.info(
                    "Agent 0 live pitches: raw=%s clusters=%s pitches=%s layers=%s",
                    meta["raw_count"],
                    meta["cluster_count"],
                    len(run["pitches"]),
                    meta["layer_counts"],
                )
                return run
            pipeline_error = "OpenAI scoring returned no valid pitches after automated retries."
        else:
            pipeline_error = "No trend clusters formed from raw feeds."
    except Exception as exc:
        logger.exception("Agent 0 live pipeline failed: %s", exc)
        pipeline_error = str(exc)

    meta["error"] = pipeline_error

    # Log incident to Agent M Control Plane
    log_system_incident(
        event_type="AGENT0_EXECUTION_FAILURE",
        actor="Agent M Orchestrator",
        details={
            "category": "Agent 0 Trend Ingest",
            "task_name": "Daily Trend Ingestion & Scoring",
            "error": pipeline_error,
            "retry_count": 3,
            "max_retries": 3,
            "requires_manual_retry": True,
            "can_retry": True,
            "action_endpoint": "/api/agent0/run",
        },
    )

    # If an existing live run from today exists, serve it
    cached_run = load_latest_pitch_run()
    if cached_run and cached_run.get("pitches") and cached_run.get("run_date") == run_date:
        cached_run = dict(cached_run)
        cached_run["meta"] = {**(cached_run.get("meta") or {}), **meta, "mode": "cached_live"}
        logger.warning("Agent 0 serving existing today's live pitch run after pipeline error")
        return cached_run

    raise RuntimeError(
        f"Agent 0 Trend Pipeline failed: {pipeline_error}. "
        "Incident logged in Agent M. Please trigger a manual retry via the Agent M Control Plane."
    )


def fetch_live_concepts() -> List[Dict[str, Any]]:
    """
    Gate 1 entrypoint: Top 5 pitch cards adapted to concept shape.
    """
    run = fetch_daily_pitch_run()
    concepts = pitches_to_concepts(run)
    if len(concepts) >= 1:
        save_cached_concepts(concepts, meta=run.get("meta") or {})
        return concepts[:5]

    cached = load_cached_concepts()
    if cached:
        return cached[:5]

    raise RuntimeError(
        "No live or cached concepts available. "
        "Please trigger a manual retry via the Agent M Control Plane."
    )


def get_latest_run_or_refresh(*, refresh: bool = False) -> Dict[str, Any]:
    if not refresh:
        existing = load_latest_pitch_run()
        if existing and existing.get("pitches"):
            return existing
    return fetch_daily_pitch_run()
