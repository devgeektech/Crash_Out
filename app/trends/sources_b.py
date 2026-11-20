"""
Layer B — Youth culture, memes & social discourse (Gen Z / Alpha signal).
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

REDDIT_TREND_SUBS = [
    "OutOfTheLoop",
]
REDDIT_YOUTH_SUBS = [
    "GenZ",
    "popculturechat",
]
REDDIT_SUBURBAN_SUBS = [
    "antiwork",
    "mildlyinfuriating",
    "Suburbanhell",
    "HOA",
]

YOUTH_CULTURE_FEEDS = [
    ("TikTok Trends", "https://news.google.com/rss/search?q=tiktok+trend+OR+viral+OR+challenge+when:24h&hl=en-US&gl=US&ceid=US:en"),
    ("Gen Z Culture & Slang", "https://news.google.com/rss/search?q=gen+z+trend+OR+slang+OR+culture+when:24h&hl=en-US&gl=US&ceid=US:en"),
    ("Suburban & Neighbor Feuds", "https://news.google.com/rss/search?q=HOA+dispute+OR+suburban+drama+OR+neighbor+dispute+when:24h&hl=en-US&gl=US&ceid=US:en"),
]

KYM_RSS = "https://knowyourmeme.com/newsfeed.rss"

YOUTUBE_CATEGORIES = [20, 24, 25]  # Gaming, Entertainment, News


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
    layer: str = "B",
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
        logger.debug("Layer B RSS fetch failed %s: %s", url, exc)
        return []

    items: List[Dict[str, Any]] = []
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


def _fetch_reddit_syndication(subs: List[str]) -> List[Dict[str, Any]]:
    """Fetch live Reddit subreddit posts via Google News direct RSS syndication (last 24h, top 5)."""
    out: List[Dict[str, Any]] = []
    for sub in subs:
        if sub == "mildlyinfuriating":
            url = "https://news.google.com/rss/search?q=site:reddit.com+%22mildlyinfuriating%22+when:24h&hl=en-US&gl=US&ceid=US:en"
        else:
            url = f"https://news.google.com/rss/search?q=site:reddit.com/r/{sub}+when:24h&hl=en-US&gl=US&ceid=US:en"
        
        rows = _fetch_rss(url)
        for i, row in enumerate(rows[:5]):
            raw_title = row.get("title") or ""
            # Strip trailing " - Reddit" from syndicated headlines
            clean_title = re.sub(r"\s*-\s*Reddit$", "", raw_title, flags=re.IGNORECASE).strip()
            if not clean_title:
                continue
            
            base_score = 80.0 - (i * 1.5)
            age = row.get("age_hours")
            if age is not None:
                if age <= 6.0:
                    base_score += 12.0
                elif age <= 24.0:
                    base_score += 6.0

            out.append(
                _item(
                    title=clean_title,
                    source=f"reddit/{sub}",
                    url=row.get("link") or "",
                    score=round(base_score, 1),
                    snippet=row.get("description") or "",
                    outlet=f"r/{sub}",
                    raw={"sub": sub, "age_hours": age, "pub_date": row.get("pub_date")},
                )
            )
        time.sleep(0.05)
    return out


def _fetch_reddit_praw(subs: List[str]) -> List[Dict[str, Any]]:
    """Authenticated Reddit API fetch via PRAW (when credentials exist)."""
    import praw  # type: ignore

    reddit = praw.Reddit(
        client_id=config.reddit_client_id,
        client_secret=config.reddit_client_secret,
        user_agent=getattr(config, "reddit_user_agent", None) or "CrashOutAgent0/1.0",
    )
    out: List[Dict[str, Any]] = []
    for sub in subs:
        try:
            subreddit = reddit.subreddit(sub)
            for post in list(subreddit.hot(limit=12)) + list(subreddit.rising(limit=8)):
                title = (getattr(post, "title", None) or "").strip()
                if not title or getattr(post, "stickied", False):
                    continue
                ups = float(getattr(post, "score", 0) or 0)
                comments = float(getattr(post, "num_comments", 0) or 0)
                out.append(
                    _item(
                        title=title,
                        source=f"reddit/{sub}",
                        url=f"https://www.reddit.com{getattr(post, 'permalink', '')}",
                        score=min(500.0, ups + comments * 2.0),
                        snippet=(getattr(post, "selftext", None) or "")[:240],
                        outlet=f"r/{sub}",
                        raw={"ups": ups, "comments": comments},
                    )
                )
        except Exception as exc:
            logger.debug("PRAW r/%s failed: %s", sub, exc)
        time.sleep(0.1)
    return out


def fetch_reddit_layer() -> List[Dict[str, Any]]:
    subs = REDDIT_TREND_SUBS + REDDIT_YOUTH_SUBS + REDDIT_SUBURBAN_SUBS
    client_id = (getattr(config, "reddit_client_id", None) or "").strip()
    client_secret = (getattr(config, "reddit_client_secret", None) or "").strip()
    if client_id and client_secret:
        try:
            results = _fetch_reddit_praw(subs)
            if results:
                return results
        except Exception as exc:
            logger.warning("PRAW failed, falling back to syndication: %s", exc)

    return _fetch_reddit_syndication(subs)


def fetch_tiktok_and_youth_trends() -> List[Dict[str, Any]]:
    """Direct RSS feeds tracking viral TikTok challenges, Gen Z slang, and suburban friction (top 4, last 24h)."""
    out: List[Dict[str, Any]] = []
    for label, url in YOUTH_CULTURE_FEEDS:
        rows = _fetch_rss(url)
        for i, row in enumerate(rows[:4]):
            title = row.get("title") or ""
            if not title:
                continue
            base_score = 82.0 - i
            age = row.get("age_hours")
            if age is not None:
                if age <= 6.0:
                    base_score += 10.0
                elif age <= 24.0:
                    base_score += 5.0
            out.append(
                _item(
                    title=title,
                    source="youth_social",
                    url=row.get("link") or "",
                    score=round(base_score, 1),
                    snippet=row.get("description") or "",
                    outlet=label,
                    raw={"age_hours": age, "pub_date": row.get("pub_date")},
                )
            )
        time.sleep(0.05)
    return out


def fetch_know_your_meme() -> List[Dict[str, Any]]:
    rows = _fetch_rss(KYM_RSS)
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(rows[:5]):
        title = (row.get("title") or "").strip()
        if not title:
            continue
        base_score = 78.0 - i
        age = row.get("age_hours")
        if age is not None:
            if age <= 12.0:
                base_score += 8.0
            elif age <= 24.0:
                base_score += 4.0
        out.append(
            _item(
                title=title,
                source="knowyourmeme",
                url=row.get("link") or "",
                score=round(base_score, 1),
                snippet=row.get("description") or "",
                outlet="Know Your Meme",
                raw={"age_hours": age, "pub_date": row.get("pub_date")},
            )
        )
    return out


def fetch_youtube_trending() -> List[Dict[str, Any]]:
    api_key = (getattr(config, "youtube_api_key", None) or "").strip()
    if not api_key:
        return []
    out: List[Dict[str, Any]] = []
    for cat in YOUTUBE_CATEGORIES:
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,statistics",
                    "chart": "mostPopular",
                    "regionCode": "US",
                    "videoCategoryId": str(cat),
                    "maxResults": 10,
                    "key": api_key,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                logger.debug("YouTube cat %s status %s", cat, resp.status_code)
                continue
            for i, item in enumerate((resp.json() or {}).get("items") or []):
                snip = item.get("snippet") or {}
                title = (snip.get("title") or "").strip()
                if not title:
                    continue
                stats = item.get("statistics") or {}
                views = float(stats.get("viewCount") or 0)
                out.append(
                    _item(
                        title=title,
                        source="youtube_trending",
                        url=f"https://www.youtube.com/watch?v={item.get('id')}",
                        score=min(200.0, views / 50000.0) + (10 - i),
                        snippet=(snip.get("description") or "")[:240],
                        outlet=f"YouTube US cat {cat}",
                        raw={"category": cat, "views": views},
                    )
                )
        except Exception as exc:
            logger.warning("YouTube trending failed cat=%s: %s", cat, exc)
        time.sleep(0.2)
    return out


def collect_layer_b() -> List[Dict[str, Any]]:
    """Gather Layer B youth/social culture, meme trends, and suburban grievances."""
    bucket: List[Dict[str, Any]] = []
    bucket.extend(fetch_reddit_layer())
    bucket.extend(fetch_tiktok_and_youth_trends())
    bucket.extend(fetch_know_your_meme())
    bucket.extend(fetch_youtube_trending())

    # Fallback web search if feed volume is thin
    if len(bucket) < 15:
        try:
            from app.trends.sources import _search_once, _trend_item

            for q in (
                "viral Gen Z TikTok trends this week",
                "trending meme slang United States",
            ):
                for rank, row in enumerate(_search_once(q, max_results=6)):
                    title = (row.get("title") or "").strip()
                    if not title:
                        continue
                    item = _trend_item(
                        title=title,
                        source="web_search_b",
                        url=row.get("href") or "",
                        score=50.0 - rank,
                        snippet=row.get("body") or "",
                        raw={"query": q, "layer": "B"},
                    )
                    item["layer"] = "B"
                    item["outlet"] = "Web"
                    bucket.append(item)
        except Exception as exc:
            logger.debug("Layer B web fallback skipped: %s", exc)

    logger.info("Layer B collected %s items", len(bucket))
    return bucket
