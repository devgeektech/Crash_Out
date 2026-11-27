"""
Agent 0: US News & Viral Trend Ingestion Agent.

Cross-references youth social/memes (Layer B) and mainstream US media (Layer A),
then scores Friction Intersection pitches for HITL Gateway 1 (Top 5).
"""
from typing import Any, Dict, List

from app.trends.pipeline import fetch_daily_pitch_run, get_latest_run_or_refresh
from app.trends.schema import pitches_to_concepts
from app.trends.store import load_latest_pitch_run


class Agent0TrendIngest:
    def __init__(self):
        self.name = "Agent 0 (Trend Ingestion)"

    def fetch_trending_concepts(self) -> List[Dict[str, Any]]:
        """
        Gate 1 cards from an existing pitch run only — does not scrape/score.
        New pitches come from Trend Research → Create top 5 pitches.
        """
        run = load_latest_pitch_run() or {}
        concepts = pitches_to_concepts(run) if run.get("pitches") else []
        if concepts:
            return concepts[:5]
        return []

    def fetch_daily_pitches(self, *, force_refresh: bool = True) -> Dict[str, Any]:
        """Explicit full scoring run (Agent M / API). Prefer selection-based create-pitches in studio."""
        if force_refresh:
            return fetch_daily_pitch_run()
        return get_latest_run_or_refresh(refresh=False)

    def concepts_from_latest_run(self) -> List[Dict[str, Any]]:
        run = load_latest_pitch_run() or {}
        if not run.get("pitches"):
            return []
        return pitches_to_concepts(run)


trend_ingest_agent = Agent0TrendIngest()
