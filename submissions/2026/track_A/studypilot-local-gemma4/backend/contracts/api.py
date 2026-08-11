"""Strict HTTP request and response contracts for parent calibration APIs."""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from backend.contracts.family import (
    CalibrationState,
    CalibrationSummary,
    DeliveryMetadata,
    PendingKind,
    ProfileCommit,
    ProfilePatchDraft,
    ProposedObservation,
    ProposedObservationInput,
    SchoolBriefRevision,
    SchoolBriefWriteResult,
)
from backend.contracts.calibration_tools import (
    CalibrationEvidenceDetail,
    CalibrationSubject,
    CalibrationTaskType,
    CalibrationWorkloadBand,
)
from backend.contracts.models import StrictModel
from backend.domain.workflow import allowed_actions as workflow_allowed_actions


def _require_unique_operation_ids(operation_ids: tuple[str, ...]) -> None:
    if len(operation_ids) != len(set(operation_ids)):
        raise ValueError("accepted_operation_ids must be unique")


class _FrozenStrictModel(StrictModel):
    model_config = ConfigDict(frozen=True)


class CalibrationCreateRequest(StrictModel):
    text: str = Field(max_length=20_000)
    expected_calibration_version: Literal[0] = 0
    expected_profile_version: int = Field(ge=0)

    @field_validator("expected_calibration_version", mode="before")
    @classmethod
    def validate_integer_zero(cls, value: object) -> object:
        if type(value) is not int or value != 0:
            raise ValueError("expected_calibration_version must be integer zero")
        return value


class CalibrationRetryRequest(StrictModel):
    expected_calibration_version: int = Field(ge=1)


class SimplifiedDurationGroup(StrictModel):
    subject: CalibrationSubject
    task_type: CalibrationTaskType
    workload_band: CalibrationWorkloadBand = CalibrationWorkloadBand.MEDIUM
    conservative_minutes: int = Field(ge=5, le=600)

    @field_validator("subject", mode="before")
    @classmethod
    def validate_subject_type(cls, value: object) -> CalibrationSubject:
        if isinstance(value, CalibrationSubject):
            return value
        if type(value) is str:
            return CalibrationSubject(value)
        raise ValueError("subject must be a calibration subject or string")

    @field_validator("task_type", mode="before")
    @classmethod
    def validate_task_type_type(cls, value: object) -> CalibrationTaskType:
        if isinstance(value, CalibrationTaskType):
            return value
        if type(value) is str:
            return CalibrationTaskType(value)
        raise ValueError("task_type must be a calibration task type or string")

    @field_validator("workload_band", mode="before")
    @classmethod
    def validate_workload_band_type(cls, value: object) -> CalibrationWorkloadBand:
        if isinstance(value, CalibrationWorkloadBand):
            return value
        if type(value) is str:
            return CalibrationWorkloadBand(value)
        raise ValueError("workload_band must be a calibration workload band or string")


class CalibrationSimplifyRequest(StrictModel):
    expected_calibration_version: int = Field(ge=1)
    duration_groups: tuple[SimplifiedDurationGroup, ...] = Field(
        min_length=1,
        max_length=8,
    )

    @model_validator(mode="after")
    def validate_unique_groups(self) -> CalibrationSimplifyRequest:
        identities = tuple(
            (group.subject, group.task_type) for group in self.duration_groups
        )
        if len(identities) != len(set(identities)):
            raise ValueError("simplified duration groups must be unique")
        return self


