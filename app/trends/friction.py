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
import os
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

CRITICAL RULES FOR "possible_storyline" VERSATILITY:
- DO NOT default repeatedly to the Pearson kitchen or driveway. Every pitch MUST explore a DIFFERENT suburban arena across modern America:
  * RETAIL / CONSUMER: Costco bulk aisle standoff, Trader Joe's parking spot territorial battle, Apple Store Genius Bar warranty meltdown, Self-checkout kiosk error accusations, Drive-thru intercom screaming match, Car dealership showroom EV lease negotiation.
  * SUBURBAN CIVIC & RECREATIONAL: HOA Emergency Board meeting, School Board public microphone spectacle, High school sports bleachers, Pickleball court turf war, Little League dugout brawl, Community pool wristband enforcement raid.
  * IN-TRANSIT & INFRASTRUCTURE: Stalled in a Cybertruck charging queue, TSA security line status clash, Family road-trip EV battery range anxiety, Urgent Care waiting room triage dispute.
  * DOMESTIC BEYOND THE KITCHEN: Cul-de-sac property-line dispute with neighbor's robot lawnmower, Open House walkthrough where Linda pretends to buy, Attic prepper stash crisis, Backyard BBQ smoking out the neighbor's wedding.
- possible_storyline MUST be 3-5 vivid sentences covering setting, inciting conflict, character collision, and crash-out climax.
- merch_punchline MUST be identical to episode_name (hoodie-ready episode title).

Return ONLY valid JSON matching this exact structure:
{
  "pitches": [
    {
      "cluster_id": "...",
      "episode_name": "punchy episode title that also works as hoodie merch",
      "merch_punchline": "MUST equal episode_name exactly",
      "episode_potential": "1-2 sentences on why this episode can pop / viral + satire upside",
      "character_involvement": "how Gary, Linda, Chris, and Chloe specifically collide in this episode",
      "possible_storyline": "3-5 sentence narrative escalation",
      "comedy_angle": "the core satirical joke / comedy engine in 1-2 sentences",
      "cross_layer_consensus": 1-10,
      "generational_friction": 1-10,
      "absurdity_visual_gag": 1-10,
      "brand_safety": 1-10,
      "sensitivity_flag": "SAFE" | "SENSITIVE_REVIEW",
      "sources": {
        "mainstream": ["outlet or trend labels"],
        "youth_social": ["r/sub or meme labels"]
      }
    }
  ]
}

- Produce 8 to 10 top friction pitches ranked 1 to 10 (the downstream selector will pick the top 5 most original, non-duplicate concepts).
- For selected-topic Create Pitch, return exactly one complete pitch with all six content fields filled.
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
    editorial = str(cluster.get("agent_take") or cluster.get("editorial") or "").strip()
    summary = str(cluster.get("ai_summary") or "").strip()
    extra = []
    if summary:
        extra.append(f"   ai_summary={summary[:280]}")
    if editorial:
        extra.append(f"   agent_take={editorial[:320]}")
    return (
        f"{index}. id={cluster.get('id')} label={cluster.get('label')}\n"
        f"   layers={cluster.get('layers')} cross_layer={cluster.get('cross_layer')} "
        f"hits={cluster.get('layer_hits')} members={cluster.get('member_count')}\n"
        f"   outlets={', '.join(cluster.get('outlets') or [])}\n"
        + ("\n".join(extra) + "\n" if extra else "")
        + "\n".join(sample)
    )


def _hitl_regen_block(
    *,
    mode: str = "fresh",
    guidance: str = "",
    prior_pitch: Optional[Dict[str, Any]] = None,
) -> str:
    """Extra user-prompt instructions for Regenerate / Improve HITL."""
    mode = str(mode or "fresh").strip().lower()
    notes = str(guidance or "").strip()
    prior = prior_pitch if isinstance(prior_pitch, dict) else {}
    prior_bits = []
    for key, label in (
        ("episode_name", "Episode name"),
        ("headline", "Headline"),
        ("merch_punchline", "Merch"),
        ("episode_potential", "Episode potential"),
        ("character_involvement", "Characters"),
        ("possible_storyline", "Storyline"),
        ("comedy_angle", "Comedy"),
        ("crash_out_angle", "Crash-out angle"),
        ("premise", "Premise"),
    ):
        val = str(prior.get(key) or "").strip()
        if val:
            prior_bits.append(f"- {label}: {val[:280]}")
    prior_block = "\n".join(prior_bits[:8])

    if mode in {"improve", "revise", "edit"}:
        if not notes and not prior_block:
            return ""
        return (
            "\n\nHITL IMPROVE MODE (human-in-the-loop):\n"
            "Rewrite ONE stronger pitch for the same topic using the notes below.\n"
            "Keep the same news/social event, but upgrade satire, character collision, and merch punch.\n"
            "Return a FULL replacement pitch card (not a diff).\n"
            + (f"Human improvement notes:\n{notes}\n" if notes else "")
            + (f"Current pitch to improve:\n{prior_block}\n" if prior_block else "")
        )

    # fresh regenerate
    return (
        "\n\nHITL REGENERATE MODE:\n"
        "Generate a COMPLETELY NEW pitch for this topic — different episode_name, storyline, comedy angle, and character collision.\n"
        "Do NOT reuse the previous merch punchline or climax.\n"
        + (f"Optional human direction:\n{notes}\n" if notes else "")
        + (f"Avoid echoing this previous pitch:\n{prior_block}\n" if prior_block else "")
    )


