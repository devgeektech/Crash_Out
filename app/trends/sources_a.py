"""
Layer A — Mainstream US consensus & breaking news (parent / suburban signal).
"""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
import requests

from app.config import config

logger = logging.getLogger(__name__)

GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss?geo=US"

BRIEFING_FEEDS = [
    ("Axios AM", "https://api.axios.com/feed/"),
    ("CNBC Make It", "https://www.cnbc.com/id/10001147/device/rss/rss.html"),
    ("Tech layoffs pulse", "https://techcrunch.com/category/startups/feed/"),
]

NEWSAPI_OUTLETS = [
    "associated-press",
    "reuters",
    "usa-today",
    "cnn",
    "nbc-news",
    "the-new-york-times",
    "fox-news",
    "new-york-post",
]


def _item(
    *,
    title: str,
    source: str,
    layer: str = "A",
    url: str = "",
    score: float = 0.0,
    snippet: str = "",
    outlet: str = "",
    raw: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "title": (title or "").strip(),
        "source": source,
        "layer": layer,
        "url": url or "",
        "score": float(score or 0),
        "snippet": (snippet or "").strip()[:400],
        "outlet": outlet or source,
        "fetched_at": time.time(),
        "raw": raw or {},
    }


def _fetch_rss(url: str, *, timeout: int = 12) -> List[Dict[str, Any]]:
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "CrashOutAgent0/1.0"},
        )
        if resp.status_code != 200 or not resp.content:
            return []
        root = ET.fromstring(resp.content)
    except Exception as exc:
        logger.debug("RSS fetch failed %s: %s", url, exc)
        return []

    items: List[Dict[str, Any]] = []
    # RSS 2.0 + Atom
    for node in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = (
            (node.findtext("title") or node.findtext("{http://www.w3.org/2005/Atom}title") or "")
            .strip()
        )
        if not title:
            continue
        link = node.findtext("link") or ""
        if not link:
            link_el = node.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                link = link_el.attrib.get("href") or ""
        desc = (
            node.findtext("description")
            or node.findtext("{http://www.w3.org/2005/Atom}summary")
            or ""
        )
        items.append({"title": title, "link": link, "description": desc})
    return items


def fetch_google_trends_us() -> List[Dict[str, Any]]:
    rows = _fetch_rss(GOOGLE_TRENDS_RSS)
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(rows[:40]):
        title = row.get("title") or ""
        # Google Trends RSS often includes approx traffic in description / ht:approx_traffic
        traffic = 0
        desc = row.get("description") or ""
        for token in desc.replace(",", "").split():
            if token.isdigit():
                traffic = max(traffic, int(token))
        # Prefer spikes; keep lower-volume as soft signals
        score = 90.0 - i + (15.0 if traffic >= 50000 else 0.0)
        out.append(
            _item(
                title=title,
                source="google_trends",
                url=row.get("link") or "",
                score=score,
                snippet=desc[:240],
                outlet="Google Trends US",
                raw={"approx_traffic": traffic},
            )
        )
    return out


def fetch_newsapi_headlines() -> List[Dict[str, Any]]:
    api_key = (getattr(config, "newsapi_api_key", None) or "").strip()
    if not api_key:
        return []
    out: List[Dict[str, Any]] = []
    # Batch by sources groups to stay under URL limits
    chunks = [NEWSAPI_OUTLETS[i : i + 4] for i in range(0, len(NEWSAPI_OUTLETS), 4)]
    for chunk in chunks:
        try:
            resp = requests.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "apiKey": api_key,
                    "sources": ",".join(chunk),
                    "pageSize": 20,
                    "language": "en",
                },
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning("NewsAPI %s: %s", resp.status_code, resp.text[:160])
                continue
            articles = (resp.json() or {}).get("articles") or []
            for i, art in enumerate(articles):
                title = (art.get("title") or "").strip()
                if not title or title.lower() == "[removed]":
                    continue
                src_name = ((art.get("source") or {}).get("name") or chunk[0]).strip()
                out.append(
                    _item(
                        title=title,
                        source="newsapi",
                        url=art.get("url") or "",
                        score=80.0 - i,
                        snippet=(art.get("description") or "")[:400],
                        outlet=src_name,
                        raw={"source_id": (art.get("source") or {}).get("id")},
                    )
                )
        except Exception as exc:
            logger.warning("NewsAPI fetch failed: %s", exc)
        time.sleep(0.2)
    return out


