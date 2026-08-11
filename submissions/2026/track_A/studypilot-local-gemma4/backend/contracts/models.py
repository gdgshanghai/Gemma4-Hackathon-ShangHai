"""Pydantic contracts for V13 domain data and API envelopes."""

from __future__ import annotations

from datetime import date, datetime, time
from enum import StrEnum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SessionStage(StrEnum):
    CREATED = "created"
    INTAKE_DRAFT = "intake_draft"
    COVERAGE_PENDING = "coverage_pending"
    INVENTORY_CONFIRMED = "inventory_confirmed"
    PLAN_DRAFT = "plan_draft"
    COMMITTED = "committed"
    CLOSED = "closed"
    CAPACITY_CONFLICT = "capacity_conflict"
    NEEDS_CONFIRMATION = "needs_confirmation"
    MODEL_UNAVAILABLE = "model_unavailable"


class CoverageMode(StrEnum):
    SCHOOL_VERIFIED = "school_verified"
    CHILD_REPORTED = "child_reported"


class TaskCompletionState(StrEnum):
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETED = "completed"
    UNCERTAIN = "uncertain"
    NO_TASK = "no_task"


class Source(StrEnum):
    CHILD = "child"
    SCHOOL = "school"
    BOTH = "both"
    PARENT = "parent"
    SYSTEM = "system"


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
    )


class SchoolBrief(StrictModel):
    id: str = Field(min_length=1)
    brief_date: date
    source_path: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_text: str
    created_at: datetime


class EveningSession(StrictModel):
    id: str = Field(min_length=1)
    session_date: date
    timezone: str = Field(min_length=1)
    sleep_time: time
    stage: SessionStage
    version: int = Field(ge=0)
    available_minutes: int = Field(ge=0)
    school_brief_id: str | None = None
    created_at: datetime
    updated_at: datetime


class EstimateBreakdownItem(StrictModel):
    component: str = Field(min_length=1)
    label: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    remaining_quantity: int | None = Field(default=None, ge=0)
    unit: str | None = None
    reference_minutes: int = Field(ge=0)
    calibrated_minutes: int = Field(ge=0)
    source: Literal[
        "history_p80",
        "parent_range",
        "child_adjusted",
        "domain_default",
    ] = "domain_default"
    confidence: Literal["low", "medium", "high"] = "low"


class TaskItem(StrictModel):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    subject: str | None = None
    task_type: str | None = None
    source: Source
    completion_state: TaskCompletionState
    estimated_minutes: int = Field(ge=0)
    conservative_minutes: int = Field(ge=0)
    priority: int = Field(ge=0)
    must_do_tonight: bool = False
    child_estimate_minutes: int | None = Field(default=None, ge=0)
    estimate_source: Literal[
        "history_p80",
        "parent_range",
        "child_adjusted",
        "domain_default",
    ] = "domain_default"
    estimate_confidence: Literal["low", "medium", "high"] = "low"
    avoidance_score: int = Field(default=0, ge=0, le=3)
    preference_score: int = Field(default=0, ge=0, le=3)
    due_at: datetime | None = None
    school_brief_id: str | None = None
    notes: str | None = None
    assignment_id: str | None = None
    deadline_text: str | None = None
    remaining_percent: int = Field(default=100, ge=0, le=100)
    planning_bucket: Literal[
        "tonight_required", "tonight_advance", "future_scheduled"
    ] = "tonight_required"
    planned_evening_date: date | None = None
    estimate_breakdown: tuple[EstimateBreakdownItem, ...] = ()
    estimate_signature: str | None = None
    created_at: datetime
    updated_at: datetime


class CoverageDiff(StrictModel):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    mode: CoverageMode
    source: Source
    summary: str = Field(min_length=1)
    school_task_id: str | None = None
    reported_task_id: str | None = None
    resolved: bool
    resolved_at: datetime | None = None
    created_at: datetime


