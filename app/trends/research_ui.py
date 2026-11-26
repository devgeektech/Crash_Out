"""
Agent 0 Trend Research UI helpers:
- Map raw Layer A/B items → signal cards + detail panels
- Single-select a topic from All signals → Create Pitch / View Pitch
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.trends.cluster import jaccard
from app.trends.schema import normalize_pitch_run, pitches_to_concepts, today_run_date
from app.trends.store import load_latest_pitch_run, load_raw_items, save_pitch_run

logger = logging.getLogger(__name__)

MAX_SELECTED_SIGNALS = 1
MAX_VIRAL_LIST = 10  # Trend Research list: top viral across media + youth social
PRESENCE_JACCARD = 0.28  # post-scrape topic merge threshold
SESSION_SELECTED_KEY = "agent0_selected_signal_ids"
SESSION_ACTIVE_KEY = "agent0_active_signal_id"
SESSION_VIEW_KEY = "agent0_research_view"
SESSION_FILTER_KEY = "agent0_research_filter"
SESSION_QUERY_KEY = "agent0_research_query"

# Per-user selection store so selection survives flaky cookie sessions (JWT auth).
_SELECTED_BY_USER: Dict[str, List[str]] = {}
# Created pitch cards keyed by "user|signal_id" so View Pitch follows the selection.
_PITCH_BY_SIGNAL: Dict[str, Dict[str, Any]] = {}

FILTER_LABELS = {
    "all": "All signals",
    "mainstream": "Mainstream (A)",
    "social": "Social Proof (B)",
}

# Trend Research presence / confidence uses Mainstream + Social only (no Layer C).
RESEARCH_LAYERS = frozenset({"A", "B"})


def _research_feed_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop Layer C (Character Niche) from Trend Research scoring UI."""
    out: List[Dict[str, Any]] = []
    for it in items or []:
        layer = str(it.get("layer") or "").upper()
        if layer in RESEARCH_LAYERS:
            out.append(it)
    return out


def signal_id_for(item: Dict[str, Any], *, index: int = 0) -> str:
    """Stable id for a raw item. `index` is ignored (kept for call-site compat)."""
    del index
    seed = "|".join(
        [
            str(item.get("url") or ""),
            str(item.get("title") or ""),
            str(item.get("outlet") or item.get("source") or ""),
            str(item.get("layer") or ""),
        ]
    )
    return "sig_" + hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _relative_time(ts: Any) -> str:
    try:
        age = max(0, int(time.time() - float(ts)))
    except (TypeError, ValueError):
        return "—"
    if age < 60:
        return "just now"
    if age < 3600:
        return f"{age // 60} min ago"
    if age < 86400:
        hours = age // 3600
        return f"{hours} hr ago" if hours == 1 else f"{hours} hrs ago"
    days = age // 86400
    return f"{days} day ago" if days == 1 else f"{days} days ago"


def _score_100(raw_score: float, ceiling: float) -> int:
    if ceiling <= 0:
        return 50
    # Soft-log scale so Reddit/YouTube outliers don't flatten the rest.
    norm = math.log1p(max(0.0, raw_score)) / math.log1p(ceiling)
    return max(1, min(99, int(round(norm * 100))))


def _layer_bucket(layer: str) -> str:
    """UI filter buckets: A=mainstream, B=social."""
    layer = (layer or "").upper()
    if layer == "A":
        return "mainstream"
    if layer == "B":
        return "social"
    return "other"


def _layer_label(layer: str) -> str:
    layer = (layer or "").upper()
    if layer == "A":
        return "Mainstream (A)"
    if layer == "B":
        return "Social Proof (B)"
    return "Layer ?"


def _topic_id_for(members: Sequence[Dict[str, Any]]) -> str:
    seeds = sorted(signal_id_for(it) for it in members)
    return "topic_" + hashlib.sha1("|".join(seeds).encode("utf-8")).hexdigest()[:14]


