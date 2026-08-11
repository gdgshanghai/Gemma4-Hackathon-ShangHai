"""Strict contracts for the child evening workflow."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from backend.contracts.models import (
    CapacityProof,
    EstimateBreakdownItem,
    PlanBlock,
    SessionStage,
    StrictModel,
    TaskCompletionState,
)
from backend.domain.study_time import EARLIEST_STUDY_START, LATEST_STUDY_END


def _require_supported_study_window(start_time: time, sleep_time: time) -> None:
    if sleep_time <= start_time:
        raise ValueError("sleep_time must be after start_time")
    if start_time < EARLIEST_STUDY_START:
        raise ValueError("start_time cannot be before 18:45")
    if sleep_time > LATEST_STUDY_END:
        raise ValueError("sleep_time cannot be after the 22:20 study stop")


class EveningCreateRequest(StrictModel):
    start_time: time
    sleep_time: time
    expected_version: Literal[0] = 0

    @model_validator(mode="after")
    def require_forward_window(self) -> EveningCreateRequest:
        _require_supported_study_window(self.start_time, self.sleep_time)
        return self

    @property
    def window_minutes(self) -> int:
        start = self.start_time.hour * 60 + self.start_time.minute
        end = self.sleep_time.hour * 60 + self.sleep_time.minute
        return end - start

    @field_validator("expected_version", mode="before")
    @classmethod
    def require_integer_zero(cls, value: object) -> object:
        if isinstance(value, bool) or value != 0:
            raise ValueError("expected_version must be integer zero")
        return value


class EveningTimeBoundaryRequest(StrictModel):
    start_time: time
    sleep_time: time
    expected_version: int = Field(ge=1)

    @model_validator(mode="after")
    def require_forward_window(self) -> EveningTimeBoundaryRequest:
        _require_supported_study_window(self.start_time, self.sleep_time)
        return self

    @property
    def window_minutes(self) -> int:
        start = self.start_time.hour * 60 + self.start_time.minute
        end = self.sleep_time.hour * 60 + self.sleep_time.minute
        return end - start


class EveningIntakeRequest(StrictModel):
    text: str = Field(min_length=1, max_length=10_000)
    expected_version: int = Field(ge=1)


class EveningConfirmRequest(StrictModel):
    expected_version: int = Field(ge=1)


class EveningPlanRequest(StrictModel):
    expected_version: int = Field(ge=1)
    reason: Literal[
        "initial",
        "child_reorder",
        "focus_pace",
        "manual_deadline_risk",
    ]
    preferred_order: list[str] | None = None
    deadline_risk_task_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_deadline_risk_action(self) -> EveningPlanRequest:
        if len(self.deadline_risk_task_ids) != len(set(self.deadline_risk_task_ids)):
            raise ValueError("deadline_risk_task_ids must be unique")
        if self.reason == "manual_deadline_risk":
            if not self.deadline_risk_task_ids:
                raise ValueError("manual_deadline_risk requires an explicit task")
        elif self.deadline_risk_task_ids:
            raise ValueError("deadline risk tasks require manual_deadline_risk")
        return self


class EveningCommitRequest(StrictModel):
    expected_version: int = Field(ge=1)


class LargestDeviationInput(StrictModel):
    task_id: str = Field(min_length=1)
    actual_minutes: int = Field(ge=1, le=720)


class EveningCloseRequest(StrictModel):
    expected_version: int = Field(ge=1)
    unfinished_task_ids: list[str]
    largest_deviation: LargestDeviationInput | None = None
    note: str | None = Field(default=None, max_length=2_000)


class IntakeDraftTask(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    subject: str | None = Field(default=None, max_length=100)
    completion_state: TaskCompletionState = TaskCompletionState.PENDING
    child_estimate_minutes: int | None = Field(default=None, ge=0, le=720)
    deadline_text: str | None = Field(default=None, max_length=100)
    total_units: int | None = Field(default=None, ge=1, le=10_000)
    completed_units: int | None = Field(default=None, ge=0, le=10_000)
    notes: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_progress_units(self) -> IntakeDraftTask:
        if (self.total_units is None) != (self.completed_units is None):
            raise ValueError("total_units and completed_units must be supplied together")
        if (
            self.total_units is not None
            and self.completed_units is not None
            and self.completed_units > self.total_units
        ):
            raise ValueError("completed_units cannot exceed total_units")
        return self


CoverageNote = Annotated[str, Field(min_length=1, max_length=300)]


class IntakeFixedBlock(StrictModel):
    label: str = Field(min_length=1, max_length=100)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def require_forward_interval(self) -> IntakeFixedBlock:
        if self.end_time <= self.start_time:
            raise ValueError("fixed block end_time must be after start_time")
        return self


class SaveIntakeDraftArguments(StrictModel):
    tasks: list[IntakeDraftTask] = Field(min_length=1, max_length=100)
    fixed_blocks: list[IntakeFixedBlock] = Field(default_factory=list, max_length=10)
    coverage_notes: list[CoverageNote] = Field(default_factory=list, max_length=20)


class IntakeDraftView(StrictModel):
    id: str
    tasks: list[IntakeDraftTask]
    fixed_blocks: list[IntakeFixedBlock] = Field(default_factory=list, max_length=10)
    coverage_notes: list[CoverageNote] = Field(default_factory=list, max_length=20)


class InventoryTaskView(StrictModel):
    id: str
    title: str
    subject: str | None
    task_type: str | None
    completion_state: TaskCompletionState
    estimated_minutes: int
    conservative_minutes: int
    priority: int
    must_do_tonight: bool
    due_at: datetime | None
    child_estimate_minutes: int | None
    estimate_source: Literal[
        "history_p80",
        "parent_range",
        "child_adjusted",
        "domain_default",
    ]
    estimate_confidence: Literal["low", "medium", "high"]
    notes: str | None
    assignment_id: str | None = None
    deadline_text: str | None = None
    remaining_percent: int = Field(default=100, ge=0, le=100)
    planning_bucket: Literal[
        "tonight_required", "tonight_advance", "future_scheduled"
    ] = "tonight_required"
    planned_evening_date: date | None = None
    estimate_breakdown: list[EstimateBreakdownItem] = Field(default_factory=list)
    estimate_signature: str | None = None


class FutureAssignmentView(StrictModel):
    assignment_id: str
    title: str
    subject: str | None
    deadline_text: str | None
    due_at: datetime | None
    planned_evening_date: date
    remaining_percent: int = Field(ge=1, le=100)
    latest_change_reason: str | None = None


class PaceTargetView(StrictModel):
    task_id: str = Field(min_length=1)
    conservative_minutes: int = Field(ge=0)
    target_minutes: int = Field(ge=0)


class CapacityRecoveryView(StrictModel):
    mode: Literal["start_earlier", "focus_pace", "manual_choice"]
    baseline_shortfall_minutes: int = Field(gt=0)
    earliest_start_time: time
    recommended_start_time: time
    speedup_percent: int = Field(ge=0, le=20)
    pace_targets: list[PaceTargetView] = Field(default_factory=list)
    recovered_minutes: int = Field(ge=0)
    residual_shortfall_minutes: int = Field(ge=0)


class PlanView(StrictModel):
    id: str
    plan_version: int = Field(ge=1)
    capacity: CapacityProof
    baseline_capacity: CapacityProof
    blocks: list[PlanBlock]
    ordered_task_ids: list[str]
    deferred_task_ids: list[str]
    future_scheduled_task_ids: list[str] = Field(default_factory=list)
    deadline_risk_task_ids: list[str] = Field(default_factory=list)
    capacity_recovery: CapacityRecoveryView | None = None
    pace_targets: list[PaceTargetView] = Field(default_factory=list)
    reason: str
    committed: bool
    scheduled_optional_minutes: int = Field(ge=0)
    true_surplus_minutes: int = Field(ge=0)
    predicted_finish_at: datetime | None


class OutcomeView(StrictModel):
    id: str
    task_id: str
    completion_state: TaskCompletionState
    actual_minutes: int | None
    note: str | None


class TimeBoundaryView(StrictModel):
    start_time: time
    sleep_time: time
    gross_minutes: int = Field(gt=0)
    fixed_minutes: int = Field(ge=0)
    net_minutes: int = Field(ge=0)


class EveningData(StrictModel):
    narration: str | None = None
    intake_draft: IntakeDraftView | None = None
    coverage_mode: Literal["school_verified", "child_reported"] | None = None
    inventory: list[InventoryTaskView] = Field(default_factory=list)
    plan: PlanView | None = None
    outcomes: list[OutcomeView] = Field(default_factory=list)
    time_boundary: TimeBoundaryView
    future_assignments: list[FutureAssignmentView] = Field(default_factory=list)


class EveningResponse(StrictModel):
    session_id: str
    session_date: date
    planning_date: date
    version: int = Field(ge=0)
    stage: SessionStage
    allowed_actions: list[str]
    trace_id: str
    data: EveningData
