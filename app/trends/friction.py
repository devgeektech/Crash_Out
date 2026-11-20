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
import time
from typing import Any, Dict, List, Optional

import requests

from app.config import config
from app.db import log_system_incident
from app.trends.schema import SENSITIVITY_REVIEW, SENSITIVITY_SAFE, normalize_pitch

logger = logging.getLogger(__name__)

WEIGHTS = {
    "cross_layer_consensus": 0.35,
    "generational_friction": 0.30,
    "absurdity_visual_gag": 0.25,
    "brand_safety": 0.10,
}

SYSTEM_PROMPT = """You are the lead editorial satirist and scorer for CRASH OUT, an adult 2D animated web series (South Park meets Arrested Development in modern US suburbia).

Your job: Take breaking US news/social trend clusters and forge them into 5 distinct, highly versatile, explosive episode pitches for the Pearson family.

THE CAST:
- GARY (44): Overleveraged suburban dad. Tries gentle parenting until his stress watch hits 175 BPM, then pivots to MAGA/sovereign-citizen conspiracy logic, tactical DIY over-engineering, or stockpiling weird gear.
- LINDA (42): Performative Goop-wellness / HOA architectural review committee enforcer. Weaponizes gentle-mom therapy jargon and neighborhood petitions while hiding secret fast-food binges from the Ring doorbell camera.
- CHRIS (15): Techno-nihilist Gen Z doomer. Monotone, dry existential philosophy. Hacks neighborhood tech, runs absurd arbitrage bots, shorts local businesses on Robinhood.
- CHLOE (11): Ruthless pre-teen influencer / "momager". Treats her parents' meltdowns as monetizable content. Conducts street interviews with bewildered bystanders, runs live TikTok polls ("Vote: Should Dad get arrested or apologize?"), sells drop-shipped merch mid-crisis.

CRITICAL RULES FOR "crash_out_angle" VERSATILITY:
- DO NOT default repeatedly to the Pearson kitchen or driveway. Every pitch MUST explore a DIFFERENT suburban arena across modern America:
  * RETAIL / CONSUMER: Costco bulk aisle standoff, Trader Joe's parking spot territorial battle, Apple Store Genius Bar warranty meltdown, Self-checkout kiosk error accusations, Drive-thru intercom screaming match, Car dealership showroom EV lease negotiation.
  * SUBURBAN CIVIC & RECREATIONAL: HOA Emergency Board meeting, School Board public microphone spectacle, High school sports bleachers, Pickleball court turf war, Little League dugout brawl, Community pool wristband enforcement raid.
  * IN-TRANSIT & INFRASTRUCTURE: Stalled in a Cybertruck charging queue, TSA security line status clash, Family road-trip EV battery range anxiety, Urgent Care waiting room triage dispute.
  * DOMESTIC BEYOND THE KITCHEN: Cul-de-sac property-line dispute with neighbor's robot lawnmower, Open House walkthrough where Linda pretends to buy, Attic prepper stash crisis, Backyard BBQ smoking out the neighbor's wedding.
- Each pitch MUST have 3-5 vivid sentences establishing:
  1. Setting: Specific, visual, culturally resonant location.
  2. Inciting Conflict: How today's news event creates suburban crisis.
  3. Character Collision: Unique, non-repetitive actions for Gary, Linda, Chris, and Chloe.
  4. The Crash-Out Climax: Fresh, visual escalation (e.g., local TV news vans arrive, HOA golf-cart chase, store manager calling the police, Chloe's livestream poll deciding Gary's fate, sirens blaring).

Return ONLY valid JSON matching this exact structure:
{
  "pitches": [
    {
      "cluster_id": "...",
      "headline": "newsroom-style punchy headline",
      "cross_layer_consensus": 1-10,
      "generational_friction": 1-10,
      "absurdity_visual_gag": 1-10,
      "brand_safety": 1-10,
      "sensitivity_flag": "SAFE" | "SENSITIVE_REVIEW",
      "youth_sentiment_summary": "one sentence cynical Gen Z / TikTok takeaway",
      "crash_out_angle": "detailed, versatile 3-5 sentence narrative escalation",
      "proposed_merch_hook": "punchy 2-4 word hoodie slogan",
      "sources": {
        "mainstream": ["outlet or trend labels"],
        "youth_social": ["r/sub or meme labels"]
      }
    }
  ]
}

- Produce exactly 5 top friction pitches ranked 1 to 5.
- Reject / mark SENSITIVE_REVIEW for mass violence, tragic loss of life, or explicit atrocities.
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
    if not api_key:
        err_msg = "OpenAI API key (OPENAI_API_KEY) is missing. Set OPENAI_API_KEY in .env."
        logger.error(err_msg)
        log_system_incident(
            event_type="AGENT0_CONFIG_ERROR",
            actor="Agent M Orchestrator",
            details={
                "category": "Agent 0 Trend Ingest",
                "task_name": "OpenAI Configuration Check",
                "error": err_msg,
                "can_retry": True,
            },
        )
        raise RuntimeError(err_msg)

    if not clusters:
        return []

    model = (config.openai_model or "gpt-6-luna").strip()
    brief = "\n\n".join(_cluster_brief(c, i) for i, c in enumerate(clusters[:18], 1))
    user = (
        "Score these event clusters for CRASH OUT daily pitch cards. "
        "Return at most 5 strongest friction-intersection pitches with maximum narrative and setting versatility.\n\n"
        f"{brief}"
    )
    payload: Dict[str, Any] = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    # Only set temperature if not a model that rejects non-default values (luna, o1, o3, etc.)
    if not any(m in model.lower() for m in ("luna", "o1", "o3", "reasoning")):
        payload["temperature"] = 0.75

    max_retries = 3
    last_error = ""

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Agent M: Scoring clusters via OpenAI (%s) — attempt %d/%d...", model, attempt, max_retries)
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=90,
            )
            if resp.status_code == 200:
                content = (((resp.json() or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                pitches = _parse_scored_pitches(content, clusters=clusters, run_date=run_date)
                if pitches and len(pitches) >= 1:
                    logger.info("Agent M: Successfully scored %d pitches via OpenAI on attempt %d.", len(pitches), attempt)
                    return pitches
                else:
                    last_error = f"OpenAI returned empty or unparseable pitch payload: {content[:150]}"
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:250]}"
        except Exception as exc:
            last_error = f"Request exception: {exc}"

        logger.warning("Agent M: Scoring attempt %d/%d failed: %s", attempt, max_retries, last_error)
        if attempt < max_retries:
            time.sleep(2.0 * attempt)

    # All 3 automated retries exhausted — log incident to Agent M and fail explicitly (NO fallback!)
    incident_msg = f"Agent 0 LLM scoring failed after {max_retries} automated attempts: {last_error}"
    logger.error("Agent M Alert: %s. Requires manual retry.", incident_msg)
    log_system_incident(
        event_type="AGENT0_LLM_FAILURE",
        actor="Agent M Orchestrator",
        details={
            "category": "Agent 0 Trend Ingest",
            "task_name": "OpenAI Pitch Generation",
            "error": incident_msg,
            "retry_count": max_retries,
            "max_retries": 3,
            "requires_manual_retry": True,
            "can_retry": True,
            "run_date": run_date,
        },
    )
    raise RuntimeError(f"{incident_msg}. Manual retry required via Agent M.")


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
    from app.trends.cluster import embed_texts, cosine
    from app.trends.store import find_similar_pitches

    candidates = score_clusters_with_llm(clusters, run_date=run_date)
    if not candidates:
        raise RuntimeError(
            "Agent 0 LLM scoring returned 0 candidate pitches after automated retries. "
            "Incident logged in Agent M. Manual retry required via UI."
        )

    # Generate embeddings for candidate pitches for similarity validation
    pitch_texts = [
        f"{p.get('headline') or ''}. {p.get('youth_sentiment_summary') or ''} {p.get('crash_out_angle') or ''}"
        for p in candidates
    ]
    embeddings = embed_texts(pitch_texts) or []

    valid_pitches: List[Dict[str, Any]] = []
    accepted_embeddings: List[List[float]] = []

    for i, p in enumerate(candidates):
        emb = embeddings[i] if (embeddings and i < len(embeddings)) else None
        is_duplicate = False

        if emb and len(emb) == 1536:
            # 1. Intra-batch uniqueness check against already accepted pitches in this run
            for prev_emb in accepted_embeddings:
                sim = cosine(emb, prev_emb)
                if sim >= 0.82:
                    logger.info("Skipping candidate pitch '%s' - too similar to current batch (%.2f)", p.get("headline"), sim)
                    is_duplicate = True
                    break

            # 2. Historical database check via pgvector
            if not is_duplicate:
                similar_hist = find_similar_pitches(emb, threshold=0.82, limit=1)
                if similar_hist:
                    matched = similar_hist[0]
                    logger.info(
                        "Skipping candidate pitch '%s' - matches historical pitch '%s' (similarity: %s)",
                        p.get("headline"),
                        matched.get("headline"),
                        matched.get("similarity"),
                    )
                    is_duplicate = True

            if not is_duplicate:
                p["embedding"] = emb
                accepted_embeddings.append(emb)
        else:
            # Fallback when embeddings are not available: Jaccard text comparison
            from app.trends.cluster import jaccard
            p_text = pitch_texts[i]
            for prev_p in valid_pitches:
                prev_text = f"{prev_p.get('headline') or ''}. {prev_p.get('crash_out_angle') or ''}"
                if jaccard(p_text, prev_text) >= 0.65:
                    is_duplicate = True
                    break

        if not is_duplicate:
            valid_pitches.append(p)
            if len(valid_pitches) >= 5:
                break

    # If strict filtering left us with fewer than 5, backfill from remaining candidates to keep system resilient
    if len(valid_pitches) < 5:
        existing_ids = {p.get("cluster_id") or p.get("headline") for p in valid_pitches}
        for p in candidates:
            ident = p.get("cluster_id") or p.get("headline")
            if ident not in existing_ids:
                valid_pitches.append(p)
                if len(valid_pitches) >= 5:
                    break

    for i, p in enumerate(valid_pitches[:5], 1):
        p["rank"] = i
    return valid_pitches[:5]
