"""
LLM Friction Intersection scoring (client Agent 0 weights).

Dimensions (1–10 each):
  Cross-Layer Consensus 35%
  Generational Friction Potential 30%
  Absurdity & Visual Gag Potential 25%
  Brand Safety & Sensitivity Check 10%  → also SAFE / SENSITIVE_REVIEW
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests

from app.config import config
from app.trends.schema import SENSITIVITY_REVIEW, SENSITIVITY_SAFE, normalize_pitch

logger = logging.getLogger(__name__)

WEIGHTS = {
    "cross_layer_consensus": 0.35,
    "generational_friction": 0.30,
    "absurdity_visual_gag": 0.25,
    "brand_safety": 0.10,
}

SYSTEM_PROMPT = """You are the editorial scorer for CRASH OUT, a satirical animated series
about a dysfunctional US suburban family (Gary, Linda, Chris, Chloe).

Score each EVENT CLUSTER for "Friction Intersection" — stories where mainstream suburban
parental anxiety collides with cynical Gen Z / Alpha internet humor.

Return ONLY valid JSON:
{
  "pitches": [
    {
      "cluster_id": "...",
      "headline": "newsroom-style headline",
      "cross_layer_consensus": 1-10,
      "generational_friction": 1-10,
      "absurdity_visual_gag": 1-10,
      "brand_safety": 1-10,
      "sensitivity_flag": "SAFE" | "SENSITIVE_REVIEW",
      "youth_sentiment_summary": "one sentence Gen Z take",
      "crash_out_angle": "detailed Pearson-family escalation (3-5 sentences)",
      "proposed_merch_hook": "short hoodie-ready phrase",
      "sources": {
        "mainstream": ["outlet or trend labels"],
        "youth_social": ["r/sub or meme labels"]
      }
    }
  ]
}

Rules:
- Prefer clusters present in BOTH mainstream (Layer A) and youth (Layer B).
- Reject / mark SENSITIVE_REVIEW for mass tragedies, graphic violence, sexual exploitation of minors, or active war atrocities.
- brand_safety 10 = clearly safe comedy fuel; lower if borderline.
- Produce at most 5 pitches, ranked by editorial strength (you may omit weak clusters).
- crash_out_angle MUST be detailed (3–5 sentences): specific setting (kitchen/driveway/Zoom),
  what Gary/Linda/Chris/Chloe each do, the viral/content beat, and how it escalates into a crash-out.
  Do not write a single short line — make it production-ready episode fuel.
