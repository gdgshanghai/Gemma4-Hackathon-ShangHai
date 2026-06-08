"""Unit tests for the MissionService."""

import unittest
from tests.base import BaseDbTestCase, TEST_PLAYER_ID
from app.models import orm as models
from app.models.schemas import MissionGenerateRequest, MissionGenerateResponse
from app.services import agent
from app.services.factory import get_mission_orchestrator
from app.services.mission import generate_mission


class TestMissionService(BaseDbTestCase):
  """Mission Service testing suite."""

  def test_generate_first_mission_defaults_to_index_1(self):
    """Tests that the first generated mission corresponds to task index 1 (no completed missions)."""
    req = MissionGenerateRequest(role_id="mentor_ying", difficulty="easy")
    response = self.run_async(generate_mission(
        req, self.db_session, TEST_PLAYER_ID, get_mission_orchestrator(),
    ))

    self.assertIsNotNone(response.mission_id)
    self.assertIsNotNone(response.title)
    self.assertGreater(len(response.delivery_requirements), 0)
    self.assertEqual(response.career_id, "career_data_analyst")
    self.assertEqual(response.role_id, "mentor_ying")
    self.assertEqual(response.status, "active")
    self.assertEqual(response.difficulty, "easy")
    self.assertGreater(response.reward_xp, 0)
    self.assertGreater(len(response.reward_skills), 0)
    self.assertGreater(len(response.evaluation_criteria), 0)

    # Verify database state
    active_missions = self.db_session.query(models.MissionRecord).filter_by(
      user_id=TEST_PLAYER_ID, status="active"
    ).all()
    self.assertEqual(len(active_missions), 1)
    self.assertEqual(active_missions[0].title, response.title)
    self.assertEqual(active_missions[0].mission_id, response.mission_id)
    self.assertEqual(active_missions[0].career_id, "career_data_analyst")
    self.assertEqual(active_missions[0].role_id, "mentor_ying")
    self.assertEqual(active_missions[0].difficulty, "easy")
    self.assertEqual(active_missions[0].status, "active")
    self.assertGreater(active_missions[0].reward_xp, 0)
    self.assertGreater(len(active_missions[0].reward_skills), 0)
    self.assertGreater(len(active_missions[0].evaluation_criteria), 0)

  def test_generate_mission_abandons_previous_active(self):
    """Tests that generating a new mission automatically sets previous active ones to failed."""
    prev_mission = models.MissionRecord(
      user_id=TEST_PLAYER_ID,
        mission_id="prev_mission_id",
        title="Prev Mission",
        description="Prev Description",
        mock_data_url="https://example.com/prev",
        delivery_requirements_json="[]",
        status="active",
        feynman_active=False,
    )
    self.db_session.add(prev_mission)
    self.db_session.commit()

    # Generate new mission
    req = MissionGenerateRequest(role_id="mentor_ling", difficulty="easy")
    response = self.run_async(generate_mission(
        req, self.db_session, TEST_PLAYER_ID, get_mission_orchestrator(),
    ))

    # Check previous mission state was updated to failed
    self.db_session.refresh(prev_mission)
    self.assertEqual(prev_mission.status, "failed")

    # New mission is active
    active_missions = self.db_session.query(models.MissionRecord).filter_by(
      user_id=TEST_PLAYER_ID, status="active"
    ).all()
    self.assertEqual(len(active_missions), 1)
    self.assertEqual(active_missions[0].mission_id, response.mission_id)


class TestMissionUnwrap(unittest.TestCase):
  """``_unwrap_to_required_keys`` accepts deeply wrapped LLM outputs."""

  required = ("title", "description", "mock_data_url", "delivery_requirements")

  def _payload(self):
    return {
        "title": "T",
        "description": "D",
        "mock_data_url": "https://x",
        "delivery_requirements": ["a"],
    }

  def test_flat_payload_passes_through(self):
    p = self._payload()
    self.assertIs(agent._unwrap_to_required_keys(p, self.required), p)

  def test_one_level_nested(self):
    p = {"task": self._payload()}
    self.assertEqual(agent._unwrap_to_required_keys(p, self.required)["title"], "T")

  def test_two_level_nested(self):
    p = {"envelope": {"task_config": self._payload()}}
    self.assertEqual(agent._unwrap_to_required_keys(p, self.required)["title"], "T")

  def test_missing_required_returns_none(self):
    p = {"task": {"title": "T", "description": "D"}}
    self.assertIsNone(agent._unwrap_to_required_keys(p, self.required))


class TestMissionFallbackContract(unittest.TestCase):
  """Fallback dict must satisfy MissionGenerateResponse."""

  def test_generic_fallback_validates(self):
    payload = agent._generic_mission_fallback("mentor_ling", "easy")
    MissionGenerateResponse.model_validate(payload)
