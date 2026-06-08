"""Pydantic models for incoming API requests and outgoing payloads."""

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, RootModel, ValidationInfo, field_validator

logger = logging.getLogger(__name__)

MissionStyle = Literal["ticket", "project", "interview", "feynman"]

_DATA_ANALYST_DIRECTIONS = {"data-cleaning", "sql-analysis", "visualization"}
_SOFTWARE_ENGINEER_DIRECTIONS = {"bug-fix", "unit-test", "api-design"}
_KNOWN_TASK_DIRECTIONS = _DATA_ANALYST_DIRECTIONS | _SOFTWARE_ENGINEER_DIRECTIONS
_ROLE_DIRECTIONS = {
    "mentor_ying": _DATA_ANALYST_DIRECTIONS,
    "mentor_ling": _SOFTWARE_ENGINEER_DIRECTIONS,
}


class MissionDisplayMetadata(BaseModel):
  """AI-authored display fields normalized by the backend."""

  ai_lead: str | None = None
  business_background: str | None = None
  objectives: list[str] = Field(default_factory=list)
  recommended_skills: list[str] = Field(default_factory=list)
  recommended_resources: list[str] = Field(default_factory=list)
  estimated_time: str | None = None


class MissionGenerateRequest(BaseModel):
  """Request payload for dynamically generating a new mission."""

  role_id: str = Field(
      ...,
      description="Unique identifier for the AI mentor/role.",
      examples=["mentor_ling"],
  )
  difficulty: str = Field(
      default="easy",
      description="Requested difficulty level.",
      examples=["easy"],
  )
  task_direction: str | None = Field(
      default=None,
      description="Optional mission direction selected by the player.",
      examples=["data-cleaning"],
  )
  mission_style: MissionStyle | None = Field(
      default=None,
      description="Optional generation style selected by the player.",
      examples=["ticket"],
  )

  @field_validator("task_direction")
  @classmethod
  def _validate_task_direction(
      cls, value: str | None, info: ValidationInfo,
  ) -> str | None:
    if value is None:
      return None
    role_id = info.data.get("role_id")
    allowed = _ROLE_DIRECTIONS.get(role_id, _KNOWN_TASK_DIRECTIONS)
    if value not in allowed:
      allowed_text = ", ".join(sorted(allowed))
      raise ValueError(
          f"task_direction {value!r} is not allowed for role_id {role_id!r}; "
          f"allowed values: {allowed_text}"
      )
    return value


class MissionGenerateResponse(BaseModel):
  """Structured payload representing a generated mission."""

  mission_id: str
  career_id: str | None = None
  role_id: str | None = None
  title: str
  description: str
  mock_data_url: HttpUrl
  delivery_requirements: list[str]
  difficulty: str = "medium"
  task_direction: str | None = None
  mission_style: MissionStyle | None = None
  status: str = "active"
  reward_xp: int = 150
  reward_skills: list[str] = Field(default_factory=list)
  evaluation_criteria: list[str] = Field(default_factory=list)
  display_metadata: MissionDisplayMetadata = Field(default_factory=MissionDisplayMetadata)


class SubmissionEvaluateRequest(BaseModel):
  """Payload for submitting user work to be evaluated."""

  mission_id: str
  submission_text: str = Field(
      ...,
      description="User report content or valid artifact link.",
  )


class EvaluationExperienceGains(RootModel[dict[str, int]]):
  """Free-form mapping of skill_id → XP gain.

  Legal keys are career-scoped and enforced at the service layer (see
  ``app.services.skill_catalog.allowed_skills_for``) rather than as Pydantic
  fields, so the contract can support multiple career trees without a model
  hierarchy. Values must be non-negative ints (bool rejected explicitly to
  avoid Python's ``bool ⊂ int`` silently passing through as 0/1 XP).
  """

  @field_validator("root", mode="before")
  @classmethod
  def _validate_non_negative(cls, raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
      raise ValueError(f"experience_gains must be a dict, got {type(raw).__name__}")
    for key, amount in raw.items():
      if isinstance(amount, bool) or not isinstance(amount, int):
        raise ValueError(
            f"experience_gains[{key!r}] must be int, got {type(amount).__name__}"
        )
      if amount < 0:
        raise ValueError(f"experience_gains[{key!r}] must be >= 0, got {amount}")
    return raw


class SubmissionEvaluateResponse(BaseModel):
  """Structured output of an AI peer evaluation."""

  status: Literal["success", "fail"]
  feedback: str
  experience_gains: EvaluationExperienceGains
  trigger_feynman_challenge: bool
  feynman_question: str | None = None
  mission_status: str | None = None
  feynman_active: bool | None = None


class UserProfileResponse(BaseModel):
  """User profile data payload."""

  id: str
  current_career_id: str | None = ""
  total_xp: int


class SkillProgressResponse(BaseModel):
  """Single skill node progress entry."""

  skill_id: str
  level: int
  experience: int


class MissionRecordResponse(BaseModel):
  """Mission history and state representation."""

  mission_id: str
  career_id: str | None = None
  role_id: str | None = None
  title: str
  description: str
  mock_data_url: str
  delivery_requirements: list[str]
  difficulty: str = "medium"
  task_direction: str | None = None
  mission_style: MissionStyle | None = None
  reward_xp: int = 150
  reward_skills: list[str] = Field(default_factory=list)
  evaluation_criteria: list[str] = Field(default_factory=list)
  display_metadata: MissionDisplayMetadata = Field(default_factory=MissionDisplayMetadata)
  status: str
  submission_text: str | None = None
  feedback: str | None = None
  experience_gains: dict[str, int] = Field(default_factory=dict)
  feynman_active: bool
  feynman_question: str | None = None
  feynman_answer: str | None = None
  feynman_feedback: str | None = None

  @field_validator("mock_data_url", mode="before")
  @classmethod
  def _normalize_legacy_mock_data_url(cls, v: Any) -> str:
    # Historical rows predating the HttpUrl tightening on MissionGenerateResponse
    # may hold empty strings or non-http payloads. Normalize so a single bad
    # row cannot break the entire /user/sync response.
    if not isinstance(v, str) or not v.startswith(("http://", "https://")):
      logger.warning("legacy mock_data_url normalized: %r", v)
      return "https://example.com/legacy"
    return v


class SyncResponse(BaseModel):
  """Aggregation of player states for store synchronization."""

  user: UserProfileResponse
  skills: list[SkillProgressResponse]
  missions: list[MissionRecordResponse]


class UpdateCareerRequest(BaseModel):
  """Payload for shifting player career focus."""

  career_id: str


class UpgradeSkillRequest(BaseModel):
  """Payload to save manual node upgrade events."""

  skill_id: str
  level: int
  experience: int


class FeynmanSubmitRequest(BaseModel):
  """Payload to submit Feynman challenge answers."""

  mission_id: str
  answer: str


class FeynmanSubmitResponse(BaseModel):
  """Structured Feynman-challenge review payload."""

  status: Literal["success"]
  feedback: str
  mission_status: str = "completed"


class CareerResponse(BaseModel):
  """Career track metadata for the world map."""

  career_id: str
  name: str
  description: str
  unlocked: bool
  role_id: str | None = None
  resource_domain: str | None = None
  api_supported: bool = True


class ResourceResponse(BaseModel):
  """Knowledge-base search result displayed by the frontend."""

  doc_id: str
  title: str
  snippet: str
  relevance_score: float
  source: str | None = None
  tags: list[str] = Field(default_factory=list)