class CalibrationCommitRequest(StrictModel):
    expected_calibration_version: int = Field(ge=1)
    draft_id: str = Field(min_length=1, max_length=128)
    draft_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_operation_ids: tuple[str, ...] = Field(
        min_length=1,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_unique_operation_ids(self) -> CalibrationCommitRequest:
        _require_unique_operation_ids(self.accepted_operation_ids)
        return self


class CalibrationReviseRequest(StrictModel):
    expected_calibration_version: int = Field(ge=1)
    draft_id: str = Field(min_length=1, max_length=128)
    revised_observations: tuple[ProposedObservationInput, ...] = Field(
        min_length=1,
        max_length=20,
    )


class CalibrationAbandonRequest(StrictModel):
    expected_calibration_version: int = Field(ge=1)


class SchoolBriefWriteRequest(StrictModel):
    brief_date: date
    raw_text: str = Field(max_length=50_000)
    expected_revision: int = Field(ge=0)

    @field_validator("brief_date", mode="before")
    @classmethod
    def parse_http_date(cls, value: object) -> object:
        if type(value) is date:
            return value
        if type(value) is not str:
            raise ValueError("brief_date must be a date or YYYY-MM-DD string")
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
            raise ValueError("brief_date must use YYYY-MM-DD")
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError("brief_date must be a valid calendar date") from None


class CalibrationAction(StrEnum):
    GENERATE_PROFILE_PATCH = "generate_profile_patch"
    RETRY_LAST_TURN = "retry_last_turn"
    USE_SIMPLIFIED_CALIBRATION = "use_simplified_calibration"
    COMMIT_PROFILE_PATCH = "commit_profile_patch"
    REVISE_PROFILE_PATCH = "revise_profile_patch"
    ABANDON_PROFILE_PATCH = "abandon_profile_patch"
    START_CALIBRATION = "start_calibration"


class NarrationStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_REQUESTED = "not_requested"


def _validate_narration(
    narration: str | None,
    status: NarrationStatus,
) -> None:
    if status is NarrationStatus.AVAILABLE:
        if narration is None or not narration.strip():
            raise ValueError("available narration must be nonblank")
    elif narration is not None:
        raise ValueError("unavailable or unrequested narration must be absent")


class ProfilePatchProposalData(_FrozenStrictModel):
    kind: Literal["profile_patch_proposal"] = "profile_patch_proposal"
    draft: ProfilePatchDraft
    diff_preview: tuple[ProposedObservation, ...]
    narration: str | None = None
    narration_status: NarrationStatus
    unapplied_notes: tuple[str, ...] = ()
    calibration_details: tuple[CalibrationEvidenceDetail, ...] = ()

    @model_validator(mode="after")
    def validate_narration_state(self) -> ProfilePatchProposalData:
        _validate_narration(self.narration, self.narration_status)
        return self


class ProfilePatchCommitData(_FrozenStrictModel):
    kind: Literal["profile_patch_commit"] = "profile_patch_commit"
    commit: ProfileCommit
    draft_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_operation_ids: tuple[str, ...] = Field(min_length=1)
    observation_event_ids: tuple[str, ...] = Field(min_length=1)
    narration: str | None = None
    narration_status: NarrationStatus

    @model_validator(mode="after")
    def validate_narration_state(self) -> ProfilePatchCommitData:
        _validate_narration(self.narration, self.narration_status)
        return self


class CalibrationRecoveryData(_FrozenStrictModel):
    kind: Literal["calibration_recovery"] = "calibration_recovery"
    input_saved: Literal[True] = True
    input_receipt_id: str = Field(min_length=1)
    resume_stage: Literal["profile_propose", "profile_commit"] | None
    pending_kind: PendingKind | None
    pending_entity_id: str | None
    failure_code: str | None = None

    @field_validator("input_saved", mode="before")
    @classmethod
    def validate_input_saved_type(cls, value: object) -> bool:
        if type(value) is not bool:
            raise ValueError("input_saved must be a boolean")
        return value


CalibrationResponseData = Annotated[
    ProfilePatchProposalData | ProfilePatchCommitData | CalibrationRecoveryData,
    Field(discriminator="kind"),
]


class CalibrationResponseEnvelope(_FrozenStrictModel):
    calibration_id: str = Field(min_length=1)
    calibration_version: int = Field(ge=1)
    profile_version: int = Field(ge=0)
    stage: CalibrationState
    allowed_actions: tuple[CalibrationAction, ...]
    trace_id: str = Field(min_length=1)
    data: CalibrationResponseData
    delivery: DeliveryMetadata

    @model_validator(mode="after")
    def validate_state_specific_payload(self) -> CalibrationResponseEnvelope:
        expected_kind = {
            CalibrationState.NEEDS_CONFIRMATION: "profile_patch_proposal",
            CalibrationState.COMMITTED: "profile_patch_commit",
            CalibrationState.INPUT_SAVED: "calibration_recovery",
            CalibrationState.MODEL_UNAVAILABLE: "calibration_recovery",
            CalibrationState.RETRY_PENDING: "calibration_recovery",
            CalibrationState.ABANDONED: "calibration_recovery",
        }[self.stage]
        if self.data.kind != expected_kind:
            raise ValueError("calibration stage and data kind disagree")
        expected_actions = tuple(
            CalibrationAction(item) for item in workflow_allowed_actions(self.stage)
        )
        if self.allowed_actions != expected_actions:
            raise ValueError("calibration actions do not match stage")
        if isinstance(self.data, ProfilePatchProposalData):
            if (
                self.data.draft.calibration_id != self.calibration_id
                or self.data.draft.base_profile_version != self.profile_version
            ):
                raise ValueError("proposal data does not belong to envelope")
        if isinstance(self.data, ProfilePatchCommitData):
            if (
                self.data.commit.calibration_id != self.calibration_id
                or self.data.commit.profile_version != self.profile_version
            ):
                raise ValueError("commit data does not belong to envelope")
        return self


class ApiErrorCode(StrEnum):
    SCHEMA_INVALID = "schema_invalid"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    VERSION_CONFLICT = "version_conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    INVALID_TRANSITION = "invalid_transition"
    DRAFT_DIGEST_MISMATCH = "draft_digest_mismatch"
    COMMIT_COMMAND_INVALID = "commit_command_invalid"
    PROFILE_PROPOSAL_INVALID = "profile_proposal_invalid"
    RETRY_LINEAGE_CONFLICT = "retry_lineage_conflict"
    MODEL_PROTOCOL_ERROR = "model_protocol_error"
    MODEL_UNAVAILABLE = "model_unavailable"
    INTERNAL_ERROR = "internal_error"


class ValidationIssue(_FrozenStrictModel):
    location: tuple[str | int, ...]
    type: str = Field(min_length=1)


class ApiErrorDetail(_FrozenStrictModel):
    code: ApiErrorCode
    message: str = Field(min_length=1)
    issues: tuple[ValidationIssue, ...] = ()


class ModelRecoveryData(_FrozenStrictModel):
    calibration_id: str
    calibration_version: int = Field(ge=1)
    profile_version: int = Field(ge=0)
    stage: Literal[CalibrationState.MODEL_UNAVAILABLE]
    allowed_actions: tuple[
        Literal["retry_last_turn"],
        Literal["use_simplified_calibration"],
        Literal["abandon_profile_patch"],
    ]
    resume_stage: Literal["profile_propose", "profile_commit"]
    pending_kind: Literal[PendingKind.MODEL_RETRY]
    pending_entity_id: str
    input_receipt_id: str
    input_saved: Literal[True] = True
    failure_code: str | None = None

    @field_validator("input_saved", mode="before")
    @classmethod
    def validate_input_saved_type(cls, value: object) -> bool:
        if type(value) is not bool:
            raise ValueError("input_saved must be a boolean")
        return value


class ErrorEnvelope(_FrozenStrictModel):
    error: ApiErrorDetail
    trace_id: str = Field(min_length=1)
    recovery: ModelRecoveryData | None = None


class SchoolBriefWriteEnvelope(_FrozenStrictModel):
    trace_id: str = Field(min_length=1)
    data: SchoolBriefWriteResult
    delivery: DeliveryMetadata


class SchoolBriefReadEnvelope(_FrozenStrictModel):
    trace_id: str = Field(min_length=1)
    data: SchoolBriefRevision


class SchoolBriefHistoryEnvelope(_FrozenStrictModel):
    trace_id: str = Field(min_length=1)
    brief_date: date
    revisions: tuple[SchoolBriefRevision, ...]


class HealthComponent(_FrozenStrictModel):
    status: Literal["ok", "degraded"]
    error_code: str | None

    @model_validator(mode="after")
    def validate_status(self) -> HealthComponent:
        if self.status == "ok" and self.error_code is not None:
            raise ValueError("healthy component must not carry an error code")
        if self.status == "degraded" and (self.error_code is None or not self.error_code.strip()):
            raise ValueError("degraded component requires an error code")
        return self


class ModelHealthComponent(HealthComponent):
    model_id: str = Field(min_length=1)
    loaded: bool
    tool_use: bool
    quantization: str | None

    @model_validator(mode="after")
    def validate_model_status(self) -> ModelHealthComponent:
        if self.status == "ok" and (not self.loaded or not self.tool_use):
            raise ValueError("healthy model must be loaded with tool use")
        if self.status == "degraded" and (
            self.loaded or self.tool_use or self.quantization is not None
        ):
            raise ValueError("degraded model must not claim loaded metadata")
        return self


class HealthResponse(_FrozenStrictModel):
    ready: bool
    trace_id: str = Field(min_length=1)
    api: HealthComponent
    sqlite: HealthComponent
    model: ModelHealthComponent

    @model_validator(mode="after")
    def validate_readiness(self) -> HealthResponse:
        expected = all(
            component.status == "ok" for component in (self.api, self.sqlite, self.model)
        )
        if self.ready is not expected:
            raise ValueError("overall readiness does not match components")
        return self


class NoDataMetric(_FrozenStrictModel):
    value: None
    numerator: Literal[0]
    denominator: Literal[0]
    status: Literal["no_data"]

    @field_validator("numerator", "denominator", mode="before")
    @classmethod
    def validate_counter_type(cls, value: object) -> int:
        if type(value) is not int:
            raise ValueError("no-data counters must be integers")
        return value


class WeeklySummaryData(_FrozenStrictModel):
    week_start: date
    week_end: date
    profile_version: int = Field(ge=0)
    latest_calibration: CalibrationSummary | None
    confirmed_observation_count: int = Field(ge=0)
    estimate_error: NoDataMetric
    omissions: NoDataMetric
    start_confidence: NoDataMetric
    parent_interventions: NoDataMetric


class WeeklySummaryResponse(_FrozenStrictModel):
    trace_id: str = Field(min_length=1)
    data: WeeklySummaryData
