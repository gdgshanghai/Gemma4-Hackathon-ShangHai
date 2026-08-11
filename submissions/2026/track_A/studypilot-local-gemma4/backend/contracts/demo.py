"""Strict contracts for the local-only demonstration workspace."""

from __future__ import annotations

from datetime import date, time

from pydantic import Field

from backend.contracts.calibration_tools import CalibrationSubject, CalibrationTaskType
from backend.contracts.models import StrictModel


class DemoCalibrationGroup(StrictModel):
    subject: CalibrationSubject
    task_type: CalibrationTaskType
    conservative_minutes: int = Field(ge=5, le=600)


class DemoScenarioResponse(StrictModel):
    scenario_id: str
    label: str
    planning_date: date
    start_time: time
    sleep_time: time
    school_brief_text: str
    child_report_text: str
    weekly_calibration_text: str
    weekly_calibration_groups: tuple[DemoCalibrationGroup, ...]


class DemoResetRequest(StrictModel):
    expected_session_id: str | None = Field(default=None, min_length=1, max_length=128)
