from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from backend.contracts.calibration_tools import (
    CommitProfilePatchArgs,
    ExtractCalibrationEvidenceArgs,
    ProfileToolFailure,
    ProfileToolFailureCode,
    ProfileToolSuccess,
    TrustedProfileCommitCommand,
)
from backend.contracts.family import (
    CalibrationState,
    CalibrationWorkflowResult,
    DeliveredCalibrationResult,
    DeliveryMetadata,
    FamilyWriteContext,
    MemoryCategory,
    ProfilePatchAction,
    ProposedObservationInput,
)
from backend.errors import (
    CommitCommandInvalidError,
    DraftDigestMismatchError,
    IdempotencyConflictError,
    InvalidTransitionError,
    NotFoundError,
    ProfileProposalInvalidError,
    VersionConflictError,
)
from backend.orchestration import calibration as calibration_adapter
from backend.orchestration.calibration import (
    PROFILE_PROPOSE_SYSTEM_PROMPT,
    build_profile_propose_execution,
)
from backend.orchestration.harness import HarnessError
from backend.orchestration.lm_studio import LMStudioClient
from backend.orchestration.tool_registry import (
    ToolExecutionContext,
    WorkflowPhase,
    derive_write_idempotency_key,
)
from backend.storage.database import connect_database, run_migrations
from backend.storage.family_context import FamilyContextRepository
from backend.storage.run_traces import RunTraceRepository


MODEL = "gemma-4-26b-a4b-it"
BASE_URL = "http://127.0.0.1:1234/v1"
OBSERVED_AT = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def _save_recovery(
    repository: FamilyContextRepository,
    *,
    calibration_id: str = "calibration-adapter-1",
):
    repository.save_calibration_input(
        calibration_id,
        "Mathematics written work is usually completed securely.",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=FamilyWriteContext(
            actor="local-parent",
            role="parent",
            trace_id="trace-receipt",
            idempotency_key="receipt-http-key-0001",
        ),
    )
    return repository.get_calibration_recovery(calibration_id)


def _observation(**overrides: object) -> ProposedObservationInput:
    payload: dict[str, object] = {
        "action": ProfilePatchAction.ASSERT,
        "category": MemoryCategory.SUBJECT_PERFORMANCE,
        "subject": "Mathematics",
        "task_type": "written",
        "metric": "assessment_level",
        "value_text": "secure",
        "value_number": None,
        "unit": None,
        "confidence": 0.85,
        "sample_count": None,
        "observed_at": OBSERVED_AT,
        "target_event_id": None,
    }
    payload.update(overrides)
    return ProposedObservationInput(**payload)


def _proposal_arguments() -> ExtractCalibrationEvidenceArgs:
    return ExtractCalibrationEvidenceArgs(
        duration_groups=(
            {
                "subject": "mathematics",
                "task_type": "written",
                "minutes": (31, 34, 29),
            },
            {
                "subject": "chinese",
                "task_type": "reading",
                "minutes": (24, 26, 22),
            },
            {
                "subject": "english",
                "task_type": "recitation",
                "minutes": (28, 30),
            },
            {
                "subject": "geography",
                "task_type": "map_reading",
                "minutes": (18, 21),
            },
        ),
        unapplied_notes=("英语开始前需要提醒",),
    )


def _tool_call_response(
    arguments: ExtractCalibrationEvidenceArgs,
    *,
    call_id: str = "proposal-call-1",
    content: str | None = "",
) -> dict[str, object]:
    return {
        "model": MODEL,
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": "extract_calibration_evidence",
                                "arguments": json.dumps(
                                    arguments.model_dump(mode="json"),
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                            },
                        }
                    ],
                },
            }
        ],
    }


def _raw_tool_call_response(
    arguments: str,
    *,
    call_id: str,
) -> dict[str, object]:
    return {
        "model": MODEL,
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": "extract_calibration_evidence",
                                "arguments": arguments,
                            },
                        }
                    ],
                },
            }
        ],
    }


def _text_response(content: str = "Proposal ready for parent review.") -> dict[str, object]:
    return {
        "model": MODEL,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
    }


class _QueuedTransport:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = list(responses)
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.payloads.append(json.loads(request.content))
        return httpx.Response(200, json=self.responses.pop(0))


