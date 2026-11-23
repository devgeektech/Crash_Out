"""
Unit & Integration Test Suite for Agent M Retry & Incident Management.

Tests:
1. Agent 0 (Trend Ingest) retries 3 times with 1-min (+60s) gap and logs critical incident.
2. Agent 1 (Scriptwriter) retries 3 times with 1-min (+60s) gap and logs critical incident.
3. Agent M Log Board surfaces both Agent 0 and Agent 1 failure incidents with CRITICAL severity.
4. Agent M One-Click Task Retry for Agent 0 re-executes trend ingest and resolves incident.
5. Agent M One-Click Task Retry for Agent 1 regenerates script, updates state, and resolves incident.
6. Resolved incidents are cleanly excluded from the active Log Board.
"""
import os
import unittest
from unittest.mock import MagicMock, patch

from app.agents.agent_m_orchestrator import orchestrator
from app.state import state_manager, Episode


class TestAgentMRetryProcess(unittest.TestCase):
    def setUp(self):
        # Set default 60s retry delay for testing (mocking sleep so no real delay occurs)
        os.environ["AGENT_RETRY_INTERVAL_SECONDS"] = "60"

    @patch("time.sleep")
    @patch("requests.post")
    @patch("app.trends.friction.log_system_incident")
    def test_agent_0_retries_three_times_with_one_min_gap(self, mock_log_incident, mock_post, mock_sleep):
        """Test Agent 0 scores clusters with exactly 3 attempts and 60s (1 min) gaps before failing."""
        from app.trends.friction import score_clusters

        # Simulate persistent HTTP 500 error from OpenAI
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        dummy_clusters = [{"cluster_id": 1, "topic": "AI News", "items": [{"title": "News 1"}]}]

        with self.assertRaises(RuntimeError) as ctx:
            score_clusters(dummy_clusters, run_date="20261123")

        self.assertIn("failed after 3 automated attempts", str(ctx.exception))
        # Verify exactly 3 API attempts were made
        self.assertEqual(mock_post.call_count, 3)

        # Verify 2 sleep calls between the 3 attempts, each sleeping 60 seconds (1 minute gap)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(60)

        # Verify incident was logged to Agent M Log Board
        mock_log_incident.assert_called_once()
        call_kwargs = mock_log_incident.call_args[1]
        self.assertEqual(call_kwargs.get("event_type"), "AGENT0_LLM_FAILURE")
        details = call_kwargs.get("details", {})
        self.assertEqual(details.get("retry_count"), 3)
        self.assertEqual(details.get("max_retries"), 3)
        self.assertTrue(details.get("can_retry"))
        self.assertTrue(details.get("requires_manual_retry"))

    @patch("time.sleep")
    @patch("requests.post")
    @patch("app.agents.agent_1_scriptwriter.log_system_incident")
    def test_agent_1_retries_three_times_with_one_min_gap(self, mock_log_incident, mock_post, mock_sleep):
        """Test Agent 1 generates script with exactly 3 attempts and 60s (1 min) gaps before failing."""
        from app.agents.agent_1_scriptwriter import scriptwriter_agent

        # Simulate persistent failure from OpenAI
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.text = "Bad Gateway"
        mock_post.return_value = mock_response

        dummy_concept = {
            "id": "ep_test_001",
            "title": "Suburban Crash Out Test",
            "headline": "Suburban Crash Out Test",
            "crash_out_angle": "Angle test",
            "proposed_merch_hook": "Prompted This",
        }

        with self.assertRaises(RuntimeError) as ctx:
            scriptwriter_agent.generate_script(dummy_concept, episode_id="ep_test_001")

        self.assertIn("failed after 3 attempts", str(ctx.exception))
        # Verify exactly 3 API attempts were made
        self.assertEqual(mock_post.call_count, 3)

        # Verify 2 sleep calls between the 3 attempts, each sleeping 60 seconds (1 minute gap)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(60)

        # Verify incident was logged to Agent M Log Board
        mock_log_incident.assert_called_once()
        call_kwargs = mock_log_incident.call_args[1]
        self.assertEqual(call_kwargs.get("event_type"), "AGENT1_SCRIPT_FAILURE")
        details = call_kwargs.get("details", {})
        self.assertEqual(details.get("episode_id"), "ep_test_001")
        self.assertEqual(details.get("retry_count"), 3)
        self.assertEqual(details.get("max_retries"), 3)
        self.assertTrue(details.get("can_retry"))

    @patch("app.agents.agent_m_orchestrator.list_system_audit_logs")
    def test_agent_m_log_board_surfaces_agent0_and_agent1_failures(self, mock_audit_logs):
        """Test that get_system_incidents parses and displays AGENT0 and AGENT1 errors as CRITICAL incidents."""
        mock_audit_logs.return_value = [
            {
                "id": 101,
                "event_type": "AGENT0_LLM_FAILURE",
                "actor": "Agent M Orchestrator",
                "created_at": "2026-11-23 12:00:00",
                "details": {
                    "category": "Agent 0 Trend Ingest",
                    "task_name": "OpenAI Pitch Generation",
                    "error": "Agent 0 LLM scoring failed after 3 automated attempts",
                    "retry_count": 3,
                    "max_retries": 3,
                    "can_retry": True,
                },
            },
            {
                "id": 102,
                "event_type": "AGENT1_SCRIPT_FAILURE",
                "actor": "Agent M Orchestrator",
                "created_at": "2026-11-23 12:05:00",
                "details": {
                    "category": "Agent 1 Scriptwriter",
                    "task_name": "OpenAI Script Generation",
                    "error": "Agent 1 Scriptwriter failed after 3 attempts",
                    "episode_id": "ep_test_002",
                    "episode_title": "Test Episode Title",
                    "retry_count": 3,
                    "max_retries": 3,
                    "can_retry": True,
                },
            },
        ]

        incidents = orchestrator.get_system_incidents(limit=10)
        self.assertEqual(len(incidents), 2)

        # Check Agent 0 incident attributes
        a0_inc = next((i for i in incidents if i["incident_id"] == "audit_101"), None)
        self.assertIsNotNone(a0_inc)
        self.assertEqual(a0_inc["category"], "Agent 0 Trend Ingest")
        self.assertEqual(a0_inc["severity"], "CRITICAL")
        self.assertEqual(a0_inc["retry_count"], 3)
        self.assertEqual(a0_inc["max_retries"], 3)
        self.assertTrue(a0_inc["can_retry"])

        # Check Agent 1 incident attributes
        a1_inc = next((i for i in incidents if i["incident_id"] == "audit_102"), None)
        self.assertIsNotNone(a1_inc)
        self.assertEqual(a1_inc["category"], "Agent 1 Scriptwriter")
        self.assertEqual(a1_inc["severity"], "CRITICAL")
        self.assertEqual(a1_inc["episode_id"], "ep_test_002")
        self.assertEqual(a1_inc["retry_count"], 3)
        self.assertTrue(a1_inc["can_retry"])

    @patch("app.trends.pipeline.fetch_daily_pitch_run")
    @patch("app.agents.agent_m_orchestrator.log_system_incident")
    @patch("app.agents.agent_m_orchestrator.list_system_audit_logs")
    def test_agent_m_retry_task_for_agent_0(self, mock_audit_logs, mock_log_incident, mock_fetch_run):
        """Test hitting retry on an Agent 0 incident re-runs Agent 0 pipeline and logs resolution."""
        mock_audit_logs.return_value = [
            {
                "id": 201,
                "event_type": "AGENT0_EXECUTION_FAILURE",
                "details": {
                    "category": "Agent 0 Trend Ingest",
                    "error": "Pipeline error",
                },
            }
        ]
        mock_fetch_run.return_value = {"pitches": [{"title": "Pitch 1"}, {"title": "Pitch 2"}]}

        success, msg = orchestrator.retry_task("audit_201")
        self.assertTrue(success)
        self.assertIn("Agent 0 Trend Ingestion re-executed successfully", msg)
        mock_fetch_run.assert_called_once_with(force_refresh=True)

        # Verify resolution incident recorded
        mock_log_incident.assert_called_once()
        self.assertEqual(mock_log_incident.call_args[1].get("event_type"), "INCIDENT_RESOLVED")

    @patch("app.agents.agent_1_scriptwriter.scriptwriter_agent.generate_script")
    @patch("app.agents.agent_m_orchestrator.log_system_incident")
    @patch("app.agents.agent_m_orchestrator.list_system_audit_logs")
    def test_agent_m_retry_task_for_agent_1(self, mock_audit_logs, mock_log_incident, mock_gen_script):
        """Test hitting retry on an Agent 1 incident re-runs Scriptwriter and updates episode."""
        ep_id = "ep_retry_test_99"
        test_ep = Episode(
            id=ep_id,
            title="Retry Test Episode",
            selected_concept={"headline": "Retry Test Headline", "crash_out_angle": "Crisis", "proposed_merch_hook": "Prompted This"},
        )
        state_manager.episodes[ep_id] = test_ep

        mock_audit_logs.return_value = [
            {
                "id": 301,
                "event_type": "AGENT1_SCRIPT_FAILURE",
                "details": {
                    "category": "Agent 1 Scriptwriter",
                    "episode_id": ep_id,
                    "episode_title": "Retry Test Episode",
                },
            }
        ]
        mock_gen_script.return_value = {
            "episode_id": ep_id,
            "scenes": [{"scene_id": 1}, {"scene_id": 2}, {"scene_id": 3}, {"scene_id": 4}],
        }

        success, msg = orchestrator.retry_task("audit_301")
        self.assertTrue(success)
        self.assertIn(f"Agent 1 Scriptwriter re-executed successfully for episode {ep_id}", msg)
        mock_gen_script.assert_called_once()
        self.assertIsNotNone(test_ep.script)
        self.assertEqual(len(test_ep.script.get("scenes")), 4)

        # Verify resolution incident recorded
        mock_log_incident.assert_called_once()
        self.assertEqual(mock_log_incident.call_args[1].get("event_type"), "INCIDENT_RESOLVED")

    @patch("app.agents.agent_m_orchestrator.list_system_audit_logs")
    def test_resolved_incidents_are_cleared_from_log_board(self, mock_audit_logs):
        """Test that resolved incidents do not show up as active on the Incident Log Board."""
        mock_audit_logs.return_value = [
            {
                "id": 401,
                "event_type": "AGENT0_LLM_FAILURE",
                "details": {"category": "Agent 0 Trend Ingest", "error": "Fail"},
            },
            {
                "id": 402,
                "event_type": "INCIDENT_RESOLVED",
                "details": {"audit_id": "401", "action": "Resolved via retry"},
            },
        ]

        incidents = orchestrator.get_system_incidents(limit=10)
        # 401 was resolved by 402, so active incidents should be empty
        self.assertEqual(len(incidents), 0)


if __name__ == "__main__":
    unittest.main()
