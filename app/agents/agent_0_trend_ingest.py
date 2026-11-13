"""
Agent 0: US News & Viral Trend Ingestion Agent.
Fetches latest cultural signals (Reddit / Google Trends / optional NewsAPI),
filters to Crash Out themes, and returns 3 satirical Gate 1 concepts.
"""
from typing import Any, Dict, List

from app.trends.pipeline import fetch_live_concepts


class Agent0TrendIngest:
    def __init__(self):
        self.name = "Agent 0 (Trend Ingestion)"

    def fetch_trending_concepts(self) -> List[Dict[str, Any]]:
        """Gate 1 concept cards from live trends (cache / static fallback if needed)."""
        return fetch_live_concepts()


trend_ingest_agent = Agent0TrendIngest()
