from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from backend.contracts.api import (
    ApiErrorCode,
    ApiErrorDetail,
    CalibrationAbandonRequest,
    CalibrationAction,
    CalibrationCommitRequest,
    CalibrationCreateRequest,
    CalibrationRecoveryData,
    CalibrationResponseEnvelope,
    CalibrationRetryRequest,
    CalibrationSimplifyRequest,
    CalibrationReviseRequest,
    ErrorEnvelope,
    HealthComponent,
    HealthResponse,
    ModelHealthComponent,
    ModelRecoveryData,
    NarrationStatus,
    NoDataMetric,
    ProfilePatchCommitData,
    ProfilePatchProposalData,
    SchoolBriefHistoryEnvelope,
    SchoolBriefReadEnvelope,
    SchoolBriefWriteEnvelope,
    SchoolBriefWriteRequest,
    ValidationIssue,
    WeeklySummaryData,
    WeeklySummaryResponse,
)
from backend.contracts.family import (
    CalibrationState,
    CalibrationSummary,
    DeliveryMetadata,
    MemoryCategory,
    PendingKind,
    ProfileCommit,
    ProfilePatchAction,
    ProfilePatchDraft,
    ProposedObservation,
    ProposedObservationInput,
    SchoolBriefRevision,
    SchoolBriefWriteResult,
)


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
HASH_A = "a" * 64
HASH_B = "b" * 64
FORBIDDEN_POST_FIELDS = (
    "actor",
    "role",
    "session_id",
    "source_path",
    "trace_id",
)


def _observation_input() -> ProposedObservationInput:
    return ProposedObservationInput(
        action=ProfilePatchAction.ASSERT,
        category=MemoryCategory.SUBJECT_PERFORMANCE,
        subject="Mathematics",
        task_type="written",
        metric="score",
        value_number=88.0,
        unit="points",
        confidence=0.9,
        sample_count=1,
        observed_at=NOW,
    )


def _observation() -> ProposedObservation:
    return ProposedObservation(
        **_observation_input().model_dump(),
        operation_id="operation-1",
    )


def _draft(**updates: Any) -> ProfilePatchDraft:
    payload = {
        "id": "draft-1",
        "calibration_id": "calibration-1",
        "receipt_id": "receipt-1",
        "base_profile_version": 0,
        "proposal_digest": HASH_A,
        "draft_digest": HASH_B,
        "observations": (_observation(),),
        "created_at": NOW,
    }
    return ProfilePatchDraft(**{**payload, **updates})


def _commit(**updates: Any) -> ProfileCommit:
    payload = {
        "id": "commit-1",
        "calibration_id": "calibration-1",
        "draft_id": "draft-1",
        "profile_version": 1,
        "accepted_operation_ids": ("operation-1",),
        "confirmed_by": "parent-1",
        "committed_at": NOW,
    }
    return ProfileCommit(**{**payload, **updates})


def _proposal_data(**updates: Any) -> ProfilePatchProposalData:
    payload = {
        "draft": _draft(),
        "diff_preview": (_observation(),),
        "narration": "Please confirm this profile change.",
        "narration_status": NarrationStatus.AVAILABLE,
    }
    return ProfilePatchProposalData(**{**payload, **updates})


def _commit_data(**updates: Any) -> ProfilePatchCommitData:
    payload = {
        "commit": _commit(),
        "draft_digest": HASH_B,
        "accepted_operation_ids": ("operation-1",),
        "observation_event_ids": ("memory-1",),
        "narration": None,
        "narration_status": NarrationStatus.NOT_REQUESTED,
    }
    return ProfilePatchCommitData(**{**payload, **updates})


def _recovery_data() -> CalibrationRecoveryData:
    return CalibrationRecoveryData(
        input_receipt_id="receipt-1",
        resume_stage="profile_propose",
        pending_kind=PendingKind.MODEL_RETRY,
        pending_entity_id="calibration-1",
    )


def _model_recovery_data() -> ModelRecoveryData:
    return ModelRecoveryData(
        calibration_id="calibration-1",
        calibration_version=2,
        profile_version=0,
        stage=CalibrationState.MODEL_UNAVAILABLE,
        allowed_actions=(
            "retry_last_turn",
            "use_simplified_calibration",
            "abandon_profile_patch",
        ),
        resume_stage="profile_propose",
        pending_kind=PendingKind.MODEL_RETRY,
        pending_entity_id="calibration-1",
        input_receipt_id="receipt-1",
    )


