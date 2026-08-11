from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from backend.contracts.family import (
    CalibrationCheckpoint,
    CalibrationInputReceiptResult,
    CalibrationRecoverySnapshot,
    CalibrationState,
    CalibrationTurnReceipt,
    CalibrationWorkflowResult,
    DeliveredCalibrationResult,
    DeliveredSchoolBriefResult,
    DeliveryMetadata,
    FamilyWriteContext,
    MemoryCategory,
    MemoryEvidenceSummary,
    MemoryObservation,
    MemoryQuery,
    MemoryRelevanceReason,
    ObservationEvidenceLevel,
    PendingKind,
    ProfileCommit,
    ProfilePatchAction,
    ProfilePatchDraft,
    ProfileVersion,
    ProposedObservation,
    ProposedObservationInput,
    RecoveryDirective,
    SchoolBriefRevision,
    SchoolBriefWriteResult,
)
from backend.contracts.models import Source, StrictModel


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
HASH_A = "a" * 64
HASH_B = "b" * 64


def _proposal(**overrides: Any) -> ProposedObservationInput:
    payload: dict[str, Any] = {
        "action": ProfilePatchAction.ASSERT,
        "category": MemoryCategory.SUBJECT_PERFORMANCE,
        "subject": "Mathematics",
        "task_type": "written",
        "metric": "assessment_level",
        "value_text": "developing",
        "value_number": None,
        "unit": None,
        "confidence": 0.8,
        "sample_count": None,
        "observed_at": NOW,
        "target_event_id": None,
    }
    payload.update(overrides)
    return ProposedObservationInput(**payload)


def _stored_proposal(operation_id: str = "operation-1", **overrides: Any) -> ProposedObservation:
    payload = _proposal(**overrides).model_dump()
    return ProposedObservation(operation_id=operation_id, **payload)


def _memory_observation(**overrides: Any) -> MemoryObservation:
    payload: dict[str, Any] = {
        "id": "event-1",
        "action": ProfilePatchAction.ASSERT,
        "category": MemoryCategory.SUBJECT_PERFORMANCE,
        "subject": "Mathematics",
        "task_type": "written",
        "metric": "assessment_level",
        "value_text": "developing",
        "value_number": None,
        "unit": None,
        "confidence": 0.8,
        "sample_count": None,
        "observed_at": NOW,
        "target_event_id": None,
        "source": Source.PARENT,
        "evidence_level": ObservationEvidenceLevel.PARENT_CONFIRMED,
        "confirmed_by": "parent-1",
        "profile_version": 1,
        "canonical_order": 0,
        "committed_at": NOW,
    }
    payload.update(overrides)
    return MemoryObservation(**payload)


def _receipt() -> CalibrationTurnReceipt:
    return CalibrationTurnReceipt(
        id="receipt-1",
        calibration_id="calibration-1",
        actor="parent-1",
        role="parent",
        content_sha256=HASH_A,
        raw_text="Parent-provided local calibration text",
        created_at=NOW,
    )


def _checkpoint() -> CalibrationCheckpoint:
    return CalibrationCheckpoint(
        calibration_id="calibration-1",
        calibration_version=1,
        profile_version=0,
        state=CalibrationState.INPUT_SAVED,
        resume_stage="profile_propose",
        pending_kind=None,
        pending_entity_id=None,
        last_stable_calibration_version=1,
        last_stable_profile_version=0,
        input_receipt_id="receipt-1",
        trace_id="trace-1",
        occurred_at=NOW,
    )


def _workflow_result() -> CalibrationWorkflowResult:
    return CalibrationWorkflowResult(
        calibration_id="calibration-1",
        calibration_version=1,
        profile_version=0,
        state=CalibrationState.INPUT_SAVED,
        allowed_actions=("generate_profile_patch",),
        trace_id="trace-1",
        data={"receipt_id": "receipt-1"},
    )


def _draft() -> ProfilePatchDraft:
    return ProfilePatchDraft(
        id="draft-1",
        calibration_id="calibration-1",
        receipt_id="receipt-1",
        base_profile_version=0,
        proposal_digest=HASH_A,
        draft_digest=HASH_B,
        observations=(_stored_proposal(),),
        revises_draft_id=None,
        created_at=NOW,
    )