def _direct_context(execution, *, trace_id: str | None = None) -> ToolExecutionContext:
    caller_key = execution.request.idempotency_key
    assert caller_key is not None
    return ToolExecutionContext(
        session_id=execution.request.session_id,
        actor=execution.request.actor,
        role=execution.request.role,
        expected_version=execution.request.expected_version,
        trace_id=trace_id or execution.request.trace_id,
        idempotency_key=derive_write_idempotency_key(
            caller_key,
            WorkflowPhase.PROFILE_PROPOSE,
            "extract_calibration_evidence",
        ),
    )


def _build_direct_execution(
    database_path: Path,
    repository: FamilyContextRepository,
    recovery,
    *,
    trace_id: str = "trace-proposal",
    caller_idempotency_key: str = "proposal-http-key-0001",
):
    client = LMStudioClient(
        BASE_URL,
        MODEL,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=_text_response())
        ),
    )
    return build_profile_propose_execution(
        repository=repository,
        recovery=recovery,
        profile_snapshot=repository.get_profile_snapshot(recovery.profile_version),
        client=client,
        trace_repository=RunTraceRepository(database_path),
        caller_idempotency_key=caller_idempotency_key,
        trace_id=trace_id,
    )


def _proposal_handler(execution):
    return execution.harness.registry.expose_phase(
        WorkflowPhase.PROFILE_PROPOSE
    )[0].handler


def _prepare_commit_command(
    repository: FamilyContextRepository,
    *,
    calibration_id: str = "calibration-adapter-1",
) -> tuple[Any, TrustedProfileCommitCommand]:
    initial = _save_recovery(repository, calibration_id=calibration_id)
    repository.propose_profile_patch(
        calibration_id,
        initial.receipt.id,
        (
            _observation(subject="Mathematics", value_text="secure"),
            _observation(subject="English", value_text="developing"),
        ),
        expected_calibration_version=initial.calibration_version,
        context=FamilyWriteContext(
            actor="local-parent",
            role="parent",
            trace_id="trace-prepare-proposal",
            idempotency_key="prepare-proposal-key",
        ),
    )
    recovery = repository.get_calibration_recovery(calibration_id)
    draft = recovery.pending_draft
    assert draft is not None
    return recovery, TrustedProfileCommitCommand(
        calibration_id=calibration_id,
        expected_calibration_version=recovery.calibration_version,
        draft_id=draft.id,
        draft_digest=draft.draft_digest,
        accepted_operation_ids=tuple(
            observation.operation_id for observation in draft.observations
        ),
    )


def _commit_arguments(
    command: TrustedProfileCommitCommand,
    **overrides: object,
) -> CommitProfilePatchArgs:
    payload: dict[str, object] = {
        "draft_id": command.draft_id,
        "draft_digest": command.draft_digest,
        "accepted_operation_ids": command.accepted_operation_ids,
    }
    payload.update(overrides)
    return CommitProfilePatchArgs(**payload)


def _commit_tool_call_response(
    arguments: CommitProfilePatchArgs,
    *,
    content: str | None = "",
) -> dict[str, object]:
    return {
        "model": MODEL,
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": "commit-call-1",
                            "type": "function",
                            "function": {
                                "name": "commit_profile_patch",
                                "arguments": json.dumps(
                                    arguments.model_dump(mode="json"),
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                            },
                        }
                    ],
                },
            }
        ],
    }


def _build_commit_execution(
    database_path: Path,
    repository: FamilyContextRepository,
    recovery,
    command: TrustedProfileCommitCommand,
    *,
    trace_id: str = "trace-commit",
    caller_idempotency_key: str = "commit-http-key-0001",
    client: LMStudioClient | None = None,
):
    return calibration_adapter.build_profile_commit_execution(
        repository=repository,
        recovery=recovery,
        command=command,
        client=client
        or LMStudioClient(
            BASE_URL,
            MODEL,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=_text_response("Committed."))
            ),
        ),
        trace_repository=RunTraceRepository(database_path),
        caller_idempotency_key=caller_idempotency_key,
        trace_id=trace_id,
    )


