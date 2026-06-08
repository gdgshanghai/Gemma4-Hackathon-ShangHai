"""Single source of truth for legal skill IDs per career.

Used by:
- ``app.services.agent.evaluate_submission`` to build the per-career JSON
  Schema enum for ``experience_gains`` keys.
- ``app.services.eval.evaluate_user_submission`` to drop LLM keys that fall
  outside the player's career before persisting.

Skill IDs mirror ``docs/skill_tree_definition.md``; keep both in sync when
extending the tree.
"""

from __future__ import annotations

DATA_ANALYST_SKILLS: frozenset[str] = frozenset({
    "skill_data_cleaning",
    "skill_data_quality",
    "skill_exploratory_analysis",
    "skill_business_insight",
    "skill_data_storytelling",
    "skill_strategic_recommendation",
    "skill_stakeholder_mgmt",
    "skill_kpi_system_design",
    "skill_dashboard_design",
    "skill_drill_down_analysis",
    "skill_root_cause_analysis",
})

SOFTWARE_ENGINEER_SKILLS: frozenset[str] = frozenset({
    "skill_debugging",
    "skill_unit_testing",
    "skill_code_quality",
    "skill_api_design",
    "skill_communication",
    "skill_refactoring",
    "skill_software_design",
    "skill_perf_troubleshooting",
    "skill_sql_optimization",
    "skill_incident_response",
})

CAREER_SKILLS: dict[str, frozenset[str]] = {
    "career_data_analyst": DATA_ANALYST_SKILLS,
    "career_software_engineer": SOFTWARE_ENGINEER_SKILLS,
}

# role_id (mentor) → career_id. Mirrors app.services.mission_catalog._ROLE_TO_CATALOG.
ROLE_TO_CAREER: dict[str, str] = {
    "mentor_ying": "career_data_analyst",
    "mentor_ling": "career_software_engineer",
}

DEFAULT_CAREER_ID = "career_data_analyst"


def allowed_skills_for(career_id: str | None) -> frozenset[str]:
  """Return the legal skill-id set for ``career_id``.

  Unknown / empty inputs fall back to :data:`DEFAULT_CAREER_ID` so callers in
  legacy paths (missing ``current_career_id`` on older user rows) still get a
  usable whitelist rather than an exception.
  """
  if not career_id:
    return CAREER_SKILLS[DEFAULT_CAREER_ID]
  return CAREER_SKILLS.get(career_id, CAREER_SKILLS[DEFAULT_CAREER_ID])


def infer_career_id(
    *,
    mission_id: str | None = None,
    role_id: str | None = None,
    fallback: str | None = None,
) -> str:
  """Best-effort career resolution from any available signal.

  Resolution order:
  1. ``mission_id`` prefix (``mvp_mission_data_`` / ``mvp_mission_software_``).
  2. ``mission_id`` containing a known mentor role token
     (covers legacy fallback ids like ``mvp_mission_mentor_ling_beginner``).
  3. Explicit ``role_id``.
  4. ``fallback`` (typically ``User.current_career_id``).
  5. :data:`DEFAULT_CAREER_ID`.
  """
  if mission_id:
    if mission_id.startswith("mvp_mission_data_"):
      return "career_data_analyst"
    if mission_id.startswith("mvp_mission_software_"):
      return "career_software_engineer"
    for token, career in ROLE_TO_CAREER.items():
      if token in mission_id:
        return career
  if role_id and role_id in ROLE_TO_CAREER:
    return ROLE_TO_CAREER[role_id]
  if fallback in CAREER_SKILLS:
    return fallback  # type: ignore[return-value]
  return DEFAULT_CAREER_ID