def _envelope_payload(
    stage: CalibrationState = CalibrationState.NEEDS_CONFIRMATION,
) -> dict[str, Any]:
    return {
        "calibration_id": "calibration-1",
        "calibration_version": 2,
        "profile_version": 0,
        "stage": stage,
        "allowed_actions": (
            CalibrationAction.COMMIT_PROFILE_PATCH,
            CalibrationAction.REVISE_PROFILE_PATCH,
            CalibrationAction.ABANDON_PROFILE_PATCH,
        ),
        "trace_id": "trace-1",
        "data": _proposal_data(),
        "delivery": DeliveryMetadata(replayed=False),
    }


def _school_revision() -> SchoolBriefRevision:
    return SchoolBriefRevision(
        id="school-1-r1",
        brief_date=date(2026, 7, 11),
        revision=1,
        content_sha256=HASH_A,
        raw_text="",
        source="manual-paste",
        created_at=NOW,
    )


def _school_write_result() -> SchoolBriefWriteResult:
    revision = _school_revision()
    return SchoolBriefWriteResult(
        brief_date=revision.brief_date,
        revision=revision.revision,
        record=revision,
        trace_id="trace-1",
        no_op=False,
        allowed_actions=("replace_school_brief",),
    )


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_all_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value))
    return set()


POST_REQUESTS: tuple[tuple[type[Any], dict[str, Any]], ...] = (
    (
        CalibrationCreateRequest,
        {
            "text": "Math homework takes longer than expected.",
            "expected_calibration_version": 0,
            "expected_profile_version": 0,
        },
    ),
    (
        CalibrationRetryRequest,
        {"expected_calibration_version": 1},
    ),
    (
        CalibrationSimplifyRequest,
        {
            "expected_calibration_version": 2,
            "duration_groups": (
                {
                    "subject": "mathematics",
                    "task_type": "written",
                    "conservative_minutes": 34,
                },
            ),
        },
    ),
    (
        CalibrationCommitRequest,
        {
            "expected_calibration_version": 1,
            "draft_id": "draft-1",
            "draft_digest": HASH_A,
            "accepted_operation_ids": ("operation-1",),
        },
    ),
    (
        CalibrationReviseRequest,
        {
            "expected_calibration_version": 1,
            "draft_id": "draft-1",
            "revised_observations": (_observation_input(),),
        },
    ),
    (
        CalibrationAbandonRequest,
        {"expected_calibration_version": 1},
    ),
    (
        SchoolBriefWriteRequest,
        {
            "brief_date": date(2026, 7, 11),
            "raw_text": "",
            "expected_revision": 0,
        },
    ),
)


