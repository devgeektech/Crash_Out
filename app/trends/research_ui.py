"""
Agent 0 Trend Research UI helpers:
- Map raw Layer A/B/C items → signal cards + detail panels
- Track up to 5 selected topics
- Mint Top-5 pitches from the selected topics
"""
from __future__ import annotations

import hashlib
import math
import re
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.trends.cluster import jaccard
from app.trends.schema import normalize_pitch_run, pitches_to_concepts, today_run_date
from app.trends.store import load_latest_pitch_run, load_raw_items, save_pitch_run

MAX_SELECTED_SIGNALS = 5
PRESENCE_JACCARD = 0.28  # post-scrape topic merge threshold
SESSION_SELECTED_KEY = "agent0_selected_signal_ids"
SESSION_ACTIVE_KEY = "agent0_active_signal_id"
SESSION_VIEW_KEY = "agent0_research_view"
SESSION_FILTER_KEY = "agent0_research_filter"
SESSION_QUERY_KEY = "agent0_research_query"

FILTER_LABELS = {
    "all": "All signals",
    "mainstream": "Mainstream (A)",
    "social": "Social Proof (B)",
    "character": "Character Niche (C)",
}


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
    """UI filter buckets: A=mainstream, B=social, C=character niche."""
    layer = (layer or "").upper()
    if layer == "A":
        return "mainstream"
    if layer == "B":
        return "social"
    if layer == "C":
        return "character"
    return "other"


def _layer_label(layer: str) -> str:
    layer = (layer or "").upper()
    if layer == "A":
        return "Mainstream (A)"
    if layer == "B":
        return "Social Proof (B)"
    if layer == "C":
        return "Character Niche (C)"
    return "Layer ?"


def _topic_id_for(members: Sequence[Dict[str, Any]]) -> str:
    seeds = sorted(signal_id_for(it) for it in members)
    return "topic_" + hashlib.sha1("|".join(seeds).encode("utf-8")).hexdigest()[:14]


