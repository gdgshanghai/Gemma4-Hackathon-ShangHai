"""Unit tests for the EvaluationService."""

import unittest
from fastapi import HTTPException
from tests.base import BaseDbTestCase, TEST_PLAYER_ID
from app.models import orm as models
from app.models.schemas import (
    EvaluationExperienceGains,
    SubmissionEvaluateRequest,
    SubmissionEvaluateResponse,
)
from app.services import agent
from app.services.agents.base import EvaluationContext, SubagentResult
from app.services.eval import evaluate_user_submission
from app.services.factory import (
    get_artifact_storage,
    get_evaluation_orchestrator,
)
from app.services.orchestrators import EvaluationOrchestrator


class _FakeEvalSubagent:
  """Returns a fixed evaluation payload regardless of context."""

  name = "fake.evaluate"

  def __init__(self, payload: dict) -> None:
    self._payload = payload

  async def run(self, ctx: EvaluationContext) -> SubagentResult[dict]:
    return SubagentResult(payload=dict(self._payload))

  async def fallback(self, ctx: EvaluationContext) -> SubagentResult[dict]:
    return SubagentResult(payload=dict(self._payload), used_fallback=True)


def _orchestrator_with(payload: dict) -> EvaluationOrchestrator:
  return EvaluationOrchestrator(
      eval_subagent=_FakeEvalSubagent(payload),
      storage=get_artifact_storage(),
  )


class TestEvaluationService(BaseDbTestCase):
  """Evaluation Service testing suite."""

  def test_evaluate_submission_gains_experience_and_updates_db(self):
    """Tests that evaluation correctly processes user text, allocates XP, and updates progress."""
    user_id = TEST_PLAYER_ID
    mission_id = "test_mission_123"

    # Setup database state with an active mission to evaluate
    active_mission = models.MissionRecord(
        user_id=user_id,
        mission_id=mission_id,
        title="Test Mission",
        description="Test Description",
        mock_data_url="https://example.com/mock",
        delivery_requirements_json="[]",
        status="active",
        feynman_active=False,
    )
    self.db_session.add(active_mission)
    self.db_session.commit()

    # Create evaluation request
    req = SubmissionEvaluateRequest(
        mission_id=mission_id,
        submission_text="Here is my completed work report...",
    )

    # Process evaluation
    response = self.run_async(evaluate_user_submission(
        req, self.db_session, user_id, get_evaluation_orchestrator(),
    ))
    self.assertEqual(response.status, "success")
    self.assertIsNotNone(response.feedback)
    self.assertIsNotNone(response.experience_gains)
    self.assertEqual(
        response.mission_status,
        "active" if response.trigger_feynman_challenge else "completed",
    )
    self.assertEqual(response.feynman_active, response.trigger_feynman_challenge)

    # Verify database changes
    self.db_session.refresh(active_mission)
    self.assertEqual(active_mission.submission_text, req.submission_text)
    self.assertEqual(active_mission.feedback, response.feedback)
    self.assertEqual(active_mission.feynman_active, response.trigger_feynman_challenge)

    # Check user total experience was accumulated
    user = self.db_session.query(models.User).filter_by(id=user_id).first()
    self.assertIsNotNone(user)
    self.assertGreater(user.total_xp, 0)

    # Check skill progresses were created / updated
    skill_progresses = self.db_session.query(models.SkillProgress).filter_by(user_id=user_id).all()
    self.assertGreater(len(skill_progresses), 0)
    for sp in skill_progresses:
      self.assertGreater(sp.experience, 0)

  def test_evaluate_missing_mission_returns_404_before_llm(self):
    req = SubmissionEvaluateRequest(
        mission_id="missing_mission",
        submission_text="x",
    )

    with self.assertRaises(HTTPException) as ctx:
      self.run_async(evaluate_user_submission(
          req, self.db_session, TEST_PLAYER_ID, get_evaluation_orchestrator(),
      ))

    self.assertEqual(ctx.exception.status_code, 404)
    self.assertEqual(
        self.db_session.query(models.SkillProgress).filter_by(user_id=TEST_PLAYER_ID).count(),
        0,
    )

  def test_evaluate_non_active_mission_returns_409_before_llm(self):
    mission_id = "completed_mission"
    mission = models.MissionRecord(
        user_id=TEST_PLAYER_ID,
        mission_id=mission_id,
        title="Done",
        description="Done",
        mock_data_url="https://example.com/mock",
        delivery_requirements_json="[]",
        status="completed",
        feynman_active=False,
    )
    self.db_session.add(mission)
    self.db_session.commit()

    req = SubmissionEvaluateRequest(
        mission_id=mission_id,
        submission_text="x",
    )

    with self.assertRaises(HTTPException) as ctx:
      self.run_async(evaluate_user_submission(
          req, self.db_session, TEST_PLAYER_ID, get_evaluation_orchestrator(),
      ))

    self.assertEqual(ctx.exception.status_code, 409)
    self.db_session.refresh(mission)
    self.assertIsNone(mission.feedback)