@pytest.mark.parametrize(("model_type", "payload"), POST_REQUESTS)
@pytest.mark.parametrize("field", FORBIDDEN_POST_FIELDS)
def test_every_post_body_rejects_trusted_context(
    model_type: type[Any],
    payload: dict[str, Any],
    field: str,
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model_type(**payload, **{field: "trusted-value"})


@pytest.mark.parametrize("value", [-1, 1, False, 0.0, "0"])
def test_calibration_create_version_accepts_only_integer_zero(value: object) -> None:
    payload = POST_REQUESTS[0][1]
    with pytest.raises(ValidationError):
        CalibrationCreateRequest(**{**payload, "expected_calibration_version": value})


def test_calibration_create_accepts_integer_zero() -> None:
    request = CalibrationCreateRequest(**POST_REQUESTS[0][1])
    assert request.expected_calibration_version == 0
    assert type(request.expected_calibration_version) is int


def test_commit_request_rejects_duplicate_operation_ids() -> None:
    payload = POST_REQUESTS[3][1]
    with pytest.raises(ValidationError, match="accepted_operation_ids must be unique"):
        CalibrationCommitRequest(
            **{
                **payload,
                "accepted_operation_ids": ("operation-1", "operation-1"),
            }
        )


def test_school_write_accepts_empty_text() -> None:
    request = SchoolBriefWriteRequest(**POST_REQUESTS[6][1])
    assert request.raw_text == ""


def test_school_write_accepts_exact_http_date_string() -> None:
    request = SchoolBriefWriteRequest.model_validate(
        {
            "brief_date": "2026-07-11",
            "raw_text": "",
            "expected_revision": 0,
        }
    )

    assert request.brief_date == date(2026, 7, 11)


class _DateSubclass(date):
    pass


@pytest.mark.parametrize(
    "brief_date",
    [
        _DateSubclass(2026, 7, 11),
        datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        b"2026-07-11",
        20260711,
        True,
        "20260711",
        "2026-W28-6",
        "2026-02-30",
    ],
)
def test_school_write_rejects_non_exact_http_date_values(brief_date: object) -> None:
    with pytest.raises(ValidationError):
        SchoolBriefWriteRequest.model_validate(
            {
                "brief_date": brief_date,
                "raw_text": "",
                "expected_revision": 0,
            }
        )


def test_calibration_action_values_are_exact() -> None:
    assert {item.value for item in CalibrationAction} == {
        "generate_profile_patch",
        "retry_last_turn",
        "use_simplified_calibration",
        "commit_profile_patch",
        "revise_profile_patch",
        "abandon_profile_patch",
        "start_calibration",
    }


def test_simplified_calibration_contract_is_strict_and_bounded() -> None:
    request = CalibrationSimplifyRequest(
        expected_calibration_version=2,
        duration_groups=(
            {
                "subject": "english",
                "task_type": "recitation",
                "conservative_minutes": 30,
            },
        ),
    )

    assert request.duration_groups[0].conservative_minutes == 30
    assert request.duration_groups[0].workload_band.value == "medium"
    with pytest.raises(ValidationError):
        CalibrationSimplifyRequest(
            expected_calibration_version=2,
            duration_groups=(),
        )
    with pytest.raises(ValidationError):
        CalibrationSimplifyRequest(
            expected_calibration_version=2,
            duration_groups=(
                {
                    "subject": "english",
                    "task_type": "recitation",
                    "conservative_minutes": 4,
                },
            ),
        )
    with pytest.raises(ValidationError):
        CalibrationSimplifyRequest(
            expected_calibration_version=2,
            duration_groups=(
                {
                    "subject": "english",
                    "task_type": "recitation",
                    "conservative_minutes": 30,
                },
                {
                    "subject": "english",
                    "task_type": "recitation",
                    "conservative_minutes": 31,
                },
            ),
        )


def test_calibration_response_compatibility_fields_default_empty() -> None:
    assert _proposal_data().unapplied_notes == ()
    assert _proposal_data().calibration_details == ()
    assert _recovery_data().failure_code is None
    assert _model_recovery_data().failure_code is None


def test_calibration_envelope_uses_two_explicit_versions() -> None:
    response = CalibrationResponseEnvelope(**_envelope_payload())

    dumped = response.model_dump(mode="json")
    assert "version" not in dumped
    assert dumped["calibration_version"] == 2
    assert dumped["profile_version"] == 0
    assert response.stage is CalibrationState.NEEDS_CONFIRMATION
    assert all(isinstance(action, CalibrationAction) for action in response.allowed_actions)


@pytest.mark.parametrize(
    ("stage", "data"),
    [
        (CalibrationState.NEEDS_CONFIRMATION, _commit_data()),
        (CalibrationState.NEEDS_CONFIRMATION, _recovery_data()),
        (CalibrationState.COMMITTED, _proposal_data()),
        (CalibrationState.COMMITTED, _recovery_data()),
        (CalibrationState.INPUT_SAVED, _proposal_data()),
        (CalibrationState.MODEL_UNAVAILABLE, _proposal_data()),
        (CalibrationState.RETRY_PENDING, _proposal_data()),
        (CalibrationState.ABANDONED, _proposal_data()),
    ],
)
def test_calibration_envelope_rejects_stage_data_mismatch(
    stage: CalibrationState,
    data: object,
) -> None:
    payload = _envelope_payload(stage)
    with pytest.raises(ValidationError, match="calibration stage and data kind disagree"):
        CalibrationResponseEnvelope(**{**payload, "data": data})


@pytest.mark.parametrize(
    "actions",
    [
        (
            CalibrationAction.REVISE_PROFILE_PATCH,
            CalibrationAction.COMMIT_PROFILE_PATCH,
            CalibrationAction.ABANDON_PROFILE_PATCH,
        ),
        (
            CalibrationAction.COMMIT_PROFILE_PATCH,
            CalibrationAction.REVISE_PROFILE_PATCH,
        ),
        (
            CalibrationAction.COMMIT_PROFILE_PATCH,
            CalibrationAction.REVISE_PROFILE_PATCH,
            CalibrationAction.ABANDON_PROFILE_PATCH,
            CalibrationAction.START_CALIBRATION,
        ),
    ],
)
def test_calibration_envelope_requires_exact_action_order(
    actions: tuple[CalibrationAction, ...],
) -> None:
    with pytest.raises(ValidationError, match="calibration actions do not match stage"):
        CalibrationResponseEnvelope(**{**_envelope_payload(), "allowed_actions": actions})


@pytest.mark.parametrize(
    "draft",
    [
        _draft(calibration_id="calibration-2"),
        _draft(base_profile_version=1),
    ],
)
def test_proposal_data_must_belong_to_envelope(draft: ProfilePatchDraft) -> None:
    with pytest.raises(ValidationError, match="proposal data does not belong to envelope"):
        CalibrationResponseEnvelope(
            **{
                **_envelope_payload(),
                "data": _proposal_data(draft=draft),
            }
        )


@pytest.mark.parametrize(
    "commit",
    [
        _commit(calibration_id="calibration-2"),
        _commit(profile_version=2),
    ],
)
def test_commit_data_must_belong_to_envelope(commit: ProfileCommit) -> None:
    payload = _envelope_payload(CalibrationState.COMMITTED)
    payload.update(
        profile_version=1,
        allowed_actions=(CalibrationAction.START_CALIBRATION,),
        data=_commit_data(commit=commit),
    )
    with pytest.raises(ValidationError, match="commit data does not belong to envelope"):
        CalibrationResponseEnvelope(**payload)


@pytest.mark.parametrize("data_factory", [_proposal_data, _commit_data])
@pytest.mark.parametrize(
    ("status", "narration"),
    [
        (NarrationStatus.AVAILABLE, None),
        (NarrationStatus.AVAILABLE, "   "),
        (NarrationStatus.UNAVAILABLE, "Unexpected narration"),
        (NarrationStatus.NOT_REQUESTED, "Unexpected narration"),
    ],
)
def test_profile_response_data_validates_narration(
    data_factory: Any,
    status: NarrationStatus,
    narration: str | None,
) -> None:
    with pytest.raises(ValidationError, match="narration"):
        data_factory(narration_status=status, narration=narration)


def test_api_error_literals_are_locked() -> None:
    values = {item.value for item in ApiErrorCode}
    assert {
        "commit_command_invalid",
        "profile_proposal_invalid",
        "retry_lineage_conflict",
        "method_not_allowed",
    } <= values
    assert values == {
        "schema_invalid",
        "not_found",
        "method_not_allowed",
        "version_conflict",
        "idempotency_conflict",
        "invalid_transition",
        "draft_digest_mismatch",
        "commit_command_invalid",
        "profile_proposal_invalid",
        "retry_lineage_conflict",
        "model_protocol_error",
        "model_unavailable",
        "internal_error",
    }


def test_error_envelope_is_strict_and_sanitized() -> None:
    envelope = ErrorEnvelope(
        error=ApiErrorDetail(
            code=ApiErrorCode.SCHEMA_INVALID,
            message="The request body is invalid.",
            issues=(ValidationIssue(location=("body", "text"), type="string_too_long"),),
        ),
        trace_id="trace-1",
    )

    dumped = envelope.model_dump(mode="json")
    assert _all_keys(dumped).isdisjoint(
        {"exception", "exception_message", "input", "context", "provenance"}
    )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ErrorEnvelope(**envelope.model_dump(), exception="private detail")


def test_model_recovery_data_has_fixed_public_state() -> None:
    recovery = _model_recovery_data()

    assert recovery.input_saved is True
    with pytest.raises(ValidationError):
        ModelRecoveryData(**{**recovery.model_dump(), "input_saved": False})


@pytest.mark.parametrize("recovery", [_recovery_data(), _model_recovery_data()])
@pytest.mark.parametrize("input_saved", [1, 0])
def test_recovery_input_saved_rejects_integer_literals(
    recovery: CalibrationRecoveryData | ModelRecoveryData,
    input_saved: int,
) -> None:
    with pytest.raises(ValidationError):
        type(recovery)(**{**recovery.model_dump(), "input_saved": input_saved})


def test_school_envelopes_are_separate_and_strict() -> None:
    write = SchoolBriefWriteEnvelope(
        trace_id="trace-1",
        data=_school_write_result(),
        delivery=DeliveryMetadata(replayed=False),
    )
    read = SchoolBriefReadEnvelope(trace_id="trace-2", data=_school_revision())
    history = SchoolBriefHistoryEnvelope(
        trace_id="trace-3",
        brief_date=date(2026, 7, 11),
        revisions=(_school_revision(),),
    )

    assert write.trace_id == write.data.trace_id
    assert read.data.raw_text == ""
    assert history.brief_date == read.data.brief_date
    assert history.revisions == (read.data,)
    for envelope in (write, read, history):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            type(envelope)(**envelope.model_dump(), provenance={"source": "runtime"})


def test_school_write_envelope_preserves_request_and_stored_outcome_traces() -> None:
    envelope = SchoolBriefWriteEnvelope(
        trace_id="trace-request-2",
        data=_school_write_result(),
        delivery=DeliveryMetadata(replayed=True),
    )

    dumped = envelope.model_dump(mode="json")
    assert dumped["trace_id"] == "trace-request-2"
    assert dumped["data"]["trace_id"] == "trace-1"


def test_health_response_has_strict_components_and_consistent_readiness() -> None:
    response = HealthResponse(
        ready=True,
        trace_id="trace-health-1",
        api=HealthComponent(status="ok", error_code=None),
        sqlite=HealthComponent(status="ok", error_code=None),
        model=ModelHealthComponent(
            status="ok",
            model_id="gemma-4-26b-a4b-it",
            loaded=True,
            tool_use=True,
            quantization="Q4_K_M",
            error_code=None,
        ),
    )

    assert response.model.model_id == "gemma-4-26b-a4b-it"
    assert response.model.quantization == "Q4_K_M"
    with pytest.raises(ValidationError):
        HealthComponent(status="ok", error_code="sqlite_unavailable")
    with pytest.raises(ValidationError, match="readiness"):
        HealthResponse(**{**response.model_dump(), "ready": False})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("value", 0.0),
        ("numerator", 1),
        ("denominator", 1),
        ("status", "available"),
    ],
)
def test_no_data_metric_has_exact_empty_values(field: str, value: object) -> None:
    payload = {
        "value": None,
        "numerator": 0,
        "denominator": 0,
        "status": "no_data",
    }
    with pytest.raises(ValidationError):
        NoDataMetric(**{**payload, field: value})