def _commit_handler(execution):
    return execution.harness.registry.expose_phase(
        WorkflowPhase.PROFILE_COMMIT
    )[0].handler


def _commit_context(execution) -> ToolExecutionContext:
    caller_key = execution.request.idempotency_key
    assert caller_key is not None
    return ToolExecutionContext(
        session_id=execution.request.session_id,
        actor=execution.request.actor,
        role=execution.request.role,
        expected_version=execution.request.expected_version,
        trace_id=execution.request.trace_id,
        idempotency_key=derive_write_idempotency_key(
            caller_key,
            WorkflowPhase.PROFILE_COMMIT,
            "commit_profile_patch",
        ),
    )


def _delivered_proposal(
    recovery,
    *,
    trace_id: str,
    state: CalibrationState = CalibrationState.NEEDS_CONFIRMATION,
    calibration_version: int | None = None,
    profile_version: int | None = None,
    replayed: bool = False,
) -> DeliveredCalibrationResult:
    return DeliveredCalibrationResult(
        outcome=CalibrationWorkflowResult(
            calibration_id=recovery.calibration_id,
            calibration_version=(
                recovery.calibration_version + 1
                if calibration_version is None
                else calibration_version
            ),
            profile_version=(
                recovery.profile_version
                if profile_version is None
                else profile_version
            ),
            state=state,
            allowed_actions=(),
            trace_id=trace_id,
            data={},
        ),
        delivery=DeliveryMetadata(replayed=replayed),
    )


def test_profile_propose_exposes_only_model_arguments_and_exact_trusted_request(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "calibration-adapter.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery = _save_recovery(repository)
    payloads: list[dict[str, object]] = []

    def transport(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": MODEL,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "no tool"},
                    }
                ],
            },
        )

    client = LMStudioClient(
        BASE_URL,
        MODEL,
        transport=httpx.MockTransport(transport),
    )
    execution = build_profile_propose_execution(
        repository=repository,
        recovery=recovery,
        profile_snapshot=repository.get_profile_snapshot(0),
        client=client,
        trace_repository=RunTraceRepository(database_path),
        caller_idempotency_key="proposal-http-key-0001",
        trace_id="trace-proposal",
    )

    exposed = execution.harness.registry.expose_phase(
        WorkflowPhase.PROFILE_PROPOSE
    )
    assert tuple(item.name for item in exposed) == ("extract_calibration_evidence",)
    assert execution.request.session_id == recovery.calibration_id
    assert execution.request.expected_version == recovery.calibration_version
    assert execution.request.role == "parent"
    assert execution.request.actor == "local-parent"
    assert execution.request.idempotency_key == "proposal-http-key-0001"
    assert client.evidence_provenance == "synthetic_transport"
    assert execution.request.max_tokens == 4096
    assert execution.request.messages[0] == {
        "role": "system",
        "content": PROFILE_PROPOSE_SYSTEM_PROMPT,
    }
    assert "extract_calibration_evidence" in PROFILE_PROPOSE_SYSTEM_PROMPT
    assert "Do not output timestamps, units, confidence, actions, ids, or versions" in (
        PROFILE_PROPOSE_SYSTEM_PROMPT
    )
    assert "Geography map or coordinate-grid reading must use map_reading" in (
        PROFILE_PROPOSE_SYSTEM_PROMPT
    )
    assert "Never classify Chinese 读图 as ordinary reading" in (
        PROFILE_PROPOSE_SYSTEM_PROMPT
    )
    user_payload = json.loads(execution.request.messages[1]["content"])
    assert user_payload == {"receipt_text": recovery.receipt.raw_text}

    with pytest.raises(HarnessError) as raised:
        execution.harness.run(execution.request)

    assert raised.value.code == "required_tool_not_called"
    assert payloads[0]["tool_choice"] == "required"
    tools = payloads[0]["tools"]
    assert isinstance(tools, list)
    assert len(tools) == 1
    parameters = tools[0]["function"]["parameters"]
    assert set(parameters["properties"]) == {"duration_groups", "unapplied_notes"}
    assert not {
        "session_id",
        "actor",
        "role",
        "expected_version",
        "trace_id",
        "idempotency_key",
    } & set(parameters["properties"])


