"""
Trend signal collectors: Reddit RSS/OAuth, Google Trends RSS, GDELT, optional NewsAPI.
Prefer public feeds / official APIs — no HTML scraping.
"""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests

from app.config import config

logger = logging.getLogger(__name__)

REDDIT_SUBREDDITS = [
    "mildlyinfuriating",
    "GenZ",
    "antiwork",
    "fuckHOA",
    "Parenting",
    "TikTokCringe",
    "LateStageCapitalism",
    "ABoringDystopia",
]

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
HT_NS = {"ht": "https://trends.google.com/trending/rss"}

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


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


def _session_headers() -> Dict[str, str]:
    return {
        "User-Agent": config.reddit_user_agent or BROWSER_UA,
        "Accept": "application/json, application/atom+xml, application/rss+xml, text/xml, */*",
    }


def fetch_reddit_trends(limit_per_sub: int = 8) -> List[Dict[str, Any]]:
    """Hot posts from curated US-culture subs (OAuth JSON if keyed, else Atom RSS)."""
    token = _reddit_oauth_token()
    if token:
        items = _fetch_reddit_oauth(token, limit_per_sub=limit_per_sub)
        if items:
            return items
    return _fetch_reddit_rss(limit_per_sub=limit_per_sub)


def _reddit_oauth_token() -> Optional[str]:
    client_id = (config.reddit_client_id or "").strip()
    client_secret = (config.reddit_client_secret or "").strip()
    if not client_id or not client_secret:
        return None
    try:
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": config.reddit_user_agent or BROWSER_UA},
            timeout=12,
        )
        if resp.status_code != 200:
            logger.warning("Reddit OAuth failed: %s", resp.status_code)
            return None
        return (resp.json() or {}).get("access_token")
    except Exception as exc:
        logger.warning("Reddit OAuth error: %s", exc)
        return None


def _fetch_reddit_oauth(token: str, *, limit_per_sub: int) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    headers = {
        "User-Agent": config.reddit_user_agent or BROWSER_UA,
        "Authorization": f"Bearer {token}",
    }
    for sub in REDDIT_SUBREDDITS:
        try:
            resp = requests.get(
                f"https://oauth.reddit.com/r/{sub}/hot",
                headers=headers,
                params={"limit": limit_per_sub, "raw_json": 1},
                timeout=12,
            )
            if resp.status_code != 200:
                logger.warning("Reddit OAuth r/%s status %s", sub, resp.status_code)
                continue
            children = (resp.json().get("data") or {}).get("children") or []
            for child in children:
                data = child.get("data") or {}
                title = data.get("title") or ""
                if not title or data.get("stickied"):
                    continue
                permalink = data.get("permalink") or ""
                items.append(
                    _trend_item(
                        title=title,
                        source=f"reddit/r/{sub}",
                        url=f"https://www.reddit.com{permalink}" if permalink else "",
                        score=float(data.get("score") or 0)
                        + float(data.get("num_comments") or 0) * 0.5,
                        snippet=(data.get("selftext") or "")[:280],
                        raw={"subreddit": sub, "id": data.get("id")},
                    )
                )
        except Exception as exc:
            logger.warning("Reddit OAuth fetch failed for r/%s: %s", sub, exc)
        time.sleep(0.35)
    return items


def _fetch_reddit_rss(limit_per_sub: int) -> List[Dict[str, Any]]:
    """Public Atom feeds — one multi-sub request to avoid per-sub 429s."""
    items: List[Dict[str, Any]] = []
    headers = _session_headers()
    headers["User-Agent"] = BROWSER_UA
    # Reddit allows r/a+b+c combined feeds (fewer requests = fewer 429s).
    combos = [
        "+".join(REDDIT_SUBREDDITS[:4]),
        "+".join(REDDIT_SUBREDDITS[4:]),
    ]
    for combo in combos:
        if not combo:
            continue
        url = f"https://www.reddit.com/r/{combo}/hot/.rss"
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 429:
                logger.warning("Reddit RSS rate-limited on multi %s", combo[:40])
                time.sleep(3.0)
                continue
            if resp.status_code != 200 or not resp.content:
                logger.warning("Reddit RSS multi status %s", resp.status_code)
                continue
            root = ET.fromstring(resp.content)
            entries = root.findall("atom:entry", ATOM_NS)
            per_feed_cap = max(limit_per_sub * 2, 16)
            for entry in entries[:per_feed_cap]:
                title_el = entry.find("atom:title", ATOM_NS)
                title = (title_el.text or "").strip() if title_el is not None else ""
                if not title:
                    continue
                low = title.lower()
                if any(
                    s in low
                    for s in (
                        "acceptable discourse",
                        "purpose of this sub",
                        "megathread",
                        "daily discussion",
                        "subreddit rules",
                    )
                ):
                    continue
                link = ""
                for link_el in entry.findall("atom:link", ATOM_NS):
                    if link_el.get("rel") in (None, "alternate"):
                        link = link_el.get("href") or ""
                        if link:
                            break
                # Infer subreddit from link path /r/Name/...
                sub = "multi"
                if "/r/" in link:
                    try:
                        sub = link.split("/r/")[1].split("/")[0]
                    except IndexError:
                        sub = "multi"
                content_el = entry.find("atom:content", ATOM_NS)
                snippet = ""
                if content_el is not None and content_el.text:
                    snippet = _strip_tags(content_el.text)[:280]
                category = entry.find("atom:category", ATOM_NS)
                if category is not None and category.get("label"):
                    sub = category.get("label", sub).replace("r/", "")
                items.append(
                    _trend_item(
                        title=title,
                        source=f"reddit/r/{sub}",
                        url=link,
                        score=80.0,
                        snippet=snippet,
                        raw={"subreddit": sub},
                    )
                )
        except Exception as exc:
            logger.warning("Reddit RSS multi failed: %s", exc)
        time.sleep(1.5)
    return items


