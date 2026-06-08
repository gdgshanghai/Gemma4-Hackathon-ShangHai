"""Subagent-level unit tests with a fake LLM client.

These exercise the new ``app.services.agents`` layer in isolation so PR-3
orchestrator wiring does not have to re-establish coverage at this level.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.core.llm import LLMProviderError
from app.services.agents.base import (
    EvaluationContext,
    FeynmanContext,
    MissionContext,
    invoke_with_fallback,
)
from app.services.agents.subagents.artifact import (
    MAX_CONTENT_BYTES,
    MissionArtifactSubagent,
)
from app.services.agents.subagents.evaluate import SubmissionEvaluateSubagent
from app.services.agents.subagents.feynman import FeynmanReviewSubagent
from app.services.agents.subagents.spec import MissionSpecSubagent


class TestMissionSpecSubagent(unittest.TestCase):
  """Verify spec generation honors LLM contract and falls back cleanly."""

  def setUp(self):
    self.ctx = MissionContext(
        role_id="data_analyst",
        difficulty="easy",
        task_index=1,
        mission_id="",
        user_id="u1",
    )

  def test_run_offline_returns_catalog_payload(self):
    """When LLM is disabled, a catalog spec is returned without calling LLM."""
    with patch("app.services.agents.subagents.spec.llm_disabled", return_value=True):
      result = asyncio.run(MissionSpecSubagent().run(self.ctx))
    self.assertIn("title", result.payload)
    self.assertIn("delivery_requirements", result.payload)
    self.assertFalse(result.used_fallback)

  def test_unwrap_handles_nested_response(self):
    """If the LLM wraps the payload in ``task``, the subagent unwraps it."""
    nested = {
        "task": {
            "title": "T",
            "description": "D",
            "mock_data_url": "https://example.com/x.csv",
            "delivery_requirements": ["a", "b"],
        }
    }
    fake = AsyncMock(chat_json=AsyncMock(return_value=nested))
    with patch(
        "app.services.agents.subagents.spec.llm_disabled", return_value=False,
    ), patch(
        "app.services.agents.llm_io.get_llm_client", return_value=fake,
    ):
      result = asyncio.run(MissionSpecSubagent().run(self.ctx))
    self.assertEqual(result.payload["title"], "T")

  def test_invoke_with_fallback_on_provider_error(self):
    """LLMProviderError translates into used_fallback=True via the orchestrator helper."""
    fake = AsyncMock(chat_json=AsyncMock(side_effect=LLMProviderError("boom")))
    with patch(
        "app.services.agents.subagents.spec.llm_disabled", return_value=False,
    ), patch(
        "app.services.agents.llm_io.get_llm_client", return_value=fake,
    ):
      result = asyncio.run(invoke_with_fallback(MissionSpecSubagent(), self.ctx))
    self.assertTrue(result.used_fallback)
    self.assertIn("Fallback", result.payload["title"])


class TestMissionArtifactSubagent(unittest.TestCase):
  """Validate the new artifact stage's schema/size enforcement."""

  def _ctx(self) -> MissionContext:
    return MissionContext(
        role_id="data_analyst", difficulty="easy", task_index=1,
        mission_id="m1", user_id="u1",
        spec={
            "mission_id": "mvp_mission_data_1",
            "title": "T", "description": "D",
            "delivery_requirements": ["a"],
        },
    )

  def test_runs_when_payload_within_limits(self):
    payload = {
        "filename": "data.csv", "mime_type": "text/csv",
        "content": "a,b\n1,2\n",
    }
    fake = AsyncMock(chat_json=AsyncMock(return_value=payload))
    with patch(
        "app.services.agents.subagents.artifact.llm_disabled", return_value=False,
    ), patch(
        "app.services.agents.llm_io.get_llm_client", return_value=fake,
    ):
      result = asyncio.run(MissionArtifactSubagent().run(self._ctx()))
    self.assertEqual(result.payload.filename, "data.csv")
    self.assertEqual(result.payload.mime_type, "text/csv")

  def test_oversize_content_falls_back(self):
    payload = {
        "filename": "x.csv", "mime_type": "text/csv",
        "content": "x" * (MAX_CONTENT_BYTES + 100),
    }
    fake = AsyncMock(chat_json=AsyncMock(return_value=payload))
    with patch(
        "app.services.agents.subagents.artifact.llm_disabled", return_value=False,
    ), patch(
        "app.services.agents.llm_io.get_llm_client", return_value=fake,
    ):
      result = asyncio.run(invoke_with_fallback(MissionArtifactSubagent(), self._ctx()))
    self.assertTrue(result.used_fallback)

  def test_bad_mime_falls_back(self):
    payload = {
        "filename": "x.bin", "mime_type": "application/octet-stream",
        "content": "ignored",
    }
    fake = AsyncMock(chat_json=AsyncMock(return_value=payload))
    with patch(
        "app.services.agents.subagents.artifact.llm_disabled", return_value=False,
    ), patch(
        "app.services.agents.llm_io.get_llm_client", return_value=fake,
    ):
      result = asyncio.run(invoke_with_fallback(MissionArtifactSubagent(), self._ctx()))
    self.assertTrue(result.used_fallback)

  def test_offline_uses_bundled_sample(self):
    """LLM-disabled path always falls back; bundled sample exists for catalog id."""
    with patch(
        "app.services.agents.subagents.artifact.llm_disabled", return_value=True,
    ):
      result = asyncio.run(invoke_with_fallback(MissionArtifactSubagent(), self._ctx()))
    self.assertTrue(result.used_fallback)
    self.assertTrue(result.payload.filename)


