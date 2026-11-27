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
# Seed pool for dynamic rotation (extra youth / culture subs beyond the core set).
REDDIT_DYNAMIC_POOL = [
    "tiktokcringe",
    "NoStupidQuestions",
    "explained",
    "Fauxmoi",
    "television",
    "hiphopheads",
    "LivestreamFail",
    "nonsense",
    "youthrights",
    "genzlife",
]
MAX_DYNAMIC_SUBS = 5

YOUTH_CULTURE_FEEDS = [
    ("TikTok Trends", "https://news.google.com/rss/search?q=tiktok+trend+OR+viral+OR+challenge+when:24h&hl=en-US&gl=US&ceid=US:en"),
    ("Gen Z Culture & Slang", "https://news.google.com/rss/search?q=gen+z+trend+OR+slang+OR+culture+when:24h&hl=en-US&gl=US&ceid=US:en"),
    ("Suburban & Neighbor Feuds", "https://news.google.com/rss/search?q=HOA+dispute+OR+suburban+drama+OR+neighbor+dispute+when:24h&hl=en-US&gl=US&ceid=US:en"),
]

KYM_RSS = "https://knowyourmeme.com/newsfeed.rss"

# Prioritize News + Entertainment for mainstream crossover; Gaming last / thinner.
# YouTube category IDs: 25=News, 24=Entertainment, 20=Gaming
YOUTUBE_CATEGORY_PLAN = (
    {"id": 25, "label": "YouTube News", "max_results": 15, "score_boost": 28.0},
    {"id": 24, "label": "YouTube Entertainment", "max_results": 12, "score_boost": 18.0},
    {"id": 20, "label": "YouTube Gaming", "max_results": 5, "score_boost": 0.0},
)
YOUTUBE_CATEGORIES = [row["id"] for row in YOUTUBE_CATEGORY_PLAN]  # compat

_SLANG_STOP = {
    "the", "and", "for", "with", "this", "that", "from", "what", "when", "viral",
    "trend", "trends", "tiktok", "news", "gen", "slang", "culture", "challenge",
    "week", "today", "know", "your", "meme", "knowyourmeme", "http", "https",
}


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


def _core_reddit_subs() -> List[str]:
    return list(dict.fromkeys(REDDIT_TREND_SUBS + REDDIT_YOUTH_SUBS + REDDIT_SUBURBAN_SUBS))


def _dynamic_reddit_subs_praw() -> List[str]:
    """Pull rising/popular sub names via PRAW when credentials exist."""
    client_id = (getattr(config, "reddit_client_id", None) or "").strip()
    client_secret = (getattr(config, "reddit_client_secret", None) or "").strip()
    if not client_id or not client_secret:
        return []
    try:
        import praw  # type: ignore

        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=getattr(config, "reddit_user_agent", None) or "CrashOutAgent0/1.0",
        )
        found: List[str] = []
        core = {s.lower() for s in _core_reddit_subs()}
        for post in list(reddit.subreddit("popular").hot(limit=25)):
            name = str(getattr(getattr(post, "subreddit", None), "display_name", "") or "").strip()
            if not name or name.lower() in core or name.lower().startswith("u_"):
                continue
            if name not in found:
                found.append(name)
            if len(found) >= MAX_DYNAMIC_SUBS:
                break
        return found[:MAX_DYNAMIC_SUBS]
    except Exception as exc:
        logger.debug("Dynamic PRAW subs skipped: %s", exc)
        return []


