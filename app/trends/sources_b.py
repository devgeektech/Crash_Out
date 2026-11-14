"""
Layer B — Youth culture, memes & social discourse (Gen Z / Alpha signal).
"""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests

from app.config import config

logger = logging.getLogger(__name__)

REDDIT_TREND_SUBS = [
    "OutOfTheLoop",
    "NoStupidQuestions",
    "ExplainTheJoke",
]
REDDIT_YOUTH_SUBS = [
    "teenagers",
    "GenZ",
    "TikTokCringe",
    "popculturechat",
]
REDDIT_SUBURBAN_SUBS = [
    "antiwork",
    "mildlyinfuriating",
    "Suburbanhell",
    "HOA",
]

KYM_RSS = "https://knowyourmeme.com/newsfeed.rss"

YOUTUBE_CATEGORIES = [20, 24, 25]  # Gaming, Entertainment, News


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


def _reddit_listing(sub: str, sort: str = "hot", limit: int = 15) -> List[Dict[str, Any]]:
    url = f"https://www.reddit.com/r/{sub}/{sort}.json"
    try:
        resp = requests.get(
            url,
            params={"limit": limit, "raw_json": 1},
            timeout=12,
            headers={"User-Agent": "CrashOutAgent0/1.0 (trend ingest)"},
        )
        if resp.status_code != 200:
            logger.debug("Reddit %s/%s status %s", sub, sort, resp.status_code)
            return []
        children = ((resp.json() or {}).get("data") or {}).get("children") or []
    except Exception as exc:
        logger.debug("Reddit fetch r/%s failed: %s", sub, exc)
        return []
    out: List[Dict[str, Any]] = []
    for child in children:
        data = (child or {}).get("data") or {}
        title = (data.get("title") or "").strip()
        if not title or data.get("stickied"):
            continue
        ups = float(data.get("ups") or data.get("score") or 0)
        comments = float(data.get("num_comments") or 0)
        # Velocity proxy: ups + comments weight
        velocity = ups + comments * 2.0
        out.append(
            _item(
                title=title,
                source=f"reddit/{sub}",
                url=f"https://www.reddit.com{data.get('permalink') or ''}",
                score=min(500.0, velocity),
                snippet=(data.get("selftext") or "")[:240],
                outlet=f"r/{sub}",
                raw={
                    "ups": ups,
                    "comments": comments,
                    "upvote_ratio": data.get("upvote_ratio"),
                    "sort": sort,
                },
            )
        )
    return out


def fetch_reddit_layer() -> List[Dict[str, Any]]:
    subs = REDDIT_TREND_SUBS + REDDIT_YOUTH_SUBS + REDDIT_SUBURBAN_SUBS
    # Optional PRAW path when credentials exist
    client_id = (getattr(config, "reddit_client_id", None) or "").strip()
    client_secret = (getattr(config, "reddit_client_secret", None) or "").strip()
    if client_id and client_secret:
        try:
            return _fetch_reddit_praw(subs)
        except Exception as exc:
            logger.warning("PRAW failed, falling back to public JSON: %s", exc)

    bucket: List[Dict[str, Any]] = []
    for sub in subs:
        bucket.extend(_reddit_listing(sub, sort="hot", limit=12))
        time.sleep(0.35)
        bucket.extend(_reddit_listing(sub, sort="rising", limit=8))
        time.sleep(0.35)
    return bucket


def _fetch_reddit_praw(subs: List[str]) -> List[Dict[str, Any]]:
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
        time.sleep(0.2)
    return out


def fetch_know_your_meme() -> List[Dict[str, Any]]:
    try:
        resp = requests.get(
            KYM_RSS,
            timeout=12,
            headers={"User-Agent": "CrashOutAgent0/1.0"},
        )
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
    except Exception as exc:
        logger.debug("KYM RSS failed: %s", exc)
        return []
    out: List[Dict[str, Any]] = []
    for i, node in enumerate(root.findall(".//item")[:25]):
        title = (node.findtext("title") or "").strip()
        if not title:
            continue
        out.append(
            _item(
                title=title,
                source="knowyourmeme",
                url=node.findtext("link") or "",
                score=75.0 - i,
                snippet=(node.findtext("description") or "")[:240],
                outlet="Know Your Meme",
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
    bucket: List[Dict[str, Any]] = []
    bucket.extend(fetch_reddit_layer())
    bucket.extend(fetch_know_your_meme())
    bucket.extend(fetch_youtube_trending())
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
