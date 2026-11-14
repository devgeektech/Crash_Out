"""
Agent 0 pitch-card schema (client Top-5 Gate 1 format) + concept adapter.
"""
from __future__ import annotations

import time
from datetime import date
from typing import Any, Dict, List, Optional


SENSITIVITY_SAFE = "SAFE"
SENSITIVITY_REVIEW = "SENSITIVE_REVIEW"


def today_run_date() -> str:
    return date.today().isoformat()


def empty_pitch_run(*, run_date: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "run_date": run_date or today_run_date(),
        "pitches": [],
        "meta": meta or {},
        "generated_at": time.time(),
    }


def normalize_pitch(raw: Dict[str, Any], *, rank: int, run_date: str) -> Dict[str, Any]:
    sources = raw.get("sources") if isinstance(raw.get("sources"), dict) else {}
    mainstream = _str_list(sources.get("mainstream"))
    youth = _str_list(sources.get("youth_social"))
    flag = str(raw.get("sensitivity_flag") or SENSITIVITY_SAFE).strip().upper()
    if flag not in {SENSITIVITY_SAFE, SENSITIVITY_REVIEW}:
        flag = SENSITIVITY_SAFE
    try:
        score = float(raw.get("consensus_score") or raw.get("friction_score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    score = max(1.0, min(10.0, score)) if score else 1.0
    headline = str(raw.get("headline") or raw.get("title") or f"Pitch {rank}").strip()
    angle = str(raw.get("crash_out_angle") or raw.get("premise") or "").strip()
    merch = str(raw.get("proposed_merch_hook") or raw.get("suggested_merch") or "Capitalism broke my dad").strip()
    youth_summary = str(raw.get("youth_sentiment_summary") or raw.get("cultural_hook") or "").strip()
    return {
        "rank": int(raw.get("rank") or rank),
        "headline": headline,
        "consensus_score": round(score, 1),
        "sources": {
            "mainstream": mainstream[:6],
            "youth_social": youth[:6],
        },
        "youth_sentiment_summary": youth_summary,
        "crash_out_angle": angle,
        "proposed_merch_hook": merch,
        "sensitivity_flag": flag,
        "run_date": run_date,
        # Internal scoring breakdown (optional UI / debug)
        "score_breakdown": raw.get("score_breakdown") if isinstance(raw.get("score_breakdown"), dict) else {},
        "cluster_id": raw.get("cluster_id"),
        "layer_hits": raw.get("layer_hits") if isinstance(raw.get("layer_hits"), dict) else {},
    }


def normalize_pitch_run(
    pitches: List[Dict[str, Any]],
    *,
    run_date: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    day = run_date or today_run_date()
    cleaned = [normalize_pitch(p, rank=i, run_date=day) for i, p in enumerate(pitches[:5], 1)]
    # Re-rank by consensus_score descending, keep top 5
    cleaned.sort(key=lambda p: float(p.get("consensus_score") or 0), reverse=True)
    for i, p in enumerate(cleaned, 1):
        p["rank"] = i
    return {
        "run_date": day,
        "pitches": cleaned[:5],
        "meta": meta or {},
        "generated_at": time.time(),
    }


def pitch_to_concept(pitch: Dict[str, Any], *, run_date: Optional[str] = None) -> Dict[str, Any]:
    """Adapt a client pitch card into the Gate 1 / Agent 1 concept shape."""
    day = run_date or pitch.get("run_date") or today_run_date()
    sources = pitch.get("sources") if isinstance(pitch.get("sources"), dict) else {}
    mainstream = _str_list(sources.get("mainstream"))
    youth = _str_list(sources.get("youth_social"))
    source_trends = (mainstream + youth)[:4] or [str(pitch.get("headline") or "US culture")]
    headline = str(pitch.get("headline") or "Untitled pitch").strip()
    angle = str(pitch.get("crash_out_angle") or "").strip()
    youth_summary = str(pitch.get("youth_sentiment_summary") or "").strip()
    merch = str(pitch.get("proposed_merch_hook") or "Capitalism broke my dad").strip()
    rank = int(pitch.get("rank") or 1)
    return {
        "id": f"pitch_{day}_{rank}",
        "title": headline[:120],
        "cultural_hook": youth_summary or angle,
        "premise": angle or youth_summary or headline,
        "synopsis": angle or youth_summary,
        "conflict": angle or "Suburban parent anxiety vs Gen Z internet humor.",
        "tone": "Friction-intersection satire — parent panic × youth meme culture",
        "suggested_merch": merch,
        "source_trends": source_trends,
        "characters_involved": ["gary", "linda", "chris", "chloe"],
        "script_key": str(pitch.get("script_key") or "hoa_violation"),
        # Pitch fields preserved for Gate 1 UI
        "is_pitch": True,
        "rank": rank,
        "headline": headline,
        "consensus_score": float(pitch.get("consensus_score") or 0),
        "sources": {"mainstream": mainstream, "youth_social": youth},
        "youth_sentiment_summary": youth_summary,
        "crash_out_angle": angle,
        "proposed_merch_hook": merch,
        "sensitivity_flag": str(pitch.get("sensitivity_flag") or SENSITIVITY_SAFE),
        "run_date": day,
        "score_breakdown": pitch.get("score_breakdown") or {},
    }


def pitches_to_concepts(run: Dict[str, Any]) -> List[Dict[str, Any]]:
    day = str(run.get("run_date") or today_run_date())
    pitches = run.get("pitches") if isinstance(run, dict) else []
    if not isinstance(pitches, list):
        return []
    return [pitch_to_concept(p, run_date=day) for p in pitches[:5] if isinstance(p, dict)]


def is_sensitive_pitch(concept_or_pitch: Dict[str, Any]) -> bool:
    flag = str(
        concept_or_pitch.get("sensitivity_flag")
        or (concept_or_pitch.get("selected_concept") or {}).get("sensitivity_flag")
        or ""
    ).upper()
    return flag == SENSITIVITY_REVIEW


def _str_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out