@pytest.mark.parametrize("field", ["numerator", "denominator"])
@pytest.mark.parametrize("value", [False, 0.0])
def test_no_data_metric_rejects_cross_type_zero(
    field: str,
    value: bool | float,
) -> None:
    payload = {
        "value": None,
        "numerator": 0,
        "denominator": 0,
        "status": "no_data",
    }
    with pytest.raises(ValidationError):
        NoDataMetric(**{**payload, field: value})


def test_no_data_metric_accepts_exact_integer_zero() -> None:
    metric = NoDataMetric(
        value=None,
        numerator=0,
        denominator=0,
        status="no_data",
    )

    assert type(metric.numerator) is int
    assert type(metric.denominator) is int


def test_weekly_summary_has_four_no_data_metrics_without_provenance() -> None:
    metric = NoDataMetric(value=None, numerator=0, denominator=0, status="no_data")
    summary = WeeklySummaryResponse(
        trace_id="trace-weekly-1",
        data=WeeklySummaryData(
            week_start=date(2026, 7, 6),
            week_end=date(2026, 7, 12),
            profile_version=1,
            latest_calibration=CalibrationSummary(
                calibration_id="calibration-1",
                calibration_version=2,
                profile_version=1,
                state=CalibrationState.COMMITTED,
                occurred_at=NOW,
            ),
            confirmed_observation_count=1,
            estimate_error=metric,
            omissions=metric,
            start_confidence=metric,
            parent_interventions=metric,
        ),
    )

    dumped = summary.model_dump(mode="json")
    assert set(dumped) == {"trace_id", "data"}
    assert set(dumped["data"]) == {
        "week_start",
        "week_end",
        "profile_version",
        "latest_calibration",
        "confirmed_observation_count",
        "estimate_error",
        "omissions",
        "start_confidence",
        "parent_interventions",
    }
    assert "provenance" not in _all_keys(dumped)
