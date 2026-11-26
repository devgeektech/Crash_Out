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

    # Episode name is the canonical title; merch punchline must match it.
    episode_name = str(
        raw.get("episode_name") or raw.get("headline") or raw.get("title") or f"Pitch {rank}"
    ).strip()[:140]
    merch = episode_name  # merch punchline == episode name

    storyline = str(
        raw.get("possible_storyline")
        or raw.get("crash_out_angle")
        or raw.get("premise")
        or ""
    ).strip()
    comedy = str(
        raw.get("comedy_angle")
        or raw.get("youth_sentiment_summary")
        or raw.get("cultural_hook")
        or ""
    ).strip()
    potential = str(raw.get("episode_potential") or "").strip()
    if not potential:
        potential = (
            f"Friction score {round(score, 1)}/10 — strong suburban satire potential "
            f"from cross-layer news heat and Pearson family collision."
        )
    characters = str(
        raw.get("character_involvement")
        or raw.get("characters_blurb")
        or ""
    ).strip()
    if not characters:
        characters = (
            "Gary spirals into conspiracy/DIY panic; Linda weaponizes wellness + HOA optics; "
            "Chris monetizes the chaos with dry tech nihilism; Chloe turns the meltdown into a livestream poll."
        )

    out = {
        "rank": int(raw.get("rank") or rank),
        # Canonical + legacy aliases kept in sync for Gate 1 / Agent 1
        "episode_name": episode_name,
        "headline": episode_name,
        "title": episode_name,
        "merch_punchline": merch,
        "proposed_merch_hook": merch,
        "suggested_merch": merch,
        "episode_potential": potential,
        "character_involvement": characters,
        "possible_storyline": storyline,
        "crash_out_angle": storyline,
        "premise": storyline,
        "comedy_angle": comedy,
        "youth_sentiment_summary": comedy,
        "cultural_hook": comedy,
        "consensus_score": round(score, 1),
        "sources": {
            "mainstream": mainstream[:6],
            "youth_social": youth[:6],
        },
        "sensitivity_flag": flag,
        "run_date": run_date,
        "score_breakdown": raw.get("score_breakdown") if isinstance(raw.get("score_breakdown"), dict) else {},
        "cluster_id": raw.get("cluster_id"),
        "layer_hits": raw.get("layer_hits") if isinstance(raw.get("layer_hits"), dict) else {},
        "characters_involved": raw.get("characters_involved")
        if isinstance(raw.get("characters_involved"), list)
        else ["gary", "linda", "chris", "chloe"],
    }
    if "embedding" in raw and isinstance(raw["embedding"], (list, tuple)) and len(raw["embedding"]) == 1536:
        out["embedding"] = list(raw["embedding"])
    return out


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
    normalized = normalize_pitch(pitch, rank=int(pitch.get("rank") or 1), run_date=run_date or pitch.get("run_date") or today_run_date())
    day = str(normalized.get("run_date") or today_run_date())
    sources = normalized.get("sources") if isinstance(normalized.get("sources"), dict) else {}
    mainstream = _str_list(sources.get("mainstream"))
    youth = _str_list(sources.get("youth_social"))
    episode_name = str(normalized.get("episode_name") or "Untitled pitch").strip()
    storyline = str(normalized.get("possible_storyline") or "").strip()
    comedy = str(normalized.get("comedy_angle") or "").strip()
    merch = episode_name
    potential = str(normalized.get("episode_potential") or "").strip()
    characters = str(normalized.get("character_involvement") or "").strip()
    rank = int(normalized.get("rank") or 1)
    source_trends = (mainstream + youth)[:4] or [episode_name or "US culture"]
    return {
        "id": f"pitch_{day}_{rank}",
        "title": episode_name[:120],
        "episode_name": episode_name,
        "cultural_hook": comedy or storyline,
        "premise": storyline or comedy or episode_name,
        "synopsis": storyline or comedy,
        "conflict": storyline or "Suburban parent anxiety vs Gen Z internet humor.",
        "tone": "Friction-intersection satire — parent panic × youth meme culture",
        "suggested_merch": merch,
        "merch_punchline": merch,
        "source_trends": source_trends,
        "characters_involved": normalized.get("characters_involved") or ["gary", "linda", "chris", "chloe"],
        "character_involvement": characters,
        "episode_potential": potential,
        "possible_storyline": storyline,
        "comedy_angle": comedy,
        "script_key": str(pitch.get("script_key") or "hoa_violation"),
        "is_pitch": True,
        "rank": rank,
        "headline": episode_name,
        "consensus_score": float(normalized.get("consensus_score") or 0),
        "sources": {"mainstream": mainstream, "youth_social": youth},
        "youth_sentiment_summary": comedy,
        "crash_out_angle": storyline,
        "proposed_merch_hook": merch,
        "sensitivity_flag": str(normalized.get("sensitivity_flag") or SENSITIVITY_SAFE),
        "run_date": day,
        "score_breakdown": normalized.get("score_breakdown") or {},
    }


def pitches_to_concepts(run_or_pitches: Any) -> List[Dict[str, Any]]:
    if isinstance(run_or_pitches, dict):
        day = str(run_or_pitches.get("run_date") or today_run_date())
        pitches = run_or_pitches.get("pitches") or []
    elif isinstance(run_or_pitches, list):
        day = today_run_date()
        pitches = run_or_pitches
    else:
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
