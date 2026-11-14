"""
Layer C — Character-specific niche feeds (satirical fuel for Gary / Linda / kids).
"""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

GARY_FEEDS = [
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
]
GARY_SUBS = ["Layoffs", "cscareerquestions"]

LINDA_FEEDS = [
    ("Well+Good", "https://www.wellandgood.com/feed/"),
    ("MindBodyGreen", "https://www.mindbodygreen.com/rss.xml"),
]
LINDA_SUBS = ["ShitMomGroupsSay"]

KIDS_FEEDS = [
    ("Dexerto", "https://www.dexerto.com/feed/"),
    ("Tubefilter", "https://www.tubefilter.com/feed/"),
    ("Complex Pop Culture", "https://www.complex.com/pop-culture/rss"),
]


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


def _fetch_rss(url: str) -> List[Dict[str, Any]]:
    try:
        resp = requests.get(url, timeout=12, headers={"User-Agent": "CrashOutAgent0/1.0"})
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
    except Exception as exc:
        logger.debug("Layer C RSS failed %s: %s", url, exc)
        return []
    items: List[Dict[str, Any]] = []
    for node in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = (
            node.findtext("title") or node.findtext("{http://www.w3.org/2005/Atom}title") or ""
        ).strip()
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


def _reddit_hot(sub: str, *, character: str, limit: int = 10) -> List[Dict[str, Any]]:
    try:
        resp = requests.get(
            f"https://www.reddit.com/r/{sub}/hot.json",
            params={"limit": limit, "raw_json": 1},
            timeout=12,
            headers={"User-Agent": "CrashOutAgent0/1.0 (character niche)"},
        )
        if resp.status_code != 200:
            return []
        children = ((resp.json() or {}).get("data") or {}).get("children") or []
    except Exception as exc:
        logger.debug("Layer C reddit r/%s failed: %s", sub, exc)
        return []
    out: List[Dict[str, Any]] = []
    for child in children:
        data = (child or {}).get("data") or {}
        title = (data.get("title") or "").strip()
        if not title or data.get("stickied"):
            continue
        out.append(
            _item(
                title=title,
                source=f"reddit/{sub}",
                character=character,
                url=f"https://www.reddit.com{data.get('permalink') or ''}",
                score=float(data.get("ups") or data.get("score") or 0),
                snippet=(data.get("selftext") or "")[:240],
                outlet=f"r/{sub}",
            )
        )
    return out


def collect_layer_c() -> List[Dict[str, Any]]:
    bucket: List[Dict[str, Any]] = []

    for label, url in GARY_FEEDS:
        for i, row in enumerate(_fetch_rss(url)[:10]):
            bucket.append(
                _item(
                    title=row["title"],
                    source="character_rss",
                    character="gary",
                    url=row.get("link") or "",
                    score=65.0 - i,
                    snippet=row.get("description") or "",
                    outlet=label,
                )
            )
        time.sleep(0.15)
    for sub in GARY_SUBS:
        bucket.extend(_reddit_hot(sub, character="gary"))
        time.sleep(0.3)

    for label, url in LINDA_FEEDS:
        for i, row in enumerate(_fetch_rss(url)[:10]):
            bucket.append(
                _item(
                    title=row["title"],
                    source="character_rss",
                    character="linda",
                    url=row.get("link") or "",
                    score=65.0 - i,
                    snippet=row.get("description") or "",
                    outlet=label,
                )
            )
        time.sleep(0.15)
    for sub in LINDA_SUBS:
        bucket.extend(_reddit_hot(sub, character="linda"))
        time.sleep(0.3)

    for label, url in KIDS_FEEDS:
        for i, row in enumerate(_fetch_rss(url)[:10]):
            bucket.append(
                _item(
                    title=row["title"],
                    source="character_rss",
                    character="kids",
                    url=row.get("link") or "",
                    score=65.0 - i,
                    snippet=row.get("description") or "",
                    outlet=label,
                )
            )
        time.sleep(0.15)

    logger.info("Layer C collected %s items", len(bucket))
    return bucket
