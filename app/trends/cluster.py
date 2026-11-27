"""
Semantic deduplication + event clustering for Agent 0.

Uses OpenAI embeddings when available; otherwise token Jaccard similarity.
Groups items with cosine/Jaccard similarity > 0.82 into unified event clusters.
"""
from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

from app.config import config

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.58
JACCARD_THRESHOLD = 0.25


def _text_of(item: Dict[str, Any]) -> str:
    title = str(item.get("title") or "").strip()
    snip = str(item.get("snippet") or "").strip()
    return f"{title}. {snip}".strip()


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def embed_texts(texts: List[str]) -> Optional[List[List[float]]]:
    api_key = (config.openai_api_key or "").strip()
    if not api_key or not texts:
        return None
    model = (getattr(config, "openai_embed_model", None) or "text-embedding-3-small").strip()
    
    # Batch embeddings in chunks of 100 to avoid request payload limits
    batch_size = 100
    all_embeddings: List[List[float]] = []
    try:
        for offset in range(0, len(texts), batch_size):
            chunk = [t[:4000] for t in texts[offset : offset + batch_size]]
            resp = requests.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": model, "input": chunk},
                timeout=60,
            )
            if resp.status_code != 200:
                logger.warning("Embedding API %s: %s", resp.status_code, resp.text[:180])
                return None
            data = (resp.json() or {}).get("data") or []
            data = sorted(data, key=lambda row: int(row.get("index") or 0))
            all_embeddings.extend([list(row.get("embedding") or []) for row in data])
        return all_embeddings
    except Exception as exc:
        logger.warning("Embedding request failed: %s", exc)
        return None


def cluster_items(
    items: List[Dict[str, Any]],
    *,
    threshold: float = SIMILARITY_THRESHOLD,
    prior_embeddings: Optional[List[Tuple[str, List[float]]]] = None,
) -> List[Dict[str, Any]]:
    """
    Return event clusters:
    {
      id, label, items, layers, outlets, characters,
      layer_hits: {A,B,C}, representative, embedding?
    }
    Drops clusters too similar to prior episode topics when prior_embeddings provided.
    """
    if not items:
        return []

    texts = [_text_of(it) for it in items]
    vectors = embed_texts(texts)
    use_vectors = bool(vectors and len(vectors) == len(items))

    parents = list(range(len(items)))

    def find(i: int) -> int:
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parents[rj] = ri

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if use_vectors:
                sim = cosine(vectors[i], vectors[j])
                is_match = sim >= threshold
            else:
                sim = jaccard(texts[i], texts[j])
                is_match = sim >= JACCARD_THRESHOLD
            if is_match:
                union(i, j)

    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(len(items)):
        groups[find(i)].append(i)

    clusters: List[Dict[str, Any]] = []
    for idx, (root, members) in enumerate(groups.items(), 1):
        member_items = [items[i] for i in members]
        layers = sorted({str(it.get("layer") or "?").upper() for it in member_items})
        outlets = []
        seen_out = set()
        for it in sorted(member_items, key=lambda x: float(x.get("score") or 0), reverse=True):
            out = str(it.get("outlet") or it.get("source") or "").strip()
            if out and out not in seen_out:
                seen_out.add(out)
                outlets.append(out)
        characters = sorted(
            {str(it.get("character") or "").lower() for it in member_items if it.get("character")}
        )
        layer_hits = {
            "A": sum(1 for it in member_items if str(it.get("layer") or "").upper() == "A"),
            "B": sum(1 for it in member_items if str(it.get("layer") or "").upper() == "B"),
        }
        rep = max(member_items, key=lambda it: float(it.get("score") or 0))
        emb = vectors[members[0]] if use_vectors else None

        # 30-day episode memory rejection
        if prior_embeddings and emb:
            too_close = False
            for _ep_id, prior in prior_embeddings:
                if cosine(emb, prior) >= threshold:
                    too_close = True
                    break
            if too_close:
                continue
        elif prior_embeddings and not emb:
            # Jaccard against prior labels stored as text in second slot when vector missing
            label = _text_of(rep)
            for prior_label, prior_vec in prior_embeddings:
                if prior_vec:
                    continue
                if jaccard(label, prior_label) >= JACCARD_THRESHOLD:
                    # skip duplicate topic
                    rep = None  # marker
                    break
            if rep is None:
                continue

        is_cross = len(layers) >= 2

        clusters.append(
            {
                "id": f"cluster_{idx}",
                "label": str(rep.get("title") or f"Cluster {idx}"),
                "items": member_items,
                "layers": layers,
                "outlets": outlets[:8],
                "characters": characters,
                "layer_hits": layer_hits,
                "cross_layer": is_cross,
                "representative": rep,
                "embedding": emb,
                "member_count": len(member_items),
                "score_hint": sum(float(it.get("score") or 0) for it in member_items)
                / max(1, len(member_items)),
            }
        )

    clusters.sort(
        key=lambda c: (
            1 if c.get("cross_layer") else 0,
            len(c.get("layers", [])),
            c.get("member_count") or 0,
            c.get("score_hint") or 0,
        ),
        reverse=True,
    )
    return clusters