def test_family_enums_have_exact_values() -> None:
    assert {item.value for item in MemoryCategory} == {
        "subject_performance",
        "task_speed",
        "behavior",
        "environment",
    }
    assert {item.value for item in ProfilePatchAction} == {"assert", "supersede", "revoke"}
    assert {item.value for item in CalibrationState} == {
        "input_saved",
        "model_unavailable",
        "needs_confirmation",
        "retry_pending",
        "committed",
        "abandoned",
    }
    assert {item.value for item in PendingKind} == {"profile_patch", "model_retry"}
    assert {item.value for item in RecoveryDirective} == {
        "initial_inference",
        "return_stored",
        "explicit_retry_allowed",
    }
    assert {item.value for item in ObservationEvidenceLevel} == {
        "parent_confirmed",
        "system_observed",
        "inferred_by_exclusion",
    }


def test_every_family_model_inherits_strict_model() -> None:
    model_types = (
        FamilyWriteContext,
        ProposedObservationInput,
        ProposedObservation,
        ProfilePatchDraft,
        ProfileCommit,
        ProfileVersion,
        MemoryObservation,
        MemoryEvidenceSummary,
        MemoryQuery,
        CalibrationTurnReceipt,
        CalibrationCheckpoint,
        CalibrationRecoverySnapshot,
        CalibrationInputReceiptResult,
        CalibrationWorkflowResult,
        DeliveryMetadata,
        DeliveredCalibrationResult,
        SchoolBriefRevision,
        SchoolBriefWriteResult,
        DeliveredSchoolBriefResult,
    )
    assert all(issubclass(model_type, StrictModel) for model_type in model_types)


def test_model_facing_proposal_rejects_trusted_fields() -> None:
    payload = _proposal().model_dump()
    payload["actor"] = "parent-1"
    payload["idempotency_key"] = "hidden-key"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProposedObservationInput(**payload)


def test_family_models_forbid_extra_fields() -> None:
    payload = _receipt().model_dump()
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CalibrationTurnReceipt(**payload, unexpected=True)


@pytest.mark.parametrize(
    ("action", "target_event_id", "value_text", "valid"),
    [
        (ProfilePatchAction.ASSERT, None, "developing", True),
        (ProfilePatchAction.ASSERT, "event-1", "developing", False),
        (ProfilePatchAction.SUPERSEDE, "event-1", "secure", True),
        (ProfilePatchAction.SUPERSEDE, None, "secure", False),
        (ProfilePatchAction.REVOKE, "event-1", None, True),
        (ProfilePatchAction.REVOKE, None, None, False),
        (ProfilePatchAction.REVOKE, "event-1", "replacement", False),
    ],
)
def test_action_target_and_replacement_rules(
    action: ProfilePatchAction,
    target_event_id: str | None,
    value_text: str | None,
    valid: bool,
) -> None:
    payload = {
        "action": action,
        "target_event_id": target_event_id,
        "value_text": value_text,
    }
    if action is ProfilePatchAction.REVOKE:
        payload.update(value_number=None, unit=None, sample_count=None)

    if valid:
        assert _proposal(**payload).action is action
    else:
        with pytest.raises(ValidationError):
            _proposal(**payload)


@pytest.mark.parametrize(
    ("category", "metric"),
    [
        (MemoryCategory.SUBJECT_PERFORMANCE, "assessment_level"),
        (MemoryCategory.SUBJECT_PERFORMANCE, "score"),
        (MemoryCategory.SUBJECT_PERFORMANCE, "school_feedback"),
        (MemoryCategory.SUBJECT_PERFORMANCE, "foundation"),
        (MemoryCategory.TASK_SPEED, "typical_minutes_low"),
        (MemoryCategory.TASK_SPEED, "typical_minutes_high"),
        (MemoryCategory.TASK_SPEED, "estimated_actual_ratio"),
        (MemoryCategory.BEHAVIOR, "start_avoidance"),
        (MemoryCategory.BEHAVIOR, "subject_overrun"),
        (MemoryCategory.BEHAVIOR, "late_omission"),
        (MemoryCategory.BEHAVIOR, "start_confidence"),
        (MemoryCategory.ENVIRONMENT, "sleep_boundary"),
        (MemoryCategory.ENVIRONMENT, "arrival_time"),
        (MemoryCategory.ENVIRONMENT, "fixed_activity"),
        (MemoryCategory.ENVIRONMENT, "family_rule"),
    ],
)
def test_metric_category_allowlist_accepts_exact_pairs(
    category: MemoryCategory,
    metric: str,
) -> None:
    value_overrides: dict[str, Any]
    if metric in {"assessment_level", "school_feedback", "foundation", "fixed_activity", "family_rule"}:
        value_overrides = {"value_text": "confirmed detail"}
    elif metric == "score":
        value_overrides = {
            "value_text": None,
            "value_number": 80,
            "unit": "points",
            "sample_count": 1,
        }
    elif metric in {"typical_minutes_low", "typical_minutes_high"}:
        value_overrides = {
            "value_text": None,
            "value_number": 30,
            "unit": "minutes",
            "sample_count": 1,
        }
    elif metric in {"estimated_actual_ratio", "subject_overrun"}:
        value_overrides = {
            "value_text": None,
            "value_number": 1.2,
            "unit": "ratio",
            "sample_count": 1,
        }
    elif metric == "start_avoidance":
        value_overrides = {
            "value_text": None,
            "value_number": 0.5,
            "unit": "ratio",
            "sample_count": 1,
        }
    elif metric == "late_omission":
        value_overrides = {
            "value_text": None,
            "value_number": 2,
            "unit": "count",
            "sample_count": 1,
        }
    elif metric == "start_confidence":
        value_overrides = {
            "value_text": None,
            "value_number": 4,
            "unit": "scale_1_5",
            "sample_count": 1,
        }
    else:
        value_overrides = {
            "value_text": "21:30",
            "value_number": None,
            "unit": "local_time",
            "sample_count": None,
        }

    proposal = _proposal(category=category, metric=metric, **value_overrides)
    assert proposal.category is category
    assert proposal.metric == metric


