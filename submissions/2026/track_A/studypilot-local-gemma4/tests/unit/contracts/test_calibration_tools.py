from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

import backend.contracts.calibration_tools as calibration_tools
from backend.contracts.calibration_tools import (
    CommitProfilePatchArgs,
    ProfileToolFailure,
    ProfileToolFailureCode,
    ProfileToolError,
    ProfileToolSuccess,
    ProposeProfilePatchArgs,
    TrustedProfileCommitCommand,
    validate_profile_tool_result,
)
from backend.contracts.family import (
    CalibrationState,
    CalibrationWorkflowResult,
    DeliveryMetadata,
    MemoryCategory,
    ProfilePatchAction,
    ProposedObservationInput,
)


TRUSTED_NAMES = {
    "calibration_id",
    "session_id",
    "receipt_id",
    "actor",
    "role",
    "trace_id",
    "idempotency_key",
    "expected_version",
    "expected_calibration_version",
    "expected_profile_version",
    "profile_version",
}
NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


def _observation() -> ProposedObservationInput:
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


def _commit_args() -> dict[str, Any]:
    return {
        "draft_id": "draft-1",
        "draft_digest": "a" * 64,
        "accepted_operation_ids": ("op-1",),
    }


def _outcome(state: CalibrationState) -> CalibrationWorkflowResult:
    return CalibrationWorkflowResult(
        calibration_id="calibration-1",
        calibration_version=2,
        profile_version=1 if state is CalibrationState.COMMITTED else 0,
        state=state,
        allowed_actions=("start_calibration",),
        trace_id="trace-1",
        data={},
    )


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_all_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value))
    return set()


def test_propose_schema_contains_only_observations() -> None:
    schema = ProposeProfilePatchArgs.model_json_schema()

    assert set(schema["properties"]) == {"observations"}
    assert TRUSTED_NAMES.isdisjoint(schema["properties"])
    assert schema["additionalProperties"] is False


def test_propose_requires_between_one_and_twenty_observations() -> None:
    with pytest.raises(ValidationError):
        ProposeProfilePatchArgs(observations=())
    with pytest.raises(ValidationError):
        ProposeProfilePatchArgs(observations=tuple(_observation() for _ in range(21)))

    assert len(
        ProposeProfilePatchArgs(
            observations=tuple(_observation() for _ in range(20))
        ).observations
    ) == 20


def test_commit_schema_is_exact_and_rejects_duplicate_ids() -> None:
    schema = CommitProfilePatchArgs.model_json_schema()

    assert set(schema["properties"]) == {
        "draft_id",
        "draft_digest",
        "accepted_operation_ids",
    }
    assert schema["additionalProperties"] is False
    with pytest.raises(ValidationError, match="accepted_operation_ids must be unique"):
        CommitProfilePatchArgs(
            draft_id="draft-1",
            draft_digest="a" * 64,
            accepted_operation_ids=("op-1", "op-1"),
        )


@pytest.mark.parametrize("draft_id", ["", "d" * 129])
def test_commit_rejects_invalid_draft_id_length(draft_id: str) -> None:
    with pytest.raises(ValidationError):
        CommitProfilePatchArgs(**{**_commit_args(), "draft_id": draft_id})


@pytest.mark.parametrize(
    "draft_digest",
    ["a" * 63, "a" * 65, "A" * 64, "g" * 64],
)
def test_commit_requires_lowercase_sha256_digest(draft_digest: str) -> None:
    with pytest.raises(ValidationError):
        CommitProfilePatchArgs(
            **{**_commit_args(), "draft_digest": draft_digest}
        )


def test_commit_requires_between_one_and_twenty_operation_ids() -> None:
    with pytest.raises(ValidationError):
        CommitProfilePatchArgs(
            **{**_commit_args(), "accepted_operation_ids": ()}
        )
    with pytest.raises(ValidationError):
        CommitProfilePatchArgs(
            **{
                **_commit_args(),
                "accepted_operation_ids": tuple(f"op-{index}" for index in range(21)),
            }
        )


def test_trusted_commit_command_is_frozen_and_rejects_duplicate_ids() -> None:
    payload = {
        "calibration_id": "calibration-1",
        "expected_calibration_version": 2,
        **_commit_args(),
    }
    command = TrustedProfileCommitCommand(**payload)

    with pytest.raises(ValidationError, match="frozen"):
        command.draft_id = "draft-2"
    with pytest.raises(ValidationError, match="accepted_operation_ids must be unique"):
        TrustedProfileCommitCommand(
            **{**payload, "accepted_operation_ids": ("op-1", "op-1")}
        )


