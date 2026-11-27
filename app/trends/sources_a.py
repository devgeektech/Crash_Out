"""
Layer A — Mainstream US consensus & breaking news (parent / suburban signal).
"""
from __future__ import annotations

import email.utils
import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

from app.config import config

logger = logging.getLogger(__name__)

GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss?geo=US"

# Google Trends commercial SEO spam keywords to discard
GOOGLE_TRENDS_SPAM = {
    "lawyer",
    "attorney",
    "law firm",
    "settlement",
    "lawsuit",
    "mesothelioma",
    "insurance quote",
    "car accident",
    "truck accident",
    "slip and fall",
    "crypto exchange",
    "personal loan",
    "mortgage rate",
}

# Free Direct RSS Feeds (high-signal mainstream US consensus & suburban signal, strictly last 24h)
MAINSTREAM_RSS_FEEDS = [
    ("Associated Press", "https://news.google.com/rss/search?q=site:apnews.com+when:24h&hl=en-US&gl=US&ceid=US:en"),
    ("Reuters", "https://news.google.com/rss/search?q=site:reuters.com+when:24h&hl=en-US&gl=US&ceid=US:en"),
    ("CNN", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("Fox News", "https://moxie.foxnews.com/google-publisher/latest.xml"),
    ("New York Post", "https://nypost.com/feed/"),
    ("CBS News", "https://www.cbsnews.com/latest/rss/main"),
    ("ABC News", "https://abcnews.go.com/abcnews/topstories"),
    ("Google News US", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"),
    ("Google News Business", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
]

BRIEFING_FEEDS = [
    ("Axios AM", "https://api.axios.com/feed/"),
    ("CNBC Make It", "https://www.cnbc.com/id/10001147/device/rss/rss.html"),
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


def _clean_html_text(raw: str) -> str:
    """Unescape HTML entities, strip tags, and collapse whitespace."""
    if not raw:
        return ""
    text = html.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split()).strip()


def _parse_age_hours(date_str: str) -> Optional[float]:
    """Parse RFC-822 or ISO pubDate string to age in hours."""
    if not date_str:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff_sec = (now - dt).total_seconds()
        return max(0.0, diff_sec / 3600.0)
    except Exception:
        return None


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
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            },
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
        raw_title = (
            (node.findtext("title") or node.findtext("{http://www.w3.org/2005/Atom}title") or "")
            .strip()
        )
        title = _clean_html_text(raw_title)
        if not title:
            continue
        link = node.findtext("link") or ""
        if not link:
            link_el = node.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                link = link_el.attrib.get("href") or ""
        raw_desc = (
            node.findtext("description")
            or node.findtext("{http://www.w3.org/2005/Atom}summary")
            or node.findtext("{http://www.w3.org/2005/Atom}content")
            or ""
        )
        desc = _clean_html_text(raw_desc)
        pub_date = (
            node.findtext("pubDate")
            or node.findtext("{http://www.w3.org/2005/Atom}published")
            or node.findtext("{http://www.w3.org/2005/Atom}updated")
            or ""
        )
        age_hours = _parse_age_hours(pub_date)
        # Strict 24-hour window filter: only topics from the last 24 hours
        if age_hours is not None and age_hours > 24.0:
            continue
        items.append({
            "title": title,
            "link": link,
            "description": desc,
            "pub_date": pub_date,
            "age_hours": age_hours,
        })
    return items


def fetch_google_trends_us() -> List[Dict[str, Any]]:
    rows = _fetch_rss(GOOGLE_TRENDS_RSS)
    out: List[Dict[str, Any]] = []
    rank = 0
    for row in rows[:5]:
        title = row.get("title") or ""
        lower_t = title.lower()
        if any(spam in lower_t for spam in GOOGLE_TRENDS_SPAM):
            continue

        # Google Trends RSS often includes approx traffic in description / ht:approx_traffic
        traffic = 0
        desc = row.get("description") or ""
        for token in desc.replace(",", "").split():
            if token.isdigit():
                traffic = max(traffic, int(token))
        # Prefer spikes; keep lower-volume as soft signals
        score = 92.0 - rank + (15.0 if traffic >= 50000 else 0.0)
        out.append(
            _item(
                title=title,
                source="google_trends",
                url=row.get("link") or "",
                score=score,
                snippet=desc[:240],
                outlet="Google Trends US",
                raw={"approx_traffic": traffic, "age_hours": row.get("age_hours")},
            )
        )
        rank += 1
    return out


def fetch_mainstream_rss() -> List[Dict[str, Any]]:
    """Fetch free direct RSS feeds from AP, Reuters, CNN, Fox News, NY Post, CBS, ABC, and Google News (top 5, last 24h)."""
    out: List[Dict[str, Any]] = []
    for label, url in MAINSTREAM_RSS_FEEDS:
        rows = _fetch_rss(url)
        for i, row in enumerate(rows[:5]):
            title = row.get("title") or ""
            if not title:
                continue
            base_score = 85.0 - i
            age = row.get("age_hours")
            if age is not None:
                if age <= 6.0:
                    base_score += 10.0
                elif age <= 24.0:
                    base_score += 5.0
            out.append(
                _item(
                    title=title,
                    source="mainstream_rss",
                    url=row.get("link") or "",
                    score=round(base_score, 1),
                    snippet=(row.get("description") or "")[:400],
                    outlet=label,
                    raw={"age_hours": age, "pub_date": row.get("pub_date")},
                )
            )
        time.sleep(0.05)
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
        for i, row in enumerate(rows[:4]):
            title = row.get("title") or ""
            if not title:
                continue
            base_score = 75.0 - i
            age = row.get("age_hours")
            if age is not None:
                if age <= 6.0:
                    base_score += 10.0
                elif age <= 24.0:
                    base_score += 5.0
            out.append(
                _item(
                    title=title,
                    source="briefing_rss",
                    url=row.get("link") or "",
                    score=round(base_score, 1),
                    snippet=(row.get("description") or "")[:400],
                    outlet=label,
                    raw={"age_hours": age, "pub_date": row.get("pub_date")},
                )
            )
        time.sleep(0.05)
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


def _bridge_query_from_title(title: str) -> str:
    """Compress a YouTube title into a Google News search query."""
    cleaned = re.sub(r"[^\w\s\-']", " ", title or "", flags=re.UNICODE)
    tokens = [t for t in cleaned.split() if len(t) > 2][:8]
    return " ".join(tokens).strip()


def fetch_mainstream_bridges_from_youtube(
    youtube_titles: List[str],
    *,
    per_title: int = 4,
) -> List[Dict[str, Any]]:
    """
    For viral YouTube News/Entertainment titles, pull matching mainstream
    Google News hits (Layer A) so social heat can cross-check with wires.
    """
    out: List[Dict[str, Any]] = []
    seen_titles: set[str] = set()
    for title in youtube_titles:
        query = _bridge_query_from_title(title)
        if len(query) < 6:
            continue
        from urllib.parse import quote

        url = (
            "https://news.google.com/rss/search?"
            f"q={quote(query)}+when:24h&hl=en-US&gl=US&ceid=US:en"
        )
        rows = _fetch_rss(url)
        for i, row in enumerate(rows[:per_title]):
            hit_title = (row.get("title") or "").strip()
            key = hit_title.lower()
            if not hit_title or key in seen_titles:
                continue
            # Skip near-identical YouTube mirror rows.
            if key == title.strip().lower():
                continue
            seen_titles.add(key)
            base_score = 88.0 - i
            age = row.get("age_hours")
            if age is not None:
                if age <= 6.0:
                    base_score += 10.0
                elif age <= 24.0:
                    base_score += 5.0
            out.append(
                _item(
                    title=hit_title,
                    source="youtube_mainstream_bridge",
                    url=row.get("link") or "",
                    score=round(base_score, 1),
                    snippet=(row.get("description") or "")[:400],
                    outlet="Google News (YT bridge)",
                    raw={
                        "seed_youtube_title": title,
                        "query": query,
                        "age_hours": age,
                        "pub_date": row.get("pub_date"),
                    },
                )
            )
        time.sleep(0.05)
    logger.info(
        "YouTube→mainstream bridges: seeds=%d hits=%d",
        len(youtube_titles),
        len(out),
    )
    return out


def collect_layer_a(
    *,
    youtube_bridge_titles: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Mainstream / parent-suburban signal layer using free direct sources."""
    bucket: List[Dict[str, Any]] = []
    # 0. Bridge: mainstream coverage of viral YouTube News/Entertainment titles.
    if youtube_bridge_titles:
        try:
            bucket.extend(fetch_mainstream_bridges_from_youtube(youtube_bridge_titles))
        except Exception as exc:
            logger.debug("YouTube mainstream bridge skipped: %s", exc)

    # 1. Free Google Trends US RSS
    bucket.extend(fetch_google_trends_us())
    
    # 2. Free direct mainstream RSS feeds (AP, Reuters, CNN, Fox News, NY Post, Morning Brew, The Verge, Google News)
    bucket.extend(fetch_mainstream_rss())
    bucket.extend(fetch_briefing_rss())

    # 3. Optional fallbacks if API keys are provided in .env (no error if unconfigured)
    if not any(i.get("source") == "google_trends" for i in bucket):
        bucket.extend(fetch_serpapi_trends_fallback())
    bucket.extend(fetch_newsapi_headlines())
    if not any(i.get("source") in {"newsapi", "gnews"} for i in bucket):
        bucket.extend(fetch_gnews_headlines())
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