@pytest.mark.parametrize(
    ("category", "metric"),
    [
        (MemoryCategory.BEHAVIOR, "score"),
        (MemoryCategory.ENVIRONMENT, "start_avoidance"),
        (MemoryCategory.TASK_SPEED, "family_rule"),
        (MemoryCategory.SUBJECT_PERFORMANCE, "typical_minutes_low"),
    ],
)
def test_metric_category_allowlist_rejects_mismatches(
    category: MemoryCategory,
    metric: str,
) -> None:
    with pytest.raises(ValidationError, match="metric is not allowed"):
        _proposal(category=category, metric=metric)


@pytest.mark.parametrize(
    "metric",
    ["assessment_level", "foundation", "school_feedback", "fixed_activity", "family_rule"],
)
def test_text_metrics_require_only_non_empty_text(metric: str) -> None:
    category = (
        MemoryCategory.ENVIRONMENT
        if metric in {"fixed_activity", "family_rule"}
        else MemoryCategory.SUBJECT_PERFORMANCE
    )
    assert _proposal(category=category, metric=metric, value_text="confirmed").value_text == "confirmed"
    for overrides in (
        {"value_text": ""},
        {"value_text": "   "},
        {"value_text": "confirmed", "value_number": 1},
        {"value_text": "confirmed", "unit": "text"},
        {"value_text": "confirmed", "sample_count": 1},
    ):
        with pytest.raises(ValidationError):
            _proposal(category=category, metric=metric, **overrides)


@pytest.mark.parametrize(
    ("metric", "category", "minimum", "maximum", "unit", "integer_only"),
    [
        ("score", MemoryCategory.SUBJECT_PERFORMANCE, 0, 100, "points", False),
        ("typical_minutes_low", MemoryCategory.TASK_SPEED, 5, 600, "minutes", True),
        ("typical_minutes_high", MemoryCategory.TASK_SPEED, 5, 600, "minutes", True),
        ("estimated_actual_ratio", MemoryCategory.TASK_SPEED, 0.1, 10, "ratio", False),
        ("subject_overrun", MemoryCategory.BEHAVIOR, 0.1, 10, "ratio", False),
        ("start_avoidance", MemoryCategory.BEHAVIOR, 0, 1, "ratio", False),
        ("late_omission", MemoryCategory.BEHAVIOR, 0, 100, "count", True),
        ("start_confidence", MemoryCategory.BEHAVIOR, 1, 5, "scale_1_5", False),
    ],
)
def test_numeric_metric_value_unit_and_sample_rules(
    metric: str,
    category: MemoryCategory,
    minimum: float,
    maximum: float,
    unit: str,
    integer_only: bool,
) -> None:
    valid = _proposal(
        category=category,
        metric=metric,
        value_text=None,
        value_number=minimum,
        unit=unit,
        sample_count=1,
    )
    assert valid.value_number == minimum
    invalid_payloads = (
        {"value_number": minimum - 0.01, "unit": unit, "sample_count": 1},
        {"value_number": maximum + 0.01, "unit": unit, "sample_count": 1},
        {"value_number": minimum, "unit": "wrong", "sample_count": 1},
        {"value_number": minimum, "unit": unit, "sample_count": None},
        {"value_number": minimum, "unit": unit, "sample_count": 0},
        {"value_number": minimum, "unit": unit, "sample_count": 1, "value_text": "both"},
    )
    for overrides in invalid_payloads:
        invalid = {
            "category": category,
            "metric": metric,
            "value_text": None,
            **overrides,
        }
        with pytest.raises(ValidationError):
            _proposal(**invalid)
    if integer_only:
        with pytest.raises(ValidationError, match="integer"):
            _proposal(
                category=category,
                metric=metric,
                value_text=None,
                value_number=minimum + 0.5,
                unit=unit,
                sample_count=1,
            )


