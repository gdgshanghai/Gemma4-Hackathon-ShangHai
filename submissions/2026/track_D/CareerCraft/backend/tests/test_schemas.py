"""Tests for tightened Pydantic API contracts."""

import unittest

from pydantic import ValidationError

from app.models.schemas import (
    EvaluationExperienceGains,
    FeynmanSubmitResponse,
    MissionGenerateResponse,
    SubmissionEvaluateResponse,
)


class TestMissionGenerateResponse(unittest.TestCase):
  def _base(self, **overrides):
    payload = {
        "mission_id": "m1",
        "title": "t",
        "description": "d",
        "mock_data_url": "https://example.com/x.csv",
        "delivery_requirements": ["a"],
    }
    payload.update(overrides)
    return payload

  def test_accepts_valid_http_url(self):
    MissionGenerateResponse.model_validate(self._base())

  def test_rejects_non_url_mock_data_url(self):
    with self.assertRaises(ValidationError):
      MissionGenerateResponse.model_validate(self._base(mock_data_url="待补充"))

  def test_rejects_empty_mock_data_url(self):
    with self.assertRaises(ValidationError):
      MissionGenerateResponse.model_validate(self._base(mock_data_url=""))


class TestSubmissionEvaluateResponse(unittest.TestCase):
  def _base(self, **overrides):
    payload = {
        "status": "success",
        "feedback": "ok",
        "experience_gains": {"skill_data_cleaning": 5},
        "trigger_feynman_challenge": False,
        "feynman_question": None,
    }
    payload.update(overrides)
    return payload

  def test_accepts_success_and_fail(self):
    SubmissionEvaluateResponse.model_validate(self._base(status="success"))
    SubmissionEvaluateResponse.model_validate(self._base(status="fail"))

  def test_rejects_non_enum_status(self):
    with self.assertRaises(ValidationError):
      SubmissionEvaluateResponse.model_validate(self._base(status="通过"))
    with self.assertRaises(ValidationError):
      SubmissionEvaluateResponse.model_validate(self._base(status="passed"))

  def test_experience_gains_passes_through_arbitrary_skill_keys(self):
    # RootModel: per-career whitelisting moved to service layer
    # (app.services.eval). The Pydantic model only enforces value type/sign.
    resp = SubmissionEvaluateResponse.model_validate(
        self._base(experience_gains={"skill_data_cleaning": 5, "skill_debugging": 7})
    )
    self.assertEqual(
        resp.experience_gains.root,
        {"skill_data_cleaning": 5, "skill_debugging": 7},
    )

  def test_negative_experience_gain_rejected(self):
    with self.assertRaises(ValidationError):
      SubmissionEvaluateResponse.model_validate(
          self._base(experience_gains={"skill_data_cleaning": -1})
      )


class TestFeynmanSubmitResponse(unittest.TestCase):
  def test_status_must_be_success(self):
    FeynmanSubmitResponse(status="success", feedback="x")
    with self.assertRaises(ValidationError):
      FeynmanSubmitResponse(status="fail", feedback="x")


class TestEvaluationExperienceGains(unittest.TestCase):
  def test_root_model_accepts_any_skill_key(self):
    obj = EvaluationExperienceGains.model_validate(
        {"skill_data_cleaning": 3, "skill_debugging": 7}
    )
    self.assertEqual(obj.root, {"skill_data_cleaning": 3, "skill_debugging": 7})

  def test_root_model_rejects_non_int(self):
    with self.assertRaises(ValidationError):
      EvaluationExperienceGains.model_validate({"skill_data_cleaning": "5"})

  def test_root_model_rejects_bool(self):
    with self.assertRaises(ValidationError):
      EvaluationExperienceGains.model_validate({"skill_data_cleaning": True})


class TestMissionRecordResponseLegacyUrlNormalization(unittest.TestCase):
  def _base(self, mock_data_url):
    return {
        "mission_id": "m1",
        "title": "t", "description": "d",
        "mock_data_url": mock_data_url,
        "delivery_requirements": ["x"],
        "status": "completed",
        "experience_gains": {},
        "feynman_active": False,
    }

  def test_valid_url_preserved(self):
    from app.models.schemas import MissionRecordResponse
    resp = MissionRecordResponse.model_validate(self._base("https://example.com/x.csv"))
    self.assertEqual(resp.mock_data_url, "https://example.com/x.csv")

  def test_empty_string_normalized_to_placeholder(self):
    from app.models.schemas import MissionRecordResponse
    resp = MissionRecordResponse.model_validate(self._base(""))
    self.assertEqual(resp.mock_data_url, "https://example.com/legacy")

  def test_non_http_path_normalized_to_placeholder(self):
    from app.models.schemas import MissionRecordResponse
    resp = MissionRecordResponse.model_validate(self._base("local/foo.csv"))
    self.assertEqual(resp.mock_data_url, "https://example.com/legacy")


if __name__ == "__main__":
  unittest.main()