@pytest.mark.parametrize("trusted_name", sorted(TRUSTED_NAMES))
@pytest.mark.parametrize(
    ("model_type", "payload"),
    [
        (ProposeProfilePatchArgs, {"observations": (_observation(),)}),
        (CommitProfilePatchArgs, _commit_args()),
    ],
)
def test_tool_arguments_reject_every_trusted_field_alias(
    trusted_name: str,
    model_type: type[ProposeProfilePatchArgs | CommitProfilePatchArgs],
    payload: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model_type(**payload, **{trusted_name: "trusted-value"})


def test_proposal_success_requires_needs_confirmation() -> None:
    invalid = {
        "ok": True,
        "operation": "profile_patch_proposed",
        "outcome": _outcome(CalibrationState.COMMITTED),
        "delivery": {"replayed": False},
    }

    with pytest.raises(
        ValidationError,
        match="tool operation and workflow state disagree",
    ):
        validate_profile_tool_result(invalid)


def test_commit_success_requires_committed() -> None:
    invalid = {
        "ok": True,
        "operation": "profile_patch_committed",
        "outcome": _outcome(CalibrationState.NEEDS_CONFIRMATION),
        "delivery": {"replayed": False},
    }

    with pytest.raises(
        ValidationError,
        match="tool operation and workflow state disagree",
    ):
        validate_profile_tool_result(invalid)


@pytest.mark.parametrize(
    ("operation", "state"),
    [
        ("profile_patch_proposed", CalibrationState.NEEDS_CONFIRMATION),
        ("profile_patch_committed", CalibrationState.COMMITTED),
    ],
)
def test_success_result_is_strict_and_sanitized(
    operation: str,
    state: CalibrationState,
) -> None:
    payload = {
        "ok": True,
        "operation": operation,
        "outcome": _outcome(state),
        "delivery": DeliveryMetadata(replayed=False),
    }
    result = validate_profile_tool_result(payload)

    assert isinstance(result, ProfileToolSuccess)
    dumped = result.model_dump(mode="json")
    assert _all_keys(dumped).isdisjoint(
        {
            "raw_text",
            "receipt_text",
            "prompt",
            "idempotency_key",
            "exception",
            "exception_message",
        }
    )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        validate_profile_tool_result({**payload, "trace_id": "trusted-trace"})


def test_failure_is_strict_and_sanitized() -> None:
    result = validate_profile_tool_result(
        {
            "ok": False,
            "operation": "commit_profile_patch",
            "error": {"code": "version_conflict", "retryable": False},
        }
    )

    assert isinstance(result, ProfileToolFailure)
    dumped = result.model_dump(mode="json")
    assert _all_keys(dumped).isdisjoint(
        {
            "raw_text",
            "receipt_text",
            "prompt",
            "idempotency_key",
            "exception",
            "exception_message",
        }
    )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        validate_profile_tool_result({**dumped, "exception": "private detail"})
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        validate_profile_tool_result(
            {**dumped, "error": {**dumped["error"], "message": "private detail"}}
        )


def test_profile_tool_failure_codes_are_exact() -> None:
    assert {item.value for item in ProfileToolFailureCode} == {
        "version_conflict",
        "idempotency_conflict",
        "invalid_transition",
        "not_found",
        "draft_digest_mismatch",
        "commit_command_invalid",
        "proposal_invalid",
        "model_confirmation_mismatch",
    }


@pytest.mark.parametrize(
    "code",
    [ProfileToolFailureCode.VERSION_CONFLICT, "version_conflict"],
)
def test_profile_tool_failure_code_accepts_enum_or_json_string(
    code: ProfileToolFailureCode | str,
) -> None:
    error = ProfileToolError(code=code, retryable=False)

    assert error.code is ProfileToolFailureCode.VERSION_CONFLICT


@pytest.mark.parametrize(
    "code",
    [b"version_conflict", bytearray(b"version_conflict"), 1],
)
def test_profile_tool_failure_code_rejects_non_string_inputs(code: object) -> None:
    with pytest.raises(ValidationError):
        ProfileToolError(code=code, retryable=False)


@pytest.mark.parametrize("ok", [1, 1.0])
def test_profile_tool_success_rejects_numeric_discriminator(ok: int | float) -> None:
    with pytest.raises(ValidationError):
        validate_profile_tool_result(
            {
                "ok": ok,
                "operation": "profile_patch_proposed",
                "outcome": _outcome(CalibrationState.NEEDS_CONFIRMATION),
                "delivery": DeliveryMetadata(replayed=False),
            }
        )


@pytest.mark.parametrize("ok", [0, 0.0])
def test_profile_tool_failure_rejects_numeric_discriminator(ok: int | float) -> None:
    with pytest.raises(ValidationError):
        validate_profile_tool_result(
            {
                "ok": ok,
                "operation": "commit_profile_patch",
                "error": {"code": "version_conflict", "retryable": False},
            }
        )


@pytest.mark.parametrize("ok", [1, 1.0])
def test_profile_tool_success_constructor_rejects_numeric_ok(ok: int | float) -> None:
    with pytest.raises(ValidationError):
        ProfileToolSuccess(
            ok=ok,
            operation="profile_patch_proposed",
            outcome=_outcome(CalibrationState.NEEDS_CONFIRMATION),
            delivery=DeliveryMetadata(replayed=False),
        )


@pytest.mark.parametrize("ok", [0, 0.0])
def test_profile_tool_failure_constructor_rejects_numeric_ok(ok: int | float) -> None:
    with pytest.raises(ValidationError):
        ProfileToolFailure(
            ok=ok,
            operation="commit_profile_patch",
            error=ProfileToolError(
                code=ProfileToolFailureCode.VERSION_CONFLICT,
                retryable=False,
            ),
        )


def test_profile_tool_result_constructors_accept_exact_bool() -> None:
    success = ProfileToolSuccess(
        ok=True,
        operation="profile_patch_proposed",
        outcome=_outcome(CalibrationState.NEEDS_CONFIRMATION),
        delivery=DeliveryMetadata(replayed=False),
    )
    failure = ProfileToolFailure(
        ok=False,
        operation="commit_profile_patch",
        error=ProfileToolError(
            code=ProfileToolFailureCode.VERSION_CONFLICT,
            retryable=False,
        ),
    )

    assert success.ok is True
    assert failure.ok is False


def test_extract_calibration_evidence_schema_is_small_and_strict() -> None:
    model_type = calibration_tools.ExtractCalibrationEvidenceArgs
    schema = model_type.model_json_schema()

    assert set(schema["properties"]) == {"duration_groups", "unapplied_notes"}
    assert TRUSTED_NAMES.isdisjoint(_all_keys(schema))
    assert schema["additionalProperties"] is False
    evidence = model_type(
        duration_groups=(
            {
                "subject": "mathematics",
                "task_type": "written",
                "minutes": (31, 34, 29),
            },
        ),
        unapplied_notes=("英语开始前需要提醒",),
    )

    assert evidence.duration_groups[0].minutes == (31, 34, 29)
    assert evidence.duration_groups[0].workload_band.value == "medium"

    explicit = model_type(
        duration_groups=(
            {
                "subject": "mathematics",
                "task_type": "written",
                "workload_band": "small",
                "minutes": (10,),
            },
        )
    )
    assert explicit.duration_groups[0].workload_band.value == "small"


def test_extract_calibration_evidence_rejects_invalid_limits_and_duplicates() -> None:
    model_type = calibration_tools.ExtractCalibrationEvidenceArgs
    group = {
        "subject": "mathematics",
        "task_type": "written",
        "minutes": (31,),
    }

    with pytest.raises(ValidationError):
        model_type(duration_groups=())
    with pytest.raises(ValidationError):
        model_type(duration_groups=(group, group))
    with pytest.raises(ValidationError):
        model_type(duration_groups=({**group, "minutes": (4,)},))
    with pytest.raises(ValidationError):
        model_type(duration_groups=({**group, "minutes": tuple(range(10, 19))},))
    with pytest.raises(ValidationError):
        model_type(
            duration_groups=(group,),
            unapplied_notes=tuple(f"note-{index}" for index in range(6)),
        )
    with pytest.raises(ValidationError):
        model_type(
            duration_groups=({**group, "subject": "physics"},),
        )
