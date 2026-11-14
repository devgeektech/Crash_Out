"""
Agent 0: US News & Viral Trend Ingestion Agent.

Cross-references mainstream US media (Layer A), youth social/memes (Layer B),
and character niche feeds (Layer C), then scores Friction Intersection pitches
for HITL Gateway 1 (Top 5).
"""
from typing import Any, Dict, List

from app.trends.pipeline import fetch_daily_pitch_run, fetch_live_concepts, get_latest_run_or_refresh
from app.trends.schema import pitches_to_concepts


class Agent0TrendIngest:
    def __init__(self):
        self.name = "Agent 0 (Trend Ingestion)"

    def fetch_trending_concepts(self) -> List[Dict[str, Any]]:
        """Gate 1 cards: Top 5 friction pitches adapted to concept shape."""
        return fetch_live_concepts()

    def fetch_daily_pitches(self, *, force_refresh: bool = True) -> Dict[str, Any]:
        """Client schema pitch run (run_date + pitches[5])."""
        if force_refresh:
            return fetch_daily_pitch_run()
        return get_latest_run_or_refresh(refresh=False)

    def concepts_from_latest_run(self) -> List[Dict[str, Any]]:
        run = get_latest_run_or_refresh(refresh=False)
        return pitches_to_concepts(run)


trend_ingest_agent = Agent0TrendIngest()
