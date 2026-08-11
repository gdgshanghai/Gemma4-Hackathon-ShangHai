"""Strict contracts for trusted family context and confirmed Memory."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import AwareDatetime, ConfigDict, Field, JsonValue, model_validator

from backend.contracts.models import Source, StrictModel


_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_LOCAL_TIME_PATTERN = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d\Z")
_FORBIDDEN_LABELS = frozenset(
    unicodedata.normalize("NFKC", label).strip().casefold()
    for label in ("lazy", "stupid", "hopeless", "懒", "笨", "没救")
)

_METRICS_BY_CATEGORY: dict[MemoryCategory, frozenset[str]]


class MemoryCategory(StrEnum):
    SUBJECT_PERFORMANCE = "subject_performance"
    TASK_SPEED = "task_speed"
    BEHAVIOR = "behavior"
    ENVIRONMENT = "environment"


class ProfilePatchAction(StrEnum):
    ASSERT = "assert"
    SUPERSEDE = "supersede"
    REVOKE = "revoke"


class CalibrationState(StrEnum):
    INPUT_SAVED = "input_saved"
    MODEL_UNAVAILABLE = "model_unavailable"
    NEEDS_CONFIRMATION = "needs_confirmation"
    RETRY_PENDING = "retry_pending"
    COMMITTED = "committed"
    ABANDONED = "abandoned"


class PendingKind(StrEnum):
    PROFILE_PATCH = "profile_patch"
    MODEL_RETRY = "model_retry"


class RecoveryDirective(StrEnum):
    INITIAL_INFERENCE = "initial_inference"
    RETURN_STORED = "return_stored"
    EXPLICIT_RETRY_ALLOWED = "explicit_retry_allowed"


class ObservationEvidenceLevel(StrEnum):
    PARENT_CONFIRMED = "parent_confirmed"
    SYSTEM_OBSERVED = "system_observed"
    INFERRED_BY_EXCLUSION = "inferred_by_exclusion"


class MemoryRelevanceReason(StrEnum):
    SUBJECT_AND_TASK_TYPE_MATCH = "subject_and_task_type_match"
    SUBJECT_MATCH = "subject_match"
    TASK_TYPE_MATCH = "task_type_match"
    GENERAL_CATEGORY_MATCH = "general_category_match"


_METRICS_BY_CATEGORY = {
    MemoryCategory.SUBJECT_PERFORMANCE: frozenset(
        {"assessment_level", "score", "school_feedback", "foundation"}
    ),
    MemoryCategory.TASK_SPEED: frozenset(
        {"typical_minutes_low", "typical_minutes_high", "estimated_actual_ratio"}
    ),
    MemoryCategory.BEHAVIOR: frozenset(
        {"start_avoidance", "subject_overrun", "late_omission", "start_confidence"}
    ),
    MemoryCategory.ENVIRONMENT: frozenset(
        {"sleep_boundary", "arrival_time", "fixed_activity", "family_rule"}
    ),
}
_TEXT_METRICS = frozenset(
    {"assessment_level", "foundation", "school_feedback", "fixed_activity", "family_rule"}
)
_TIME_METRICS = frozenset({"sleep_boundary", "arrival_time"})
_NUMERIC_RULES: dict[str, tuple[float, float, str, bool]] = {
    "score": (0, 100, "points", False),
    "typical_minutes_low": (5, 600, "minutes", True),
    "typical_minutes_high": (5, 600, "minutes", True),
    "estimated_actual_ratio": (0.1, 10, "ratio", False),
    "subject_overrun": (0.1, 10, "ratio", False),
    "start_avoidance": (0, 1, "ratio", False),
    "late_omission": (0, 100, "count", True),
    "start_confidence": (1, 5, "scale_1_5", False),
}


def normalize_family_text(value: str | None) -> str | None:
    """Normalize family-context identity and safety text without changing display text."""
    if value is None:
        return None
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _reject_permanent_labels(*values: str | None) -> None:
    for value in values:
        normalized = normalize_family_text(value)
        if normalized is None:
            continue
        if any(label in normalized for label in _FORBIDDEN_LABELS):
            raise ValueError("structured Memory text contains a permanent label")


class _FrozenStrictModel(StrictModel):
    model_config = ConfigDict(frozen=True)


class FamilyWriteContext(_FrozenStrictModel):
    actor: str = Field(min_length=1)
    role: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class _ObservationFields(StrictModel):
    action: ProfilePatchAction
    category: MemoryCategory
    subject: str | None = None
    task_type: str | None = None
    metric: str = Field(min_length=1)
    value_text: str | None = None
    value_number: float | None = None
    unit: str | None = None
    confidence: float = Field(ge=0, le=1)
    sample_count: int | None = None
    observed_at: AwareDatetime
    target_event_id: str | None = None

    @model_validator(mode="after")
    def validate_observation(self) -> _ObservationFields:
        for name, value in (("subject", self.subject), ("task_type", self.task_type)):
            if value is not None and not value.strip():
                raise ValueError(f"{name} must be non-empty when present")
        _reject_permanent_labels(self.subject, self.task_type, self.value_text)

        if self.metric not in _METRICS_BY_CATEGORY[self.category]:
            raise ValueError("metric is not allowed for category")
        if self.action is ProfilePatchAction.ASSERT:
            if self.target_event_id is not None:
                raise ValueError("assert must not target an existing event")
        elif self.target_event_id is None or not self.target_event_id.strip():
            raise ValueError("supersede and revoke require target_event_id")

        if self.action is ProfilePatchAction.REVOKE:
            if any(
                value is not None
                for value in (
                    self.value_text,
                    self.value_number,
                    self.unit,
                    self.sample_count,
                )
            ):
                raise ValueError("revoke must not carry replacement values")
            return self

        if self.metric in _TEXT_METRICS:
            if self.value_text is None or not self.value_text.strip():
                raise ValueError("text metric requires non-empty value_text")
            if (
                self.value_number is not None
                or self.unit is not None
                or self.sample_count is not None
            ):
                raise ValueError("text metric accepts only value_text")
            return self

        if self.metric in _TIME_METRICS:
            if self.value_text is None or _LOCAL_TIME_PATTERN.fullmatch(self.value_text) is None:
                raise ValueError("local time metric requires strict HH:MM value_text")
            if (
                self.value_number is not None
                or self.unit != "local_time"
                or self.sample_count is not None
            ):
                raise ValueError("local time metric requires only local_time unit")
            return self

        minimum, maximum, expected_unit, integer_only = _NUMERIC_RULES[self.metric]
        if self.value_text is not None or self.value_number is None:
            raise ValueError("numeric metric requires only value_number")
        if not minimum <= self.value_number <= maximum:
            raise ValueError("numeric metric is outside its allowed range")
        if integer_only and not self.value_number.is_integer():
            raise ValueError("numeric metric requires an integer number")
        if self.unit != expected_unit:
            raise ValueError("numeric metric has an invalid unit")
        if self.sample_count is None or self.sample_count < 1:
            raise ValueError("numeric metric requires sample_count >= 1")
        return self


class ProposedObservationInput(_ObservationFields):
    """Id-free proposal accepted from a future model-facing boundary."""


class ProposedObservation(_ObservationFields):
    model_config = ConfigDict(frozen=True)

    operation_id: str = Field(min_length=1)


class ProfilePatchDraft(_FrozenStrictModel):
    id: str = Field(min_length=1)
    calibration_id: str = Field(min_length=1)
    receipt_id: str = Field(min_length=1)
    base_profile_version: int = Field(ge=0)
    proposal_digest: str = Field(pattern=_SHA256_PATTERN)
    draft_digest: str = Field(pattern=_SHA256_PATTERN)
    observations: tuple[ProposedObservation, ...] = Field(min_length=1)
    revises_draft_id: str | None = None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_speed_range(self) -> ProfilePatchDraft:
        grouped: dict[tuple[str | None, str | None], dict[str, list[float]]] = {}
        for observation in self.observations:
            if observation.action is ProfilePatchAction.REVOKE:
                continue
            if observation.metric not in {"typical_minutes_low", "typical_minutes_high"}:
                continue
            identity = (
                normalize_family_text(observation.subject),
                normalize_family_text(observation.task_type),
            )
            metric_values = grouped.setdefault(identity, {})
            metric_values.setdefault(observation.metric, []).append(float(observation.value_number))
        for metric_values in grouped.values():
            lows = metric_values.get("typical_minutes_low", [])
            highs = metric_values.get("typical_minutes_high", [])
            if lows and highs and max(lows) > min(highs):
                raise ValueError("typical_minutes_low may not exceed typical_minutes_high")
        return self


class ProfileCommit(_FrozenStrictModel):
    id: str = Field(min_length=1)
    calibration_id: str = Field(min_length=1)
    draft_id: str = Field(min_length=1)
    profile_version: int = Field(ge=1)
    accepted_operation_ids: tuple[str, ...] = Field(min_length=1)
    confirmed_by: str = Field(min_length=1)
    committed_at: AwareDatetime


class ProfileVersion(_FrozenStrictModel):
    profile_version: int = Field(ge=1)
    commit_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    committed_at: AwareDatetime


class MemoryObservation(_ObservationFields):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    source: Source
    evidence_level: ObservationEvidenceLevel
    confirmed_by: str = Field(min_length=1)
    profile_version: int = Field(ge=1)
    canonical_order: int = Field(ge=0)
    committed_at: AwareDatetime


class ProfileSnapshot(_FrozenStrictModel):
    profile_version: int = Field(ge=0)
    active_observations: tuple[MemoryObservation, ...]


class MemoryEvidenceSummary(_FrozenStrictModel):
    observation: MemoryObservation
    source: Source
    observed_at: AwareDatetime
    confidence: float = Field(ge=0, le=1)
    sample_count: int | None = None
    relevance_reason: MemoryRelevanceReason

    @model_validator(mode="after")
    def validate_evidence_copy(self) -> MemoryEvidenceSummary:
        if (
            self.source is not self.observation.source
            or self.observed_at != self.observation.observed_at
            or self.confidence != self.observation.confidence
            or self.sample_count != self.observation.sample_count
        ):
            raise ValueError("evidence summary must match its observation")
        return self


class MemoryQuery(_FrozenStrictModel):
    categories: tuple[MemoryCategory, ...] = Field(min_length=1)
    subjects: tuple[str, ...] = ()
    task_types: tuple[str, ...] = ()
    as_of: AwareDatetime
    limit: int = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def validate_query_terms(self) -> MemoryQuery:
        if any(not value.strip() for value in (*self.subjects, *self.task_types)):
            raise ValueError("query terms must be non-empty")
        return self


class CalibrationTurnReceipt(_FrozenStrictModel):
    id: str = Field(min_length=1)
    calibration_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    role: str = Field(min_length=1)
    content_sha256: str = Field(pattern=_SHA256_PATTERN)
    raw_text: str
    created_at: AwareDatetime


class CalibrationCommitInputReceipt(_FrozenStrictModel):
    id: str = Field(min_length=1)
    calibration_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    role: Literal["parent"]
    expected_calibration_version: int = Field(ge=1)
    draft_id: str = Field(min_length=1, max_length=128)
    draft_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_operation_ids: tuple[str, ...] = Field(min_length=1, max_length=20)
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_unique_accepted_ids(self) -> CalibrationCommitInputReceipt:
        if len(self.accepted_operation_ids) != len(set(self.accepted_operation_ids)):
            raise ValueError("accepted_operation_ids must be unique")
        return self


class CalibrationCommitInputReceiptResult(_FrozenStrictModel):
    input: CalibrationCommitInputReceipt
    replayed: bool


class CalibrationCheckpoint(_FrozenStrictModel):
    calibration_id: str = Field(min_length=1)
    calibration_version: int = Field(ge=1)
    profile_version: int = Field(ge=0)
    state: CalibrationState
    resume_stage: str | None = None
    pending_kind: PendingKind | None = None
    pending_entity_id: str | None = None
    last_stable_calibration_version: int = Field(ge=0)
    last_stable_profile_version: int = Field(ge=0)
    input_receipt_id: str | None = None
    trace_id: str | None = None
    occurred_at: AwareDatetime


class CalibrationSummary(_FrozenStrictModel):
    calibration_id: str = Field(min_length=1)
    calibration_version: int = Field(ge=1)
    profile_version: int = Field(ge=0)
    state: CalibrationState
    occurred_at: AwareDatetime


class CalibrationWorkflowResult(_FrozenStrictModel):
    calibration_id: str = Field(min_length=1)
    calibration_version: int = Field(ge=1)
    profile_version: int = Field(ge=0)
    state: CalibrationState
    allowed_actions: tuple[str, ...]
    trace_id: str = Field(min_length=1)
    data: dict[str, JsonValue]


class DeliveryMetadata(_FrozenStrictModel):
    replayed: bool


class DeliveredCalibrationResult(_FrozenStrictModel):
    outcome: CalibrationWorkflowResult
    delivery: DeliveryMetadata


class RetryBeginOutcomeData(_FrozenStrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str = Field(min_length=1)
    recovery_directive: Literal["initial_inference"]
    resume_stage: Literal["profile_propose", "profile_commit"]
    pending_entity_id: str = Field(min_length=1)


class CalibrationRecoverySnapshot(_FrozenStrictModel):
    calibration_id: str = Field(min_length=1)
    calibration_version: int = Field(ge=1)
    profile_version: int = Field(ge=0)
    receipt: CalibrationTurnReceipt
    latest_checkpoint: CalibrationCheckpoint
    pending_draft: ProfilePatchDraft | None = None
    pending_draft_result: CalibrationWorkflowResult | None = None
    pending_commit_input: CalibrationCommitInputReceipt | None = None
    last_outcome: CalibrationWorkflowResult | None = None
    directive: RecoveryDirective


class CalibrationInputReceiptResult(_FrozenStrictModel):
    receipt: CalibrationTurnReceipt
    replayed: bool


class SchoolBriefRevision(_FrozenStrictModel):
    id: str = Field(min_length=1)
    brief_date: date
    revision: int = Field(ge=1)
    content_sha256: str = Field(pattern=_SHA256_PATTERN)
    raw_text: str
    source: Literal["manual-paste"] = "manual-paste"
    created_at: AwareDatetime


class SchoolBriefWriteResult(_FrozenStrictModel):
    brief_date: date
    revision: int = Field(ge=1)
    record: SchoolBriefRevision
    trace_id: str = Field(min_length=1)
    no_op: bool
    allowed_actions: tuple[Literal["replace_school_brief"], ...]


class DeliveredSchoolBriefResult(_FrozenStrictModel):
    outcome: SchoolBriefWriteResult
    delivery: DeliveryMetadata


FamilyJsonObject = dict[str, JsonValue]
FamilyModel = StrictModel


def family_model_to_json_object(model: StrictModel) -> dict[str, Any]:
    """Return a JSON-compatible object for durable outcome storage."""
    value = model.model_dump(mode="json")
    if not isinstance(value, dict):
        raise TypeError("family model must serialize to a JSON object")
    return value
