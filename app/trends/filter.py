"""
Score raw trends against Crash Out Personas themes.
Drops hard-news / celebrity / non-suburban noise.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# Word-ish tokens; matched with word boundaries where short (avoid "tip" in random words).
FIT_KEYWORDS = [
    "hoa",
    "nextdoor",
    "suburb",
    "suburban",
    "pta",
    "parent",
    "parents",
    "parenting",
    "dad",
    "mom",
    "family",
    "grocery",
    "groceries",
    "inflation",
    "rent",
    "mortgage",
    "cost of living",
    "tipping",
    "no tip",
    "stanley",
    "tumbler",
    "wellness",
    "goop",
    "gentle parenting",
    "tiktok",
    "influencer",
    "brainrot",
    "gen z",
    "genz",
    "gen alpha",
    "aura",
    "rizz",
    "cooked",
    "capitalism",
    "antiwork",
    "wage",
    "debt",
    "crypto",
    "doomer",
    "neighbor",
    "neighbours",
    "lawn",
    "driveway",
    "school",
    "teacher",
    "teenager",
    "screen time",
    "iphone",
    "smart home",
    "thermostat",
    "hoa fine",
    "cul-de-sac",
]

REJECT_KEYWORDS = [
    "war in",
    "missile",
    "earthquake",
    "stock market close",
    "earnings report",
    "nba finals",
    "nfl ",
    "mlb ",
    "nascar",
    "oscar",
    "grammy",
    "box office",
    "celebrity divorce",
    "acceptable discourse",
    "purpose of this sub",
    "megathread",
    "daily discussion",
    "u.s. senate",
    "senate majority",
    "majority leader",
    "legislature",
    "finalizes divorce",
    "shot,",
    "shot ",
    "killed",
    "shooting",
    "murder",
    "homicide",
    "mass shooting",
]

# News wires need a stronger suburban/culture hit than a single weak token.
STRONG_KEYWORDS = [
    "hoa",
    "nextdoor",
    "suburb",
    "suburban",
    "tipping",
    "no tip",
    "stanley",
    "tumbler",
    "tiktok",
    "gen z",
    "genz",
    "parenting",
    "gentle parenting",
    "cost of living",
    "grocery",
    "groceries",
    "wellness",
    "brainrot",
    "antiwork",
    "influencer",
]


def _title_text(item: Dict[str, Any]) -> str:
    """Title-only — snippets/HTML often false-positive on short keywords."""
    return (item.get("title") or "").lower()


def _keyword_hits(text: str) -> int:
    hits = 0
    for kw in FIT_KEYWORDS:
        if " " in kw or len(kw) >= 5:
            if kw in text:
                hits += 1
        else:
            # Short tokens: word-boundary match (dad/mom/hoa/rent/wage…)
            if re.search(rf"(?<![a-z]){re.escape(kw)}(?![a-z])", text):
                hits += 1
    return hits


def score_fit(item: Dict[str, Any]) -> float:
    text = _title_text(item)
    if not text.strip():
        return 0.0
    for bad in REJECT_KEYWORDS:
        if bad in text:
            return 0.0
    hits = _keyword_hits(text)
    source = str(item.get("source") or "").lower()
    base = float(item.get("score") or 0)
    source_boost = 25.0 if source.startswith("reddit/") else (10.0 if source in {"gdelt", "newsapi"} else 0.0)
    # Normalize reddit scores a bit; boost keyword hits hard.
    return hits * 40.0 + min(base, 500.0) * 0.05 + source_boost + (5.0 if hits else 0.0)


def filter_trends(
    items: List[Dict[str, Any]],
    *,
    min_score: float = 40.0,
    limit: int = 24,
) -> List[Dict[str, Any]]:
    ranked: List[Tuple[float, Dict[str, Any]]] = []
    soft: List[Tuple[float, Dict[str, Any]]] = []
    for item in items:
        fit = score_fit(item)
        if fit <= 0:
            continue
        enriched = dict(item)
        enriched["fit_score"] = fit
        text = _title_text(item)
        hits = _keyword_hits(text)
        if hits < 1:
            continue
        source = str(item.get("source") or "").lower()
        strong = sum(1 for kw in STRONG_KEYWORDS if kw in text)
        # All sources need a strong cultural token in the title (Crash Out fit).
        if strong < 1:
            continue
        if fit >= min_score:
            ranked.append((fit, enriched))
        else:
            soft.append((fit, enriched))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    if ranked:
        return [item for _, item in ranked[:limit]]
    soft.sort(key=lambda pair: pair[0], reverse=True)
    if soft:
        return [item for _, item in soft[:limit]]
    return []


def summarize_for_prompt(items: List[Dict[str, Any]], max_items: int = 18) -> str:
    lines = []
    for i, item in enumerate(items[:max_items], 1):
        title = re.sub(r"\s+", " ", item.get("title") or "").strip()
        src = item.get("source") or "web"
        snip = re.sub(r"\s+", " ", item.get("snippet") or "").strip()[:160]
        lines.append(f"{i}. [{src}] {title}" + (f" — {snip}" if snip else ""))
    return "\n".join(lines)