def score_clusters_with_llm(
    clusters: List[Dict[str, Any]],
    *,
    run_date: str,
    mode: str = "fresh",
    guidance: str = "",
    prior_pitch: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Score clusters via OpenAI. Returns [] on failure so callers can heuristic-fallback.
    Single-topic Create Pitch asks for exactly one card (not an empty batch).
    """
    api_key = (config.openai_api_key or "").strip()
    if not api_key:
        err_msg = "OpenAI API key (OPENAI_API_KEY) is missing. Set OPENAI_API_KEY in .env."
        logger.error("[friction] %s", err_msg)
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
        logger.warning("[friction] score_clusters_with_llm called with 0 clusters")
        return []

    from app.trends.store import load_recent_pitches_for_dedup

    selected_mode = len(clusters) <= 2
    hitl_mode = str(mode or "fresh").strip().lower()
    logger.info(
        "[friction] LLM scoring start · clusters=%d · mode=%s · hitl=%s · run_date=%s",
        len(clusters),
        "selected_topic" if selected_mode else "daily_batch",
        hitl_mode,
        run_date,
    )

    # Collect prior pitch history from the last 14 days to inoculate the LLM against duplicates
    recent_history = load_recent_pitches_for_dedup(days=14)
    exclusion_text = ""
    if recent_history:
        seen_headlines = set()
        exclusion_lines = []
        for item in recent_history:
            hl = (item.get("headline") or "").strip()
            if hl and hl.lower() not in seen_headlines:
                seen_headlines.add(hl.lower())
                angle_snip = (item.get("crash_out_angle") or "")[:110].replace("\n", " ").strip()
                r_day = item.get("run_date") or "recent"
                exclusion_lines.append(f'- "{hl}" ({r_day}): {angle_snip}...')
            if len(exclusion_lines) >= 16:
                break
        if exclusion_lines:
            if selected_mode:
                # Explicit user pick: never refuse with empty pitches[]; just demand a fresh angle.
                exclusion_text = (
                    "\n\nANGLE FRESHNESS (selected topic — still REQUIRED to return a pitch):\n"
                    "Recent studio pitches (avoid copying their crash_out_angle / merch):\n"
                    + "\n".join(exclusion_lines[:8])
                    + "\n- You MUST still return a non-empty pitches array for the selected cluster.\n"
                    "- Invent a NEW suburban arena and climax even if the news topic overlaps.\n"
                )
            else:
                exclusion_text = (
                    "\n\nCRITICAL DEDUPLICATION RULE — DO NOT REPEAT RECENT TOPICS:\n"
                    "The studio has ALREADY produced pitches on these topics in the last 14 days:\n"
                    + "\n".join(exclusion_lines)
                    + "\n\nSTRICT REQUIREMENT:\n"
                    "- Do NOT generate pitches covering these same news events, companies, controversy angles, or suburban situations.\n"
                    "- Every candidate pitch MUST explore fresh real-world news friction with novel settings and unique collision dynamics.\n"
                )

    model = (config.openai_model or "gpt-6-luna").strip()
    brief = "\n\n".join(_cluster_brief(c, i) for i, c in enumerate(clusters[:18], 1))
    hitl_block = _hitl_regen_block(mode=hitl_mode, guidance=guidance, prior_pitch=prior_pitch)
    if selected_mode:
        cluster_ids = ", ".join(str(c.get("id") or "") for c in clusters)
        user = (
            "SELECTED-TOPIC Create Pitch handoff for CRASH OUT.\n"
            f"Return EXACTLY {len(clusters)} pitch object(s) in pitches[] — one per cluster below.\n"
            f"Required cluster_id value(s): {cluster_ids}\n"
            "Each pitch MUST include: episode_name, merch_punchline (= episode_name), "
            "episode_potential, character_involvement, possible_storyline, comedy_angle.\n"
            "NEVER return {\"pitches\": []}. If unsure, still invent a strong possible_storyline.\n"
            "Use ai_summary / agent_take when provided as editorial context.\n"
            f"{exclusion_text}"
            f"{hitl_block}\n"
            f"EVENT CLUSTER(S) TO SCORE:\n\n{brief}"
        )
    else:
        user = (
            "Score these event clusters for CRASH OUT daily pitch cards.\n"
            "Generate 8 to 10 top candidate pitches ranked by friction consensus and originality.\n"
            "Ensure maximum narrative, thematic, and suburban setting versatility.\n"
            "NEVER return an empty pitches array when clusters are provided.\n"
            f"{exclusion_text}"
            f"{hitl_block}\n"
            f"EVENT CLUSTERS TO SCORE:\n\n{brief}"
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
    is_reasoning = any(m in model.lower() for m in ("luna", "o1", "o3", "reasoning"))
    if not is_reasoning:
        payload["temperature"] = 0.75
        payload["max_tokens"] = 3500
    else:
        # gpt-*-luna / reasoning models reject temperature + max_tokens
        payload["max_completion_tokens"] = 4000

    max_retries = 3
    last_error = ""

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "[friction] OpenAI chat.completions · model=%s · attempt=%d/%d · clusters=%d",
                model,
                attempt,
                max_retries,
                len(clusters),
            )
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
                body = resp.json() or {}
                content = (((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
                usage = body.get("usage") or {}
                logger.info(
                    "[friction] OpenAI OK · attempt=%d · content_chars=%d · usage=%s · preview=%s",
                    attempt,
                    len(content),
                    {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage},
                    (content[:120] or "").replace("\n", " "),
                )
                pitches = _parse_scored_pitches(content, clusters=clusters, run_date=run_date)
                if pitches and len(pitches) >= 1:
                    logger.info(
                        "[friction] Parsed %d pitch(es) from OpenAI on attempt %d",
                        len(pitches),
                        attempt,
                    )
                    return pitches
                last_error = f"OpenAI returned empty or unparseable pitch payload: {(content or '')[:180]}"
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:250]}"
                logger.warning("[friction] OpenAI HTTP error · %s", last_error)
        except Exception as exc:
            last_error = f"Request exception: {exc}"
            logger.warning("[friction] OpenAI request exception · %s", exc)

        logger.warning("[friction] Scoring attempt %d/%d failed: %s", attempt, max_retries, last_error)
        empty_payload = "empty or unparseable" in last_error
        if attempt < max_retries:
            # Empty JSON is not a rate-limit — short retry. HTTP/network uses longer delay.
            if empty_payload:
                retry_delay_sec = int(os.getenv("AGENT_EMPTY_RETRY_SECONDS", "3"))
            else:
                retry_delay_sec = int(os.getenv("AGENT_RETRY_INTERVAL_SECONDS", "15"))
            logger.info(
                "[friction] Waiting %ds before retry attempt %d/%d...",
                retry_delay_sec,
                attempt + 1,
                max_retries,
            )
            time.sleep(retry_delay_sec)

    incident_msg = f"Agent 0 LLM scoring failed after {max_retries} automated attempts: {last_error}"
    logger.error("[friction] %s — falling back to heuristic scoring.", incident_msg)
    log_system_incident(
        event_type="AGENT0_LLM_FAILURE",
        actor="Agent M Orchestrator",
        details={
            "category": "Agent 0 Trend Ingest",
            "task_name": "OpenAI Pitch Generation",
            "error": incident_msg,
            "retry_count": max_retries,
            "max_retries": 3,
            "requires_manual_retry": False,
            "fallback": "heuristic",
            "can_retry": True,
            "run_date": run_date,
            "cluster_count": len(clusters),
            "mode": "selected_topic" if selected_mode else "daily_batch",
        },
    )
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
        episode_name = (
            row.get("episode_name")
            or row.get("headline")
            or row.get("title")
            or (cluster or {}).get("label")
        )
        pitch = normalize_pitch(
            {
                "rank": i,
                "episode_name": episode_name,
                "merch_punchline": episode_name,  # enforced same as episode name
                "episode_potential": row.get("episode_potential"),
                "character_involvement": row.get("character_involvement"),
                "possible_storyline": row.get("possible_storyline") or row.get("crash_out_angle"),
                "comedy_angle": row.get("comedy_angle") or row.get("youth_sentiment_summary"),
                "consensus_score": weighted_consensus(breakdown),
                "sources": {"mainstream": mainstream, "youth_social": youth},
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
    """Deterministic fallback when LLM is unavailable or returns empty pitches[]."""
    logger.info("[friction] Heuristic scoring · clusters=%d · run_date=%s", len(clusters), run_date)
    pitches: List[Dict[str, Any]] = []
    for cluster in clusters[:12]:
        hits = cluster.get("layer_hits") or {}
        a, b = int(hits.get("A") or 0), int(hits.get("B") or 0)
        # Layer C removed — cross-layer consensus is Mainstream × Social only.
        cross = 9.0 if a and b else 4.0
        if cluster.get("ai_consensus_score") is not None:
            try:
                ai_score = float(cluster.get("ai_consensus_score"))
                # Map 0-100 or 1-10 editorial score into cross-layer-ish weight
                if ai_score > 10:
                    cross = max(cross, min(10.0, ai_score / 10.0))
                else:
                    cross = max(cross, min(10.0, ai_score))
            except (TypeError, ValueError):
                pass
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
        editorial = str(cluster.get("agent_take") or cluster.get("editorial") or "").strip()
        summary = str(cluster.get("ai_summary") or "").strip()
        if editorial and len(editorial) > 40:
            angle = editorial[:900]
        else:
            angle = (
                f"At a Costco bulk aisle, Gary doomscrolls a push alert about '{headline}' and starts "
                f"narrating it like a rally speech while his stress watch flashes CRITICAL. "
                f"Linda interrupts with vibrational HOA optics language, insisting the family cannot "
                f"look 'chaotically online' in front of the sample cart. Chloe already has a vertical "
                f"livestream framed on Gary's reflection in the freezer door, selling the meltdown as content, "
                f"while Chris open-sources the household budget in the comments to prove Dad is cooked. "
                f"The beat escalates when a store manager and two local news phones arrive mid-argument."
            )
            if summary:
                angle = f"{summary[:180].rstrip('.')}. {angle}"
        comedy = (
            summary[:220]
            if summary
            else "Adults panic in public while the kids treat the meltdown as monetizable content."
        )
        characters = (
            "Gary doomscrolls into conspiracy/DIY panic; Linda polices HOA optics with wellness jargon; "
            "Chris dryly hacks the money/status math; Chloe livestreams the climax for engagement."
        )
        potential = (
            f"Cross-layer heat ({a}A/{b}B) plus Pearson collision makes a tight 60s short with clear merch hook."
        )
        episode_name = headline[:140]
        pitches.append(
            normalize_pitch(
                {
                    "episode_name": episode_name,
                    "merch_punchline": episode_name,
                    "episode_potential": potential,
                    "character_involvement": characters,
                    "possible_storyline": angle,
                    "comedy_angle": comedy,
                    "consensus_score": weighted_consensus(breakdown),
                    "sources": {"mainstream": mainstream or ["US news"], "youth_social": youth or ["youth discourse"]},
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
    logger.info("[friction] Heuristic scoring done · pitches=%d", len(ordered[:5]))
    return ordered[:5]


def score_clusters(
    clusters: List[Dict[str, Any]],
    *,
    run_date: str,
    mode: str = "fresh",
    guidance: str = "",
    prior_pitch: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    from app.trends.cluster import embed_texts, cosine, jaccard
    from app.trends.store import find_similar_pitches, load_recent_pitches_for_dedup

    logger.info(
        "[friction] score_clusters · input_clusters=%d · run_date=%s · hitl=%s",
        len(clusters or []),
        run_date,
        mode,
    )
    candidates: List[Dict[str, Any]] = []
    try:
        candidates = score_clusters_with_llm(
            clusters,
            run_date=run_date,
            mode=mode,
            guidance=guidance,
            prior_pitch=prior_pitch,
        )
    except Exception as exc:
        logger.warning("[friction] LLM scoring raised — heuristic fallback: %s", exc)
        candidates = []
    if not candidates:
        logger.warning("[friction] LLM returned 0 pitches — using heuristic fallback")
        candidates = score_clusters_heuristic(clusters, run_date=run_date)
    if not candidates:
        raise RuntimeError(
            "Agent 0 scoring returned 0 candidate pitches (LLM + heuristic). "
            "Check selected topic data and retry."
        )
    logger.info("[friction] Candidate pitches before dedupe: %d", len(candidates))

    # Load 14-day history for multi-layered duplicate elimination
    recent_history = load_recent_pitches_for_dedup(days=14)

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
        p_text = pitch_texts[i]
        is_duplicate = False

        if emb and len(emb) == 1536:
            # 1. Intra-batch uniqueness check against already accepted pitches in this run
            for prev_emb in accepted_embeddings:
                sim = cosine(emb, prev_emb)
                if sim >= 0.75:
                    logger.info("Skipping candidate pitch '%s' - too similar to current batch (%.2f)", p.get("headline"), sim)
                    is_duplicate = True
                    break

            # 2. Historical database check via pgvector cosine similarity (14-day window, threshold=0.68)
            if not is_duplicate:
                similar_hist = find_similar_pitches(emb, threshold=0.68, limit=3, days=14)
                if similar_hist:
                    matched = similar_hist[0]
                    logger.info(
                        "Skipping candidate pitch '%s' - matches historical pitch from %s '%s' (similarity: %s)",
                        p.get("headline"),
                        matched.get("run_date"),
                        matched.get("headline"),
                        matched.get("similarity"),
                    )
                    is_duplicate = True
                elif recent_history:
                    # In-memory cosine check fallback when pgvector extension is unavailable
                    for hist in recent_history:
                        h_emb = hist.get("embedding")
                        if h_emb and len(h_emb) == 1536:
                            h_sim = cosine(emb, h_emb)
                            if h_sim >= 0.68:
                                logger.info(
                                    "Skipping candidate pitch '%s' - matches historical pitch '%s' via vector cosine (%.2f)",
                                    p.get("headline"),
                                    hist.get("headline"),
                                    h_sim,
                                )
                                is_duplicate = True
                                break

            # 3. Text lexical & keyword overlap check against recent history
            if not is_duplicate and recent_history:
                for hist in recent_history:
                    h_text = f"{hist.get('headline') or ''}. {hist.get('crash_out_angle') or ''}"
                    jc = jaccard(p_text, h_text)
                    if jc >= 0.35:
                        logger.info(
                            "Skipping candidate pitch '%s' - high lexical overlap (%.2f) with historical pitch '%s'",
                            p.get("headline"),
                            jc,
                            hist.get("headline"),
                        )
                        is_duplicate = True
                        break

            if not is_duplicate:
                p["embedding"] = emb
                accepted_embeddings.append(emb)
        else:
            # Fallback when embeddings are not available: Jaccard text comparison
            for prev_p in valid_pitches:
                prev_text = f"{prev_p.get('headline') or ''}. {prev_p.get('crash_out_angle') or ''}"
                if jaccard(p_text, prev_text) >= 0.50:
                    is_duplicate = True
                    break

            if not is_duplicate and recent_history:
                for hist in recent_history:
                    h_text = f"{hist.get('headline') or ''}. {hist.get('crash_out_angle') or ''}"
                    if jaccard(p_text, h_text) >= 0.45:
                        is_duplicate = True
                        break

        if not is_duplicate:
            valid_pitches.append(p)
            if len(valid_pitches) >= 5:
                break

    # If strict filtering left us with fewer than 5, backfill from remaining candidates
    # while ensuring they do NOT have high similarity (>= 0.78) to historical pitches
    if len(valid_pitches) < 5:
        existing_ids = {p.get("cluster_id") or p.get("headline") for p in valid_pitches}
        for idx, p in enumerate(candidates):
            ident = p.get("cluster_id") or p.get("headline")
            if ident in existing_ids:
                continue
            cand_emb = embeddings[idx] if (embeddings and idx < len(embeddings)) else None
            # Check if this fallback candidate is too close to historical pitches
            if cand_emb and len(cand_emb) == 1536:
                too_close = find_similar_pitches(cand_emb, threshold=0.78, limit=1, days=14)
                if too_close:
                    continue
                p["embedding"] = cand_emb
            valid_pitches.append(p)
            existing_ids.add(ident)
            if len(valid_pitches) >= 5:
                break

    for i, p in enumerate(valid_pitches[:5], 1):
        p["rank"] = i
    logger.info(
        "[friction] score_clusters done · final_pitches=%d · top=%s",
        len(valid_pitches[:5]),
        (valid_pitches[0].get("headline") if valid_pitches else "")[:80],
    )
    return valid_pitches[:5]