def _dynamic_reddit_subs_rotating() -> List[str]:
    """Day-rotated slice of the youth/culture pool when PRAW is unavailable."""
    core = {s.lower() for s in _core_reddit_subs()}
    pool = [s for s in REDDIT_DYNAMIC_POOL if s.lower() not in core]
    if not pool:
        return []
    day_seed = int(time.time() // 86400)
    start = day_seed % max(1, len(pool))
    rotated = pool[start:] + pool[:start]
    return rotated[:MAX_DYNAMIC_SUBS]


def resolve_reddit_subs() -> List[str]:
    """Core youth/trend subs + up to MAX_DYNAMIC_SUBS extras (PRAW or day-rotated pool)."""
    core = _core_reddit_subs()
    extras = _dynamic_reddit_subs_praw() or _dynamic_reddit_subs_rotating()
    merged = list(dict.fromkeys(core + extras))
    logger.info(
        "Reddit subs: core=%d dynamic=%d total=%d (%s)",
        len(core),
        len(extras),
        len(merged),
        ",".join(extras) if extras else "none",
    )
    return merged


def _extract_slang_phrases(items: List[Dict[str, Any]], *, limit: int = 4) -> List[str]:
    """Pull short meme/slang phrases from youth/KYM titles for follow-up searches."""
    scored: Dict[str, float] = {}
    for it in items:
        title = str(it.get("title") or "")
        outlet = str(it.get("outlet") or it.get("source") or "").lower()
        boost = 1.5 if ("slang" in outlet or "meme" in outlet or "tiktok" in outlet) else 1.0
        # Quoted phrases or multi-word Proper/lowercase slang chunks.
        for m in re.finditer(r'"([^"]{3,40})"', title):
            phrase = m.group(1).strip().lower()
            if phrase:
                scored[phrase] = scored.get(phrase, 0.0) + 3.0 * boost
        tokens = [
            t
            for t in re.findall(r"[a-z0-9']{3,}", title.lower())
            if t not in _SLANG_STOP and not t.isdigit()
        ]
        for i in range(len(tokens)):
            unigram = tokens[i]
            scored[unigram] = scored.get(unigram, 0.0) + 1.0 * boost
            if i + 1 < len(tokens):
                bigram = f"{tokens[i]} {tokens[i + 1]}"
                scored[bigram] = scored.get(bigram, 0.0) + 2.0 * boost
    ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
    phrases: List[str] = []
    for phrase, _ in ranked:
        if len(phrase) < 3 or phrase in phrases:
            continue
        # Prefer multi-word or distinctive single tokens.
        if " " in phrase or len(phrase) >= 5:
            phrases.append(phrase)
        if len(phrases) >= limit:
            break
    return phrases


def fetch_dynamic_slang_followups(seed_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """1–2 Google News RSS queries from today's slang/meme phrases."""
    phrases = _extract_slang_phrases(seed_items, limit=4)
    if not phrases:
        return []
    out: List[Dict[str, Any]] = []
    for phrase in phrases[:2]:
        from urllib.parse import quote

        q = quote(f'"{phrase}" viral OR trend when:24h')
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        rows = _fetch_rss(url)
        for i, row in enumerate(rows[:4]):
            title = (row.get("title") or "").strip()
            if not title:
                continue
            base_score = 84.0 - i
            age = row.get("age_hours")
            if age is not None:
                if age <= 6.0:
                    base_score += 10.0
                elif age <= 24.0:
                    base_score += 5.0
            out.append(
                _item(
                    title=title,
                    source="youth_slang_dynamic",
                    url=row.get("link") or "",
                    score=round(base_score, 1),
                    snippet=row.get("description") or "",
                    outlet=f"Gen Z slang · {phrase}",
                    raw={"phrase": phrase, "age_hours": age, "pub_date": row.get("pub_date")},
                )
            )
        time.sleep(0.05)
    logger.info("Dynamic slang follow-ups: phrases=%s hits=%d", phrases[:2], len(out))
    return out


def fetch_reddit_layer() -> List[Dict[str, Any]]:
    subs = resolve_reddit_subs()
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
    """
    US mostPopular by category. News + Entertainment first (mainstream-matchable);
    Gaming last with a smaller pull so it does not crowd the board.
    """
    api_key = (getattr(config, "youtube_api_key", None) or "").strip()
    if not api_key:
        return []
    out: List[Dict[str, Any]] = []
    for plan in YOUTUBE_CATEGORY_PLAN:
        cat = int(plan["id"])
        label = str(plan["label"])
        max_results = int(plan.get("max_results") or 10)
        score_boost = float(plan.get("score_boost") or 0.0)
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,statistics",
                    "chart": "mostPopular",
                    "regionCode": "US",
                    "videoCategoryId": str(cat),
                    "maxResults": max_results,
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
                # News/Entertainment get an explicit boost so they outrank gaming noise.
                score = min(200.0, views / 50000.0) + (max_results - i) + score_boost
                out.append(
                    _item(
                        title=title,
                        source="youtube_trending",
                        url=f"https://www.youtube.com/watch?v={item.get('id')}",
                        score=round(score, 1),
                        snippet=(snip.get("description") or "")[:240],
                        outlet=label,
                        raw={
                            "category": cat,
                            "category_label": label,
                            "views": views,
                            "priority": "news_entertainment" if cat in (24, 25) else "gaming",
                        },
                    )
                )
        except Exception as exc:
            logger.warning("YouTube trending failed cat=%s: %s", cat, exc)
        time.sleep(0.2)
    logger.info(
        "YouTube trending: %d items (News/Entertainment prioritized)",
        len(out),
    )
    return out


def youtube_news_entertainment_titles(
    items: List[Dict[str, Any]],
    *,
    limit: int = 8,
) -> List[str]:
    """Top News/Entertainment YouTube titles for mainstream bridge searches."""
    rows = [
        it
        for it in items
        if str(it.get("source") or "") == "youtube_trending"
        and int((it.get("raw") or {}).get("category") or 0) in (24, 25)
    ]
    rows.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    titles: List[str] = []
    seen: set[str] = set()
    for it in rows:
        title = str(it.get("title") or "").strip()
        key = title.lower()
        if not title or key in seen:
            continue
        seen.add(key)
        titles.append(title)
        if len(titles) >= limit:
            break
    return titles


def collect_layer_b() -> List[Dict[str, Any]]:
    """
    Gather Layer B youth/social culture first:
    YouTube (News → Entertainment → Gaming) → Reddit → youth/slang RSS → KYM → slang follow-ups.
    """
    bucket: List[Dict[str, Any]] = []
    # YouTube first — News + Entertainment prioritized for mainstream crossover.
    bucket.extend(fetch_youtube_trending())
    bucket.extend(fetch_reddit_layer())
    youth = fetch_tiktok_and_youth_trends()
    bucket.extend(youth)
    kym = fetch_know_your_meme()
    bucket.extend(kym)
    # Dynamic Gen Z slang queries seeded from today's youth/KYM titles.
    try:
        bucket.extend(fetch_dynamic_slang_followups(youth + kym))
    except Exception as exc:
        logger.debug("Dynamic slang follow-ups skipped: %s", exc)

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