def fetch_gnews_headlines() -> List[Dict[str, Any]]:
    api_key = (getattr(config, "gnews_api_key", None) or "").strip()
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://gnews.io/api/v4/top-headlines",
            params={"token": api_key, "lang": "en", "country": "us", "max": 25},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("GNews %s: %s", resp.status_code, resp.text[:160])
            return []
        articles = (resp.json() or {}).get("articles") or []
    except Exception as exc:
        logger.warning("GNews fetch failed: %s", exc)
        return []
    out: List[Dict[str, Any]] = []
    for i, art in enumerate(articles):
        title = (art.get("title") or "").strip()
        if not title:
            continue
        outlet = ((art.get("source") or {}).get("name") or "GNews").strip()
        out.append(
            _item(
                title=title,
                source="gnews",
                url=art.get("url") or "",
                score=78.0 - i,
                snippet=(art.get("description") or "")[:400],
                outlet=outlet,
            )
        )
    return out


def fetch_briefing_rss() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for label, url in BRIEFING_FEEDS:
        rows = _fetch_rss(url)
        for i, row in enumerate(rows[:12]):
            title = row.get("title") or ""
            if not title:
                continue
            out.append(
                _item(
                    title=title,
                    source="briefing_rss",
                    url=row.get("link") or "",
                    score=70.0 - i,
                    snippet=(row.get("description") or "")[:400],
                    outlet=label,
                )
            )
        time.sleep(0.15)
    return out


def fetch_serpapi_trends_fallback() -> List[Dict[str, Any]]:
    api_key = (getattr(config, "serpapi_api_key", None) or "").strip()
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={"engine": "google_trends_trending_now", "geo": "US", "api_key": api_key},
            timeout=20,
        )
        if resp.status_code != 200:
            return []
        data = resp.json() or {}
        rows = data.get("trending_searches") or data.get("daily_searches") or []
    except Exception as exc:
        logger.warning("SerpApi trends failed: %s", exc)
        return []
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(rows[:30]):
        if isinstance(row, dict):
            title = str(row.get("query") or row.get("title") or "").strip()
        else:
            title = str(row).strip()
        if not title:
            continue
        out.append(
            _item(
                title=title,
                source="serpapi_trends",
                score=85.0 - i,
                outlet="Google Trends (SerpApi)",
                raw={"row": row} if isinstance(row, dict) else {},
            )
        )
    return out


def collect_layer_a() -> List[Dict[str, Any]]:
    """Mainstream / parent-suburban signal layer."""
    bucket: List[Dict[str, Any]] = []
    bucket.extend(fetch_google_trends_us())
    if not any(i.get("source") == "google_trends" for i in bucket):
        bucket.extend(fetch_serpapi_trends_fallback())
    bucket.extend(fetch_newsapi_headlines())
    if not any(i.get("source") in {"newsapi", "gnews"} for i in bucket):
        bucket.extend(fetch_gnews_headlines())
    bucket.extend(fetch_briefing_rss())
    # Soft web-search boost for suburban economic panic themes when wires are thin
    if len(bucket) < 20:
        try:
            from app.trends.sources import _search_once, _trend_item

            for q in (
                "US inflation housing costs news today",
                "corporate return to office layoffs news",
            ):
                for rank, row in enumerate(_search_once(q, max_results=5)):
                    title = (row.get("title") or "").strip()
                    if not title:
                        continue
                    bucket.append(
                        _trend_item(
                            title=title,
                            source="web_search_a",
                            url=row.get("href") or "",
                            score=55.0 - rank,
                            snippet=row.get("body") or "",
                            raw={"query": q, "layer": "A"},
                        )
                    )
                    bucket[-1]["layer"] = "A"
                    bucket[-1]["outlet"] = "Web"
        except Exception as exc:
            logger.debug("Layer A web fallback skipped: %s", exc)
    logger.info("Layer A collected %s items", len(bucket))
    return bucket
