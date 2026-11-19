"""
Agent 0 pipeline: Layer A/B/C fetch → cluster → friction score → Top 5 pitches.
Always returns concepts adapted from pitches (Gate 1 compatible).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

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


def static_fallback_concepts() -> List[Dict[str, Any]]:
    """Hardcoded Gate 1 cards — last resort when live + cache fail."""
    from app.core.catalog import VIDEO_CATALOG
    from app.trends.schema import pitch_to_concept

    first = dict(VIDEO_CATALOG[0]["concept"])
    first.setdefault(
        "source_trends",
        ["Suburban HOA Tyranny", "TikTok Parent-Shaming", "Family Humiliation Merch"],
    )
    second = dict(VIDEO_CATALOG[1]["concept"])
    second.setdefault(
        "source_trends",
        ["HOA Violation Continuity Cut", "Vidu Q4 Prompt Pack"],
    )
    third = {
        "id": "concept_3",
        "title": "Linda's Stanley Cup Emotional Support Crisis",
        "cultural_hook": (
            "Consumerist tumbler obsession, pastel aesthetic mania, and the way suburban "
            "wellness culture turns a spilled drink into a family referendum on love."
        ),
        "premise": (
            "Linda drops her limited-edition Stanley and treats the dent like a bereavement "
            "while Gary refuses the resale markup and Chloe polls the driveway vigil."
        ),
        "synopsis": "Status objects outrank joint finances in a suburban crash-out.",
        "source_trends": ["Stanley Cup Collector Frenzy", "Suburban Wellness"],
        "characters_involved": ["gary", "linda", "chris", "chloe"],
        "suggested_merch": "Emotionally Dependent on Hydration",
        "conflict": "Performative wellness vs household solvency.",
        "tone": "Passive-aggressive suburban melodrama",
        "script_key": "hoa_violation",
    }
    # Pad to 5 with pitch-shaped extras derived from catalog themes
    extras = [
        pitch_to_concept(
            {
                "rank": 4,
                "headline": "Quiet-Quitting Kids Rate Dad's Tariff Rant as Mid",
                "consensus_score": 7.2,
                "sources": {
                    "mainstream": ["cost of living"],
                    "youth_social": ["r/antiwork"],
                },
                "youth_sentiment_summary": "Gen Z clips parental meltdowns for engagement.",
                "crash_out_angle": (
                    "Gary practices a kitchen-island rally speech while Chris open-sources the "
                    "family budget and Chloe sells merch mid-rant."
                ),
                "proposed_merch_hook": "Capitalism broke my dad",
                "sensitivity_flag": "SAFE",
            }
        ),
        pitch_to_concept(
            {
                "rank": 5,
                "headline": "HOA Board Threatens Lawn Signs After PTA Livestream",
                "consensus_score": 7.0,
                "sources": {
                    "mainstream": ["suburban local news"],
                    "youth_social": ["r/HOA"],
                },
                "youth_sentiment_summary": "Teens treat HOA drama as free reality TV.",
                "crash_out_angle": (
                    "Linda weaponizes vibrational HOA language while Chloe livestreams the "
                    "board email thread and Gary parks on the lawn in protest."
                ),
                "proposed_merch_hook": "Optics are catastrophic",
                "sensitivity_flag": "SAFE",
            }
        ),
    ]
    first.setdefault("script_key", "hoa_violation")
    second.setdefault("script_key", "hoa_q4_prompts")
    return [first, second, third] + extras


def fetch_daily_pitch_run(*, force_refresh: bool = True) -> Dict[str, Any]:
    """
    Full Agent 0 run → Top 5 pitch cards (client schema).
    """
    run_date = today_run_date()
    meta: Dict[str, Any] = {
        "mode": "unknown",
        "raw_count": 0,
        "cluster_count": 0,
        "layer_counts": {"A": 0, "B": 0, "C": 0},
    }
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
            meta["error"] = "scorer returned no pitches"
        else:
            meta["error"] = "no clusters"
    except Exception as exc:
        logger.exception("Agent 0 live pipeline failed: %s", exc)
        meta["error"] = str(exc)

    cached_run = load_latest_pitch_run()
    if cached_run and cached_run.get("pitches"):
        cached_run = dict(cached_run)
        cached_run["meta"] = {**(cached_run.get("meta") or {}), **meta, "mode": "cache"}
        logger.info("Agent 0 serving cached pitch run")
        return cached_run

    # Build pitches from static concepts
    concepts = static_fallback_concepts()
    from app.trends.schema import normalize_pitch

    pitches = []
    for i, c in enumerate(concepts[:5], 1):
        pitches.append(
            normalize_pitch(
                {
                    "rank": i,
                    "headline": c.get("title"),
                    "consensus_score": 6.5,
                    "sources": {
                        "mainstream": (c.get("source_trends") or [])[:2],
                        "youth_social": (c.get("source_trends") or [])[2:4],
                    },
                    "youth_sentiment_summary": c.get("cultural_hook"),
                    "crash_out_angle": c.get("premise") or c.get("synopsis"),
                    "proposed_merch_hook": c.get("suggested_merch"),
                    "sensitivity_flag": "SAFE",
                },
                rank=i,
                run_date=run_date,
            )
        )
    meta["mode"] = "static_fallback"
    run = normalize_pitch_run(pitches, run_date=run_date, meta=meta)
    save_pitch_run(run)
    logger.info("Agent 0 serving static fallback pitches")
    return run


def fetch_live_concepts() -> List[Dict[str, Any]]:
    """
    Gate 1 entrypoint: Top 5 pitch cards adapted to concept shape.
    """
    run = fetch_daily_pitch_run()
    concepts = pitches_to_concepts(run)
    if len(concepts) >= 3:
        save_cached_concepts(concepts, meta=run.get("meta") or {})
        return concepts[:5]

    cached = load_cached_concepts()
    if cached:
        return cached[:5]

    fallback = static_fallback_concepts()
    save_cached_concepts(fallback, meta={"mode": "static_fallback"})
    return fallback[:5]


def get_latest_run_or_refresh(*, refresh: bool = False) -> Dict[str, Any]:
    if not refresh:
        existing = load_latest_pitch_run()
        if existing and existing.get("pitches"):
            return existing
    return fetch_daily_pitch_run()