class CapacityProof(StrictModel):
    available_minutes: int = Field(ge=0)
    fixed_minutes: int = Field(ge=0)
    task_minutes: int = Field(ge=0)
    buffer_minutes: int = Field(ge=0)
    required_minutes: int = Field(ge=0)
    remaining_minutes: int = Field(ge=0)
    shortfall_minutes: int = Field(ge=0)
    feasible: bool

    @model_validator(mode="after")
    def validate_arithmetic(self) -> CapacityProof:
        expected_required = self.fixed_minutes + self.task_minutes + self.buffer_minutes
        expected_remaining = max(self.available_minutes - expected_required, 0)
        expected_shortfall = max(expected_required - self.available_minutes, 0)
        expected_feasible = expected_shortfall == 0
        if (
            self.required_minutes != expected_required
            or self.remaining_minutes != expected_remaining
            or self.shortfall_minutes != expected_shortfall
            or self.feasible is not expected_feasible
        ):
            raise ValueError("capacity arithmetic is inconsistent")
        return self


class FixedBlock(StrictModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    starts_at: datetime
    ends_at: datetime
    source: Source

    @model_validator(mode="after")
    def validate_interval(self) -> FixedBlock:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class PlanBlock(StrictModel):
    id: str = Field(min_length=1)
    block_type: Literal["task", "fixed", "buffer", "break"]
    label: str = Field(min_length=1)
    starts_at: datetime
    ends_at: datetime
    ordinal: int = Field(ge=0)
    task_id: str | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> PlanBlock:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class PlanVersion(StrictModel):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    stage: SessionStage
    capacity: CapacityProof
    blocks: list[PlanBlock]
    reason: str = Field(min_length=1)
    committed: bool
    created_at: datetime


class ObservationEvent(StrictModel):
    id: str = Field(min_length=1)
    session_id: str | None = None
    event_type: str = Field(min_length=1)
    source: Source
    payload: dict[str, Any]
    occurred_at: datetime
    created_at: datetime


class TaskOutcome(StrictModel):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    completion_state: TaskCompletionState
    actual_minutes: int | None = Field(default=None, ge=0)
    note: str | None = None
    created_at: datetime


class LLMRun(StrictModel):
    id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    ordinal: int = Field(ge=1)
    session_id: str | None = None
    model: str = Field(min_length=1)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generation_parameters: dict[str, Any]
    response: dict[str, Any] | None = None
    finish_reason: str | None = None
    status: Literal["started", "completed", "failed"]
    error_code: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = Field(default=None, ge=0)


class ToolRun(StrictModel):
    id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    ordinal: int = Field(ge=1)
    session_id: str | None = None
    llm_run_id: str | None = None
    tool_name: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    cache_hit: bool
    handler_executed: bool
    status: Literal["started", "completed", "failed"]
    error_code: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = Field(default=None, ge=0)


class HarnessTrace(StrictModel):
    id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    session_id: str | None = None
    workflow_phase: Literal[
        "intake_save",
        "coverage_compare",
        "inventory_confirm",
        "context_read",
        "candidates_build",
        "plan_commit",
        "profile_propose",
        "profile_commit",
        "evening_close",
        "final_narration",
    ]
    actor: str = Field(min_length=1)
    role: str = Field(min_length=1)
    expected_version: int = Field(ge=0)
    caller_idempotency_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    harness_version: str = Field(min_length=1)
    status: Literal["started", "completed", "failed"]
    final_error_code: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    model_calls: int = Field(ge=0)
    tool_rounds: int = Field(ge=0)
    handler_executions: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    schema_repair_used: bool


class HarnessTraceEvent(StrictModel):
    id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    ordinal: int = Field(ge=1)
    event_kind: Literal["llm", "tool"]
    llm_run_id: str | None = None
    tool_run_id: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_exactly_one_link(self) -> HarnessTraceEvent:
        if (self.llm_run_id is None) == (self.tool_run_id is None):
            raise ValueError("trace event must link exactly one run")
        if self.event_kind == "llm" and self.llm_run_id is None:
            raise ValueError("llm event must link an LLM run")
        if self.event_kind == "tool" and self.tool_run_id is None:
            raise ValueError("tool event must link a tool run")
        return self


class HarnessTraceRecord(StrictModel):
    trace: HarnessTrace
    events: tuple[HarnessTraceEvent, ...]
    llm_runs: tuple[LLMRun, ...]
    tool_runs: tuple[ToolRun, ...]


DataT = TypeVar("DataT")


class ResponseEnvelope(StrictModel, Generic[DataT]):
    session_id: str = Field(min_length=1)
    version: int = Field(ge=0)
    stage: SessionStage
    allowed_actions: list[str]
    trace_id: str = Field(min_length=1)
    data: DataT