"""


def _clamp(value: Any, default: float = 5.0) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = default
    return max(1.0, min(10.0, num))


def weighted_consensus(breakdown: Dict[str, float]) -> float:
    total = 0.0
    for key, weight in WEIGHTS.items():
        total += _clamp(breakdown.get(key, 5.0)) * weight
    return round(total, 1)


def _cluster_brief(cluster: Dict[str, Any], index: int) -> str:
    items = cluster.get("items") or []
    sample = []
    for it in items[:6]:
        sample.append(
            f"- [{it.get('layer')}/{it.get('outlet') or it.get('source')}] {it.get('title')}"
        )
    return (
        f"{index}. id={cluster.get('id')} label={cluster.get('label')}\n"
        f"   layers={cluster.get('layers')} cross_layer={cluster.get('cross_layer')} "
        f"hits={cluster.get('layer_hits')} members={cluster.get('member_count')}\n"
        f"   outlets={', '.join(cluster.get('outlets') or [])}\n"
        + "\n".join(sample)
    )


def score_clusters_with_llm(clusters: List[Dict[str, Any]], *, run_date: str) -> List[Dict[str, Any]]:
    api_key = (config.openai_api_key or "").strip()
    if not api_key or not clusters:
        return []
    model = (config.openai_model or "gpt-4o-mini").strip()
    brief = "\n\n".join(_cluster_brief(c, i) for i, c in enumerate(clusters[:18], 1))
    user = (
        "Score these event clusters for CRASH OUT daily pitch cards. "
        "Return at most 5 strongest friction-intersection pitches.\n\n"
        f"{brief}"
    )
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.55,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
            },
            timeout=90,
        )
        if resp.status_code != 200:
            logger.warning("Friction LLM %s: %s", resp.status_code, resp.text[:200])
            return []
        content = (((resp.json() or {}).get("choices") or [{}])[0].get("message") or {}).get(
            "content"
        ) or ""
        return _parse_scored_pitches(content, clusters=clusters, run_date=run_date)
    except Exception as exc:
        logger.warning("Friction LLM failed: %s", exc)
        return []


def _parse_scored_pitches(
    content: str, *, clusters: List[Dict[str, Any]], run_date: str
) -> List[Dict[str, Any]]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    raw = data.get("pitches") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return []
    by_id = {str(c.get("id")): c for c in clusters}
    pitches: List[Dict[str, Any]] = []
    for i, row in enumerate(raw[:5], 1):
        if not isinstance(row, dict):
            continue
        breakdown = {
            "cross_layer_consensus": _clamp(row.get("cross_layer_consensus"), 5),
            "generational_friction": _clamp(row.get("generational_friction"), 5),
            "absurdity_visual_gag": _clamp(row.get("absurdity_visual_gag"), 5),
            "brand_safety": _clamp(row.get("brand_safety"), 8),
        }
        cluster = by_id.get(str(row.get("cluster_id") or ""))
        sources = row.get("sources") if isinstance(row.get("sources"), dict) else {}
        mainstream = list(sources.get("mainstream") or [])
        youth = list(sources.get("youth_social") or [])
        if cluster:
            if not mainstream:
                mainstream = [
                    o
                    for o in (cluster.get("outlets") or [])
                    if not str(o).startswith("r/")
                ][:4]
            if not youth:
                youth = [o for o in (cluster.get("outlets") or []) if str(o).startswith("r/")][:4]
        flag = str(row.get("sensitivity_flag") or SENSITIVITY_SAFE).upper()
        if breakdown["brand_safety"] < 4:
            flag = SENSITIVITY_REVIEW
        pitch = normalize_pitch(
            {
                "rank": i,
                "headline": row.get("headline") or (cluster or {}).get("label"),
                "consensus_score": weighted_consensus(breakdown),
                "sources": {"mainstream": mainstream, "youth_social": youth},
                "youth_sentiment_summary": row.get("youth_sentiment_summary"),
                "crash_out_angle": row.get("crash_out_angle"),
                "proposed_merch_hook": row.get("proposed_merch_hook"),
                "sensitivity_flag": flag,
                "score_breakdown": breakdown,
                "cluster_id": row.get("cluster_id") or (cluster or {}).get("id"),
                "layer_hits": (cluster or {}).get("layer_hits") or {},
            },
            rank=i,
            run_date=run_date,
        )
        pitches.append(pitch)
    pitches.sort(key=lambda p: float(p.get("consensus_score") or 0), reverse=True)
    for i, p in enumerate(pitches, 1):
        p["rank"] = i
    return pitches[:5]


def score_clusters_heuristic(clusters: List[Dict[str, Any]], *, run_date: str) -> List[Dict[str, Any]]:
    """Deterministic fallback when no LLM key is available."""
    pitches: List[Dict[str, Any]] = []
    for cluster in clusters[:12]:
        hits = cluster.get("layer_hits") or {}
        a, b, c = int(hits.get("A") or 0), int(hits.get("B") or 0), int(hits.get("C") or 0)
        cross = 9.0 if a and b else (6.5 if (a and c) or (b and c) else 4.0)
        if a and b and c:
            cross = 10.0
        friction = 8.5 if cluster.get("cross_layer") else 5.5
        if any(ch in (cluster.get("characters") or []) for ch in ("gary", "linda")) and b:
            friction = 9.0
        absurdity = 7.0 + min(2.0, (cluster.get("member_count") or 1) / 5.0)
        safety = 9.0
        label = str(cluster.get("label") or "").lower()
        sensitive_tokens = (
            "shooting",
            "killed",
            "murder",
            "massacre",
            "rape",
            "suicide",
            "bombing",
        )
        flag = SENSITIVITY_SAFE
        if any(tok in label for tok in sensitive_tokens):
            safety = 2.0
            flag = SENSITIVITY_REVIEW
        breakdown = {
            "cross_layer_consensus": cross,
            "generational_friction": friction,
            "absurdity_visual_gag": absurdity,
            "brand_safety": safety,
        }
        outlets = cluster.get("outlets") or []
        mainstream = [o for o in outlets if not str(o).startswith("r/")][:4]
        youth = [o for o in outlets if str(o).startswith("r/")][:4]
        if not youth and b:
            youth = ["youth social signal"]
        if not mainstream and a:
            mainstream = ["mainstream signal"]
        headline = str(cluster.get("label") or "Suburban friction story")
        angle = (
            f"In the Pearson kitchen, Gary doomscrolls a push alert about '{headline}' and starts "
            f"narrating it like a rally speech while his stress watch flashes CRITICAL. "
            f"Linda interrupts with vibrational HOA optics language, insisting the family cannot "
            f"look 'chaotically online' in front of the cul-de-sac. Chloe already has a vertical "
            f"livestream framed on Gary's reflection in the toaster, selling the meltdown as content, "
            f"while Chris open-sources the household budget in the comments to prove Dad is cooked. "
            f"The beat escalates when Gary tries to ban phones mid-sentence and accidentally "
            f"confirms every joke the kids are clipping for the algorithm."
        )
        pitches.append(
            normalize_pitch(
                {
                    "headline": headline[:140],
                    "consensus_score": weighted_consensus(breakdown),
                    "sources": {"mainstream": mainstream or ["US news"], "youth_social": youth or ["youth discourse"]},
                    "youth_sentiment_summary": (
                        "Gen Z treats the story as proof that adults are cooked and content is the only exit."
                    ),
                    "crash_out_angle": angle,
                    "proposed_merch_hook": "My Dad Survived Another News Cycle",
                    "sensitivity_flag": flag,
                    "score_breakdown": breakdown,
                    "cluster_id": cluster.get("id"),
                    "layer_hits": hits,
                },
                rank=len(pitches) + 1,
                run_date=run_date,
            )
        )
    pitches.sort(key=lambda p: float(p.get("consensus_score") or 0), reverse=True)
    # Prefer cross-layer non-sensitive
    safe = [p for p in pitches if p.get("sensitivity_flag") != SENSITIVITY_REVIEW]
    ordered = safe + [p for p in pitches if p not in safe]
    for i, p in enumerate(ordered[:5], 1):
        p["rank"] = i
    return ordered[:5]


def score_clusters(clusters: List[Dict[str, Any]], *, run_date: str) -> List[Dict[str, Any]]:
    scored = score_clusters_with_llm(clusters, run_date=run_date)
    if len(scored) >= 3:
        return scored[:5]
    heuristic = score_clusters_heuristic(clusters, run_date=run_date)
    if scored:
        # Fill remaining slots from heuristic
        seen = {str(p.get("headline") or "").lower() for p in scored}
        for p in heuristic:
            if str(p.get("headline") or "").lower() in seen:
                continue
            scored.append(p)
            if len(scored) >= 5:
                break
        for i, p in enumerate(scored[:5], 1):
            p["rank"] = i
        return scored[:5]
    return heuristic