@pytest.mark.parametrize("metric", ["sleep_boundary", "arrival_time"])
def test_local_time_metrics_require_strict_hh_mm(metric: str) -> None:
    valid = _proposal(
        category=MemoryCategory.ENVIRONMENT,
        metric=metric,
        value_text="07:05",
        unit="local_time",
    )
    assert valid.value_text == "07:05"
    for value in ("7:05", "24:00", "12:60", "07:05:00", " 07:05 "):
        with pytest.raises(ValidationError):
            _proposal(
                category=MemoryCategory.ENVIRONMENT,
                metric=metric,
                value_text=value,
                unit="local_time",
            )
    with pytest.raises(ValidationError):
        _proposal(
            category=MemoryCategory.ENVIRONMENT,
            metric=metric,
            value_text="07:05",
            unit="local_time",
            sample_count=1,
        )


def test_draft_rejects_typical_minutes_low_above_high_for_same_identity() -> None:
    low = _stored_proposal(
        "operation-low",
        category=MemoryCategory.TASK_SPEED,
        metric="typical_minutes_low",
        value_text=None,
        value_number=45,
        unit="minutes",
        sample_count=1,
    )
    high = _stored_proposal(
        "operation-high",
        category=MemoryCategory.TASK_SPEED,
        metric="typical_minutes_high",
        value_text=None,
        value_number=30,
        unit="minutes",
        sample_count=1,
    )
    payload = _draft().model_dump()
    payload["observations"] = (low, high)

    with pytest.raises(ValidationError, match="typical_minutes_low"):
        ProfilePatchDraft(**payload)


@pytest.mark.parametrize("label", ["lazy", "ＳＴＵＰＩＤ", " hopeless ", "懒", "笨", "没救"])
def test_structured_proposals_reject_normalized_permanent_labels(label: str) -> None:
    with pytest.raises(ValidationError, match="permanent label"):
        _proposal(value_text=f"  {label}  ")


def test_memory_deserialization_rechecks_forbidden_labels() -> None:
    payload = _memory_observation().model_dump()
    payload["subject"] = "  ＬＡＺＹ  "

    with pytest.raises(ValidationError, match="permanent label"):
        MemoryObservation.model_validate(payload)


def test_raw_receipt_text_may_retain_forbidden_label_as_local_evidence() -> None:
    payload = _receipt().model_dump()
    payload["raw_text"] = "A parent wrote lazy; this raw local receipt must be retained."
    assert CalibrationTurnReceipt(**payload).raw_text.startswith("A parent")


@pytest.mark.parametrize(
    ("factory", "timestamp_field"),
    [
        (lambda: _proposal(), "observed_at"),
        (lambda: _draft(), "created_at"),
        (
            lambda: ProfileCommit(
                id="commit-1",
                calibration_id="calibration-1",
                draft_id="draft-1",
                profile_version=1,
                accepted_operation_ids=("operation-1",),
                confirmed_by="parent-1",
                committed_at=NOW,
            ),
            "committed_at",
        ),
        (
            lambda: ProfileVersion(
                profile_version=1,
                commit_id="commit-1",
                reason="parent_confirmed_patch",
                committed_at=NOW,
            ),
            "committed_at",
        ),
        (lambda: _memory_observation(), "observed_at"),
        (lambda: _memory_observation(), "committed_at"),
        (
            lambda: MemoryQuery(
                categories=(MemoryCategory.SUBJECT_PERFORMANCE,),
                subjects=("Mathematics",),
                task_types=("written",),
                as_of=NOW,
                limit=10,
            ),
            "as_of",
        ),
        (lambda: _receipt(), "created_at"),
        (lambda: _checkpoint(), "occurred_at"),
        (
            lambda: SchoolBriefRevision(
                id="school-1-r1",
                brief_date=date(2026, 7, 11),
                revision=1,
                content_sha256=HASH_A,
                raw_text="",
                source="manual-paste",
                created_at=NOW,
            ),
            "created_at",
        ),
    ],
)
def test_every_family_timestamp_requires_timezone(
    factory: Any,
    timestamp_field: str,
) -> None:
    model = factory()
    payload = model.model_dump()
    payload[timestamp_field] = NOW.replace(tzinfo=None)
    with pytest.raises(ValidationError, match="timezone"):
        type(model)(**payload)


