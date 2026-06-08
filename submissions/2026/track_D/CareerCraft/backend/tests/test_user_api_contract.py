"""Contract tests for user sync and Feynman endpoints."""

from unittest.mock import patch

from tests.base import BaseDbTestCase, TEST_PLAYER_ID
from app.api.v1.user import submit_feynman_challenge, sync_user_state
from app.models import orm as models, schemas


class _FakeFeynmanOrchestrator:
  async def review(self, ctx):
    return "Feynman answer accepted."


class TestUserApiContract(BaseDbTestCase):
  def test_sync_infers_legacy_mission_career_from_id_prefix(self):
    self.db_session.add(models.User(
        id=TEST_PLAYER_ID,
        current_career_id="career_software_engineer",
        total_xp=0,
    ))
    self.db_session.add(models.MissionRecord(
        user_id=TEST_PLAYER_ID,
        mission_id="mvp_mission_data_1",
        title="Data mission",
        description="Data mission",
        mock_data_url="https://example.com/mock.csv",
        delivery_requirements_json="[]",
        status="active",
        feynman_active=False,
    ))
    self.db_session.commit()

    response = self.run_async(sync_user_state(self.db_session, TEST_PLAYER_ID))

    self.assertEqual(len(response.missions), 1)
    self.assertEqual(response.missions[0].career_id, "career_data_analyst")
    self.assertEqual(response.missions[0].role_id, "mentor_ying")
    self.assertEqual(response.missions[0].difficulty, "medium")
    self.assertGreater(response.missions[0].reward_xp, 0)

  def test_sync_rebuilds_local_artifact_url_from_current_public_base(self):
    self.db_session.add(models.User(
        id=TEST_PLAYER_ID,
        current_career_id="career_data_analyst",
        total_xp=0,
    ))
    self.db_session.add(models.MissionRecord(
        user_id=TEST_PLAYER_ID,
        mission_id="mvp_mission_data_1",
        title="Data mission",
        description="Data mission",
        mock_data_url="http://localhost:8000/mock_data/old.csv",
        mock_data_filename="artifact.csv",
        delivery_requirements_json="[]",
        status="active",
        feynman_active=False,
    ))
    self.db_session.commit()

    with patch("app.services.storage.artifact_store.settings") as mock_settings:
      mock_settings.mock_data_public_base = "https://career.example.com/mock_data"
      response = self.run_async(sync_user_state(self.db_session, TEST_PLAYER_ID))

    self.assertEqual(
        response.missions[0].mock_data_url,
        "https://career.example.com/mock_data/artifact.csv",
    )

  def test_submit_feynman_marks_mission_completed(self):
    self.db_session.add(models.User(
        id=TEST_PLAYER_ID,
        current_career_id="career_data_analyst",
        total_xp=0,
    ))
    mission = models.MissionRecord(
        user_id=TEST_PLAYER_ID,
        mission_id="mvp_mission_data_1",
        title="Data mission",
        description="Data mission",
        mock_data_url="https://example.com/mock.csv",
        delivery_requirements_json="[]",
        status="active",
        feynman_active=True,
        feynman_question="Explain retention.",
    )
    self.db_session.add(mission)
    self.db_session.commit()

    response = self.run_async(submit_feynman_challenge(
        schemas.FeynmanSubmitRequest(
            mission_id="mvp_mission_data_1",
            answer="Retention means users come back after the first visit.",
        ),
        self.db_session,
        TEST_PLAYER_ID,
        _FakeFeynmanOrchestrator(),
    ))

    self.db_session.refresh(mission)
    self.assertEqual(response.status, "success")
    self.assertEqual(response.mission_status, "completed")
    self.assertEqual(mission.status, "completed")
    self.assertFalse(mission.feynman_active)
    self.assertEqual(mission.feynman_answer, "Retention means users come back after the first visit.")
