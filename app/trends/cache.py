"""Persist last successful Gate 1 concept trio so refresh never blanks."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from app.paths import OUTPUT_DIR

logger = logging.getLogger(__name__)

CACHE_PATH = os.path.join(OUTPUT_DIR, "trend_concepts_cache.json")


def _cache_quality_ok(concepts: List[Dict[str, Any]]) -> bool:
    """Reject stale cache entries that look like hard-news / politics noise."""
    from app.trends.filter import REJECT_KEYWORDS

    for c in concepts[:3]:
        blob = f"{c.get('title') or ''} {' '.join(c.get('source_trends') or [])}".lower()
        if any(bad in blob for bad in REJECT_KEYWORDS):
            return False
        if not (c.get("premise") or "").strip():
            return False
    return True


def load_cached_concepts() -> Optional[List[Dict[str, Any]]]:
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        concepts = data.get("concepts") if isinstance(data, dict) else data
        if isinstance(concepts, list) and len(concepts) >= 3:
            cleaned = [dict(c) for c in concepts[:3]]
            if not _cache_quality_ok(cleaned):
                logger.info("Ignoring low-quality trend cache")
                return None
            return cleaned
    except Exception as exc:
        logger.warning("Failed to read trend cache: %s", exc)
    return None


def save_cached_concepts(concepts: List[Dict[str, Any]], *, meta: Optional[Dict[str, Any]] = None) -> None:
    if not concepts or len(concepts) < 3:
        return
    payload = {
        "saved_at": time.time(),
        "saved_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "meta": meta or {},
        "concepts": concepts[:3],
    }
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Failed to write trend cache: %s", exc)