class TestSubmissionEvaluateSubagent(unittest.TestCase):
  def test_offline_returns_career_specific_payload(self):
    ctx = EvaluationContext(
        mission_id="m1", user_id="u1",
        submission_text="ok",
        career_id="career_software_engineer",
        mission_description="d",
    )
    with patch(
        "app.services.agents.subagents.evaluate.llm_disabled", return_value=True,
    ):
      result = asyncio.run(SubmissionEvaluateSubagent().run(ctx))
    self.assertEqual(result.payload["status"], "success")
    self.assertIn("skill_debugging", result.payload["experience_gains"])

  def test_provider_error_falls_back(self):
    ctx = EvaluationContext(
        mission_id="m1", user_id="u1",
        submission_text="ok",
        career_id="career_data_analyst",
        mission_description="d",
    )
    fake = AsyncMock(chat_json=AsyncMock(side_effect=LLMProviderError("boom")))
    with patch(
        "app.services.agents.subagents.evaluate.llm_disabled", return_value=False,
    ), patch(
        "app.services.agents.llm_io.get_llm_client", return_value=fake,
    ):
      result = asyncio.run(invoke_with_fallback(SubmissionEvaluateSubagent(), ctx))
    self.assertTrue(result.used_fallback)
    self.assertIn("skill_data_cleaning", result.payload["experience_gains"])


class TestFeynmanReviewSubagent(unittest.TestCase):
  def test_offline_returns_static_feedback(self):
    ctx = FeynmanContext(mission_id="", user_id="", question="q", answer="a")
    with patch(
        "app.services.agents.subagents.feynman.llm_disabled", return_value=True,
    ):
      result = asyncio.run(FeynmanReviewSubagent().run(ctx))
    self.assertTrue(result.payload)
    self.assertFalse(result.used_fallback)


class TestNonProviderExceptionsFallBack(unittest.TestCase):
  """Non-LLMProviderError exceptions must still trigger fallback, not 5xx.

  Pre-PR-2 ``agent.py`` used ``except Exception`` for the LLM call site, so
  any SDK / runtime error fell back gracefully. The subagent layer must
  preserve that contract: orchestrators only execute fallback on
  ``SubagentError``, so each ``run`` must convert other exceptions.
  """

  def test_mission_spec_runtime_error_falls_back(self):
    ctx = MissionContext(
        role_id="data_analyst", difficulty="easy", task_index=1,
        mission_id="", user_id="u1",
    )
    fake = AsyncMock(chat_json=AsyncMock(side_effect=RuntimeError("sdk boom")))
    with patch(
        "app.services.agents.subagents.spec.llm_disabled", return_value=False,
    ), patch(
        "app.services.agents.llm_io.get_llm_client", return_value=fake,
    ):
      result = asyncio.run(invoke_with_fallback(MissionSpecSubagent(), ctx))
    self.assertTrue(result.used_fallback)
    self.assertIn("Fallback", result.payload["title"])

  def test_evaluate_value_error_falls_back(self):
    ctx = EvaluationContext(
        mission_id="m1", user_id="u1",
        submission_text="ok",
        career_id="career_data_analyst",
        mission_description="d",
    )
    fake = AsyncMock(chat_json=AsyncMock(side_effect=ValueError("bad payload")))
    with patch(
        "app.services.agents.subagents.evaluate.llm_disabled", return_value=False,
    ), patch(
        "app.services.agents.llm_io.get_llm_client", return_value=fake,
    ):
      result = asyncio.run(invoke_with_fallback(SubmissionEvaluateSubagent(), ctx))
    self.assertTrue(result.used_fallback)
    self.assertEqual(result.payload["status"], "success")

  def test_feynman_runtime_error_falls_back(self):
    ctx = FeynmanContext(mission_id="", user_id="", question="q", answer="a")
    fake = AsyncMock(chat=AsyncMock(side_effect=RuntimeError("sdk boom")))
    with patch(
        "app.services.agents.subagents.feynman.llm_disabled", return_value=False,
    ), patch(
        "app.services.agents.llm_io.get_llm_client", return_value=fake,
    ):
      result = asyncio.run(invoke_with_fallback(FeynmanReviewSubagent(), ctx))
    self.assertTrue(result.used_fallback)
    self.assertTrue(result.payload)


if __name__ == "__main__":
  unittest.main()