def fetch_google_trends() -> List[Dict[str, Any]]:
    """US daily search trends via Google's public RSS (no API key / no pytrends)."""
    items: List[Dict[str, Any]] = []
    try:
        resp = requests.get(
            "https://trends.google.com/trending/rss",
            params={"geo": "US"},
            headers={"User-Agent": BROWSER_UA},
            timeout=20,
        )
        if resp.status_code != 200 or not resp.content:
            logger.warning("Google Trends RSS status %s", resp.status_code)
            return []
        root = ET.fromstring(resp.content)
        for item in root.findall("./channel/item"):
            title_el = item.find("title")
            title = (title_el.text or "").strip() if title_el is not None else ""
            if not title:
                continue
            traffic_el = item.find("ht:approx_traffic", HT_NS)
            traffic_raw = (traffic_el.text or "0") if traffic_el is not None else "0"
            score = _parse_traffic(traffic_raw)
            news_bits = []
            for news in item.findall("ht:news_item", HT_NS):
                nt = news.find("ht:news_item_title", HT_NS)
                if nt is not None and nt.text:
                    news_bits.append(_strip_tags(nt.text))
            items.append(
                _trend_item(
                    title=title,
                    source="google_trends",
                    score=score,
                    snippet="; ".join(news_bits)[:280],
                    raw={"approx_traffic": traffic_raw},
                )
            )
    except Exception as exc:
        logger.warning("Google Trends RSS unavailable: %s", exc)
    return items


def fetch_gdelt_headlines(maxrecords: int = 25) -> List[Dict[str, Any]]:
    """Free GDELT DOC 2.0 API — recent US English society/consumer headlines."""
    query = (
        "(HOA OR suburb OR suburban OR TikTok OR parenting OR grocery OR "
        "inflation OR wellness OR Stanley OR Nextdoor OR 'cost of living' OR "
        "influencer) sourcelang:english sourcecountry:US"
    )
    try:
        resp = requests.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params={
                "query": query,
                "mode": "ArtList",
                "maxrecords": str(maxrecords),
                "format": "json",
                "sort": "DateDesc",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning("GDELT status %s", resp.status_code)
            return []
        articles = (resp.json() or {}).get("articles") or []
        items: List[Dict[str, Any]] = []
        for art in articles:
            title = (art.get("title") or "").strip()
            if not title:
                continue
            items.append(
                _trend_item(
                    title=_normalize_spaced_title(title),
                    source="gdelt",
                    url=art.get("url") or "",
                    score=60.0,
                    snippet=art.get("domain") or "",
                    raw={"seendate": art.get("seendate"), "domain": art.get("domain")},
                )
            )
        return items
    except Exception as exc:
        logger.warning("GDELT fetch failed: %s", exc)
        return []


def fetch_newsapi_headlines(page_size: int = 20) -> List[Dict[str, Any]]:
    """Optional NewsAPI top US headlines (society / lifestyle bias via query)."""
    api_key = (config.news_api_key or "").strip()
    if not api_key:
        return []
    query = (
        "HOA OR suburb OR parenting OR TikTok OR grocery OR inflation "
        "OR wellness OR 'cost of living' OR Stanley"
    )
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": page_size,
                "apiKey": api_key,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("NewsAPI status %s", resp.status_code)
            return []
        articles = (resp.json() or {}).get("articles") or []
        items: List[Dict[str, Any]] = []
        for art in articles:
            title = art.get("title") or ""
            if not title or title == "[Removed]":
                continue
            items.append(
                _trend_item(
                    title=title,
                    source="newsapi",
                    url=art.get("url") or "",
                    score=50.0,
                    snippet=art.get("description") or "",
                    raw={"source_name": (art.get("source") or {}).get("name")},
                )
            )
        return items
    except Exception as exc:
        logger.warning("NewsAPI fetch failed: %s", exc)
        return []


def collect_all_trends() -> List[Dict[str, Any]]:
    """Gather + dedupe trend signals from all configured sources."""
    bucket: List[Dict[str, Any]] = []
    bucket.extend(fetch_reddit_trends())
    bucket.extend(fetch_google_trends())
    bucket.extend(fetch_gdelt_headlines())
    bucket.extend(fetch_newsapi_headlines())

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


def _parse_traffic(raw: str) -> float:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    try:
        return float(digits) if digits else 10.0
    except ValueError:
        return 10.0


def _strip_tags(html: str) -> str:
    try:
        # Wrap fragment so parser is happy.
        root = ET.fromstring(f"<div>{html}</div>")
        return "".join(root.itertext())
    except ET.ParseError:
        import re

        return re.sub(r"<[^>]+>", " ", html or "")


def _normalize_spaced_title(title: str) -> str:
    """GDELT often returns 'U . S . jobless' / 'No tip , no way' — tidy punctuation."""
    import re

    t = re.sub(r"\s+", " ", title or "").strip()
    # Collapse "U . S ." style initials
    t = re.sub(r"\b([A-Za-z])\s\.\s(?=[A-Za-z]\s\.)", r"\1.", t)
    t = re.sub(r"\b([A-Za-z])\s\.", r"\1.", t)
    t = re.sub(r"\s+([,.:;!?])", r"\1", t)
    t = re.sub(r"\s+'", "'", t)
    return t.strip()

