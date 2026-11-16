"""
Turn filtered trends into exactly 3 Gate 1 concept cards.
Uses OpenAI when OPENAI_API_KEY is set; otherwise heuristic templates.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

from app.config import config
from app.trends.filter import summarize_for_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You write episode concepts for CRASH OUT, an adult satirical 2D animated
web series (South Park meets Arrested Development in modern US suburbia).

Cast (always involve all four unless a beat truly needs fewer):
- GARY (44): MAGA gentle-parent dad; therapy jargon → Trump rally rant; stress watch.
- LINDA (42): Goop wellness / HOA optics hypocrite; Stanley tumbler; secret junk food.
- CHRIS (15): Techno-nihilist doomer; late-stage capitalism monologues.
- CHLOE (11): Pre-teen momager; livestreams / monetizes family meltdowns.

Rules:
- Concepts must be satirical suburban crash-out fuel — NOT generic hard news.
- Map real trends into Pearson kitchen / driveway / HOA conflict.
- No real healing; escalate from decorum to crash-out.
- suggested_merch: short punchy merch phrase (hoodie-ready).
- script_key: always "hoa_violation" for now.
- Return ONLY valid JSON: {"concepts": [ ... exactly 3 objects ... ]}
Each object keys:
id, title, cultural_hook, premise, synopsis, conflict, tone,
suggested_merch, source_trends (array of 2-4 strings), characters_involved,
script_key
"""


