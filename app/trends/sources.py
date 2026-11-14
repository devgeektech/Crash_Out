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
    """Gather + dedupe hot topics from web search."""
    bucket = fetch_web_search_trends()
    seen = set()
    unique: List[Dict[str, Any]] = []
    for item in bucket:
        key = (item.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    unique.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    return unique