def _finalize_presence_topic(members: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Build one presence topic dict from grouped members."""
    outlets: List[str] = []
    platforms: List[str] = []
    layers: List[str] = []
    seen_out, seen_plat, seen_layer = set(), set(), set()
    for it in sorted(members, key=lambda x: _as_float(x.get("score")), reverse=True):
        out = str(it.get("outlet") or it.get("source") or "").strip()
        plat = str(it.get("source") or it.get("outlet") or "").strip()
        layer = str(it.get("layer") or "").upper()
        if out and out.lower() not in seen_out:
            seen_out.add(out.lower())
            outlets.append(out)
        if plat and plat.lower() not in seen_plat:
            seen_plat.add(plat.lower())
            platforms.append(plat)
        if layer and layer not in seen_layer and layer != "?":
            seen_layer.add(layer)
            layers.append(layer)

    rep = max(members, key=lambda x: _as_float(x.get("score")))
    presence_count = len(outlets)
    layer_count = len(layers)
    platform_count = len(platforms)
    layer_set = {str(x).upper() for x in layers}
    has_cross = "A" in layer_set and "B" in layer_set
    title = str(rep.get("title") or "")
    theme = _theme_key(title)
    # Soft boost Crash Out lanes (suburban / youth / lifestyle) when overlap is decent.
    lifestyle_boost = 0.0
    if presence_count >= 2 and theme in {"suburban", "youth", "lifestyle", "work"}:
        lifestyle_boost = 10.0
    elif presence_count >= 2 and theme == "politics":
        lifestyle_boost = -2.0  # tiny nudge only — overlap still wins
    presence_rank = (
        presence_count * 18.0
        + platform_count * 8.0
        + layer_count * 14.0
        + (32.0 if has_cross else 0.0)  # Mainstream × Social cross-check
        + lifestyle_boost
        + math.log1p(sum(_as_float(m.get("score")) for m in members))
    )
    unanimous = presence_count >= 4 or layer_count >= 2
    return {
        "id": _topic_id_for(members),
        "members": list(members),
        "representative": rep,
        "outlets": outlets,
        "platforms": platforms,
        "layers": layers,
        "presence_count": presence_count,
        "platform_count": platform_count,
        "layer_count": layer_count,
        "presence_rank": presence_rank,
        "has_cross_layer": has_cross,
        "theme_key": theme,
        "unanimous": unanimous,
        "member_count": len(members),
    }


def _cross_attach_social_to_mainstream(topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Soft Mainstream↔Social attach: fold B-only topics into matching A topics
    when story/entity match is strong enough (same story, different wording).
    """
    if not topics:
        return topics

    a_topics: List[Dict[str, Any]] = []
    b_only: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []
    for topic in topics:
        layers = {str(x).upper() for x in (topic.get("layers") or [])}
        if "A" in layers:
            a_topics.append(topic)
        elif "B" in layers:
            b_only.append(topic)
        else:
            other.append(topic)
    if not a_topics or not b_only:
        return topics

    # Mutate member lists on A topics in place via id map.
    a_by_id = {str(t.get("id")): dict(t) for t in a_topics}
    attached_b_ids: set[str] = set()

    for b_topic in b_only:
        b_rep = b_topic.get("representative") or {}
        best_id = None
        best_score = 0.0
        for a_topic in a_by_id.values():
            a_rep = a_topic.get("representative") or {}
            match = story_match_confidence(a_rep, b_rep)
            total = float(match.get("score") or 0)
            ent = float((match.get("factors") or {}).get("entity") or 0)
            if total >= 42 or (ent >= 35 and total >= 34):
                if total > best_score:
                    best_score = total
                    best_id = str(a_topic.get("id"))
        if not best_id:
            continue
        host = a_by_id[best_id]
        merged = list(host.get("members") or []) + list(b_topic.get("members") or [])
        updated = _finalize_presence_topic(merged)
        updated["id"] = host.get("id") or updated["id"]
        a_by_id[best_id] = updated
        attached_b_ids.add(str(b_topic.get("id")))

    out = list(a_by_id.values())
    out.extend(t for t in b_only if str(t.get("id")) not in attached_b_ids)
    out.extend(other)
    out.sort(
        key=lambda t: (
            1 if t.get("has_cross_layer") else 0,
            float(t.get("presence_rank") or 0),
            int(t.get("presence_count") or 0),
            int(t.get("layer_count") or 0),
        ),
        reverse=True,
    )
    return out


def group_items_by_presence(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    After scrape (no dedupe): merge stories that appear across platforms/outlets.
    Ranking is driven by how widely a topic is present, with soft A×B attach.
    """
    rows = [it for it in items if str(it.get("title") or "").strip()]
    if not rows:
        return []

    parents = list(range(len(rows)))

    def find(i: int) -> int:
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parents[rj] = ri

    titles = [str(it.get("title") or "") for it in rows]
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if jaccard(titles[i], titles[j]) >= PRESENCE_JACCARD:
                union(i, j)

    groups: Dict[int, List[Dict[str, Any]]] = {}
    for i, it in enumerate(rows):
        groups.setdefault(find(i), []).append(it)

    topics = [_finalize_presence_topic(members) for members in groups.values()]
    topics = _cross_attach_social_to_mainstream(topics)
    topics.sort(
        key=lambda t: (
            1 if t.get("has_cross_layer") else 0,
            float(t.get("presence_rank") or 0),
            int(t.get("presence_count") or 0),
            int(t.get("layer_count") or 0),
        ),
        reverse=True,
    )
    return topics


# Theme buckets for anti-clone diversity (Top list + pitch mix).
_THEME_RULES: List[tuple[str, tuple[str, ...]]] = [
    ("politics", ("trump", "biden", "congress", "senate", "white house", "gop", "democrat", "election", "maga", "president")),
    ("suburban", ("hoa", "neighbor", "suburb", "lawn", "homeowner", "zoning", "school board", "pta")),
    ("youth", ("tiktok", "gen z", "gen-z", "influencer", "viral", "meme", "discord", "reddit")),
    ("lifestyle", ("dating", "wedding", "parent", "mom", "dad", "family", "grocery", "costco", "target")),
    ("work", ("layoff", "boss", "office", "remote work", "salary", "hr ", "coworker")),
    ("tech", ("openai", "chatgpt", "ai ", "apple", "google", "meta", "nvidia", "iphone")),
    ("celebrity", ("kardashian", "swift", "beyonce", "celebrity", "oscar")),
]


def _theme_key(title: str) -> str:
    blob = f" {(title or '').lower()} "
    for key, needles in _THEME_RULES:
        if any(n in blob for n in needles):
            return key
    return "general"


def _apply_theme_diversity(cards: Sequence[Dict[str, Any]], *, max_per_theme: int = 2) -> List[Dict[str, Any]]:
    """
    Soft anti-clone: keep overlap order, but after max_per_theme hits for a theme,
    park further clones after the diverse head so Top isn't 5 Trump variants.
    Does not delete cards — only reorders.
    """
    head: List[Dict[str, Any]] = []
    deferred: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    for card in cards:
        theme = str(card.get("theme_key") or _theme_key(str(card.get("title") or "")))
        n = counts.get(theme, 0)
        if n < max_per_theme:
            head.append(card)
            counts[theme] = n + 1
        else:
            deferred.append(card)
    return head + deferred


# Story Match Confidence weights (publisher % vs selected trend).
_MATCH_W_SEMANTIC = 0.40
_MATCH_W_ENTITY = 0.25
_MATCH_W_CONTEXT = 0.20
_MATCH_W_TIME = 0.15

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "from",
    "by", "with", "as", "is", "are", "was", "were", "be", "been", "being", "it", "its",
    "this", "that", "these", "those", "into", "over", "after", "before", "about", "says",
    "said", "new", "just", "how", "why", "what", "when", "who", "will", "can", "has",
    "have", "had", "not", "no", "yes", "via", "amp",
}


def _item_text(item: Dict[str, Any]) -> str:
    title = str(item.get("title") or "").strip()
    snip = str(item.get("snippet") or "").strip()
    return f"{title}. {snip}".strip()


def _content_tokens(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(t) > 2 and t not in _STOPWORDS
    }


def _entity_tokens(text: str) -> set[str]:
    """Rough entities: Proper Case words, ALLCAPS, numbers, $amounts."""
    entities: set[str] = set()
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text or ""):
        entities.add(m.group(1).lower())
    for m in re.finditer(r"\b([A-Z]{2,})\b", text or ""):
        entities.add(m.group(1).lower())
    for m in re.finditer(r"\$?\b\d+(?:\.\d+)?(?:k|m|b|%)?\b", (text or "").lower()):
        entities.add(m.group(0))
    return entities


def _overlap_score(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union <= 0:
        return 0.0
    # Blend Jaccard with coverage of the smaller set so partial entity hits score higher.
    j = inter / union
    cover = inter / max(1, min(len(a), len(b)))
    return max(0.0, min(100.0, (0.55 * j + 0.45 * cover) * 100.0))


def _semantic_score(anchor: Dict[str, Any], other: Dict[str, Any]) -> float:
    """Factor S (40%): title+snippet token similarity."""
    a_title = str(anchor.get("title") or "")
    b_title = str(other.get("title") or "")
    if a_title.strip().lower() == b_title.strip().lower() and a_title.strip():
        return 100.0
    title_j = jaccard(a_title, b_title) * 100.0
    body_j = jaccard(_item_text(anchor), _item_text(other)) * 100.0
    token_overlap = _overlap_score(_content_tokens(_item_text(anchor)), _content_tokens(_item_text(other)))
    return max(0.0, min(100.0, 0.45 * title_j + 0.25 * body_j + 0.30 * token_overlap))


def _entity_score(anchor: Dict[str, Any], other: Dict[str, Any]) -> float:
    """Factor E (25%): shared people / orgs / numbers."""
    a_ents = _entity_tokens(_item_text(anchor))
    b_ents = _entity_tokens(_item_text(other))
    if not a_ents and not b_ents:
        # Fall back to significant content tokens when casing is missing (social titles).
        return _overlap_score(_content_tokens(_item_text(anchor)), _content_tokens(_item_text(other)))
    return _overlap_score(a_ents, b_ents)


def _context_score(anchor: Dict[str, Any], other: Dict[str, Any]) -> float:
    """Factor C (20%): shared event/context words beyond pure entities."""
    a_tok = _content_tokens(_item_text(anchor))
    b_tok = _content_tokens(_item_text(other))
    a_ent = _entity_tokens(_item_text(anchor))
    b_ent = _entity_tokens(_item_text(other))
    # Context = non-entity topical overlap (verbs / theme words).
    a_ctx = {t for t in a_tok if t not in a_ent}
    b_ctx = {t for t in b_tok if t not in b_ent}
    if len(a_ctx) < 2 and len(b_ctx) < 2:
        return _overlap_score(a_tok, b_tok)
    return _overlap_score(a_ctx, b_ctx)


def _time_score(anchor: Dict[str, Any], other: Dict[str, Any]) -> float:
    """Factor T (15%): publication/fetch time proximity (hours)."""
    ta = _as_float(anchor.get("fetched_at") or anchor.get("published_at"))
    tb = _as_float(other.get("fetched_at") or other.get("published_at"))
    if ta <= 0 or tb <= 0:
        return 70.0  # neutral when timestamps missing
    hours = abs(ta - tb) / 3600.0
    if hours <= 1:
        return 100.0
    if hours <= 6:
        return 92.0
    if hours <= 24:
        return 80.0
    if hours <= 72:
        return 65.0
    if hours <= 168:
        return 45.0
    return 25.0


def story_match_confidence(anchor: Dict[str, Any], other: Dict[str, Any]) -> Dict[str, Any]:
    """
    Story Match Confidence for one publisher article vs the selected trend.

    Score = (S×0.40) + (E×0.25) + (C×0.20) + (T×0.15)
    """
    a_title = str(anchor.get("title") or "").strip()
    b_title = str(other.get("title") or "").strip()
    if other is anchor or (a_title and b_title and a_title.lower() == b_title.lower()):
        factors = {"semantic": 100.0, "entity": 100.0, "context": 100.0, "time": 100.0}
        return {"score": 100, "factors": factors}

    s = _semantic_score(anchor, other)
    e = _entity_score(anchor, other)
    c = _context_score(anchor, other)
    t = _time_score(anchor, other)
    raw = (s * _MATCH_W_SEMANTIC) + (e * _MATCH_W_ENTITY) + (c * _MATCH_W_CONTEXT) + (t * _MATCH_W_TIME)
    score = int(round(max(0.0, min(100.0, raw))))
    return {
        "score": score,
        "factors": {
            "semantic": round(s, 1),
            "entity": round(e, 1),
            "context": round(c, 1),
            "time": round(t, 1),
        },
    }


def _accumulate_platform_matches(
    members: Sequence[Dict[str, Any]],
    rep: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Per-publisher Story Match Confidence bars.

    1) Anchor topic is fetched first (representative).
    2) Each other platform hit is scored with S/E/C/T vs the anchor.
    3) Repeat hits on the same outlet keep the stronger match (not brand bias).
    """
    by_platform: Dict[str, Dict[str, Any]] = {}
    for it in members:
        name = str(it.get("outlet") or it.get("source") or "").strip()
        if not name:
            continue
        key = name.lower()
        match = story_match_confidence(rep, it)
        match_pct = float(match["score"])
        factors = match.get("factors") or {}
        url = str(it.get("url") or "").strip()

        prev = by_platform.get(key)
        if not prev or match_pct > float(prev.get("strength") or 0):
            by_platform[key] = {
                "name": name,
                "strength": match_pct,
                "layer": str(it.get("layer") or "").upper() or "A",
                "hits": int(prev.get("hits") or 0) + 1 if prev else 1,
                "factors": factors,
                "url": url,
            }
        elif prev:
            prev["hits"] = int(prev.get("hits") or 1) + 1
            # Keep a working link if the stronger match row had none.
            if not prev.get("url") and url:
                prev["url"] = url

    return sorted(
        (
            {
                "name": row["name"],
                "strength": int(round(min(100.0, float(row["strength"])))),
                "layer": row.get("layer") or "A",
                "hits": int(row.get("hits") or 1),
                "factors": row.get("factors") or {},
                "url": str(row.get("url") or "").strip(),
            }
            for row in by_platform.values()
        ),
        key=lambda r: int(r["strength"]),
        reverse=True,
    )


def _platform_overlap_and_confidence(topic: Dict[str, Any]) -> Dict[str, Any]:
    """
    Per-outlet Story Match bars + ring / list confidence.

    Client rule: more overlapping platforms/outlets → higher score.
    - Each bar = that outlet's S/E/C/T match vs the anchor story.
    - Ring score = mostly presence (how many outlets), blended with match quality
      so a 4-outlet story outranks a 1–2 outlet story even if avg match is lower.
    """
    members = list(topic.get("members") or [])
    rep = topic.get("representative") or (members[0] if members else {})
    all_rows = _accumulate_platform_matches(members, rep)[:8]
    mainstream_rows = [r for r in all_rows if str(r.get("layer") or "").upper() == "A"]
    layers_hit = {str(r.get("layer") or "").upper() for r in all_rows if r.get("layer")}

    if not all_rows:
        return {
            "bars": [],
            "outlet_names": [],
            "outlet_count": 0,
            "confidence": 0,
            "confidence_bar": 0,
            "avg_match_confidence": 0,
            "match_breakdown": "",
        }

    strengths = [int(r["strength"]) for r in all_rows]
    n = len(all_rows)
    avg_match = max(1, min(100, int(round(sum(strengths) / max(1, n)))))

    if n == 1:
        # One outlet only — no cross-platform confirmation yet.
        confidence = max(
            28,
            min(55, int(round(28 + math.log1p(_as_float(rep.get("score"))) * 4))),
        )
    else:
        # Presence-first base: 2→64, 3→76, 4→88, 5+→95
        presence_base = min(95, 40 + n * 12)
        # Cross-layer (Mainstream + Social) bonus — client critical cross-check.
        layer_bonus = 14 if ("A" in layers_hit and "B" in layers_hit) else 0
        # 75% how widely covered, 25% how tightly titles match.
        confidence = int(
            round(max(1.0, min(100.0, 0.75 * presence_base + 0.25 * avg_match + layer_bonus)))
        )

    parts = [f"{r['name']} {int(r['strength'])}%" for r in all_rows]
    if n == 1:
        breakdown = f"{parts[0]} (single outlet — early signal {confidence}/100)"
    else:
        breakdown = (
            f"{n} outlets · presence-first score {confidence}/100 "
            f"(avg match {avg_match}%)"
        )

    return {
        # Show every outlet that feeds the ring (not Layer A only).
        "bars": all_rows,
        "outlet_names": [b["name"] for b in all_rows],
        "outlet_count": n,
        "mainstream_count": len(mainstream_rows),
        "confidence": confidence,
        "confidence_bar": confidence,
        "platform_count": n,
        "avg_match_confidence": avg_match,
        "unique_outlets": n,
        "match_breakdown": breakdown,
    }


def _mainstream_overlap(topic: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Back-compat wrapper → platform bars only."""
    return list(_platform_overlap_and_confidence(topic).get("bars") or [])


def _format_signal_count(n: float) -> str:
    """Compact count for social chips: 2400 → 2.4k."""
    n = float(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m".rstrip("0").rstrip(".")
    if n >= 1000:
        return f"{n / 1000:.1f}k".rstrip("0").rstrip(".")
    return str(int(round(n)))


def _social_platform_family(item: Dict[str, Any]) -> str:
    """Map a Layer B hit to a display family: Reddit / X / YouTube / TikTok / Other."""
    blob = " ".join(
        [
            str(item.get("source") or ""),
            str(item.get("outlet") or ""),
            str(item.get("platform") or ""),
            str(item.get("url") or ""),
        ]
    ).lower()
    if "reddit" in blob or blob.startswith("r/"):
        return "Reddit"
    if "youtube" in blob or "youtu.be" in blob:
        return "YouTube"
    if "tiktok" in blob:
        return "TikTok"
    if (
        "twitter" in blob
        or "x.com" in blob
        or blob.startswith("x/")
        or " / x" in blob
        or blob == "x"
    ):
        return "X"
    return ""


def _social_proof_from_topic(topic: Dict[str, Any]) -> Dict[str, Any]:
    """Dynamic Social proof chips from Layer B members in this presence group."""
    members = [
        m
        for m in (topic.get("members") or [])
        if str(m.get("layer") or "").upper() == "B"
    ]
    buckets: Dict[str, Dict[str, Any]] = {}
    for it in members:
        family = _social_platform_family(it) or "Social"
        row = buckets.setdefault(
            family,
            {"name": family, "hits": 0, "volume": 0.0, "url": ""},
        )
        row["hits"] += 1
        row["volume"] += max(_as_float(it.get("score")), 1.0)
        url = str(it.get("url") or "").strip()
        if url and not row.get("url"):
            row["url"] = url

    # Prefer the known families in a stable order for the UI.
    order = ["Reddit", "X", "YouTube", "TikTok", "Social"]
    chips: List[Dict[str, Any]] = []
    for name in order:
        row = buckets.get(name)
        if not row:
            continue
        volume = float(row["volume"])
        chips.append(
            {
                "name": name,
                "hits": int(row["hits"]),
                "volume": volume,
                "label": _format_signal_count(volume),
                "tone": name.lower().replace(" ", "-"),
                "url": str(row.get("url") or ""),
            }
        )
    total_volume = sum(float(c["volume"]) for c in chips)
    return {
        "chips": chips,
        "signal_count": len(members),
        "signal_volume": total_volume,
        "signal_label": _format_signal_count(total_volume) if chips else "0",
        "has_social": bool(chips),
    }


def _component_score_for_layer(topic: Dict[str, Any], layer: str) -> int:
    """
    0–100 score for one stream alone:
    - Layer A → cross-media (mainstream outlet presence + feed volume + story match)
    - Layer B → social-proof (youth platforms + volume + story match)
    """
    layer = str(layer or "").upper()
    members = [
        m
        for m in (topic.get("members") or [])
        if str(m.get("layer") or "").upper() == layer
    ]
    if not members:
        return 0

    rep = max(members, key=lambda x: _as_float(x.get("score")))
    outlets: set[str] = set()
    for m in members:
        name = str(m.get("outlet") or m.get("source") or "").strip().lower()
        if name:
            outlets.add(name)
    # Social: also count distinct platform families so Reddit+X beats two Reddit hits.
    if layer == "B":
        families = {
            _social_platform_family(m) or "Social"
            for m in members
        }
        n = max(len(outlets), len(families), 1)
    else:
        n = max(len(outlets), 1)

    rows = _accumulate_platform_matches(members, rep)
    strengths = [int(r.get("strength") or 0) for r in rows] or [48]
    avg_match = max(1.0, min(100.0, sum(strengths) / max(1, len(strengths))))
    feed_vol = sum(max(_as_float(m.get("score")), 0.0) for m in members)
    volume_part = min(40.0, math.log1p(feed_vol) * 6.0)

    if n == 1:
        # Single-outlet / single-platform: early signal only.
        base = 26.0 + volume_part * 0.55 + avg_match * 0.18
        return max(1, min(88, int(round(base))))

    # Presence-first within the layer: more outlets/platforms → stronger alone score.
    presence_base = min(94.0, 34.0 + n * 12.0)
    score = (
        0.62 * presence_base
        + 0.26 * avg_match
        + 0.12 * min(100.0, volume_part * 2.2)
    )
    return max(1, min(99, int(round(score))))


def joint_viral_scores(topic: Dict[str, Any]) -> Dict[str, int]:
    """
    Cross-media (A) alone, social-proof (B) alone, and combined joint score.

    Joint favors topics that clear both streams: balanced mean + cross-check
    bonus when both > 0; single-stream topics are scaled down so they rank below
    comparable Media × Social hits.
    """
    media = _component_score_for_layer(topic, "A")
    social = _component_score_for_layer(topic, "B")

    if media > 0 and social > 0:
        # Combined = mean of alone scores + small cross-check bonus.
        joint = min(100, int(round(0.5 * media + 0.5 * social + 8)))
    elif media > 0:
        joint = max(1, int(round(media * 0.58)))
    elif social > 0:
        joint = max(1, int(round(social * 0.58)))
    else:
        joint = 0

    return {
        "cross_media_score": int(media),
        "social_proof_score": int(social),
        "joint_score": int(joint),
    }


def _unanimous_copy(topic: Dict[str, Any], score: int) -> Dict[str, str]:
    """Dynamic status copy for the ring — plain language, no math formula."""
    presence = int(topic.get("presence_count") or 0)
    has_ab = bool(topic.get("has_cross_layer")) or (
        "A" in {str(x).upper() for x in (topic.get("layers") or [])}
        and "B" in {str(x).upper() for x in (topic.get("layers") or [])}
    )
    if has_ab and (score >= 70 or presence >= 2):
        headline = "Cross-checked signal"
        detail = "Mainstream coverage plus social proof from the target audience"
        badge = "Media × Social"
    elif score >= 85 or (topic.get("unanimous") and presence >= 3):
        headline = "Unanimous signal"
        detail = "High confidence across media outlets"
        badge = "High debate"
    elif presence >= 2 or score >= 60:
        headline = "Emerging consensus"
        detail = "Building across monitored outlets — social resonance still thin"
        badge = "Watch list" if score < 75 else "Rising debate"
    else:
        headline = "Single-source signal"
        detail = "Needs broader platform presence to climb the rank"
        badge = "Early signal"
    return {"headline": headline, "detail": detail, "badge": badge}


def _quality_bonus(item: Dict[str, Any]) -> float:
    """Down-rank empty meme titles / boost items with usable editorial text."""
    title = str(item.get("title") or "").strip()
    snippet = str(item.get("snippet") or "").strip()
    bonus = 0.0
    if len(title) >= 28:
        bonus += 6.0
    elif len(title) < 12:
        bonus -= 12.0
    if len(snippet) >= 80:
        bonus += 8.0
    elif len(snippet) < 20:
        bonus -= 6.0
    # Mainstream gets a slight editorial boost so social raw-score spikes
    # don't monopolize "strongest" ranking.
    layer = str(item.get("layer") or "").upper()
    if layer == "A":
        bonus += 4.0
    return bonus


def _rank_score(item: Dict[str, Any], layer_ceiling: float) -> float:
    """0-100 rank using per-layer normalization + quality bonus."""
    base = float(_score_100(_as_float(item.get("score")), layer_ceiling))
    return max(1.0, min(99.0, base + _quality_bonus(item)))


def _interleave_by_layer(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Keep strong A/B/C signals visible near the top by round-robin merge
    of each layer's ranked list (instead of pure global raw-score sort).
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {"A": [], "B": [], "?": []}
    for card in cards:
        layer = str(card.get("layer") or "?").upper()
        buckets.setdefault(layer if layer in buckets else "?", []).append(card)
    for layer_cards in buckets.values():
        layer_cards.sort(key=lambda c: float(c.get("rank_score") or c.get("score") or 0), reverse=True)

    order = ["A", "B", "?"]
    merged: List[Dict[str, Any]] = []
    indexes = {k: 0 for k in order}
    while True:
        progressed = False
        for key in order:
            idx = indexes[key]
            pile = buckets.get(key) or []
            if idx < len(pile):
                merged.append(pile[idx])
                indexes[key] = idx + 1
                progressed = True
        if not progressed:
            break
    return merged


# In-memory raw feed cache so checkbox toggles don't re-parse JSON every click.
_RAW_CACHE: Dict[str, Any] = {"key": "", "bundle": None, "built_at": 0.0}
_RAW_CACHE_TTL_SEC = 45.0


def clear_raw_feed_cache() -> None:
    """Drop the in-memory raw feed cache (call after a fresh Agent 0 ingest)."""
    _RAW_CACHE["key"] = ""
    _RAW_CACHE["bundle"] = None
    _RAW_CACHE["built_at"] = 0.0


def _cached_raw_bundle(run_date: Optional[str] = None) -> Dict[str, Any]:
    day = (run_date or today_run_date()).strip()
    now = time.time()
    key = day
    if (
        _RAW_CACHE.get("key") == key
        and _RAW_CACHE.get("bundle") is not None
        and (now - float(_RAW_CACHE.get("built_at") or 0)) < _RAW_CACHE_TTL_SEC
    ):
        return dict(_RAW_CACHE["bundle"])
    bundle = load_raw_items(day)
    _RAW_CACHE["key"] = key
    _RAW_CACHE["bundle"] = bundle
    _RAW_CACHE["built_at"] = now
    return dict(bundle)


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def _real_feed_facts(item: Dict[str, Any]) -> List[Dict[str, str]]:
    """Only surface metrics that exist on the raw feed item."""
    facts: List[Dict[str, str]] = []
    outlet = str(item.get("outlet") or item.get("source") or "").strip()
    layer = str(item.get("layer") or "").upper()
    if outlet:
        facts.append({"label": "Source", "value": outlet})
    if layer:
        facts.append({"label": "Layer", "value": _layer_label(layer)})
    character = str(item.get("character") or "").strip()
    if character:
        facts.append({"label": "Character", "value": character.title()})
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    views = _as_float(raw.get("views"))
    if views > 0:
        if views >= 1_000_000:
            views_label = f"{views / 1_000_000:.1f}M"
        elif views >= 1_000:
            views_label = f"{views / 1_000:.1f}k"
        else:
            views_label = str(int(views))
        facts.append({"label": "Views", "value": views_label})
    score = _as_float(item.get("score"))
    if score > 0:
        facts.append({"label": "Feed score", "value": f"{score:g}"})
    return facts


def _related_sources(item: Dict[str, Any], pool: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Other real outlets covering a similar title — names only, no invented strength %."""
    title = str(item.get("title") or "")
    own_tokens = _tokens(title)
    scored: List[tuple[float, Dict[str, Any]]] = []
    for other in pool:
        if signal_id_for(other) == signal_id_for(item):
            continue
        other_title = str(other.get("title") or "")
        sim = jaccard(title, other_title)
        if own_tokens:
            overlap = len(own_tokens & _tokens(other_title)) / max(1, len(own_tokens))
            sim = max(sim, overlap)
        if sim < 0.22:
            continue
        scored.append((sim, other))
    scored.sort(key=lambda pair: (pair[0], _as_float(pair[1].get("score"))), reverse=True)

    out: List[Dict[str, str]] = []
    seen = set()
    lead = str(item.get("outlet") or item.get("source") or "").strip()
    if lead:
        out.append(
            {
                "name": lead,
                "layer": str(item.get("layer") or "").upper(),
                "title": str(item.get("title") or ""),
            }
        )
        seen.add(lead.lower())
    for _sim, other in scored:
        name = str(other.get("outlet") or other.get("source") or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "name": name,
                "layer": str(other.get("layer") or "").upper(),
                "title": str(other.get("title") or ""),
            }
        )
        if len(out) >= 5:
            break
    return out


def _pitch_run_take_for_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Reuse a pitch-run take only when it clearly matches THIS signal title."""
    run = load_latest_pitch_run() or {}
    pitches = list(run.get("pitches") or [])
    title = str(item.get("title") or "").strip()
    if not pitches or not title:
        return None

    best = None
    best_sim = 0.0
    for pitch in pitches:
        headline = str(pitch.get("headline") or "").strip()
        angle = str(pitch.get("crash_out_angle") or "")
        youth = str(pitch.get("youth_sentiment_summary") or "")
        sim = max(
            jaccard(title, headline),
            jaccard(title, f"{headline} {youth} {angle}"[:400]),
        )
        if sim > best_sim:
            best_sim = sim
            best = pitch

    # Strict match so unrelated left-list topics don't all inherit one pitch take.
    if not best or best_sim < 0.34:
        return None

    youth = str(best.get("youth_sentiment_summary") or "").strip()
    angle = str(best.get("crash_out_angle") or "").strip()
    take = youth or (angle[:320] + ("…" if len(angle) > 320 else ""))
    if not take:
        return None
    # Keep the take visibly tied to the selected research title.
    take = f"On “{title}”: {take}"
    try:
        consensus = float(best.get("consensus_score"))
    except (TypeError, ValueError):
        consensus = None
    return {
        "text": take,
        "pending": False,
        "headline": title[:120],
        "consensus_score": consensus,
        "match_score": round(best_sim, 2),
        "source": "pitch_run",
    }


def _heuristic_show_take(topic: Dict[str, Any], item: Dict[str, Any], confidence: int) -> Dict[str, Any]:
    """
    Agent 0 / Agent M research opinion for Crash Out — always available offline.
    Explains why this signal fits the series (Gary, Linda, Chris, Chloe) using
    media overlap + social proof presence.
    """
    title = str(item.get("title") or topic.get("representative", {}).get("title") or "This story").strip()
    outlets = [str(o) for o in (topic.get("outlets") or []) if o]
    layers = {str(x).upper() for x in (topic.get("layers") or []) if x}
    presence = int(topic.get("presence_count") or len(outlets) or 1)
    social = _social_proof_from_topic(topic)
    social_names = [c["name"] for c in (social.get("chips") or [])]
    has_a = "A" in layers
    has_b = "B" in layers or bool(social.get("has_social"))

    # Character-fit hooks from series personas.
    if has_a and has_b:
        cast_line = (
            "Gary and Linda can argue the adult/media-anxiety side while Chris and Chloe "
            "bring the youth/social-feed reaction — classic Crash Out kitchen crossfire."
        )
    elif has_b:
        cast_line = (
            "Strong youth-signal lane for Chris and Chloe; Gary/Linda can crash out when "
            "the kids treat it as content instead of news."
        )
    else:
        cast_line = (
            "Mainstream headline gives Gary and Linda a status/optics argument; "
            "Chris and Chloe can undercut it with a colder internet take."
        )

    if presence >= 4 or (has_a and has_b and presence >= 2):
        strength = (
            f"Unanimous enough for tonight: already on {presence} monitored outlets"
            + (f" ({', '.join(outlets[:3])})" if outlets else "")
            + "."
        )
    elif presence >= 2:
        strength = (
            f"Cross-media overlap is forming across {presence} outlets"
            + (f" including {', '.join(outlets[:2])}" if outlets else "")
            + " — stronger than a one-off meme."
        )
    else:
        strength = (
            "Still an early / single-source read — usable if the family argument is sharp, "
            "but weaker than a multi-outlet unanimous item."
        )

    if social_names:
        social_line = (
            f"Social proof on {', '.join(social_names[:3])} "
            f"({social.get('signal_label') or 'live'} signals) strengthens that Gen-Z actually cares."
        )
    else:
        social_line = (
            "No Social Proof (B) match yet — treat youth heat as unconfirmed until Reddit/X/YouTube catches up."
        )

    conf_note = f"Story-match confidence is {int(confidence)}/100."
    short_title = title if len(title) <= 110 else (title[:107].rstrip() + "…")
    text = f"On “{short_title}”: {strength} {social_line} {cast_line} {conf_note}".strip()
    return {
        "text": text,
        "pending": False,
        "headline": title[:120],
        "consensus_score": round(max(1.0, min(10.0, confidence / 10.0)), 1),
        "match_score": None,
        "source": "heuristic",
    }


def _live_take_enabled() -> bool:
    """OpenAI live Agent M take is ON by default; set AGENT0_LIVE_TAKE=0 to disable."""
    try:
        from app.config import config

        raw = str(getattr(config, "agent0_live_take", None) or "").strip().lower()
    except Exception:
        import os

        raw = (os.getenv("AGENT0_LIVE_TAKE") or "true").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _openai_chat_json(messages: List[Dict[str, str]], *, timeout: int = 60) -> Optional[Dict[str, Any]]:
    """
    Shared OpenAI chat → JSON object helper (luna-safe payload).
    Returns parsed dict or None on soft failure.
    """
    try:
        from app.config import config
    except Exception:
        return None
    api_key = (getattr(config, "openai_api_key", None) or "").strip()
    if not api_key:
        return None
    model = (getattr(config, "openai_model", None) or "gpt-4o-mini").strip()
    try:
        import json as _json
        import requests

        payload: Dict[str, Any] = {
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
        # gpt-*-luna / reasoning models reject custom temperature + max_tokens
        is_reasoning = any(m in model.lower() for m in ("luna", "o1", "o3", "reasoning"))
        if is_reasoning:
            payload["max_completion_tokens"] = 2200
        else:
            payload["temperature"] = 0.55
            payload["max_tokens"] = 1800
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
        text = (
            (((resp.json() or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ).strip()
        if not text:
            return None
        cleaned = text
        if "```" in cleaned:
            cleaned = cleaned.split("```", 2)[1]
            if cleaned.lstrip().startswith("json"):
                cleaned = cleaned.lstrip()[4:]
        cleaned = cleaned.strip()
        data = _json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _openai_enrich_topic(topic: Dict[str, Any], item: Dict[str, Any], confidence: int) -> Optional[Dict[str, Any]]:
    """
    OpenAI Agent M enrichment for a single squeezed viral topic:
    - editorial summary (why it trends across streams)
    - cast crash-out take for Gary/Linda/Chris/Chloe
    Falls soft to None when key/model/network fails.
    """
    title = str(item.get("title") or "").strip()
    snippet = str(item.get("snippet") or "").strip()
    outlets = [str(o) for o in (topic.get("outlets") or []) if o]
    layers = [str(x).upper() for x in (topic.get("layers") or []) if x]
    social = _social_proof_from_topic(topic)
    social_bits = ", ".join(
        f"{c.get('name')} {c.get('label')}" for c in (social.get("chips") or [])[:4]
    )
    prompt = (
        "You are Agent M for Crash Out — an adult satirical animated micro-drama "
        "(South Park x Arrested Development) about suburban family Gary, Linda, Chris, and Chloe.\n"
        "This topic already survived scrape → cross-stream matching → Top viral shortlist.\n"
        "Return STRICT JSON only with keys:\n"
        '  "summary": 1-2 sentences on why this is trending across media + youth social,\n'
        '  "agent_take": 2-3 sentences on Crash Out scene fit (which characters crash out + why),\n'
        '  "fit_score": number 1.0-10.0\n'
        f"Title: {title}\n"
        f"Feed snippet: {snippet[:280]}\n"
        f"Layers: {', '.join(layers) or 'n/a'}\n"
        f"Outlets/streams: {', '.join(outlets[:8]) or 'n/a'}\n"
        f"Social proof: {social_bits or 'none yet'}\n"
        f"Story-match confidence: {confidence}/100\n"
    )
    data = _openai_chat_json(
        [
            {
                "role": "system",
                "content": "You write Crash Out research briefs. Reply with JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        timeout=35,
    )
    if not data:
        return None
    take = str(data.get("agent_take") or data.get("take") or "").strip()
    summary = str(data.get("summary") or "").strip()
    try:
        fit = float(data.get("fit_score"))
    except (TypeError, ValueError):
        fit = round(max(1.0, min(10.0, confidence / 10.0)), 1)
    fit = round(max(1.0, min(10.0, fit)), 1)
    if len(take) < 40:
        return None
    return {
        "text": take[:520],
        "summary": (summary or snippet)[:320],
        "pending": False,
        "headline": title[:120],
        "consensus_score": fit,
        "match_score": None,
        "source": "openai",
    }


def _openai_show_take(topic: Dict[str, Any], item: Dict[str, Any], confidence: int) -> Optional[Dict[str, Any]]:
    """Back-compat alias → live OpenAI enrichment."""
    return _openai_enrich_topic(topic, item, confidence)


# Cache Agent takes per topic+title so switching left-list topics never reuses
# another story's opinion.
_AGENT_TAKE_CACHE: Dict[str, Dict[str, Any]] = {}


def _take_cache_key(topic: Dict[str, Any], item: Dict[str, Any], confidence: int) -> str:
    title = str(item.get("title") or "").strip().lower()
    topic_id = str(topic.get("id") or signal_id_for(item) or "")
    return f"{topic_id}|{title}|{int(confidence)}"


def _ai_take_for_item(
    item: Dict[str, Any],
    *,
    topic: Optional[Dict[str, Any]] = None,
    confidence: int = 0,
) -> Dict[str, Any]:
    """
    Agent M opinion for why THIS research signal fits Crash Out.

    Live path (default): OpenAI summary + take when API key is present.
    Fallback-first: heuristic if OpenAI is disabled/unavailable.
    """
    topic = topic or {}
    cache_key = _take_cache_key(topic, item, confidence)
    if cache_key in _AGENT_TAKE_CACHE:
        return _AGENT_TAKE_CACHE[cache_key]

    pitched = _pitch_run_take_for_item(item)
    if pitched:
        _AGENT_TAKE_CACHE[cache_key] = pitched
        return pitched

    if _live_take_enabled():
        live = _openai_enrich_topic(topic, item, confidence)
        if live:
            _AGENT_TAKE_CACHE[cache_key] = live
            return live

    heuristic = _heuristic_show_take(topic, item, confidence)
    heuristic["summary"] = str(item.get("snippet") or "")[:220]
    _AGENT_TAKE_CACHE[cache_key] = heuristic
    return heuristic


def _openai_batch_enrich_cards(cards: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    One OpenAI call for the whole Top-N viral board after scrape→match→squeeze.
    Returns map of signal_id → {text, summary, consensus_score, source}.
    """
    briefs: List[str] = []
    id_order: List[str] = []
    for i, card in enumerate(cards, 1):
        topic = card.get("topic") or {}
        item = card.get("item") or topic.get("representative") or {}
        sid = str(topic.get("id") or card.get("id") or signal_id_for(item) or f"n{i}")
        id_order.append(sid)
        outlets = [str(o) for o in (topic.get("outlets") or []) if o][:6]
        layers = [str(x).upper() for x in (topic.get("layers") or []) if x]
        social = _social_proof_from_topic(topic)
        social_bits = ", ".join(
            f"{c.get('name')} {c.get('label')}" for c in (social.get("chips") or [])[:3]
        )
        confidence = int(card.get("confidence") or card.get("score") or 0)
        briefs.append(
            f"{i}. id={sid}\n"
            f"   title: {str(item.get('title') or '')[:160]}\n"
            f"   snippet: {str(item.get('snippet') or '')[:180]}\n"
            f"   layers: {', '.join(layers) or 'n/a'}\n"
            f"   streams: {', '.join(outlets) or 'n/a'}\n"
            f"   social: {social_bits or 'none'}\n"
            f"   confidence: {confidence}/100"
        )
    user = (
        "These topics already survived scrape → cross-stream matching → Top viral shortlist "
        "for Crash Out (adult satirical animated micro-drama; cast Gary, Linda, Chris, Chloe).\n"
        "For EACH topic return an editorial summary + Agent M cast crash-out take.\n"
        "Return STRICT JSON:\n"
        '{ "items": [ { "id": "...", "summary": "1-2 sentences why it trends across media+social", '
        '"agent_take": "2-3 sentences scene fit (which characters crash out + why)", '
        '"fit_score": 1.0-10.0 } ] }\n'
        "Keep the same id values. Cover every topic.\n\n"
        + "\n\n".join(briefs)
    )
    data = _openai_chat_json(
        [
            {
                "role": "system",
                "content": (
                    "You are Agent M for Crash Out research. "
                    "Reply with one JSON object only — no prose outside JSON."
                ),
            },
            {"role": "user", "content": user},
        ],
        timeout=75,
    )
    if not data:
        return {}
    rows = data.get("items") or data.get("topics") or data.get("results") or []
    if not isinstance(rows, list):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or "").strip()
        take = str(row.get("agent_take") or row.get("take") or "").strip()
        summary = str(row.get("summary") or "").strip()
        if not rid or len(take) < 30:
            continue
        try:
            fit = float(row.get("fit_score"))
        except (TypeError, ValueError):
            fit = 7.0
        out[rid] = {
            "text": take[:520],
            "summary": summary[:320],
            "pending": False,
            "headline": "",
            "consensus_score": round(max(1.0, min(10.0, fit)), 1),
            "match_score": None,
            "source": "openai",
        }
    # Index-order fallback if model dropped ids
    if not out and rows and len(rows) == len(id_order):
        for sid, row in zip(id_order, rows):
            if not isinstance(row, dict):
                continue
            take = str(row.get("agent_take") or row.get("take") or "").strip()
            summary = str(row.get("summary") or "").strip()
            if len(take) < 30:
                continue
            try:
                fit = float(row.get("fit_score"))
            except (TypeError, ValueError):
                fit = 7.0
            out[sid] = {
                "text": take[:520],
                "summary": summary[:320],
                "pending": False,
                "headline": "",
                "consensus_score": round(max(1.0, min(10.0, fit)), 1),
                "match_score": None,
                "source": "openai",
            }
    return out


def _enrich_viral_cards_with_openai(cards: List[Dict[str, Any]]) -> None:
    """
    After scrape → match → Top-N squeeze: attach OpenAI summary + Agent M take
    onto each viral card (in place). One batch OpenAI call; per-card heuristic fallback.
    """
    if not cards or not _live_take_enabled():
        return

    batch = _openai_batch_enrich_cards(cards) if cards else {}

    for card in cards:
        topic = card.get("topic") or {}
        item = card.get("item") or topic.get("representative") or {}
        confidence = int(card.get("confidence") or card.get("score") or 0)
        sid = str(topic.get("id") or card.get("id") or signal_id_for(item) or "")
        cache_key = _take_cache_key(topic, item, confidence)

        take: Optional[Dict[str, Any]] = None
        if sid and sid in batch:
            take = dict(batch[sid])
            take["headline"] = str(item.get("title") or "")[:120]
            _AGENT_TAKE_CACHE[cache_key] = take
        elif cache_key in _AGENT_TAKE_CACHE:
            take = _AGENT_TAKE_CACHE[cache_key]
        else:
            # Soft fallback: single-topic OpenAI, then heuristic
            take = _ai_take_for_item(item, topic=topic, confidence=confidence)

        card["agent_take"] = (take or {}).get("text") or ""
        card["agent_take_source"] = (take or {}).get("source") or ""
        card["ai_summary"] = str((take or {}).get("summary") or card.get("summary") or "")[:320]
        card["ai_consensus_score"] = (take or {}).get("consensus_score")
        if card.get("ai_summary"):
            card["summary"] = card["ai_summary"]


def build_signal_card(
    topic: Dict[str, Any],
    *,
    index: int,
    selected_ids: Optional[Iterable[str]] = None,
    active_id: Optional[str] = None,
) -> Dict[str, Any]:
    """One list card = one post-scrape topic grouped by cross-platform presence."""
    selected = set(selected_ids or [])
    rep = topic.get("representative") or {}
    sid = str(topic.get("id") or signal_id_for(rep))
    layers = [str(x).upper() for x in (topic.get("layers") or []) if x]
    primary_layer = layers[0] if layers else str(rep.get("layer") or "").upper()
    presence = int(topic.get("presence_count") or 1)
    overlap_meta = _platform_overlap_and_confidence(topic)
    viral = joint_viral_scores(topic)
    cross_media_score = int(viral.get("cross_media_score") or 0)
    social_proof_score = int(viral.get("social_proof_score") or 0)
    joint_score = int(viral.get("joint_score") or 0)
    # List / ring score = joint (media alone + social alone, combined).
    score = joint_score
    if score <= 0:
        # Fallback: presence confidence, then feed-rank soft score.
        score = int(overlap_meta.get("confidence") or 0)
        if score <= 0:
            score = max(1, min(99, int(round(40 + math.log1p(_as_float(rep.get("score"))) * 5))))
        joint_score = score
    outlet_bars = list(overlap_meta.get("bars") or [])
    outlets = [str(b.get("name") or "") for b in outlet_bars if b.get("name")]
    if not outlets:
        outlets = list(overlap_meta.get("outlet_names") or topic.get("outlets") or [])
    if not outlets:
        fallback = str(rep.get("outlet") or rep.get("platform") or "").strip()
        if fallback:
            outlets = [fallback]
    # All outlet tabs on the list row (name + source URL) — no +N truncation.
    outlet_links: List[Dict[str, str]] = []
    mainstream_outlet_links: List[Dict[str, str]] = []
    seen_names: set[str] = set()
    seen_mainstream: set[str] = set()
    for bar in outlet_bars:
        name = str(bar.get("name") or "").strip()
        if not name or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        link = {
            "name": name,
            "url": str(bar.get("url") or "").strip(),
        }
        outlet_links.append(link)
        if str(bar.get("layer") or "").upper() == "A":
            if name.lower() not in seen_mainstream:
                seen_mainstream.add(name.lower())
                mainstream_outlet_links.append(link)
    if not outlet_links:
        for name in outlets:
            outlet_links.append({"name": name, "url": ""})
    if not mainstream_outlet_links:
        # Fall back only to Layer A members — never pull Reddit/X/YouTube into Mainstream tags.
        for it in topic.get("members") or []:
            if str(it.get("layer") or "").upper() != "A":
                continue
            text = str(it.get("outlet") or it.get("source") or "").strip()
            if not text or text.lower() in seen_mainstream:
                continue
            blob = text.lower()
            if blob.startswith("r/") or any(x in blob for x in ("reddit", "youtube", "tiktok", "twitter", "x.com")):
                continue
            seen_mainstream.add(text.lower())
            mainstream_outlet_links.append(
                {
                    "name": text,
                    "url": str(it.get("url") or "").strip(),
                }
            )
    tags = [o["name"] for o in outlet_links]
    snippet = re.sub(r"\s+", " ", str(rep.get("snippet") or "")).strip()
    if len(snippet) > 140:
        snippet = snippet[:137].rstrip() + "…"
    buckets = {_layer_bucket(L) for L in layers} or {_layer_bucket(primary_layer)}
    if "mainstream" in buckets and "social" in buckets:
        bucket = "all"
    elif "mainstream" in buckets:
        bucket = "mainstream"
    elif "social" in buckets:
        bucket = "social"
    else:
        bucket = "other"
    ordered_layers = [L for L in ("A", "B") if L in {str(x).upper() for x in layers}]
    if not ordered_layers and primary_layer:
        ordered_layers = [primary_layer]
    layer_labels = [_layer_label(L) for L in ordered_layers]
    if len(layer_labels) >= 2:
        combined_layer_label = " · ".join(layer_labels)
    else:
        combined_layer_label = layer_labels[0] if layer_labels else _layer_label(primary_layer)
    title = str(rep.get("title") or "Untitled signal").strip()
    social = _social_proof_from_topic(topic)
    has_cross = bool(topic.get("has_cross_layer")) or (
        "mainstream" in buckets and "social" in buckets
    )
    # Rank primarily by joint score; presence_rank is a tiny tie-break only.
    rank_score = float(joint_score) + float(topic.get("presence_rank") or 0) * 0.001
    return {
        "id": sid,
        "index": index + 1,
        "index_label": f"{index + 1:02d}",
        "title": title,
        "summary": snippet or "No summary captured for this signal yet.",
        "layer": primary_layer,
        "layers": ordered_layers or layers,
        "layer_label": combined_layer_label,
        "layer_labels": layer_labels,
        "bucket": bucket,
        "buckets": sorted(buckets),
        "tags": tags,
        "outlet_links": outlet_links,
        "mainstream_outlet_links": mainstream_outlet_links,
        "social_proof": social.get("chips") or [],
        "social_signal_label": social.get("signal_label") or "0",
        "social_signal_count": int(social.get("signal_count") or 0),
        "has_social_proof": bool(social.get("has_social")),
        "has_cross_layer": has_cross,
        "theme_key": str(topic.get("theme_key") or _theme_key(title)),
        "score": score,
        "cross_media_score": cross_media_score,
        "social_proof_score": social_proof_score,
        "joint_score": joint_score,
        "rank_score": rank_score,
        "score_label": f"{score}/100",
        "time_ago": _relative_time(rep.get("fetched_at")),
        "outlet": outlets[0] if outlets else str(rep.get("outlet") or ""),
        "outlets": outlets,
        "url": str(rep.get("url") or ""),
        "selected": sid in selected,
        "active": sid == active_id,
        "item": rep,
        "topic": topic,
        "presence_count": presence,
        "unanimous": bool(topic.get("unanimous")),
        "confidence": score,
        "confidence_bar": score,
        "outlet_bars": list(overlap_meta.get("bars") or []),
        "outlet_count": int(overlap_meta.get("outlet_count") or 0),
        "mainstream_outlet_names": list(overlap_meta.get("outlet_names") or []),
        "match_breakdown": str(overlap_meta.get("match_breakdown") or ""),
    }


def build_signal_detail(card: Dict[str, Any], pool_cards: Sequence[Dict[str, Any]] = ()) -> Dict[str, Any]:
    del pool_cards  # presence group already carries related outlets
    topic = card.get("topic") or {}
    overlap_meta = _platform_overlap_and_confidence(topic)
    # All streams (Mainstream A + Social B) use the same Story Match % bars.
    overlap = list(overlap_meta.get("bars") or card.get("outlet_bars") or [])
    outlet_names = [str(b.get("name") or "") for b in overlap if b.get("name")]
    if not outlet_names:
        outlet_names = list(overlap_meta.get("outlet_names") or card.get("mainstream_outlet_names") or [])
    presence_confidence = int(
        overlap_meta.get("confidence") or card.get("confidence") or card.get("score") or 0
    )
    viral = joint_viral_scores(topic) if topic else {
        "cross_media_score": int(card.get("cross_media_score") or 0),
        "social_proof_score": int(card.get("social_proof_score") or 0),
        "joint_score": int(card.get("joint_score") or presence_confidence or 0),
    }
    cross_media_score = int(viral.get("cross_media_score") or card.get("cross_media_score") or 0)
    social_proof_score = int(viral.get("social_proof_score") or card.get("social_proof_score") or 0)
    joint_score = int(
        viral.get("joint_score")
        or card.get("joint_score")
        or presence_confidence
        or card.get("score")
        or 0
    )
    display_score = joint_score or presence_confidence or int(card.get("score") or 0)
    unanimous = _unanimous_copy(topic, display_score)
    social = _social_proof_from_topic(topic)
    # Research page detail = presence / Story Match / social only.
    # OpenAI summary + Agent M take attach later on pitch handoff.
    base = {
        k: v
        for k, v in card.items()
        if k
        not in {
            "ai_summary",
            "agent_take",
            "agent_take_pending",
            "agent_take_headline",
            "agent_take_source",
            "ai_consensus_score",
        }
    }
    return {
        **base,
        "score": display_score,
        "score_label": f"{display_score}/100",
        "cross_media_score": cross_media_score,
        "social_proof_score": social_proof_score,
        "joint_score": joint_score,
        "confidence": display_score,
        "confidence_bar": display_score,
        "detail_label": f"TREND SIGNAL {card.get('index_label') or '01'}",
        "unanimous": bool(topic.get("unanimous")) or display_score >= 85,
        "unanimous_headline": unanimous["headline"],
        "unanimous_detail": unanimous["detail"],
        "debate_badge": unanimous["badge"],
        "match_breakdown": "",
        "mainstream_overlap": overlap,
        "mainstream_outlet_names": outlet_names,
        "outlet_bars": overlap,
        "outlet_count": len(overlap) or int(overlap_meta.get("outlet_count") or 0),
        "related_sources": [
            {"name": o, "layer": "", "title": card.get("title") or ""}
            for o in outlet_names
        ],
        "related_source_count": len(outlet_names),
        "social_proof": social.get("chips") or [],
        "social_signal_label": social.get("signal_label") or "0",
        "social_signal_count": int(social.get("signal_count") or 0),
        "has_social_proof": bool(social.get("has_social")),
    }


def build_research_context(
    *,
    selected_ids: Optional[Sequence[str]] = None,
    active_id: Optional[str] = None,
    filter_bucket: str = "all",
    query: str = "",
    run_date: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    bundle = _cached_raw_bundle(run_date)
    # Research UI: Mainstream (A) + Social Proof (B) only — Layer C excluded.
    items = _research_feed_items(bundle.get("items") or [])
    selected = list(selected_ids or [])[:MAX_SELECTED_SIGNALS]
    selected_signal_id = selected[0] if selected else ""
    pitch_btn_mode = pitch_mode_for_selection(selected, user_id=user_id)
    has_pitch = pitch_btn_mode == "view"

    # Post-scrape: group by presence (+ soft A×B social attach).
    # Rank by joint score (cross-media alone + social-proof alone, combined).
    topics = group_items_by_presence(items)
    cards = [
        build_signal_card(topic, index=i, selected_ids=selected, active_id=active_id)
        for i, topic in enumerate(topics)
    ]
    cards.sort(
        key=lambda c: (
            int(c.get("joint_score") or c.get("score") or 0),
            int(c.get("cross_media_score") or 0),
            int(c.get("social_proof_score") or 0),
            float(c.get("rank_score") or 0),
        ),
        reverse=True,
    )

    # Top 10 = highest joint score down. Soft theme cap while walking that order
    # (never promote a lower joint score above a higher one).
    viral_cards: List[Dict[str, Any]] = []
    theme_counts: Dict[str, int] = {}
    deferred: List[Dict[str, Any]] = []
    max_per_theme = 2
    for card in cards:
        theme = str(card.get("theme_key") or _theme_key(str(card.get("title") or "")))
        if theme_counts.get(theme, 0) < max_per_theme:
            viral_cards.append(card)
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
        else:
            deferred.append(card)
        if len(viral_cards) >= MAX_VIRAL_LIST:
            break
    if len(viral_cards) < MAX_VIRAL_LIST:
        for card in deferred:
            viral_cards.append(card)
            if len(viral_cards) >= MAX_VIRAL_LIST:
                break

    # Keep any already-selected topics visible even if they fell outside Top 10.
    selected_set = set(selected)
    if selected_set:
        have = {str(c.get("id")) for c in viral_cards}
        for c in cards:
            cid = str(c.get("id"))
            if cid in selected_set and cid not in have:
                viral_cards.append(c)
                have.add(cid)

    for i, card in enumerate(viral_cards):
        card["index"] = i + 1
        card["index_label"] = f"{i + 1:02d}"

    # Research UI stops at the thin Top-10 presence board (streams + social).
    # OpenAI summary / Agent M take run on pitch handoff, not on this page.

    bucket = (filter_bucket or "all").lower()
    if bucket not in {"all", "mainstream", "social"}:
        bucket = "all"
    q = (query or "").strip().lower()
    filtered = []
    for card in viral_cards:
        card_buckets = set(card.get("buckets") or [card.get("bucket")])
        if bucket == "mainstream" and "mainstream" not in card_buckets:
            continue
        if bucket == "social" and "social" not in card_buckets:
            continue
        hay = " ".join(
            [
                str(card.get("title") or ""),
                str(card.get("summary") or ""),
                " ".join(card.get("tags") or []),
                " ".join(card.get("outlets") or []),
                str(card.get("layer_label") or ""),
            ]
        ).lower()
        if q and q not in hay:
            continue
        filtered.append(card)

    for i, card in enumerate(filtered):
        card["index"] = i + 1
        card["index_label"] = f"{i + 1:02d}"

    id_map = {c["id"]: c for c in viral_cards}
    # Allow opening a selected/active id still present in the full ranked set.
    full_map = {c["id"]: c for c in cards}
    active = None
    if active_id and active_id in id_map:
        active = id_map[active_id]
    elif active_id and active_id in full_map and active_id in selected_set:
        active = full_map[active_id]
    elif filtered:
        active = filtered[0]
    elif viral_cards:
        active = viral_cards[0]

    detail = build_signal_detail(active) if active else None
    if detail:
        for card in viral_cards:
            card["active"] = card["id"] == detail["id"]
        detail["index"] = active.get("index")
        detail["index_label"] = active.get("index_label")
        detail["detail_label"] = f"TREND SIGNAL {active.get('index_label') or '01'}"

    day = str(bundle.get("run_date") or today_run_date())
    try:
        day_label = datetime.strptime(day, "%Y-%m-%d").strftime("%A, %B %d")
    except ValueError:
        day_label = day

    mainstream_n = sum(1 for c in viral_cards if "mainstream" in (c.get("buckets") or []))
    social_n = sum(1 for c in viral_cards if "social" in (c.get("buckets") or []))
    raw_count = len(items)

    return {
        "run_date": day,
        "day_label": day_label,
        "total_count": len(viral_cards),
        "pool_count": len(cards),
        "viral_limit": MAX_VIRAL_LIST,
        "raw_item_count": raw_count,
        "filtered_count": len(filtered),
        "mainstream_count": mainstream_n,
        "social_count": social_n,
        "character_count": 0,
        "filter_bucket": bucket,
        "filter_labels": FILTER_LABELS,
        "query": query or "",
        "signals": filtered,
        "all_signals": viral_cards,
        "active_signal": detail,
        "selected_ids": selected,
        "selected_count": len(selected),
        "selection_full": len(selected) >= MAX_SELECTED_SIGNALS,
        "can_create_pitches": pitch_btn_mode in {"create", "view"},
        "max_selected": MAX_SELECTED_SIGNALS,
        "selected_signal_id": selected_signal_id,
        "pitch_btn_mode": pitch_btn_mode,
        "has_pitch_for_selection": has_pitch,
        "sources_scanned": len({str(it.get("outlet") or it.get("source") or "") for it in items if it.get("outlet") or it.get("source")}),
    }


def _selection_user_key(session: Any, user_id: Optional[int] = None) -> Optional[str]:
    uid = user_id
    if uid is None:
        try:
            raw = session.get("user_id")
            uid = int(raw) if raw is not None else None
        except (TypeError, ValueError, AttributeError):
            uid = None
    if uid is None:
        return None
    return f"user:{int(uid)}"


def _clean_selected_ids(ids: Sequence[Any]) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for sid in ids:
        text = str(sid or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
        if len(cleaned) >= MAX_SELECTED_SIGNALS:
            break
    return cleaned


def get_selected_signal_ids(session: Any, user_id: Optional[int] = None) -> List[str]:
    key = _selection_user_key(session, user_id=user_id)
    raw: List[Any] = []
    if key and key in _SELECTED_BY_USER:
        raw = list(_SELECTED_BY_USER.get(key) or [])
    else:
        try:
            raw = list(session.get(SESSION_SELECTED_KEY) or [])
        except Exception:
            raw = []
    return _clean_selected_ids(raw)


def set_selected_signal_ids(
    session: Any,
    ids: Sequence[str],
    user_id: Optional[int] = None,
) -> List[str]:
    cleaned = _clean_selected_ids(ids)
    try:
        session[SESSION_SELECTED_KEY] = cleaned
    except Exception:
        pass
    key = _selection_user_key(session, user_id=user_id)
    if key:
        _SELECTED_BY_USER[key] = list(cleaned)
    return cleaned


def toggle_signal_selection(
    session: Any,
    signal_id: str,
    user_id: Optional[int] = None,
) -> List[str]:
    """Single-select toggle on All signals — does not change the active detail row."""
    current = get_selected_signal_ids(session, user_id=user_id)
    sid = str(signal_id or "").strip()
    if not sid:
        return current
    if sid in current:
        current = []
    else:
        current = [sid]
    return set_selected_signal_ids(session, current, user_id=user_id)


def apply_client_selection(
    session: Any,
    selected_ids: Sequence[str],
    user_id: Optional[int] = None,
) -> List[str]:
    """Trust the client’s intended selection list (post-click). Caps at MAX_SELECTED_SIGNALS."""
    return set_selected_signal_ids(session, selected_ids, user_id=user_id)


def _pitch_cache_key(user_id: Optional[int], signal_id: str) -> str:
    return f"{int(user_id) if user_id is not None else 'anon'}|{str(signal_id or '').strip()}"


def get_pitch_for_signal(signal_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    key = _pitch_cache_key(user_id, signal_id)
    pitch = _PITCH_BY_SIGNAL.get(key)
    return dict(pitch) if isinstance(pitch, dict) and pitch else None


def set_pitch_for_signal(
    signal_id: str,
    pitch: Dict[str, Any],
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    key = _pitch_cache_key(user_id, signal_id)
    cleaned = dict(pitch or {})
    cleaned["source_signal_id"] = str(signal_id)
    _PITCH_BY_SIGNAL[key] = cleaned
    return cleaned


def clear_pitch_for_signal(signal_id: str, user_id: Optional[int] = None) -> bool:
    """Drop cached pitch for a signal (e.g. after episode delete). Returns True if removed."""
    key = _pitch_cache_key(user_id, signal_id)
    return _PITCH_BY_SIGNAL.pop(key, None) is not None


def pitch_mode_for_selection(
    selected_ids: Sequence[str],
    user_id: Optional[int] = None,
) -> str:
    """Return create | view | disabled based on current single selection."""
    selected = [str(s).strip() for s in (selected_ids or []) if str(s).strip()]
    if not selected:
        return "disabled"
    return "view" if get_pitch_for_signal(selected[0], user_id=user_id) else "create"


def set_active_signal(session: Any, signal_id: str) -> str:
    sid = str(signal_id or "").strip()
    session[SESSION_ACTIVE_KEY] = sid
    return sid


def get_active_signal_id(session: Any) -> Optional[str]:
    try:
        value = session.get(SESSION_ACTIVE_KEY)
    except Exception:
        return None
    return str(value) if value else None


def remember_research_prefs(
    session: Any,
    *,
    view: Optional[str] = None,
    filter_bucket: Optional[str] = None,
    query: Optional[str] = None,
) -> None:
    if view is not None:
        session[SESSION_VIEW_KEY] = "history" if str(view).lower() in {"history", "trend-history", "28"} else "today"
    if filter_bucket is not None:
        bucket = str(filter_bucket or "all").lower()
        session[SESSION_FILTER_KEY] = (
            bucket if bucket in {"all", "mainstream", "social"} else "all"
        )
    if query is not None:
        session[SESSION_QUERY_KEY] = str(query or "")[:120]


def get_research_view(session: Any, fallback: str = "today") -> str:
    try:
        raw = session.get(SESSION_VIEW_KEY) or fallback
    except Exception:
        raw = fallback
    return "history" if str(raw).lower() in {"history", "trend-history", "28"} else "today"


def get_research_filter(session: Any, fallback: str = "all") -> str:
    try:
        raw = str(session.get(SESSION_FILTER_KEY) or fallback).lower()
    except Exception:
        raw = fallback
    return raw if raw in {"all", "mainstream", "social"} else "all"


def get_research_query(session: Any, fallback: str = "") -> str:
    try:
        return str(session.get(SESSION_QUERY_KEY) if session.get(SESSION_QUERY_KEY) is not None else fallback)
    except Exception:
        return fallback


def clusters_from_selected_topics(topics: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build friction clusters from post-scrape presence topic groups."""
    clusters: List[Dict[str, Any]] = []
    for i, topic in enumerate(topics[:MAX_SELECTED_SIGNALS]):
        members = list(topic.get("members") or [])
        rep = topic.get("representative") or (members[0] if members else {})
        layers = [str(x).upper() for x in (topic.get("layers") or []) if x]
        outlets = list(topic.get("outlets") or [])
        characters = []
        seen_char = set()
        for it in members:
            ch = str(it.get("character") or "").strip()
            if ch and ch.lower() not in seen_char:
                seen_char.add(ch.lower())
                characters.append(ch)
        layer_hits = {
            "A": sum(1 for it in members if str(it.get("layer") or "").upper() == "A"),
            "B": sum(1 for it in members if str(it.get("layer") or "").upper() == "B"),
            "C": sum(1 for it in members if str(it.get("layer") or "").upper() == "C"),
        }
        cluster: Dict[str, Any] = {
            "id": str(topic.get("id") or f"selected_{i + 1}"),
            "label": str(rep.get("title") or f"Signal {i + 1}"),
            "items": members or [rep],
            "layers": layers,
            "outlets": outlets,
            "characters": characters,
            "layer_hits": layer_hits,
            "cross_layer": len(layers) >= 2,
            "representative": rep,
            "member_count": len(members) or 1,
            "score_hint": float(topic.get("presence_rank") or _as_float(rep.get("score"))),
            "presence_count": int(topic.get("presence_count") or len(outlets) or 1),
            "unanimous": bool(topic.get("unanimous")),
        }
        if topic.get("ai_summary"):
            cluster["ai_summary"] = topic["ai_summary"]
        if topic.get("agent_take"):
            cluster["agent_take"] = topic["agent_take"]
            cluster["editorial"] = topic["agent_take"]
        if topic.get("ai_consensus_score") is not None:
            cluster["ai_consensus_score"] = topic["ai_consensus_score"]
        clusters.append(cluster)
    return clusters


def clusters_from_selected_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Legacy single-item clusters (fallback when topic lookup misses)."""
    clusters: List[Dict[str, Any]] = []
    for i, it in enumerate(items[:MAX_SELECTED_SIGNALS]):
        layer = str(it.get("layer") or "?").upper()
        outlet = str(it.get("outlet") or it.get("source") or "").strip()
        clusters.append(
            {
                "id": f"selected_{i + 1}",
                "label": str(it.get("title") or f"Signal {i + 1}"),
                "items": [it],
                "layers": [layer] if layer != "?" else [],
                "outlets": [outlet] if outlet else [],
                "characters": [str(it.get("character"))] if it.get("character") else [],
                "layer_hits": {
                    "A": 1 if layer == "A" else 0,
                    "B": 1 if layer == "B" else 0,
                    "C": 1 if layer == "C" else 0,
                },
                "cross_layer": False,
                "representative": it,
                "member_count": 1,
                "score_hint": _as_float(it.get("score")),
            }
        )
    return clusters


def create_pitches_from_signal_ids(
    signal_ids: Sequence[str],
    *,
    mode: str = "fresh",
    guidance: str = "",
    prior_pitch: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Score the selected presence topic(s) into Gate 1 pitch card(s).

    mode:
      - fresh: full regenerate (Create Pitch / Regenerate)
      - improve: rewrite using prior_pitch + HITL guidance notes
    """
    from app.trends.friction import score_clusters

    wanted = [str(s).strip() for s in signal_ids if str(s).strip()][:MAX_SELECTED_SIGNALS]
    hitl_mode = str(mode or "fresh").strip().lower()
    notes = str(guidance or "").strip()
    logger.info(
        "[create-pitch] Start · signal_ids=%s · hitl=%s · guidance_chars=%d",
        wanted,
        hitl_mode,
        len(notes),
    )
    if len(wanted) != MAX_SELECTED_SIGNALS:
        raise ValueError(f"Select exactly {MAX_SELECTED_SIGNALS} topic to create a pitch.")
    if hitl_mode in {"improve", "revise", "edit"} and not notes:
        raise ValueError("Add improvement notes before clicking Improve pitch.")

    bundle = load_raw_items()
    items = _research_feed_items(bundle.get("items") or [])
    topics = group_items_by_presence(items)
    logger.info(
        "[create-pitch] Loaded research feed · raw_items=%d · presence_topics=%d · run_date=%s",
        len(items),
        len(topics),
        bundle.get("run_date"),
    )
    by_topic = {str(t.get("id")): t for t in topics}
    # Also allow resolving legacy per-item signal ids to their presence group.
    item_to_topic: Dict[str, Dict[str, Any]] = {}
    for topic in topics:
        for member in topic.get("members") or []:
            item_to_topic[signal_id_for(member)] = topic

    selected_topics: List[Dict[str, Any]] = []
    seen_topic_ids = set()
    for sid in wanted:
        topic = by_topic.get(sid) or item_to_topic.get(sid)
        if not topic:
            logger.warning("[create-pitch] Signal id not found in today's feed: %s", sid)
            continue
        tid = str(topic.get("id"))
        if tid in seen_topic_ids:
            continue
        seen_topic_ids.add(tid)
        selected_topics.append(topic)

    if len(selected_topics) != MAX_SELECTED_SIGNALS:
        raise ValueError("Selected topic is no longer in today's research feed. Refresh and reselect.")

    selected_title = str((selected_topics[0].get("representative") or {}).get("title") or "")[:120]
    logger.info(
        "[create-pitch] Resolved topic · id=%s · title=%s · layers=%s · members=%d",
        selected_topics[0].get("id"),
        selected_title,
        selected_topics[0].get("layers"),
        len(selected_topics[0].get("members") or []),
    )

    run_date = str(bundle.get("run_date") or today_run_date())
    # Agent M handoff: AI editorial summary + cast take on the selected thin board.
    enrich_cards = [
        build_signal_card(topic, index=i) for i, topic in enumerate(selected_topics)
    ]
    logger.info("[create-pitch] Step 1/4 · OpenAI enrich (summary + Agent M take)")
    _enrich_viral_cards_with_openai(enrich_cards)
    enrich_by_id = {str(c.get("id")): c for c in enrich_cards}
    for topic in selected_topics:
        card = enrich_by_id.get(str(topic.get("id"))) or {}
        if card.get("ai_summary"):
            topic["ai_summary"] = card["ai_summary"]
        if card.get("agent_take"):
            topic["agent_take"] = card["agent_take"]
        if card.get("ai_consensus_score") is not None:
            topic["ai_consensus_score"] = card["ai_consensus_score"]
        if card.get("agent_take_source"):
            topic["agent_take_source"] = card["agent_take_source"]
        logger.info(
            "[create-pitch] Enrich result · source=%s · summary_chars=%d · take_chars=%d",
            card.get("agent_take_source") or "none",
            len(str(card.get("ai_summary") or "")),
            len(str(card.get("agent_take") or "")),
        )

    clusters = clusters_from_selected_topics(selected_topics)
    for cluster in clusters:
        tid = str(cluster.get("id") or "")
        card = enrich_by_id.get(tid) or {}
        if card.get("ai_summary"):
            cluster["ai_summary"] = card["ai_summary"]
        if card.get("agent_take"):
            cluster["agent_take"] = card["agent_take"]
            cluster["editorial"] = card["agent_take"]
        if card.get("ai_consensus_score") is not None:
            cluster["ai_consensus_score"] = card["ai_consensus_score"]
    logger.info("[create-pitch] Step 2/4 · Friction score clusters=%d · hitl=%s", len(clusters), hitl_mode)
    pitches = score_clusters(
        clusters,
        run_date=run_date,
        mode=hitl_mode,
        guidance=notes,
        prior_pitch=prior_pitch if isinstance(prior_pitch, dict) else None,
    )
    # Single-topic Create Pitch: keep the strongest card only.
    pitches = list(pitches or [])[:1]
    logger.info(
        "[create-pitch] Step 3/4 · Scored pitch · count=%d · headline=%s · score=%s",
        len(pitches),
        (pitches[0].get("headline") if pitches else "")[:100],
        (pitches[0].get("consensus_score") if pitches else None),
    )
    selected_reps = [t.get("representative") or {} for t in selected_topics]
    run = normalize_pitch_run(
        pitches,
        run_date=run_date,
        meta={
            "mode": "selected_presence_topics",
            "hitl_mode": hitl_mode,
            "hitl_guidance": notes[:500] if notes else "",
            "raw_count": len(items),
            "topic_count": len(topics),
            "selected_count": len(selected_topics),
            "cluster_count": len(clusters),
            "layer_counts": {
                "A": sum(1 for t in selected_topics if "A" in (t.get("layers") or [])),
                "B": sum(1 for t in selected_topics if "B" in (t.get("layers") or [])),
                "C": sum(1 for t in selected_topics if "C" in (t.get("layers") or [])),
            },
            "selected_titles": [str(r.get("title") or "") for r in selected_reps],
            "source_signal_id": wanted[0] if wanted else "",
        },
    )
    if not run.get("pitches"):
        raise RuntimeError("Pitch generation returned no cards for the selected topic.")
    logger.info("[create-pitch] Step 4/4 · Saving pitch run + building concept card")
    save_pitch_run(run)
    concepts = pitches_to_concepts(run)
    logger.info(
        "[create-pitch] Done · signal_id=%s · concept=%s",
        wanted[0] if wanted else "",
        (concepts[0].get("headline") or concepts[0].get("title") if concepts else "")[:100],
    )
    return {
        "run": run,
        "concepts": concepts[:1],
        "run_date": run_date,
        "signal_id": wanted[0] if wanted else "",
    }
