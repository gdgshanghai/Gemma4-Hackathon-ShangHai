"""SQLAlchemy database models for CareerCraft persistence."""

import json
import logging

from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.session import base

logger = logging.getLogger(__name__)


class User(base):
  """User profile containing player status and aggregate progress."""

  __tablename__ = "users"

  id = Column(String, primary_key=True)
  current_career_id = Column(String, nullable=True, default="")
  total_xp = Column(Integer, nullable=False, default=0)

  # Relationships for cascade deletion and easy joining
  skills = relationship(
      "SkillProgress",
      back_populates="user",
      cascade="all, delete-orphan",
  )
  missions = relationship(
      "MissionRecord",
      back_populates="user",
      cascade="all, delete-orphan",
  )


class SkillProgress(base):
  """Skill node level and experience progression per player."""

  __tablename__ = "skill_progress"

  id = Column(Integer, primary_key=True, autoincrement=True)
  user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
  skill_id = Column(String, nullable=False)
  level = Column(Integer, nullable=False, default=0)
  experience = Column(Integer, nullable=False, default=0)

  __table_args__ = (
      UniqueConstraint("user_id", "skill_id", name="uq_user_skill"),
  )

  user = relationship("User", back_populates="skills")


class MissionRecord(base):
  """Active and historical missions undertaken by players."""

  __tablename__ = "mission_records"

  id = Column(Integer, primary_key=True, autoincrement=True)
  user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
  mission_id = Column(String, nullable=False)
  career_id = Column(String, nullable=True)
  role_id = Column(String, nullable=True)
  title = Column(String, nullable=False)
  description = Column(Text, nullable=False)
  mock_data_url = Column(String, nullable=False)
  # Filename of the locally-stored artifact under generated_dir(). Nullable
  # so legacy rows produced before PR-3 (which only stored an external URL)
  # remain valid; new rows always set both columns.
  mock_data_filename = Column(String, nullable=True)
  
  # Storing lists and dictionaries as serialized JSON text
  delivery_requirements_json = Column(Text, nullable=False, default="[]")
  difficulty = Column(String, nullable=False, default="medium")
  task_direction = Column(String, nullable=True)
  mission_style = Column(String, nullable=True)
  reward_xp = Column(Integer, nullable=False, default=150)
  reward_skills_json = Column(Text, nullable=False, default="[]")
  evaluation_criteria_json = Column(Text, nullable=False, default="[]")
  display_metadata_json = Column(Text, nullable=False, default="{}")
  status = Column(String, nullable=False, default="active")  # "active", "completed", "failed"
  submission_text = Column(Text, nullable=True)
  feedback = Column(Text, nullable=True)
  experience_gains_json = Column(Text, nullable=True, default="{}")
  
  # Feynman challenge parameters
  feynman_active = Column(Boolean, nullable=False, default=False)
  feynman_question = Column(String, nullable=True)
  feynman_answer = Column(Text, nullable=True)
  feynman_feedback = Column(Text, nullable=True)

  user = relationship("User", back_populates="missions")

  @property
  def delivery_requirements(self) -> list[str]:
    """Decodes delivery requirements from JSON string."""
    if not self.delivery_requirements_json:
      return []
    try:
      return json.loads(self.delivery_requirements_json)
    except json.JSONDecodeError:
      logger.warning(
          "Malformed delivery_requirements_json on mission %s: %.120r",
          self.id, self.delivery_requirements_json,
      )
      return []

  @delivery_requirements.setter
  def delivery_requirements(self, val: list[str]) -> None:
    """Encodes delivery requirements list to JSON string."""
    self.delivery_requirements_json = json.dumps(val)

  @property
  def reward_skills(self) -> list[str]:
    """Decodes UI reward-skill identifiers from JSON string."""
    if not self.reward_skills_json:
      return []
    try:
      raw = json.loads(self.reward_skills_json)
    except json.JSONDecodeError:
      logger.warning(
          "Malformed reward_skills_json on mission %s: %.120r",
          self.id, self.reward_skills_json,
      )
      return []
    if not isinstance(raw, list):
      logger.warning(
          "reward_skills_json on mission %s is not a list: %.120r",
          self.id, self.reward_skills_json,
      )
      return []
    return [item for item in raw if isinstance(item, str)]

  @reward_skills.setter
  def reward_skills(self, val: list[str]) -> None:
    """Encodes UI reward-skill identifiers to JSON string."""
    self.reward_skills_json = json.dumps(val)

  @property
  def evaluation_criteria(self) -> list[str]:
    """Decodes task evaluation criteria from JSON string."""
    if not self.evaluation_criteria_json:
      return []
    try:
      raw = json.loads(self.evaluation_criteria_json)
    except json.JSONDecodeError:
      logger.warning(
          "Malformed evaluation_criteria_json on mission %s: %.120r",
          self.id, self.evaluation_criteria_json,
      )
      return []
    if not isinstance(raw, list):
      logger.warning(
          "evaluation_criteria_json on mission %s is not a list: %.120r",
          self.id, self.evaluation_criteria_json,
      )
      return []
    return [item for item in raw if isinstance(item, str)]

  @evaluation_criteria.setter
  def evaluation_criteria(self, val: list[str]) -> None:
    """Encodes task evaluation criteria to JSON string."""
    self.evaluation_criteria_json = json.dumps(val)

  @property
  def display_metadata(self) -> dict[str, object]:
    """Decodes AI display metadata from JSON string."""
    if not self.display_metadata_json:
      return {}
    try:
      raw = json.loads(self.display_metadata_json)
    except json.JSONDecodeError:
      logger.warning(
          "Malformed display_metadata_json on mission %s: %.120r",
          self.id, self.display_metadata_json,
      )
      return {}
    if not isinstance(raw, dict):
      logger.warning(
          "display_metadata_json on mission %s is not an object: %.120r",
          self.id, self.display_metadata_json,
      )
      return {}
    return raw

  @display_metadata.setter
  def display_metadata(self, val: dict[str, object]) -> None:
    """Encodes AI display metadata dict to JSON string."""
    self.display_metadata_json = json.dumps(val)

  @property
  def experience_gains(self) -> dict[str, int]:
    """Decode the stored experience-gain mapping verbatim.

    No key whitelisting is applied here — career-aware filtering lives in
    ``app.services.eval`` where the player's career_id is known. Keeping this
    getter career-agnostic prevents /user/sync from erasing legitimate XP
    when a row belongs to a career different from the caller's default.
    """
    if not self.experience_gains_json:
      return {}
    try:
      raw = json.loads(self.experience_gains_json)
    except json.JSONDecodeError:
      logger.warning(
          "Malformed experience_gains_json on mission %s: %.120r",
          self.id, self.experience_gains_json,
      )
      return {}
    if not isinstance(raw, dict):
      logger.warning(
          "experience_gains_json on mission %s is not an object: %.120r",
          self.id, self.experience_gains_json,
      )
      return {}
    return {k: v for k, v in raw.items() if isinstance(v, int) and not isinstance(v, bool)}

  @experience_gains.setter
  def experience_gains(self, val: dict[str, int]) -> None:
    """Encodes experience gains dict to JSON string."""
    self.experience_gains_json = json.dumps(val)