class TestFallbackContracts(unittest.TestCase):
  """Fallback payloads must conform to the response schema (SSOT)."""

  def test_offline_fallback_matches_response_model_da(self):
    payload = agent._eval_offline_fallback("career_data_analyst")
    response = SubmissionEvaluateResponse(**payload)
    self.assertEqual(response.status, "success")

  def test_error_fallback_matches_response_model_da(self):
    from app.services.skill_catalog import allowed_skills_for
    payload = agent._eval_error_fallback("career_data_analyst")
    response = SubmissionEvaluateResponse(**payload)
    declared = allowed_skills_for("career_data_analyst")
    self.assertTrue(set(payload["experience_gains"]).issubset(declared))
    self.assertGreater(sum(response.experience_gains.root.values()), 0)

  def test_offline_fallback_matches_response_model_se(self):
    payload = agent._eval_offline_fallback("career_software_engineer")
    response = SubmissionEvaluateResponse(**payload)
    self.assertEqual(response.status, "success")

  def test_error_fallback_matches_response_model_se(self):
    from app.services.skill_catalog import allowed_skills_for
    payload = agent._eval_error_fallback("career_software_engineer")
    response = SubmissionEvaluateResponse(**payload)
    declared = allowed_skills_for("career_software_engineer")
    self.assertTrue(set(payload["experience_gains"]).issubset(declared))
    self.assertGreater(sum(response.experience_gains.root.values()), 0)


class TestEvaluationDropsUnknownSkillKeys(BaseDbTestCase):
  """Unknown skill keys returned by LLM must not leak into DB or response."""

  def test_unknown_skill_keys_are_dropped_consistently(self):
    user_id = TEST_PLAYER_ID
    mission_id = "test_mission_unknown_skill"

    self.db_session.add(models.MissionRecord(
        user_id=user_id, mission_id=mission_id,
        title="t", description="d", mock_data_url="u",
        delivery_requirements_json="[]", status="active", feynman_active=False,
    ))
    self.db_session.commit()

    async def fake_eval(submission_text, mission_description, career_id="career_data_analyst"):
      return {
          "status": "success",
          "feedback": "ok",
          "experience_gains": {
              "skill_unknown": 99,
              "skill_data_cleaning": 10,
          },
          "trigger_feynman_challenge": False,
          "feynman_question": None,
      }

    orchestrator = _orchestrator_with({
        "status": "success",
        "feedback": "ok",
        "experience_gains": {
            "skill_unknown": 99,
            "skill_data_cleaning": 10,
        },
        "trigger_feynman_challenge": False,
        "feynman_question": None,
    })
    req = SubmissionEvaluateRequest(mission_id=mission_id, submission_text="x")
    response = self.run_async(evaluate_user_submission(
        req, self.db_session, user_id, orchestrator,
    ))

    # API response only carries career-whitelisted keys.
    gains = response.experience_gains.root
    self.assertEqual(gains["skill_data_cleaning"], 10)
    self.assertNotIn("skill_unknown", gains)

    # DB credit must mirror the API response, not the raw LLM payload.
    user = self.db_session.query(models.User).filter_by(id=user_id).first()
    self.assertEqual(user.total_xp, 10)
    progresses = {
        sp.skill_id: sp.experience
        for sp in self.db_session.query(models.SkillProgress)
        .filter_by(user_id=user_id).all()
    }
    self.assertEqual(progresses, {"skill_data_cleaning": 10})