def test_immutable_result_models_reject_assignment() -> None:
    result_models = (
        _draft(),
        ProfileCommit(
            id="commit-1",
            calibration_id="calibration-1",
            draft_id="draft-1",
            profile_version=1,
            accepted_operation_ids=("operation-1",),
            confirmed_by="parent-1",
            committed_at=NOW,
        ),
        ProfileVersion(
            profile_version=1,
            commit_id="commit-1",
            reason="parent_confirmed_patch",
            committed_at=NOW,
        ),
        _memory_observation(),
        MemoryEvidenceSummary(
            observation=_memory_observation(),
            source=Source.PARENT,
            observed_at=NOW,
            confidence=0.8,
            sample_count=None,
            relevance_reason=MemoryRelevanceReason.SUBJECT_AND_TASK_TYPE_MATCH,
        ),
        MemoryQuery(
            categories=(MemoryCategory.SUBJECT_PERFORMANCE,),
            subjects=("Mathematics",),
            task_types=("written",),
            as_of=NOW,
            limit=10,
        ),
    )
    for model in result_models:
        field_name = next(iter(type(model).model_fields))
        with pytest.raises(ValidationError, match="frozen"):
            setattr(model, field_name, getattr(model, field_name))


def test_memory_query_rejects_raw_history_and_enforces_limit() -> None:
    payload = {
        "categories": (MemoryCategory.SUBJECT_PERFORMANCE,),
        "subjects": ("Mathematics",),
        "task_types": (),
        "as_of": NOW,
        "limit": 10,
    }
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MemoryQuery(**payload, raw_chat_history="private conversation")
    for limit in (0, 21):
        with pytest.raises(ValidationError):
            MemoryQuery(**{**payload, "limit": limit})


def test_new_contracts_never_expose_ambiguous_version_field() -> None:
    model_types = (
        ProfilePatchDraft,
        ProfileCommit,
        ProfileVersion,
        MemoryObservation,
        CalibrationCheckpoint,
        CalibrationRecoverySnapshot,
        CalibrationWorkflowResult,
        SchoolBriefRevision,
        SchoolBriefWriteResult,
    )
    assert all("version" not in model_type.model_fields for model_type in model_types)


def test_delivery_metadata_keeps_replay_outside_business_outcome() -> None:
    outcome = _workflow_result()
    delivered = DeliveredCalibrationResult(
        outcome=outcome,
        delivery=DeliveryMetadata(replayed=True),
    )
    assert delivered.outcome == outcome
    assert delivered.delivery.replayed is True
    assert "replayed" not in outcome.model_dump()


def test_recovery_snapshot_carries_complete_explicit_state() -> None:
    snapshot = CalibrationRecoverySnapshot(
        calibration_id="calibration-1",
        calibration_version=1,
        profile_version=0,
        receipt=_receipt(),
        latest_checkpoint=_checkpoint(),
        pending_draft=None,
        pending_draft_result=None,
        last_outcome=_workflow_result(),
        directive=RecoveryDirective.INITIAL_INFERENCE,
    )
    assert snapshot.latest_checkpoint.input_receipt_id == snapshot.receipt.id
    assert snapshot.directive is RecoveryDirective.INITIAL_INFERENCE


def test_school_brief_source_is_fixed_and_delivery_is_separate() -> None:
    revision = SchoolBriefRevision(
        id="school-1-r1",
        brief_date=date(2026, 7, 11),
        revision=1,
        content_sha256=HASH_A,
        raw_text="",
        source="manual-paste",
        created_at=NOW,
    )
    outcome = SchoolBriefWriteResult(
        brief_date=revision.brief_date,
        revision=1,
        record=revision,
        trace_id="trace-1",
        no_op=False,
        allowed_actions=("replace_school_brief",),
    )
    delivered = DeliveredSchoolBriefResult(
        outcome=outcome,
        delivery=DeliveryMetadata(replayed=False),
    )
    assert delivered.outcome.record.source == "manual-paste"
    with pytest.raises(ValidationError):
        SchoolBriefRevision(**revision.model_dump(exclude={"source"}), source="file-import")


def test_calibration_input_result_has_explicit_replay_delivery() -> None:
    result = CalibrationInputReceiptResult(receipt=_receipt(), replayed=False)
    assert result.replayed is False
