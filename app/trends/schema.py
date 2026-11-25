"""
Agent 0 pitch-card schema (client Top-5 Gate 1 format) + concept adapter.
"""
from __future__ import annotations

import time
from datetime import date
from typing import Any, Dict, List, Optional


SENSITIVITY_SAFE = "SAFE"
SENSITIVITY_REVIEW = "SENSITIVE_REVIEW"

# Friction score dimensions (must stay aligned with app.trends.friction.WEIGHTS)
SCORE_DIMENSIONS = (
    (
        "cross_layer_consensus",
        "Cross-layer consensus",
        0.35,
        "Same story hitting Layer A (news) + B (youth) and/or C (niche).",
    ),
    (
        "generational_friction",
        "Generational friction",
        0.30,
        "Parent panic / HOA energy vs Gen Z meme & content culture.",
    ),
    (
        "absurdity_visual_gag",
        "Absurdity & visual gag",
        0.25,
        "How vividly the crash-out can play as 9:16 animation.",
    ),
    (
        "brand_safety",
        "Brand safety",
        0.10,
        "SAFE vs SENSITIVE_REVIEW (violence / tragedy risk).",
    ),
)


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
    out = {
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


def _pretty_source_label(label: str) -> str:
    text = (label or "").strip()
    if not text:
        return text
    try:
        from app.trends.store import _pretty_outlet_name

        return _pretty_outlet_name(text)
    except Exception:
        return text


def enrich_pitch_for_ui(pitch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add display helpers for Top Pitch cards:
    source chips, score dimension rows, layer hits, and a short ranking rationale.
    """
    if not isinstance(pitch, dict):
        return {}
    out = dict(pitch)
    sources = out.get("sources") if isinstance(out.get("sources"), dict) else {}
    mainstream = [_pretty_source_label(x) for x in _str_list(sources.get("mainstream"))]
    youth = [_pretty_source_label(x) for x in _str_list(sources.get("youth_social"))]
    niche = [_pretty_source_label(x) for x in _str_list(sources.get("character_niche") or sources.get("niche"))]
    out["sources"] = {
        "mainstream": mainstream,
        "youth_social": youth,
        "character_niche": niche,
    }
    out["source_groups"] = [
        {"id": "A", "label": "Layer A · Mainstream", "entries": mainstream},
        {"id": "B", "label": "Layer B · Youth / social", "entries": youth},
        {"id": "C", "label": "Layer C · Character niche", "entries": niche},
    ]

    hits = out.get("layer_hits") if isinstance(out.get("layer_hits"), dict) else {}
    out["layer_hit_rows"] = [
        {"id": "A", "label": "Mainstream", "count": int(hits.get("A") or 0)},
        {"id": "B", "label": "Youth / social", "count": int(hits.get("B") or 0)},
        {"id": "C", "label": "Character niche", "count": int(hits.get("C") or 0)},
    ]
    layers_present = [row["id"] for row in out["layer_hit_rows"] if row["count"] > 0]
    out["layers_present"] = layers_present or (
        (["A"] if mainstream else []) + (["B"] if youth else []) + (["C"] if niche else [])
    )

    breakdown = out.get("score_breakdown") if isinstance(out.get("score_breakdown"), dict) else {}
    dim_rows: List[Dict[str, Any]] = []
    for key, label, weight, hint in SCORE_DIMENSIONS:
        try:
            score = float(breakdown.get(key) or 0)
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(10.0, score))
        contribution = round(score * weight, 2)
        dim_rows.append(
            {
                "key": key,
                "label": label,
                "weight_pct": int(round(weight * 100)),
                "score": round(score, 1),
                "contribution": contribution,
                "hint": hint,
                "bar_pct": int(round(score * 10)),
            }
        )
    dim_rows.sort(key=lambda d: float(d.get("contribution") or 0), reverse=True)
    out["score_dimensions"] = dim_rows

    rank = int(out.get("rank") or 0)
    try:
        consensus = float(out.get("consensus_score") or 0)
    except (TypeError, ValueError):
        consensus = 0.0
    top = dim_rows[:2] if dim_rows else []
    if top:
        why_bits = [
            f"{row['label']} {row['score']}/10 ({row['weight_pct']}% weight → +{row['contribution']})"
            for row in top
        ]
        layer_bit = (
            f"Sources span Layer {'+'.join(out['layers_present'])}."
            if len(out.get("layers_present") or []) >= 2
            else (
                f"Primary signal from Layer {(out.get('layers_present') or ['—'])[0]}."
                if out.get("layers_present")
                else "Layer mix was thin on this cluster."
            )
        )
        out["ranking_rationale"] = (
            f"#{rank} because consensus is {consensus:.1f}/10. "
            f"Strongest drivers: {'; '.join(why_bits)}. {layer_bit}"
        )
    else:
        out["ranking_rationale"] = (
            f"#{rank} by consensus score {consensus:.1f}/10 "
            "(dimension breakdown unavailable for this cached run)."
        )
    return out


def enrich_pitch_run_for_ui(run: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = dict(run or {})
    pitches = [enrich_pitch_for_ui(p) for p in (payload.get("pitches") or []) if isinstance(p, dict)]
    payload["pitches"] = pitches
    payload["ranking_legend"] = [
        {
            "key": key,
            "label": label,
            "weight_pct": int(round(weight * 100)),
            "hint": hint,
        }
        for key, label, weight, hint in SCORE_DIMENSIONS
    ]
    meta = dict(payload.get("meta") or {})
    meta.setdefault(
        "ranking_blurb",
        "Top cards are sorted by weighted consensus (1–10): "
        "Cross-layer 35% + Generational friction 30% + Absurdity/visual gag 25% + Brand safety 10%. "
        "Near-duplicate pitches are dropped via embedding similarity against the current batch and the last 14 days.",
    )
    payload["meta"] = meta
    return payload