def test_proposal_handler_receives_hidden_key_and_exact_context_without_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "proposal-handler.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery = _save_recovery(repository)
    arguments = _proposal_arguments()
    queue = _QueuedTransport([_tool_call_response(arguments)])
    client = LMStudioClient(
        BASE_URL,
        MODEL,
        transport=httpx.MockTransport(queue),
    )
    seen_calls: list[tuple[tuple[object, ...], dict[str, Any]]] = []
    original = repository.propose_profile_patch

    def recording_proposal(*args: object, **kwargs: Any):
        seen_calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(repository, "propose_profile_patch", recording_proposal)
    execution = build_profile_propose_execution(
        repository=repository,
        recovery=recovery,
        profile_snapshot=repository.get_profile_snapshot(0),
        client=client,
        trace_repository=RunTraceRepository(database_path),
        caller_idempotency_key="proposal-http-key-0001",
        trace_id="trace-proposal",
    )

    harness_result = execution.harness.run(execution.request)

    assert harness_result.handler_executions == 1
    assert harness_result.model_calls == 1
    assert [payload["tool_choice"] for payload in queue.payloads] == ["required"]
    assert len(seen_calls) == 1
    call_args, call_kwargs = seen_calls[0]
    assert call_args[:2] == (recovery.calibration_id, recovery.receipt.id)
    assert call_kwargs["expected_calibration_version"] == (
        recovery.calibration_version
    )
    context = call_kwargs["context"]
    assert context.actor == "local-parent"
    assert context.role == "parent"
    assert context.trace_id == "trace-proposal"
    assert context.idempotency_key is not None
    assert len(context.idempotency_key) == 64
    assert context.idempotency_key != "proposal-http-key-0001"
    assert context.idempotency_key == derive_write_idempotency_key(
        "proposal-http-key-0001",
        WorkflowPhase.PROFILE_PROPOSE,
        "extract_calibration_evidence",
    )
    assert isinstance(execution.invocation.terminal_result, ProfileToolSuccess)
    assert execution.invocation.successful_business_result == (
        execution.invocation.terminal_result
    )
    assert execution.invocation.unexpected_handler_failure is False
    terminal = execution.invocation.terminal_result
    assert terminal.operation == "profile_patch_proposed"
    assert terminal.outcome.state is CalibrationState.NEEDS_CONFIRMATION
    assert terminal.outcome.calibration_version == recovery.calibration_version + 1
    assert terminal.outcome.profile_version == recovery.profile_version
    assert terminal.delivery.replayed is False
    assert repository.get_current_profile_version() == recovery.profile_version
    stored = repository.get_calibration_recovery(recovery.calibration_id)
    assert stored.pending_draft_result == terminal.outcome
    assert stored.calibration_version == recovery.calibration_version + 1
    assert stored.pending_draft_result is not None
    assert stored.pending_draft_result.data["unapplied_notes"] == [
        "英语开始前需要提醒"
    ]
    assert [
        item["reference_minutes"]
        for item in stored.pending_draft_result.data["calibration_details"]
    ] == [20, 20, 20, 25]
    assert {
        item["subject"]: item["value_number"]
        for item in stored.pending_draft_result.data["diff_preview"]
    } == {
        "mathematics": 1.7,
        "chinese": 1.3,
        "english": 1.5,
        "geography": 0.84,
    }
    tool_result = harness_result.tool_call_records[0].result
    assert tool_result == terminal.model_dump(mode="json")


