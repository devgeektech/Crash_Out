"""
Hot-topic collector via simple web search (no News/Reddit/Trends APIs).

Uses the `ddgs` package (DuckDuckGo search client) with a working backend.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Queries aimed at Crash Out satirical fuel (US suburban / Gen Z culture).
SEARCH_QUERIES = [
    "trending US culture news today",
    "viral Gen Z TikTok trends this week",
    "HOA neighbor drama news United States",
    "cost of living tipping culture US viral",
    "suburban parenting controversy news",
    "Stanley cup wellness trend news",
]

# Prefer backends that currently return results; fall through on failure.
SEARCH_BACKENDS = ("yahoo", "auto", "bing", "brave", "duckduckgo")


def _trend_item(
    *,
    title: str,
    source: str,
    url: str = "",
    score: float = 0.0,
    snippet: str = "",
    raw: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "title": (title or "").strip(),
        "source": source,
        "url": url or "",
        "score": float(score or 0),
        "snippet": (snippet or "").strip()[:400],
        "fetched_at": time.time(),
        "raw": raw or {},
    }


def _search_once(query: str, *, max_results: int = 8) -> List[Dict[str, Any]]:
    try:
        from ddgs import DDGS
    except ImportError:
        logger.warning("ddgs not installed; run: pip install ddgs")
        return []

    last_err: Optional[Exception] = None
    for backend in SEARCH_BACKENDS:
        try:
            with DDGS() as client:
                rows = list(
                    client.text(
                        query,
                        region="us-en",
                        safesearch="moderate",
                        max_results=max_results,
                        backend=backend,
                    )
                )
            if rows:
                return rows
        except Exception as exc:
            last_err = exc
            logger.debug("Web search backend %s failed for %r: %s", backend, query, exc)
            continue
    if last_err:
        logger.warning("Web search failed for %r: %s", query, last_err)
    return []


def fetch_web_search_trends() -> List[Dict[str, Any]]:
    """Run a few targeted web searches and return hot-topic hits."""
    items: List[Dict[str, Any]] = []
    for i, query in enumerate(SEARCH_QUERIES):
        rows = _search_once(query, max_results=8)
        for rank, row in enumerate(rows):
            title = (row.get("title") or "").strip()
            if not title:
                continue
            body = (row.get("body") or row.get("description") or "").strip()
            href = (row.get("href") or row.get("link") or "").strip()
            # Earlier queries + higher ranks score slightly higher.
            score = 100.0 - (i * 5.0) - rank
            items.append(
                _trend_item(
                    title=title,
                    source="web_search",
                    url=href,
                    score=score,
                    snippet=body,
                    raw={"query": query},
                )
            )
        time.sleep(0.35)
    return items


def collect_all_trends() -> List[Dict[str, Any]]:
    """
    Gather hot topics across Layers B → A (social-first, then mainstream).
    Layer C (character niche) has been removed.

    Important: do NOT dedupe at scrape time. Keep every outlet/platform hit so
    downstream presence ranking can measure how widely a topic appears.
    """
    bucket: List[Dict[str, Any]] = []
    ingest_order = ("B", "A")
    logger.info("Agent 0 ingest_order: %s", ",".join(ingest_order))

    # 1) Youth / social first — YouTube (News/Entertainment first), Reddit, slang, memes.
    layer_b: List[Dict[str, Any]] = []
    try:
        from app.trends.sources_b import collect_layer_b, youtube_news_entertainment_titles

        layer_b = collect_layer_b()
        bucket.extend(layer_b)
    except Exception as exc:
        logger.warning("Layer B failed: %s", exc)
        youtube_news_entertainment_titles = None  # type: ignore

    # 2) Mainstream news — seeded by viral YouTube News/Entertainment titles for A×B match.
    try:
        from app.trends.sources_a import collect_layer_a

        yt_seeds: List[str] = []
        if layer_b and youtube_news_entertainment_titles:
            try:
                yt_seeds = youtube_news_entertainment_titles(layer_b, limit=8)
            except Exception as seed_exc:
                logger.debug("YouTube seed titles skipped: %s", seed_exc)
        bucket.extend(collect_layer_a(youtube_bridge_titles=yt_seeds or None))
    except Exception as exc:
        logger.warning("Layer A failed: %s", exc)

    # Soft fill if layered sources are thin — prefer youth/social queries (Layer B).
    if len(bucket) < 25:
        for item in fetch_web_search_trends():
            item = dict(item)
            q = str((item.get("raw") or {}).get("query") or "").lower()
            youthish = any(
                tok in q
                for tok in ("gen z", "tiktok", "meme", "slang", "viral", "hoa", "suburban")
            )
            item.setdefault("layer", "B" if youthish else "A")
            item.setdefault("outlet", "Web")
            bucket.append(item)

    collected: List[Dict[str, Any]] = []
    for item in bucket:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        row = dict(item)
        if not row.get("layer"):
            row["layer"] = "B"
        collected.append(row)

    # Preserve scrape order richness; light score sort only for readability.
    collected.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    logger.info(
        "Agent 0 collected %s raw items (ingest_order=%s, no scrape-time title dedupe)",
        len(collected),
        ",".join(ingest_order),
    )
    return collected
