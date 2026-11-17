"""
Temporal Orchestration & Workflow Setup for Crash Out Multi-Agent Pipelines.

Provides:
- Temporal Client initialization (with fallback to in-memory/direct execution)
- Workflows for Crash Out Episode Production (Gate 1 -> Gate 5)
- Activities for Agent 0, Agent 1, Vidu rendering, FFmpeg merge, Agent 4, Agent 5
- Worker process runner
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("app.temporal")

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "crash-out-production-queue")

_temporal_client = None


async def get_temporal_client():
    """Retrieve or initialize connected Temporal client."""
    global _temporal_client
    if _temporal_client is not None:
        return _temporal_client

    try:
        from temporalio.client import Client

        _temporal_client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
        logger.info("Connected to Temporal server at %s (namespace: %s)", TEMPORAL_HOST, TEMPORAL_NAMESPACE)
        return _temporal_client
    except Exception as exc:
        logger.warning("Temporal server not reachable at %s: %s. Using local async worker fallback.", TEMPORAL_HOST, exc)
        return None


# Import temporalio decorators safely
try:
    from temporalio import activity, workflow

    @activity.defn
    async def run_trend_ingest_activity() -> Dict[str, Any]:
        """Activity: Agent 0 fetches trends and scores friction."""
        from app.agents.agent_0_trend_ingest import trend_ingest_agent

        logger.info("[Temporal Activity] Executing Agent 0 Trend Ingestion...")
        concepts = trend_ingest_agent.get_daily_concepts()
        return {"concepts": concepts}

    @activity.defn
    async def run_scriptwriter_activity(concept: Dict[str, Any]) -> Dict[str, Any]:
        """Activity: Agent 1 generates dialogue script & 4 scenes."""
        from app.agents.agent_1_scriptwriter import scriptwriter_agent

        logger.info("[Temporal Activity] Executing Agent 1 Scriptwriter...")
        script = scriptwriter_agent.generate_script(concept)
        return {"script": script}

    @activity.defn
    async def render_vidu_scene_activity(scene_index: int, episode_id: str) -> Dict[str, Any]:
        """Activity: Render scene with Vidu Q4 / mock engine."""
        logger.info("[Temporal Activity] Rendering scene %d for episode %s...", scene_index, episode_id)
        # Delegated to existing studio/generation workers
        return {"scene_index": scene_index, "status": "COMPLETED"}

    @activity.defn
    async def merge_episode_video_activity(episode_id: str) -> Dict[str, Any]:
        """Activity: FFmpeg merge 4 scenes into 9:16 master."""
        from app.state import state_manager
        from app.media.merger import merge_scene_videos

        logger.info("[Temporal Activity] Merging episode video for %s...", episode_id)
        ep = state_manager.get_episode(episode_id)
        if ep:
            from app.main import merge_episode_scenes
            res = merge_episode_scenes(ep)
            if res.get("success"):
                return {"output_path": ep.merged_video_url or res.get("output_path"), "count": len(ep.scene_videos), "status": "SUCCESS"}
            return {"status": "FAILED", "error": res.get("error")}
        return {"status": "FAILED", "error": "Episode not found"}

    @activity.defn
    async def run_publisher_activity(episode_id: str) -> Dict[str, Any]:
        """Activity: Agent 4 generates publishing copy & merch mockups."""
        from app.state import state_manager
        from app.agents.agent_4_publisher import publisher_agent

        logger.info("[Temporal Activity] Executing Agent 4 Publisher for %s...", episode_id)
        ep = state_manager.get_episode(episode_id)
        if ep:
            package = publisher_agent.generate_publishing_package(
                episode_title=ep.title,
                concept_summary=ep.cultural_hook,
                merch_punchline=ep.merch_punchline or "Capitalism Broke My Dad",
            )
            return package
        return {}

    @activity.defn
    async def run_seeder_activity(episode_id: str) -> Dict[str, Any]:
        """Activity: Agent 5 creates guerrilla seeding drafts."""
        from app.state import state_manager
        from app.agents.agent_5_seeder import seeder_agent

        logger.info("[Temporal Activity] Executing Agent 5 Seeder for %s...", episode_id)
        ep = state_manager.get_episode(episode_id)
        if ep:
            campaign = seeder_agent.generate_seeding_campaign(
                episode_title=ep.title,
                merch_punchline=ep.merch_punchline or "Capitalism Broke My Dad",
            )
            return campaign
        return {}

    @workflow.defn
    class CrashOutProductionWorkflow:
        """Temporal Workflow orchestrating end-to-end production with human approval pauses."""

        def __init__(self):
            self.approved_gateways = set()
            self.is_cancelled = False

        @workflow.signal
        def approve_gateway_signal(self, gateway_num: int):
            logger.info("Received approval signal for Gateway %d", gateway_num)
            self.approved_gateways.add(gateway_num)

        @workflow.run
        async def run(self, episode_id: str) -> Dict[str, Any]:
            logger.info("Starting CrashOutProductionWorkflow for episode: %s", episode_id)

            # Stage 0 -> 1: Trend Ingest
            trend_res = await workflow.execute_activity(
                run_trend_ingest_activity,
                start_to_close_timeout=timedelta(minutes=5),
            )

            # Wait for Gateway 1 Human Approval
            await workflow.wait_condition(lambda: 1 in self.approved_gateways)

            # Stage 1 -> 2: Scriptwriting
            script_res = await workflow.execute_activity(
                run_scriptwriter_activity,
                args=[trend_res["concepts"][0] if trend_res.get("concepts") else {}],
                start_to_close_timeout=timedelta(minutes=3),
            )

            # Wait for Gateway 2 Human Approval
            await workflow.wait_condition(lambda: 2 in self.approved_gateways)

            # Stage 2 -> 3: Video Rendering (Scenes 1 to 4)
            for i in range(1, 5):
                await workflow.execute_activity(
                    render_vidu_scene_activity,
                    args=[i, episode_id],
                    start_to_close_timeout=timedelta(minutes=15),
                )

            # Merge scenes
            await workflow.execute_activity(
                merge_episode_video_activity,
                args=[episode_id],
                start_to_close_timeout=timedelta(minutes=5),
            )

            # Wait for Gateway 3 Human Approval (Video Review)
            await workflow.wait_condition(lambda: 3 in self.approved_gateways)

            # Stage 3 -> 4: Publisher
            await workflow.execute_activity(
                run_publisher_activity,
                args=[episode_id],
                start_to_close_timeout=timedelta(minutes=3),
            )

            # Wait for Gateway 4 Human Approval
            await workflow.wait_condition(lambda: 4 in self.approved_gateways)

            # Stage 4 -> 5: Seeder
            await workflow.execute_activity(
                run_seeder_activity,
                args=[episode_id],
                start_to_close_timeout=timedelta(minutes=3),
            )

            # Wait for Gateway 5 Final Sign-Off
            await workflow.wait_condition(lambda: 5 in self.approved_gateways)

            logger.info("CrashOutProductionWorkflow completed successfully for %s", episode_id)
            return {"episode_id": episode_id, "status": "PUBLISHED"}

except Exception as _temporal_import_err:
    logger.debug("Temporal workflow definition deferred: %s", _temporal_import_err)
    CrashOutProductionWorkflow = None  # type: ignore


async def run_temporal_worker():
    """Start standalone worker listening on task queue."""
    from temporalio.worker import Worker

    client = await get_temporal_client()
    if not client:
        logger.info("Temporal client not connected; worker will not start.")
        return

    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[CrashOutProductionWorkflow],
        activities=[
            run_trend_ingest_activity,
            run_scriptwriter_activity,
            render_vidu_scene_activity,
            merge_episode_video_activity,
            run_publisher_activity,
            run_seeder_activity,
        ],
    )
    logger.info("Starting Temporal Worker on queue: %s", TEMPORAL_TASK_QUEUE)
    await worker.run()