class TestMissionRecordExperienceGainsPassthrough(BaseDbTestCase):
  """ORM getter is career-agnostic; service layer owns whitelisting."""

  def test_keys_from_multiple_careers_preserved(self):
    # /user/sync must return XP from every career the player has played,
    # not just the currently selected one. Filtering at the ORM layer used
    # to silently erase legitimate SE skill XP on data-analyst-default players.
    rec = models.MissionRecord(
        user_id=TEST_PLAYER_ID,
        mission_id="m_legacy",
        title="t", description="d", mock_data_url="https://x/y",
        delivery_requirements_json="[]",
        experience_gains_json='{"skill_data_cleaning": 7, "skill_code_quality": 4}',
        status="completed", feynman_active=False,
    )
    self.assertEqual(
        rec.experience_gains,
        {"skill_data_cleaning": 7, "skill_code_quality": 4},
    )

  def test_malformed_json_returns_empty(self):
    rec = models.MissionRecord(
        user_id=TEST_PLAYER_ID,
        mission_id="m_bad",
        title="t", description="d", mock_data_url="https://x/y",
        delivery_requirements_json="[]",
        experience_gains_json="not json",
        status="completed", feynman_active=False,
    )
    self.assertEqual(rec.experience_gains, {})

  def test_non_int_values_dropped(self):
    rec = models.MissionRecord(
        user_id=TEST_PLAYER_ID,
        mission_id="m_floats",
        title="t", description="d", mock_data_url="https://x/y",
        delivery_requirements_json="[]",
        experience_gains_json='{"skill_data_cleaning": 5, "skill_business_insight": "abc"}',
        status="completed", feynman_active=False,
    )
    self.assertEqual(rec.experience_gains, {"skill_data_cleaning": 5})


class TestSoftwareEngineerEvaluation(BaseDbTestCase):
  """SE missions must credit SE skill keys (regression: previously dropped)."""

  def test_evaluate_software_engineer_credits_correct_skills(self):
    user_id = TEST_PLAYER_ID
    # mission_id encodes the software_engineer career via the conventional
    # prefix produced by app.services.mission.generate_mission.
    mission_id = "mvp_mission_software_bug_hunter_01"

    self.db_session.add(models.MissionRecord(
        user_id=user_id, mission_id=mission_id,
        title="t", description="d", mock_data_url="https://x/y",
        delivery_requirements_json="[]", status="active", feynman_active=False,
    ))
    self.db_session.commit()

    async def fake_eval(submission_text, mission_description, career_id="career_data_analyst"):
      # Assert the SE career was correctly inferred and forwarded.
      assert career_id == "career_software_engineer", career_id
      return {
          "status": "success",
          "feedback": "PR looks solid.",
          "experience_gains": {
              "skill_debugging": 8,
              "skill_unit_testing": 4,
              "skill_data_cleaning": 99,  # DA key — must be dropped by SE whitelist
          },
          "trigger_feynman_challenge": False,
          "feynman_question": None,
      }

    # Custom subagent asserts the resolved career_id matches the SE inference.
    class _AssertingSubagent:
      name = "assert.evaluate"
      async def run(self, ctx):
        assert ctx.career_id == "career_software_engineer", ctx.career_id
        return SubagentResult(payload={
            "status": "success",
            "feedback": "PR looks solid.",
            "experience_gains": {
                "skill_debugging": 8,
                "skill_unit_testing": 4,
                "skill_data_cleaning": 99,
            },
            "trigger_feynman_challenge": False,
            "feynman_question": None,
        })
      async def fallback(self, ctx):
        return await self.run(ctx)

    orchestrator = EvaluationOrchestrator(
        eval_subagent=_AssertingSubagent(),
        storage=get_artifact_storage(),
    )
    req = SubmissionEvaluateRequest(mission_id=mission_id, submission_text="x")
    response = self.run_async(evaluate_user_submission(
        req, self.db_session, user_id, orchestrator,
    ))

    gains = response.experience_gains.root
    self.assertEqual(gains, {"skill_debugging": 8, "skill_unit_testing": 4})
    self.assertNotIn("skill_data_cleaning", gains)

    progresses = {
        sp.skill_id: sp.experience
        for sp in self.db_session.query(models.SkillProgress)
        .filter_by(user_id=user_id).all()
    }
    self.assertEqual(progresses, {"skill_debugging": 8, "skill_unit_testing": 4})

    user = self.db_session.query(models.User).filter_by(id=user_id).first()
    self.assertEqual(user.total_xp, 12)

