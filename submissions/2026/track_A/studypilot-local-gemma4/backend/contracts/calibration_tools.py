"""Strict model-facing contracts for parent profile calibration tools."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, TypeAdapter, field_validator, model_validator

from backend.contracts.family import (
    CalibrationState,
    CalibrationWorkflowResult,
    DeliveryMetadata,
    ProposedObservationInput,
)
from backend.contracts.models import StrictModel


def _require_unique_operation_ids(operation_ids: tuple[str, ...]) -> None:
    if len(operation_ids) != len(set(operation_ids)):
        raise ValueError("accepted_operation_ids must be unique")


class _FrozenStrictModel(StrictModel):
    model_config = ConfigDict(frozen=True)


class CalibrationSubject(StrEnum):
    CHINESE = "chinese"
    MATHEMATICS = "mathematics"
    ENGLISH = "english"
    CIVICS = "civics"
    HISTORY = "history"
    GEOGRAPHY = "geography"
    BIOLOGY = "biology"


class CalibrationTaskType(StrEnum):
    WRITTEN = "written"
    READING = "reading"
    RECITATION = "recitation"
    CORRECTION = "correction"
    PREPARATION = "preparation"
    MAP_READING = "map_reading"


class CalibrationWorkloadBand(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


CalibrationMinute = Annotated[int, Field(ge=5, le=600)]
CalibrationNote = Annotated[str, Field(min_length=1, max_length=200)]


class DurationEvidenceGroup(StrictModel):
    subject: CalibrationSubject
    task_type: CalibrationTaskType
    workload_band: CalibrationWorkloadBand = CalibrationWorkloadBand.MEDIUM
    minutes: tuple[CalibrationMinute, ...] = Field(min_length=1, max_length=8)

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


class ExtractCalibrationEvidenceArgs(StrictModel):
    duration_groups: tuple[DurationEvidenceGroup, ...] = Field(
        min_length=1,
        max_length=8,
    )
    unapplied_notes: tuple[CalibrationNote, ...] = Field(default=(), max_length=5)

    @model_validator(mode="after")
    def validate_unique_groups(self) -> ExtractCalibrationEvidenceArgs:
        identities = tuple(
            (group.subject, group.task_type) for group in self.duration_groups
        )
        if len(identities) != len(set(identities)):
            raise ValueError("duration evidence groups must be unique")
        return self


class CalibrationEvidenceDetail(_FrozenStrictModel):
    subject: CalibrationSubject
    task_type: CalibrationTaskType
    workload_band: CalibrationWorkloadBand
    reference_minutes: int = Field(ge=5, le=600)
    observed_p80_minutes: int = Field(ge=5, le=600)
    sample_count: int = Field(ge=1, le=8)
    suggested_ratio: float = Field(ge=0.1, le=10)


class ProposeProfilePatchArgs(StrictModel):
    observations: tuple[ProposedObservationInput, ...] = Field(
        min_length=1,
        max_length=20,
    )


class CommitProfilePatchArgs(StrictModel):
    draft_id: str = Field(min_length=1, max_length=128)
    draft_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_operation_ids: tuple[str, ...] = Field(
        min_length=1,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_unique_operation_ids(self) -> CommitProfilePatchArgs:
        _require_unique_operation_ids(self.accepted_operation_ids)
        return self


class TrustedProfileCommitCommand(_FrozenStrictModel):
    calibration_id: str = Field(min_length=1)
    expected_calibration_version: int = Field(ge=1)
    draft_id: str = Field(min_length=1, max_length=128)
    draft_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_operation_ids: tuple[str, ...] = Field(
        min_length=1,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_unique_operation_ids(self) -> TrustedProfileCommitCommand:
        _require_unique_operation_ids(self.accepted_operation_ids)
        return self


class ProfileToolFailureCode(StrEnum):
    VERSION_CONFLICT = "version_conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    INVALID_TRANSITION = "invalid_transition"
    NOT_FOUND = "not_found"
    DRAFT_DIGEST_MISMATCH = "draft_digest_mismatch"
    COMMIT_COMMAND_INVALID = "commit_command_invalid"
    PROPOSAL_INVALID = "proposal_invalid"
    MODEL_CONFIRMATION_MISMATCH = "model_confirmation_mismatch"


class ProfileToolError(_FrozenStrictModel):
    code: ProfileToolFailureCode
    retryable: bool

    @field_validator("code", mode="before")
    @classmethod
    def validate_code_type(cls, value: object) -> ProfileToolFailureCode:
        if isinstance(value, ProfileToolFailureCode):
            return value
        if type(value) is str:
            return ProfileToolFailureCode(value)
        raise ValueError("code must be a ProfileToolFailureCode or string")


class _ProfileToolResultModel(_FrozenStrictModel):
    @model_validator(mode="before")
    @classmethod
    def validate_ok_type(cls, value: Any) -> Any:
        if isinstance(value, Mapping) and type(value.get("ok")) is not bool:
            raise ValueError("ok must be a boolean")
        return value


class ProfileToolSuccess(_ProfileToolResultModel):
    ok: Literal[True]
    operation: Literal[
        "profile_patch_proposed",
        "profile_patch_committed",
    ]
    outcome: CalibrationWorkflowResult
    delivery: DeliveryMetadata

    @model_validator(mode="after")
    def validate_operation_state(self) -> ProfileToolSuccess:
        expected = {
            "profile_patch_proposed": CalibrationState.NEEDS_CONFIRMATION,
            "profile_patch_committed": CalibrationState.COMMITTED,
        }[self.operation]
        if self.outcome.state is not expected:
            raise ValueError("tool operation and workflow state disagree")
        return self


class ProfileToolFailure(_ProfileToolResultModel):
    ok: Literal[False]
    operation: Literal[
        "propose_profile_patch",
        "commit_profile_patch",
    ]
    error: ProfileToolError


ProfileToolResult = Annotated[
    ProfileToolSuccess | ProfileToolFailure,
    Field(discriminator="ok"),
]
_PROFILE_TOOL_RESULT_ADAPTER = TypeAdapter(ProfileToolResult)


def validate_profile_tool_result(value: Mapping[str, Any]) -> ProfileToolResult:
    return _PROFILE_TOOL_RESULT_ADAPTER.validate_python(dict(value))
