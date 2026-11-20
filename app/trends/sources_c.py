"""
Layer C — Character-specific niche feeds (satirical fuel for Gary / Linda / kids).
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

logger = logging.getLogger(__name__)

GARY_FEEDS = [
    ("TechCrunch", "https://news.google.com/rss/search?q=site:techcrunch.com+when:24h&hl=en-US&gl=US&ceid=US:en"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
]
GARY_SUBS = ["Layoffs", "cscareerquestions"]

LINDA_FEEDS = [
    ("MindBodyGreen", "https://www.mindbodygreen.com/rss.xml"),
    ("Suburban Wellness Drama", "https://news.google.com/rss/search?q=wellness+trend+OR+stanley+cup+OR+botox+when:24h&hl=en-US&gl=US&ceid=US:en"),
]
LINDA_SUBS = ["parenting", "SkincareAddiction"]

KIDS_FEEDS = [
    ("Dexerto", "https://www.dexerto.com/feed/"),
    ("Creator & Streamer Drama", "https://news.google.com/rss/search?q=streamer+drama+OR+influencer+controversy+when:24h&hl=en-US&gl=US&ceid=US:en"),
]
KIDS_SUBS = ["LivestreamFail"]


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
    character: str,
    layer: str = "C",
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
        "character": character,
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
        logger.debug("Layer C RSS failed %s: %s", url, exc)
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


def _fetch_character_reddit_syndication(sub: str, *, character: str, limit: int = 4) -> List[Dict[str, Any]]:
    """Fetch niche subreddit posts for characters via Google News syndication (last 24h, top 4)."""
    url = f"https://news.google.com/rss/search?q=site:reddit.com/r/{sub}+when:24h&hl=en-US&gl=US&ceid=US:en"
    rows = _fetch_rss(url)
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(rows[:limit]):
        raw_title = row.get("title") or ""
        clean_title = re.sub(r"\s*-\s*Reddit$", "", raw_title, flags=re.IGNORECASE).strip()
        if not clean_title:
            continue

        base_score = 75.0 - (i * 1.5)
        age = row.get("age_hours")
        if age is not None:
            if age <= 6.0:
                base_score += 10.0
            elif age <= 24.0:
                base_score += 5.0

        out.append(
            _item(
                title=clean_title,
                source=f"reddit/{sub}",
                character=character,
                url=row.get("link") or "",
                score=round(base_score, 1),
                snippet=row.get("description") or "",
                outlet=f"r/{sub}",
                raw={"character": character, "sub": sub, "age_hours": age, "pub_date": row.get("pub_date")},
            )
        )
    return out


def collect_layer_c() -> List[Dict[str, Any]]:
    """Gather Layer C character niche signals for Gary, Linda, and the Kids (top 4, strictly last 24h)."""
    bucket: List[Dict[str, Any]] = []

    # 1. Gary (Tech layoffs, corporate stand-ups, middle-management panic)
    for label, url in GARY_FEEDS:
        rows = _fetch_rss(url)
        for i, row in enumerate(rows[:4]):
            base_score = 70.0 - i
            age = row.get("age_hours")
            if age is not None and age <= 12.0:
                base_score += 8.0
            bucket.append(
                _item(
                    title=row["title"],
                    source="character_rss",
                    character="gary",
                    url=row.get("link") or "",
                    score=round(base_score, 1),
                    snippet=row.get("description") or "",
                    outlet=label,
                    raw={"character": "gary", "age_hours": age, "pub_date": row.get("pub_date")},
                )
            )
        time.sleep(0.05)
    for sub in GARY_SUBS:
        bucket.extend(_fetch_character_reddit_syndication(sub, character="gary", limit=4))
        time.sleep(0.05)

    # 2. Linda (Suburban wellness, Botox, Goop-style detox, parenting status games)
    for label, url in LINDA_FEEDS:
        rows = _fetch_rss(url)
        for i, row in enumerate(rows[:4]):
            base_score = 70.0 - i
            age = row.get("age_hours")
            if age is not None and age <= 12.0:
                base_score += 8.0
            bucket.append(
                _item(
                    title=row["title"],
                    source="character_rss",
                    character="linda",
                    url=row.get("link") or "",
                    score=round(base_score, 1),
                    snippet=row.get("description") or "",
                    outlet=label,
                    raw={"character": "linda", "age_hours": age, "pub_date": row.get("pub_date")},
                )
            )
        time.sleep(0.05)
    for sub in LINDA_SUBS:
        bucket.extend(_fetch_character_reddit_syndication(sub, character="linda", limit=4))
        time.sleep(0.05)

    # 3. Kids (Chris doomer cynicism & Chloe livestream monetizing)
    for label, url in KIDS_FEEDS:
        rows = _fetch_rss(url)
        for i, row in enumerate(rows[:4]):
            base_score = 70.0 - i
            age = row.get("age_hours")
            if age is not None and age <= 12.0:
                base_score += 8.0
            bucket.append(
                _item(
                    title=row["title"],
                    source="character_rss",
                    character="kids",
                    url=row.get("link") or "",
                    score=round(base_score, 1),
                    snippet=row.get("description") or "",
                    outlet=label,
                    raw={"character": "kids", "age_hours": age, "pub_date": row.get("pub_date")},
                )
            )
        time.sleep(0.05)
    for sub in KIDS_SUBS:
        bucket.extend(_fetch_character_reddit_syndication(sub, character="kids", limit=4))
        time.sleep(0.05)

    logger.info("Layer C collected %s items", len(bucket))
    return bucket
