"""
Agent 0 pipeline: collect → filter → write 3 concepts → cache.
Always returns 3 cards (live, cache, or static fallback).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.trends.cache import load_cached_concepts, save_cached_concepts
from app.trends.concept_writer import write_concepts
from app.trends.filter import filter_trends
from app.trends.sources import collect_all_trends

logger = logging.getLogger(__name__)


def static_fallback_concepts() -> List[Dict[str, Any]]:
    """Hardcoded Gate 1 cards — last resort when live + cache fail."""
    from app.catalog import VIDEO_CATALOG

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
            "wellness culture turns a spilled drink into a family referendum on love, "
            "loyalty, and resale-market inflation."
        ),
        "premise": (
            "Linda drops her limited-edition 40oz pastel lavender Stanley in the driveway "
            "and treats the dent like a bereavement. She demands a driveway vigil, a "
            "replacement at $95 resale, and a family Instagram story apologizing to the "
            "hydration community. Gary refuses to subsidize another tumbler while the HOA "
            "fine and Chloe's merch Shopify are already draining the account. Linda "
            "retaliates by photographing Gary's lawn-parked sedan and drafting an HOA "
            "complaint about 'visual clutter and masculine energy leakage.' Chris rates "
            "the drama as mid engagement; Chloe polls whether Mom replaces the cup before "
            "Dad replaces the transmission."
        ),
        "synopsis": (
            "A side-path crash-out where status objects outrank joint finances. Linda's "
            "emotional-support tumbler becomes the proxy fight for every unpaid bill, "
            "while the kids package the argument as content and Gary discovers the HOA "
            "email thread already includes his license plate."
        ),
        "source_trends": [
            "Stanley Cup Collector Frenzy",
            "Target Black Friday Meltdown",
            "Suburban Wellness",
        ],
        "characters_involved": ["gary", "linda", "chris", "chloe"],
        "suggested_merch": "Emotionally Dependent on Hydration",
        "conflict": (
            "Suburban status symbols and performative wellness vs household solvency — "
            "Linda weaponizes the HOA while Gary refuses the resale markup."
        ),
        "tone": "Passive-aggressive suburban melodrama with content-farm siblings",
        "script_key": "hoa_violation",
    }
    first.setdefault("script_key", "hoa_violation")
    second.setdefault("script_key", "hoa_q4_prompts")
    return [first, second, third]


def fetch_live_concepts() -> List[Dict[str, Any]]:
    """
    Produce exactly 3 Gate 1 concepts.
    Prefer live trends; else cache; else static fallback.
    """
    meta: Dict[str, Any] = {"mode": "unknown", "trend_count": 0, "filtered_count": 0}
    try:
        raw = collect_all_trends()
        meta["trend_count"] = len(raw)
        filtered = filter_trends(raw)
        meta["filtered_count"] = len(filtered)
        # If theme filter is too strict, still use top web-search hits (reject list already applied in filter).
        seed = filtered if filtered else [
            t for t in raw[:18]
            if t.get("title")
        ]
        meta["seed_count"] = len(seed)
        if seed:
            concepts = write_concepts(seed)
            if len(concepts) >= 3:
                meta["mode"] = "live" if filtered else "live_unfiltered"
                save_cached_concepts(concepts[:3], meta=meta)
                logger.info(
                    "Agent 0 live concepts: %s search hits → %s filtered → %s seeded → 3 cards",
                    meta["trend_count"],
                    meta["filtered_count"],
                    meta["seed_count"],
                )
                return concepts[:3]
            logger.warning("Concept writer returned %s cards; trying cache", len(concepts))
        else:
            logger.warning("No web-search trends available (raw=%s)", meta["trend_count"])
    except Exception as exc:
        logger.exception("Live trend pipeline failed: %s", exc)
        meta["error"] = str(exc)

    cached = load_cached_concepts()
    if cached:
        meta["mode"] = "cache"
        logger.info("Agent 0 serving cached concepts")
        return cached

    meta["mode"] = "static_fallback"
    fallback = static_fallback_concepts()
    # Seed cache so next offline open still has something stable.
    save_cached_concepts(fallback, meta=meta)
    logger.info("Agent 0 serving static fallback concepts")
    return fallback