def group_items_by_presence(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    After scrape (no dedupe): merge stories that appear across platforms/outlets.
    Ranking is driven by how widely a topic is present.
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

    topics: List[Dict[str, Any]] = []
    for members in groups.values():
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
        # Presence-first ranking: how many outlets/platforms/layers carry the topic.
        presence_rank = (
            presence_count * 18.0
            + platform_count * 8.0
            + layer_count * 14.0
            + math.log1p(sum(_as_float(m.get("score")) for m in members))
        )
        unanimous = presence_count >= 4 or layer_count >= 2
        topics.append(
            {
                "id": _topic_id_for(members),
                "members": members,
                "representative": rep,
                "outlets": outlets,
                "platforms": platforms,
                "layers": layers,
                "presence_count": presence_count,
                "platform_count": platform_count,
                "layer_count": layer_count,
                "presence_rank": presence_rank,
                "unanimous": unanimous,
                "member_count": len(members),
            }
        )

    topics.sort(
        key=lambda t: (
            float(t.get("presence_rank") or 0),
            int(t.get("presence_count") or 0),
            int(t.get("layer_count") or 0),
        ),
        reverse=True,
    )
    return topics


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

        prev = by_platform.get(key)
        if not prev or match_pct > float(prev.get("strength") or 0):
            by_platform[key] = {
                "name": name,
                "strength": match_pct,
                "layer": str(it.get("layer") or "").upper() or "A",
                "hits": int(prev.get("hits") or 0) + 1 if prev else 1,
                "factors": factors,
            }
        elif prev:
            prev["hits"] = int(prev.get("hits") or 1) + 1

    return sorted(
        (
            {
                "name": row["name"],
                "strength": int(round(min(100.0, float(row["strength"])))),
                "layer": row.get("layer") or "A",
                "hits": int(row.get("hits") or 1),
                "factors": row.get("factors") or {},
            }
            for row in by_platform.values()
        ),
        key=lambda r: int(r["strength"]),
        reverse=True,
    )


def _platform_overlap_and_confidence(topic: Dict[str, Any]) -> Dict[str, Any]:
    """
    Per-outlet Story Match bars + ring confidence.

    - Each bar = that outlet's S/E/C/T match vs the anchor story.
    - Ring confidence = average of those bars across every matched outlet
      (Layer A/B/C), not the top bar alone.
    """
    members = list(topic.get("members") or [])
    rep = topic.get("representative") or (members[0] if members else {})
    all_rows = _accumulate_platform_matches(members, rep)[:8]
    mainstream_rows = [r for r in all_rows if str(r.get("layer") or "").upper() == "A"]

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
    if len(all_rows) == 1:
        # One outlet only — no cross-platform confirmation yet.
        confidence = max(
            28,
            min(55, int(round(28 + math.log1p(_as_float(rep.get("score"))) * 4))),
        )
        avg_match = strengths[0]
    else:
        avg_match = max(1, min(100, int(round(sum(strengths) / len(strengths)))))
        confidence = avg_match

    parts = [f"{r['name']} {int(r['strength'])}%" for r in all_rows]
    if len(all_rows) == 1:
        breakdown = f"{parts[0]} (single outlet — early signal {confidence}/100)"
    else:
        breakdown = f"({' + '.join(parts)}) ÷ {len(all_rows)} = {confidence}%"

    return {
        # Show every outlet that feeds the ring average (not Layer A only).
        "bars": all_rows,
        "outlet_names": [b["name"] for b in all_rows],
        "outlet_count": len(all_rows),
        "mainstream_count": len(mainstream_rows),
        "confidence": confidence,
        "confidence_bar": confidence,
        "platform_count": len(all_rows),
        "avg_match_confidence": avg_match,
        "unique_outlets": len(all_rows),
        "match_breakdown": breakdown,
    }


def _mainstream_overlap(topic: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Back-compat wrapper → platform bars only."""
    return list(_platform_overlap_and_confidence(topic).get("bars") or [])


def _unanimous_copy(topic: Dict[str, Any], score: int) -> Dict[str, str]:
    presence = int(topic.get("presence_count") or 0)
    layers = topic.get("layers") or []
    if score >= 85 or (topic.get("unanimous") and presence >= 3):
        headline = "Unanimous signal"
        detail = "High confidence across media and social"
        badge = "High debate"
    elif presence >= 2 or score >= 60:
        headline = "Emerging consensus"
        detail = f"Confidence building across {presence} outlets"
        badge = "Watch list" if score < 75 else "Rising debate"
    else:
        headline = "Single-source signal"
        detail = "Needs broader platform presence to climb the rank"
        badge = "Early signal"
    if layers and presence >= 2 and score < 85:
        detail = f"High confidence across {presence} outlets spanning {', '.join(layers)}"
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
    # Character niche (Layer C) and mainstream get a slight editorial boost
    # so YouTube raw-view spikes don't monopolize "strongest" ranking.
    layer = str(item.get("layer") or "").upper()
    if layer == "A":
        bonus += 4.0
    elif layer == "C":
        bonus += 7.0
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
    buckets: Dict[str, List[Dict[str, Any]]] = {"A": [], "B": [], "C": [], "?": []}
    for card in cards:
        layer = str(card.get("layer") or "?").upper()
        buckets.setdefault(layer if layer in buckets else "?", []).append(card)
    for layer_cards in buckets.values():
        layer_cards.sort(key=lambda c: float(c.get("rank_score") or c.get("score") or 0), reverse=True)

    order = ["A", "C", "B", "?"]  # surface character niche early with mainstream
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


def _ai_take_for_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pull Agent M's take from the latest AI ranking / pitch-scoring run.
    Prefer youth_sentiment_summary (AI editorial read); fall back to crash_out_angle.
    """
    run = load_latest_pitch_run() or {}
    pitches = list(run.get("pitches") or [])
    title = str(item.get("title") or "").strip()
    if not pitches or not title:
        return {
            "text": "",
            "pending": True,
            "headline": "",
            "consensus_score": None,
        }

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

    if not best or best_sim < 0.18:
        return {
            "text": "",
            "pending": True,
            "headline": "",
            "consensus_score": None,
        }

    youth = str(best.get("youth_sentiment_summary") or "").strip()
    angle = str(best.get("crash_out_angle") or "").strip()
    take = youth or (angle[:320] + ("…" if len(angle) > 320 else ""))
    try:
        consensus = float(best.get("consensus_score"))
    except (TypeError, ValueError):
        consensus = None
    return {
        "text": take,
        "pending": not bool(take),
        "headline": str(best.get("headline") or ""),
        "consensus_score": consensus,
        "match_score": round(best_sim, 2),
    }


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
    # Confidence = average of per-platform match percentages.
    score = int(overlap_meta.get("confidence") or 0)
    if score <= 0:
        # Single hit with no bar data: still surface a modest score from feed rank.
        score = max(1, min(99, int(round(40 + math.log1p(_as_float(rep.get("score"))) * 5))))
    outlets = list(overlap_meta.get("outlet_names") or topic.get("outlets") or [])
    tags = [_layer_label(primary_layer)]
    tags.extend(outlets[:3])
    extra = max(0, len(outlets) - 3)
    if extra:
        tags.append(f"+{extra}")
    snippet = re.sub(r"\s+", " ", str(rep.get("snippet") or "")).strip()
    if len(snippet) > 140:
        snippet = snippet[:137].rstrip() + "…"
    buckets = {_layer_bucket(L) for L in layers} or {_layer_bucket(primary_layer)}
    if "mainstream" in buckets:
        bucket = "mainstream"
    elif "social" in buckets:
        bucket = "social"
    elif "character" in buckets:
        bucket = "character"
    else:
        bucket = "other"
    return {
        "id": sid,
        "index": index + 1,
        "index_label": f"{index + 1:02d}",
        "title": str(rep.get("title") or "Untitled signal").strip(),
        "summary": snippet or "No summary captured for this signal yet.",
        "layer": primary_layer,
        "layers": layers,
        "layer_label": _layer_label(primary_layer),
        "bucket": bucket,
        "buckets": sorted(buckets),
        "tags": tags[:5],
        "score": score,
        "rank_score": float(score) + float(topic.get("presence_rank") or 0) * 0.01,
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
        "confidence_bar": int(overlap_meta.get("confidence_bar") or score),
        "outlet_bars": list(overlap_meta.get("bars") or []),
        "outlet_count": int(overlap_meta.get("outlet_count") or 0),
        "mainstream_outlet_names": list(overlap_meta.get("outlet_names") or []),
        "match_breakdown": str(overlap_meta.get("match_breakdown") or ""),
    }


def build_signal_detail(card: Dict[str, Any], pool_cards: Sequence[Dict[str, Any]] = ()) -> Dict[str, Any]:
    del pool_cards  # presence group already carries related outlets
    topic = card.get("topic") or {}
    item = card.get("item") or topic.get("representative") or {}
    overlap_meta = _platform_overlap_and_confidence(topic)
    overlap = list(overlap_meta.get("bars") or card.get("outlet_bars") or [])
    outlet_names = list(overlap_meta.get("outlet_names") or card.get("mainstream_outlet_names") or [])
    confidence = int(overlap_meta.get("confidence") or card.get("confidence") or card.get("score") or 0)
    breakdown = str(overlap_meta.get("match_breakdown") or card.get("match_breakdown") or "")
    unanimous = _unanimous_copy(topic, confidence)
    # Prefer the explicit average formula so 100% bars vs 72 ring is obvious.
    detail = breakdown or unanimous["detail"]
    ai_take = _ai_take_for_item(item)
    return {
        **card,
        "score": confidence or int(card.get("score") or 0),
        "score_label": f"{confidence or int(card.get('score') or 0)}/100",
        "confidence": confidence,
        "confidence_bar": int(overlap_meta.get("confidence_bar") or confidence),
        "detail_label": f"TREND SIGNAL {card.get('index_label') or '01'}",
        "unanimous": bool(topic.get("unanimous")) or confidence >= 85,
        "unanimous_headline": unanimous["headline"],
        "unanimous_detail": detail,
        "debate_badge": unanimous["badge"],
        "match_breakdown": breakdown,
        "mainstream_overlap": overlap,
        "mainstream_outlet_names": outlet_names,
        "outlet_bars": overlap,
        "outlet_count": int(overlap_meta.get("outlet_count") or len(overlap)),
        "related_sources": [
            {"name": o, "layer": "", "title": card.get("title") or ""}
            for o in outlet_names
        ],
        "related_source_count": int(overlap_meta.get("outlet_count") or 0),
        "agent_take": ai_take.get("text") or "",
        "agent_take_pending": bool(ai_take.get("pending")),
        "agent_take_headline": ai_take.get("headline") or "",
        "ai_consensus_score": ai_take.get("consensus_score"),
    }


def build_research_context(
    *,
    selected_ids: Optional[Sequence[str]] = None,
    active_id: Optional[str] = None,
    filter_bucket: str = "all",
    query: str = "",
    run_date: Optional[str] = None,
) -> Dict[str, Any]:
    bundle = _cached_raw_bundle(run_date)
    items = list(bundle.get("items") or [])
    selected = list(selected_ids or [])[:MAX_SELECTED_SIGNALS]

    # Post-scrape: group by cross-platform presence, then rank.
    topics = group_items_by_presence(items)
    cards = [
        build_signal_card(topic, index=i, selected_ids=selected, active_id=active_id)
        for i, topic in enumerate(topics)
    ]
    for i, card in enumerate(cards):
        card["index"] = i + 1
        card["index_label"] = f"{i + 1:02d}"

    bucket = (filter_bucket or "all").lower()
    if bucket not in {"all", "mainstream", "social", "character"}:
        bucket = "all"
    q = (query or "").strip().lower()
    filtered = []
    for card in cards:
        card_buckets = set(card.get("buckets") or [card.get("bucket")])
        if bucket == "mainstream" and "mainstream" not in card_buckets:
            continue
        if bucket == "social" and "social" not in card_buckets:
            continue
        if bucket == "character" and "character" not in card_buckets:
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

    id_map = {c["id"]: c for c in cards}
    active = None
    if active_id and active_id in id_map:
        active = id_map[active_id]
    elif filtered:
        active = filtered[0]
    elif cards:
        active = cards[0]

    detail = build_signal_detail(active) if active else None
    if detail:
        for card in cards:
            card["active"] = card["id"] == detail["id"]

    day = str(bundle.get("run_date") or today_run_date())
    try:
        day_label = datetime.strptime(day, "%Y-%m-%d").strftime("%A, %B %d")
    except ValueError:
        day_label = day

    mainstream_n = sum(1 for c in cards if "mainstream" in (c.get("buckets") or []))
    social_n = sum(1 for c in cards if "social" in (c.get("buckets") or []))
    character_n = sum(1 for c in cards if "character" in (c.get("buckets") or []))
    raw_count = len(items)

    return {
        "run_date": day,
        "day_label": day_label,
        "total_count": len(cards),
        "raw_item_count": raw_count,
        "filtered_count": len(filtered),
        "mainstream_count": mainstream_n,
        "social_count": social_n,
        "character_count": character_n,
        "filter_bucket": bucket,
        "filter_labels": FILTER_LABELS,
        "query": query or "",
        "signals": filtered,
        "all_signals": cards,
        "active_signal": detail,
        "selected_ids": selected,
        "selected_count": len(selected),
        "selection_full": len(selected) >= MAX_SELECTED_SIGNALS,
        "can_create_pitches": len(selected) == MAX_SELECTED_SIGNALS,
        "max_selected": MAX_SELECTED_SIGNALS,
        "sources_scanned": len({str(it.get("outlet") or it.get("source") or "") for it in items if it.get("outlet") or it.get("source")}),
    }


def get_selected_signal_ids(session: Any) -> List[str]:
    raw = []
    try:
        raw = list(session.get(SESSION_SELECTED_KEY) or [])
    except Exception:
        raw = []
    out: List[str] = []
    seen = set()
    for sid in raw:
        text = str(sid or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= MAX_SELECTED_SIGNALS:
            break
    return out


def set_selected_signal_ids(session: Any, ids: Sequence[str]) -> List[str]:
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
    session[SESSION_SELECTED_KEY] = cleaned
    return cleaned


def toggle_signal_selection(session: Any, signal_id: str) -> List[str]:
    """Toggle topic selection only — does not change the active detail row."""
    current = get_selected_signal_ids(session)
    sid = str(signal_id or "").strip()
    if not sid:
        return current
    if sid in current:
        current = [x for x in current if x != sid]
    elif len(current) < MAX_SELECTED_SIGNALS:
        current = current + [sid]
    set_selected_signal_ids(session, current)
    return current


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
            bucket if bucket in {"all", "mainstream", "social", "character"} else "all"
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
    return raw if raw in {"all", "mainstream", "social", "character"} else "all"


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
        clusters.append(
            {
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
        )
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


def create_pitches_from_signal_ids(signal_ids: Sequence[str]) -> Dict[str, Any]:
    """Score the 5 selected presence topics into Top-5 Gate 1 pitch cards."""
    from app.trends.friction import score_clusters

    wanted = [str(s).strip() for s in signal_ids if str(s).strip()][:MAX_SELECTED_SIGNALS]
    if len(wanted) != MAX_SELECTED_SIGNALS:
        raise ValueError(f"Select exactly {MAX_SELECTED_SIGNALS} topics to create pitches.")

    bundle = load_raw_items()
    items = list(bundle.get("items") or [])
    topics = group_items_by_presence(items)
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
            continue
        tid = str(topic.get("id"))
        if tid in seen_topic_ids:
            continue
        seen_topic_ids.add(tid)
        selected_topics.append(topic)

    if len(selected_topics) != MAX_SELECTED_SIGNALS:
        raise ValueError("One or more selected topics are no longer in today's research feed. Refresh and reselect.")

    run_date = str(bundle.get("run_date") or today_run_date())
    clusters = clusters_from_selected_topics(selected_topics)
    pitches = score_clusters(clusters, run_date=run_date)
    selected_reps = [t.get("representative") or {} for t in selected_topics]
    run = normalize_pitch_run(
        pitches,
        run_date=run_date,
        meta={
            "mode": "selected_presence_topics",
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
        },
    )
    if not run.get("pitches"):
        raise RuntimeError("Pitch generation returned no cards for the selected topics.")
    save_pitch_run(run)
    concepts = pitches_to_concepts(run)
    return {"run": run, "concepts": concepts[:5], "run_date": run_date}