def test_calibration_schema_repair_reemits_complete_evidence_once(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "calibration-schema-repair.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery = _save_recovery(repository)
    valid = _proposal_arguments()
    queue = _QueuedTransport(
        [
            _raw_tool_call_response(
                '{"duration_groups":[{"subject":"mathematics",'
                '"task_type":"written","minutes":[31,"private"]}],'
                '"unapplied_notes":[]}',
                call_id="bad-evidence",
            ),
            _tool_call_response(valid, call_id="repaired-evidence"),
        ]
    )
    execution = build_profile_propose_execution(
        repository=repository,
        recovery=recovery,
        profile_snapshot=repository.get_profile_snapshot(0),
        client=LMStudioClient(
            BASE_URL,
            MODEL,
            transport=httpx.MockTransport(queue),
        ),
        trace_repository=RunTraceRepository(database_path),
        caller_idempotency_key="schema-repair-http-key",
        trace_id="trace-schema-repair",
    )

    result = execution.harness.run(execution.request)

    assert result.model_calls == 2
    assert result.schema_repair_used is True
    assert result.handler_executions == 1
    repair = json.loads(queue.payloads[1]["messages"][-1]["content"])
    assert {
        (tuple(issue["location"]), issue["type"])
        for issue in repair["error"]["issues"]
    } == {
        (("duration_groups", 0, "minutes", 1), "int_type"),
        (("duration_groups",), "too_short"),
    }
    assert all(set(issue) == {"location", "type"} for issue in repair["error"]["issues"])
    assert "private" not in json.dumps(repair)
    stored = repository.get_calibration_recovery(recovery.calibration_id)
    assert stored.pending_draft_result is not None
    assert len(stored.pending_draft_result.data["diff_preview"]) == 4


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (
            VersionConflictError("calibration", "calibration-adapter-1", 1, 2),
            "version_conflict",
        ),
        (
            IdempotencyConflictError("propose_profile_patch", "redacted-key"),
            "idempotency_conflict",
        ),
        (
            InvalidTransitionError("input_saved", "committed"),
            "invalid_transition",
        ),
        (NotFoundError("calibration", "missing"), "not_found"),
        (DraftDigestMismatchError("draft-1"), "draft_digest_mismatch"),
        (CommitCommandInvalidError("ids_not_in_draft"), "commit_command_invalid"),
        (ProfileProposalInvalidError("invalid_target"), "proposal_invalid"),
    ],
    ids=[
        "version",
        "idempotency",
        "transition",
        "not-found",
        "digest",
        "command",
        "proposal",
    ],
)
def test_expected_handler_errors_become_typed_tool_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_code: str,
) -> None:
    database_path = tmp_path / "expected-handler-error.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery = _save_recovery(repository)
    execution = _build_direct_execution(database_path, repository, recovery)

    def raise_expected(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(repository, "propose_profile_patch", raise_expected)

    result = _proposal_handler(execution)(
        _proposal_arguments(),
        _direct_context(execution),
    )

    assert result["ok"] is False
    assert result["operation"] == "propose_profile_patch"
    assert result["error"]["code"] == expected_code
    assert execution.invocation.terminal_result is not None
    assert execution.invocation.terminal_result.error.code.value == expected_code
    assert execution.invocation.unexpected_handler_failure is False


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("unexpected runtime failure"),
        ValueError("unexpected value failure"),
        sqlite3.DatabaseError("unexpected sqlite failure"),
    ],
    ids=["runtime", "value", "sqlite"],
)
def test_unexpected_handler_errors_set_flag_and_reraise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    database_path = tmp_path / "unexpected-handler-error.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery = _save_recovery(repository)
    execution = _build_direct_execution(database_path, repository, recovery)

    def raise_unexpected(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(repository, "propose_profile_patch", raise_unexpected)

    with pytest.raises(type(error), match="unexpected"):
        _proposal_handler(execution)(
            _proposal_arguments(),
            _direct_context(execution),
        )

    assert execution.invocation.unexpected_handler_failure is True
    assert execution.invocation.terminal_result is None


def test_unexpected_handler_failure_real_harness_records_tool_handler_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "harness-handler-failure.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery = _save_recovery(repository)
    arguments = _proposal_arguments()
    queue = _QueuedTransport([_tool_call_response(arguments)])

    def raise_unexpected(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected repository failure")

    monkeypatch.setattr(repository, "propose_profile_patch", raise_unexpected)
    execution = build_profile_propose_execution(
        repository=repository,
        recovery=recovery,
        profile_snapshot=repository.get_profile_snapshot(0),
        client=LMStudioClient(
            BASE_URL,
            MODEL,
            transport=httpx.MockTransport(queue),
        ),
        trace_repository=RunTraceRepository(database_path),
        caller_idempotency_key="failure-http-key-0001",
        trace_id="trace-handler-failure",
    )

    with pytest.raises(HarnessError) as raised:
        execution.harness.run(execution.request)

    assert raised.value.code == "tool_handler_failed"
    assert execution.invocation.unexpected_handler_failure is True
    assert execution.invocation.terminal_result is None
    stored = RunTraceRepository(database_path).get_trace("trace-handler-failure")
    assert stored.trace.status == "failed"
    assert stored.trace.final_error_code == "tool_handler_failed"
    assert stored.trace.handler_executions == 1
    assert len(stored.tool_runs) == 1
    assert stored.tool_runs[0].status == "failed"
    assert stored.tool_runs[0].error_code == "tool_handler_failed"
    assert stored.tool_runs[0].handler_executed is True
    assert stored.tool_runs[0].result is None


@pytest.mark.parametrize(
    "changed",
    [
        {"session_id": "another-calibration"},
        {"actor": "another-parent"},
        {"role": "child"},
        {"expected_version": 99},
        {"idempotency_key": None},
        {"idempotency_key": "short-key"},
    ],
    ids=["session", "actor", "role", "version", "missing-key", "short-key"],
)
def test_context_invariant_handler_failures_set_unexpected_flag(
    tmp_path: Path,
    changed: dict[str, object],
) -> None:
    database_path = tmp_path / "context-handler-error.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery = _save_recovery(repository)
    execution = _build_direct_execution(database_path, repository, recovery)
    invalid_context = _direct_context(execution).model_copy(update=changed)

    with pytest.raises(RuntimeError, match="context"):
        _proposal_handler(execution)(_proposal_arguments(), invalid_context)

    assert execution.invocation.unexpected_handler_failure is True
    assert repository.get_calibration_recovery(
        recovery.calibration_id
    ).calibration_version == recovery.calibration_version


@pytest.mark.parametrize(
    "violation",
    ["state", "calibration-version", "profile-version", "first-trace", "replay"],
)
def test_proposal_progression_handler_failures_set_unexpected_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    violation: str,
) -> None:
    database_path = tmp_path / "progression-handler-error.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery = _save_recovery(repository)
    execution = _build_direct_execution(database_path, repository, recovery)
    context = _direct_context(execution)
    options: dict[str, object] = {"trace_id": context.trace_id}
    if violation == "state":
        options["state"] = CalibrationState.INPUT_SAVED
    elif violation == "calibration-version":
        options["calibration_version"] = recovery.calibration_version
    elif violation == "profile-version":
        options["profile_version"] = recovery.profile_version + 1
    elif violation == "first-trace":
        options["trace_id"] = "trace-from-another-request"
    else:
        options["replayed"] = True
    delivered = _delivered_proposal(recovery, **options)  # type: ignore[arg-type]
    monkeypatch.setattr(
        repository,
        "propose_profile_patch",
        lambda *args, **kwargs: delivered,
    )

    with pytest.raises(RuntimeError, match="proposal"):
        _proposal_handler(execution)(_proposal_arguments(), context)

    assert execution.invocation.unexpected_handler_failure is True
    assert execution.invocation.terminal_result is None


def test_strict_result_capture_handler_failure_sets_unexpected_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "strict-result-handler-error.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery = _save_recovery(repository)
    execution = _build_direct_execution(database_path, repository, recovery)
    context = _direct_context(execution)
    delivered = _delivered_proposal(recovery, trace_id=context.trace_id)
    monkeypatch.setattr(
        repository,
        "propose_profile_patch",
        lambda *args, **kwargs: delivered,
    )
    strict_validate = calibration_adapter.validate_profile_tool_result

    def inject_extra_field(value: dict[str, Any]):
        return strict_validate({**value, "exception": "private detail"})

    monkeypatch.setattr(
        calibration_adapter,
        "validate_profile_tool_result",
        inject_extra_field,
    )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _proposal_handler(execution)(_proposal_arguments(), context)

    assert execution.invocation.unexpected_handler_failure is True
    assert execution.invocation.terminal_result is None


def test_same_key_same_body_concurrent_proposal_replays_exact_winner(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "concurrent-proposal.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery = _save_recovery(repository)
    repositories = [
        FamilyContextRepository(database_path),
        FamilyContextRepository(database_path),
    ]
    executions = [
        _build_direct_execution(
            database_path,
            repositories[index],
            recovery,
            trace_id=f"trace-concurrent-proposal-{index}",
            caller_idempotency_key="same-proposal-http-key",
        )
        for index in range(2)
    ]
    contexts = [_direct_context(execution) for execution in executions]
    assert contexts[0].idempotency_key == contexts[1].idempotency_key
    barrier = Barrier(2)

    def attempt(index: int) -> dict[str, Any]:
        barrier.wait()
        return _proposal_handler(executions[index])(
            _proposal_arguments(),
            contexts[index],
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))

    terminal_results = [execution.invocation.terminal_result for execution in executions]
    assert all(isinstance(item, ProfileToolSuccess) for item in terminal_results)
    successes = [item for item in terminal_results if isinstance(item, ProfileToolSuccess)]
    assert sum(not item.delivery.replayed for item in successes) == 1
    assert sum(item.delivery.replayed for item in successes) == 1
    winner_index = next(
        index
        for index, item in enumerate(successes)
        if item.delivery.replayed is False
    )
    winner = successes[winner_index]
    replay = next(item for item in successes if item.delivery.replayed)
    assert winner.outcome.trace_id == contexts[winner_index].trace_id
    assert replay.outcome == winner.outcome
    assert results[0]["outcome"] == results[1]["outcome"]
    stored = repository.get_calibration_recovery(recovery.calibration_id)
    assert stored.pending_draft_result == winner.outcome
    assert stored.calibration_version == recovery.calibration_version + 1
    assert repository.get_current_profile_version() == recovery.profile_version
    assert all(
        execution.invocation.unexpected_handler_failure is False
        for execution in executions
    )
    with connect_database(database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM calibration_drafts"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM idempotency_records "
            "WHERE operation = 'propose_profile_patch'"
        ).fetchone()[0] == 1


@pytest.mark.parametrize(
    "field",
    ["draft_id", "draft_digest", "accepted_operation_ids"],
)
def _legacy_commit_command_field_confirmation_mismatch_never_mutates_profile(
    tmp_path: Path,
    field: str,
) -> None:
    database_path = tmp_path / f"commit-mismatch-{field}.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery, command = _prepare_commit_command(repository)
    changes: dict[str, object]
    if field == "draft_id":
        changes = {"draft_id": "different-draft"}
    elif field == "draft_digest":
        changes = {"draft_digest": "0" * 64}
    else:
        changes = {
            "accepted_operation_ids": tuple(
                reversed(command.accepted_operation_ids)
            )
        }
    arguments = _commit_arguments(command, **changes)
    execution = _build_commit_execution(
        database_path,
        repository,
        recovery,
        command,
    )
    profile_before = repository.get_current_profile_version()
    calibration_before = recovery.calibration_version

    result = _commit_handler(execution)(arguments, _commit_context(execution))

    assert result["ok"] is False
    assert isinstance(execution.invocation.terminal_result, ProfileToolFailure)
    assert execution.invocation.terminal_result.error.code == (
        ProfileToolFailureCode.MODEL_CONFIRMATION_MISMATCH
    )
    assert execution.invocation.unexpected_handler_failure is False
    assert repository.get_current_profile_version() == profile_before
    assert repository.get_calibration_recovery(
        command.calibration_id
    ).calibration_version == calibration_before


def _legacy_exact_commit_command_runs_real_harness_once_and_advances_versions(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "exact-commit-command.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery, command = _prepare_commit_command(repository)
    arguments = _commit_arguments(command)
    queue = _QueuedTransport(
        [_commit_tool_call_response(arguments), _text_response("Committed.")]
    )
    client = LMStudioClient(
        BASE_URL,
        MODEL,
        transport=httpx.MockTransport(queue),
    )
    execution = _build_commit_execution(
        database_path,
        repository,
        recovery,
        command,
        client=client,
    )
    profile_before = repository.get_current_profile_version()
    calibration_before = recovery.calibration_version

    exposed = execution.harness.registry.expose_phase(WorkflowPhase.PROFILE_COMMIT)
    assert tuple(item.name for item in exposed) == ("commit_profile_patch",)
    assert execution.request.session_id == command.calibration_id
    assert execution.request.expected_version == command.expected_calibration_version
    assert execution.request.expected_version != recovery.profile_version
    assert execution.request.actor == "local-parent"
    assert execution.request.role == "parent"
    assert execution.request.idempotency_key == "commit-http-key-0001"
    assert execution.request.max_tokens == 4096
    trusted_payload = json.loads(execution.request.messages[1]["content"])
    assert trusted_payload == {
        "trusted_command": command.model_dump(mode="json")
    }
    parameters = exposed[0].openai_schema()["function"]["parameters"]
    assert set(parameters["properties"]) == {
        "draft_id",
        "draft_digest",
        "accepted_operation_ids",
    }
    assert not {
        "session_id",
        "actor",
        "role",
        "expected_version",
        "trace_id",
        "idempotency_key",
    } & set(parameters["properties"])

    harness_result = execution.harness.run(execution.request)

    assert harness_result.handler_executions == 1
    assert [payload["tool_choice"] for payload in queue.payloads] == [
        "required",
        "auto",
    ]
    assert isinstance(execution.invocation.terminal_result, ProfileToolSuccess)
    terminal = execution.invocation.terminal_result
    assert terminal.operation == "profile_patch_committed"
    assert terminal.delivery.replayed is False
    assert terminal.outcome.state is CalibrationState.COMMITTED
    assert terminal.outcome.calibration_version == calibration_before + 1
    assert terminal.outcome.profile_version == profile_before + 1
    assert terminal.outcome.trace_id == "trace-commit"
    accepted = terminal.outcome.data["accepted_observations"]
    assert isinstance(accepted, list)
    assert len(accepted) == len(command.accepted_operation_ids)
    assert {item["operation_id"] for item in accepted} == set(
        command.accepted_operation_ids
    )
    assert len({item["id"] for item in accepted}) == len(
        command.accepted_operation_ids
    )
    assert repository.get_current_profile_version() == profile_before + 1
    committed_recovery = repository.get_calibration_recovery(
        command.calibration_id
    )
    assert committed_recovery.calibration_version == calibration_before + 1
    assert committed_recovery.profile_version == profile_before + 1
    assert execution.invocation.unexpected_handler_failure is False
    with connect_database(database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM calibration_commits"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM profile_observation_events"
        ).fetchone()[0] == len(command.accepted_operation_ids)


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (
            VersionConflictError("calibration", "calibration-adapter-1", 2, 3),
            "version_conflict",
        ),
        (
            IdempotencyConflictError("commit_profile_patch", "redacted-key"),
            "idempotency_conflict",
        ),
        (
            InvalidTransitionError("needs_confirmation", "input_saved"),
            "invalid_transition",
        ),
        (NotFoundError("draft", "missing"), "not_found"),
        (DraftDigestMismatchError("draft-1"), "draft_digest_mismatch"),
        (CommitCommandInvalidError("ids_not_in_draft"), "commit_command_invalid"),
    ],
)
def _legacy_commit_command_expected_repository_errors_are_typed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_code: str,
) -> None:
    database_path = tmp_path / "commit-expected-error.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery, command = _prepare_commit_command(repository)
    execution = _build_commit_execution(
        database_path,
        repository,
        recovery,
        command,
    )

    def raise_expected(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(repository, "commit_profile_patch", raise_expected)

    result = _commit_handler(execution)(
        _commit_arguments(command),
        _commit_context(execution),
    )

    assert result["ok"] is False
    assert result["error"]["code"] == expected_code
    assert execution.invocation.unexpected_handler_failure is False


def _legacy_commit_command_unexpected_handler_error_sets_flag_and_reraises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "commit-unexpected-error.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = FamilyContextRepository(database_path)
    recovery, command = _prepare_commit_command(repository)
    execution = _build_commit_execution(
        database_path,
        repository,
        recovery,
        command,
    )

    def raise_unexpected(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected commit repository failure")

    monkeypatch.setattr(repository, "commit_profile_patch", raise_unexpected)

    with pytest.raises(RuntimeError, match="unexpected commit"):
        _commit_handler(execution)(
            _commit_arguments(command),
            _commit_context(execution),
        )

    assert execution.invocation.unexpected_handler_failure is True
    assert execution.invocation.terminal_result is None