def write_concepts(trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not trends:
        return []
    llm_concepts = _write_with_openai(trends)
    if llm_concepts:
        return llm_concepts
    return _write_heuristic(trends)


def _write_with_openai(trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    api_key = (config.openai_api_key or "").strip()
    if not api_key:
        return []
    model = (config.openai_model or "gpt-4o-mini").strip()
    user = (
        "Using these latest US cultural signals (last ~24-48h), invent exactly 3 "
        "original CRASH OUT episode concepts. Cite 2-4 source_trends titles from "
        "the list in each card.\n\n"
        f"{summarize_for_prompt(trends)}\n"
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
                "temperature": 0.85,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
        if resp.status_code != 200:
            logger.warning("OpenAI concept writer status %s: %s", resp.status_code, resp.text[:200])
            return []
        content = (((resp.json() or {}).get("choices") or [{}])[0].get("message") or {}).get(
            "content"
        ) or ""
        return _parse_concepts_json(content)
    except Exception as exc:
        logger.warning("OpenAI concept writer failed: %s", exc)
        return []


def _parse_concepts_json(content: str) -> List[Dict[str, Any]]:
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
    raw = data.get("concepts") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(raw[:3], 1):
        if not isinstance(item, dict):
            continue
        out.append(_normalize_concept(item, index=i))
    return out if len(out) == 3 else []


def _write_heuristic(trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deterministic concept cards from top trends when no LLM key."""
    top = trends[:9]
    buckets = [top[i::3] for i in range(3)]
    templates = [
        {
            "lead": "Gary",
            "title_prefix": "Gary's",
            "conflict_frame": (
                "Gary's stress-watch spiral and tariff rhetoric collide with the kids' "
                "content machine while Linda protects neighborhood optics."
            ),
            "tone": "Aggrieved suburban dad crash-out with Gen Z commentary",
            "merch_fallback": "Capitalism broke my dad",
        },
        {
            "lead": "Linda",
            "title_prefix": "Linda's",
            "conflict_frame": (
                "Linda's wellness-optics panic and HOA reputation war meet Gary's refusal "
                "to fund another status purchase."
            ),
            "tone": "Passive-aggressive suburban melodrama with content-farm siblings",
            "merch_fallback": "Optics are catastrophic",
        },
        {
            "lead": "Chloe",
            "title_prefix": "Chloe Monetizes",
            "conflict_frame": (
                "Chloe packages the household meltdown for the algorithm while Chris rates "
                "the engagement as mid and Gary bans the livestream mid-sentence."
            ),
            "tone": "Brainrot satire — kids treating parents as inventory",
            "merch_fallback": "Dad is cooked on main",
        },
    ]
    concepts: List[Dict[str, Any]] = []
    stamp = int(time.time())
    for i, (bucket, tmpl) in enumerate(zip(buckets, templates), 1):
        if not bucket:
            bucket = top[:2] or [{"title": "Suburban cost-of-living meltdown", "source": "fallback"}]
        titles = [str(t.get("title") or "").strip() for t in bucket if t.get("title")]
        hook_trend = titles[0] if titles else "suburban status anxiety"
        theme = _theme_label(hook_trend)
        short = _short_title(theme, max_len=42)
        premise_bits = "; ".join(titles[:3])
        concepts.append(
            _normalize_concept(
                {
                    "id": f"concept_live_{stamp}_{i}",
                    "title": f"{tmpl['title_prefix']} {short}".strip(),
                    "cultural_hook": (
                        f"Live US trend fuel — '{hook_trend}' — remixed as Pearson-family "
                        f"suburban satire ({', '.join(t.get('source','web') for t in bucket[:2])})."
                    ),
                    "premise": (
                        f"In the Pearson kitchen, a fresh cultural flare-up around {theme} "
                        f"(sourced from: {premise_bits}) ignites a 55-second crash-out. "
                        f"{tmpl['conflict_frame']} "
                        f"Gary's watch flashes CRITICAL STRESS; Linda weaponizes vibrational "
                        f"jargon; Chloe starts a livestream; Chris open-sources the math proving "
                        f"the household is cooked."
                    ),
                    "synopsis": (
                        f"A vertical satirical beat where {theme} becomes the fuse for "
                        f"financial shame, performative wellness, and teenage content extraction."
                    ),
                    "conflict": tmpl["conflict_frame"],
                    "tone": tmpl["tone"],
                    "suggested_merch": _merch_from_trend(theme, tmpl["merch_fallback"]),
                    "source_trends": titles[:4] or [hook_trend],
                    "characters_involved": ["gary", "linda", "chris", "chloe"],
                    "script_key": "hoa_violation",
                },
                index=i,
            )
        )
    return concepts


def _theme_label(trend: str) -> str:
    """Map a raw headline into a safe satirical theme phrase for titles/merch."""
    low = (trend or "").lower()
    mapping = [
        (("hoa", "nextdoor", "cul-de-sac"), "HOA Optics Meltdown"),
        (("tip", "tipping"), "Tip-Fatigue Crash Out"),
        (("stanley", "tumbler", "hydration"), "Stanley Status Crisis"),
        (("grocery", "inflation", "cost of living", "rent"), "Cost-of-Living Spiral"),
        (("tiktok", "influencer", "livestream"), "Parent-Shaming Livestream"),
        (("gen z", "genz", "brainrot", "aura", "rizz"), "Brainrot Generational War"),
        (("wellness", "goop", "gentle parenting"), "Wellness Hypocrisy Spiral"),
        (("antiwork", "wage", "capitalism"), "Late-Stage Chore Negotiations"),
    ]
    for keys, label in mapping:
        if any(k in low for k in keys):
            return label
    return "Suburban Status Anxiety"


def _short_title(text: str, max_len: int = 42) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = re.sub(r"[\"']", "", cleaned)
    if len(cleaned) <= max_len:
        return cleaned or "Suburban Meltdown"
    return cleaned[: max_len - 1].rstrip() + "…"


def _merch_from_trend(trend: str, fallback: str) -> str:
    theme = _theme_label(trend)
    if theme != "Suburban Status Anxiety":
        return theme
    words = re.findall(r"[A-Za-z0-9']+", trend or "")
    if len(words) >= 3:
        phrase = " ".join(words[:5])
        if len(phrase) <= 40:
            return phrase[0].upper() + phrase[1:]
    return fallback


def _normalize_concept(raw: Dict[str, Any], *, index: int) -> Dict[str, Any]:
    stamp = int(time.time())
    source_trends = raw.get("source_trends") or []
    if isinstance(source_trends, str):
        source_trends = [source_trends]
    source_trends = [str(s).strip() for s in source_trends if str(s).strip()][:4]
    chars = raw.get("characters_involved") or ["gary", "linda", "chris", "chloe"]
    if not isinstance(chars, list):
        chars = ["gary", "linda", "chris", "chloe"]
    return {
        "id": str(raw.get("id") or f"concept_live_{stamp}_{index}"),
        "title": str(raw.get("title") or f"Live Pitch {index}").strip(),
        "cultural_hook": str(raw.get("cultural_hook") or "").strip(),
        "premise": str(raw.get("premise") or "").strip(),
        "synopsis": str(raw.get("synopsis") or "").strip(),
        "conflict": str(raw.get("conflict") or "").strip(),
        "tone": str(
            raw.get("tone")
            or "Fast-paced satirical suburban escalation — South Park bite, Arrested Development irony"
        ).strip(),
        "suggested_merch": str(raw.get("suggested_merch") or "Capitalism broke my dad").strip(),
        "source_trends": source_trends or ["US suburban culture"],
        "characters_involved": [str(c).lower() for c in chars],
        "script_key": str(raw.get("script_key") or "hoa_violation"),
    }
