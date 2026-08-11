from __future__ import annotations

import hashlib
import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier, Lock
from typing import Any

import httpx
import pytest

from backend.services import parent_calibration as parent_module

from backend.contracts.api import (
    CalibrationAbandonRequest,
    CalibrationCommitRequest,
    CalibrationCreateRequest,
    CalibrationRetryRequest,
    CalibrationSimplifyRequest,
    CalibrationReviseRequest,
    NarrationStatus,
)
from backend.contracts.calibration_tools import (
    ProfileToolError,
    ProfileToolFailure,
    ProfileToolFailureCode,
    ProfileToolSuccess,
)
from backend.contracts.family import (
    CalibrationState,
    CalibrationWorkflowResult,
    DeliveryMetadata,
    FamilyWriteContext,
    MemoryCategory,
    ProfilePatchAction,
    ProposedObservationInput,
    RecoveryDirective,
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
from backend.orchestration.lm_studio import LMStudioClient
from backend.orchestration.tool_registry import (
    WorkflowPhase,
    derive_write_idempotency_key,
)
from backend.services.parent_calibration import (
    InferenceAuthorization,
    ParentCalibrationService,
    ParentWorkflowError,
    ParentWorkflowFailureKind,
    _parent_context,
    _present_recovery,
    _workflow_error_from_terminal_without_recovery,
    derive_calibration_id,
)
from backend.storage.database import connect_database, run_migrations
from backend.storage.family_context import FamilyContextRepository
from backend.storage.run_traces import RunTraceRepository


MODEL = "gemma-4-26b-a4b-it"
BASE_URL = "http://127.0.0.1:1234/v1"
OBSERVED_AT = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "parent-calibration.db"
    run_migrations(path, backup_dir=tmp_path / "backups")
    return path


def _proposal_arguments() -> dict[str, object]:
    return {
        "duration_groups": [
            {
                "subject": "mathematics",
                "task_type": "written",
                "minutes": [31, 34, 29],
            }
        ],
        "unapplied_notes": [],
    }


def _tool_call_response(
    *,
    name: str = "extract_calibration_evidence",
    arguments: dict[str, object] | None = None,
    call_id: str = "proposal-call-1",
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
                                "name": name,
                                "arguments": json.dumps(
                                    arguments or _proposal_arguments(),
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


POST_WRITE_FAILURE_CASES = (
    "timeout",
    "read_error",
    "connect_error",
    "http_error",
    "model_mismatch",
    "malformed_json",
    "malformed_envelope",
    "missing_choice",
    "malformed_choice",
    "output_truncated",
    "invalid_tool_call",
    "multiple_tool_calls",
    "disallowed_tool",
    "duplicate_tool_call_id",
    "different_arguments",
    "empty_final_content",
    "tool_loop_limit",
)


def _post_write_failure_tail(
    case: str,
    *,
    tool_name: str,
    arguments: dict[str, object],
    first_call_id: str,
) -> list[dict[str, object] | BaseException | httpx.Response]:
    request = httpx.Request("POST", f"{BASE_URL}/chat/completions")
    if case == "timeout":
        return [httpx.ReadTimeout("post-write timeout", request=request)]
    if case == "read_error":
        return [httpx.ReadError("post-write read error", request=request)]
    if case == "connect_error":
        return [httpx.ConnectError("post-write connect error", request=request)]
    if case == "http_error":
        return [httpx.Response(503, json={"error": "synthetic"})]
    if case == "model_mismatch":
        response = _text_response()
        response["model"] = "different-model"
        return [response]
    if case == "malformed_json":
        return [httpx.Response(200, content=b"{not-json")]
    if case == "malformed_envelope":
        return [httpx.Response(200, json=[])]
    if case == "missing_choice":
        return [{"model": MODEL, "choices": []}]
    if case == "malformed_choice":
        return [{"model": MODEL, "choices": [None]}]
    if case == "output_truncated":
        return [
            {
                "model": MODEL,
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"role": "assistant", "content": "partial"},
                    }
                ],
            }
        ]
    if case == "invalid_tool_call":
        return [
            {
                "model": MODEL,
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [{}],
                        },
                    }
                ],
            }
        ]
    if case == "multiple_tool_calls":
        response = _tool_call_response(
            name=tool_name,
            arguments=arguments,
            call_id="multiple-call-1",
        )
        calls = response["choices"][0]["message"]["tool_calls"]
        calls.append(
            json.loads(
                json.dumps(
                    _tool_call_response(
                        name=tool_name,
                        arguments=arguments,
                        call_id="multiple-call-2",
                    )["choices"][0]["message"]["tool_calls"][0]
                )
            )
        )
        return [response]
    if case == "disallowed_tool":
        return [
            _tool_call_response(
                name="unexpected_tool",
                arguments=arguments,
                call_id="disallowed-call",
            )
        ]
    if case == "duplicate_tool_call_id":
        return [
            _tool_call_response(
                name=tool_name,
                arguments=arguments,
                call_id=first_call_id,
            )
        ]
    if case == "different_arguments":
        changed = json.loads(json.dumps(arguments))
        if tool_name == "extract_calibration_evidence":
            changed["duration_groups"][0]["minutes"] = [35]
        else:
            changed["accepted_operation_ids"] = ["different-operation"]
        return [
            _tool_call_response(
                name=tool_name,
                arguments=changed,
                call_id="different-arguments-call",
            )
        ]
    if case == "empty_final_content":
        return [_text_response("   ")]
    if case == "tool_loop_limit":
        return [
            _tool_call_response(
                name=tool_name,
                arguments=arguments,
                call_id=f"loop-call-{index}",
            )
            for index in range(2, 9)
        ]
    raise AssertionError(f"unsupported test case: {case}")


class _QueuedTransport:
    def __init__(
        self,
        responses: list[dict[str, object] | BaseException | httpx.Response],
        *,
        callback: Any | None = None,
    ) -> None:
        self.responses = list(responses)
        self.callback = callback
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.payloads.append(json.loads(request.content))
        if self.callback is not None:
            self.callback(request)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, httpx.Response):
            return response
        return httpx.Response(200, json=response)


def _mock_client(transport: Any) -> LMStudioClient:
    client = LMStudioClient(
        BASE_URL,
        MODEL,
        transport=httpx.MockTransport(transport),
    )
    assert client.evidence_provenance == "synthetic_transport"
    return client


def _service(
    database_path: Path,
    transport: _QueuedTransport,
    *,
    repository: FamilyContextRepository | None = None,
) -> ParentCalibrationService:
    return ParentCalibrationService(
        repository=repository or FamilyContextRepository(database_path),
        client=_mock_client(transport),
        trace_repository=RunTraceRepository(database_path),
    )


def test_derive_calibration_id_is_stable_distinct_and_opaque() -> None:
    caller_key = "calibration-create-key-0001"

    first = derive_calibration_id(caller_key)
    second = derive_calibration_id(caller_key)
    other = derive_calibration_id("calibration-create-key-0002")

    assert first == second
    assert first != other
    assert caller_key not in first
    assert hashlib.sha256(caller_key.encode("utf-8")).hexdigest() not in first


def test_parent_context_has_fixed_parent_identity() -> None:
    signature = inspect.signature(_parent_context)

    assert tuple(signature.parameters) == ("trace_id", "idempotency_key")
    assert _parent_context("trace-1", "caller-key-0000001") == FamilyWriteContext(
        actor="local-parent",
        role="parent",
        trace_id="trace-1",
        idempotency_key="caller-key-0000001",
    )


@pytest.mark.parametrize(
    ("code", "expected_kind"),
    [
        (ProfileToolFailureCode.NOT_FOUND, ParentWorkflowFailureKind.NOT_FOUND),
        (
            ProfileToolFailureCode.VERSION_CONFLICT,
            ParentWorkflowFailureKind.VERSION_CONFLICT,
        ),
        (
            ProfileToolFailureCode.IDEMPOTENCY_CONFLICT,
            ParentWorkflowFailureKind.IDEMPOTENCY_CONFLICT,
        ),
        (
            ProfileToolFailureCode.INVALID_TRANSITION,
            ParentWorkflowFailureKind.INVALID_TRANSITION,
        ),
        (
            ProfileToolFailureCode.DRAFT_DIGEST_MISMATCH,
            ParentWorkflowFailureKind.DRAFT_DIGEST_MISMATCH,
        ),
        (
            ProfileToolFailureCode.COMMIT_COMMAND_INVALID,
            ParentWorkflowFailureKind.COMMIT_COMMAND_INVALID,
        ),
        (
            ProfileToolFailureCode.PROPOSAL_INVALID,
            ParentWorkflowFailureKind.MODEL_PROTOCOL_ERROR,
        ),
        (
            ProfileToolFailureCode.MODEL_CONFIRMATION_MISMATCH,
            ParentWorkflowFailureKind.MODEL_PROTOCOL_ERROR,
        ),
    ],
)
def test_terminal_without_recovery_maps_typed_failures(
    code: ProfileToolFailureCode,
    expected_kind: ParentWorkflowFailureKind,
) -> None:
    terminal = ProfileToolFailure(
        ok=False,
        operation="propose_profile_patch",
        error=ProfileToolError(code=code, retryable=False),
    )

    error = _workflow_error_from_terminal_without_recovery(terminal, "trace-terminal")

    assert error.kind is expected_kind
    assert error.cause_code == code.value
    assert error.trace_id == "trace-terminal"
    assert error.recovery is None


@pytest.mark.parametrize("terminal", [None, object()])
def test_terminal_without_recovery_sanitizes_missing_or_unrecognized_terminal(
    terminal: object | None,
) -> None:
    error = _workflow_error_from_terminal_without_recovery(terminal, "trace-terminal")

    assert error.kind is ParentWorkflowFailureKind.INTERNAL_ERROR
    assert error.cause_code == "missing_typed_terminal_result"
    assert error.trace_id == "trace-terminal"
    assert error.recovery is None


def test_terminal_without_recovery_sanitizes_unexpected_success() -> None:
    terminal = ProfileToolSuccess(
        ok=True,
        operation="profile_patch_proposed",
        outcome=CalibrationWorkflowResult(
            calibration_id="calibration-terminal",
            calibration_version=2,
            profile_version=0,
            state=CalibrationState.NEEDS_CONFIRMATION,
            allowed_actions=("commit_profile_patch",),
            trace_id="trace-winner",
            data={},
        ),
        delivery=DeliveryMetadata(replayed=False),
    )

    error = _workflow_error_from_terminal_without_recovery(terminal, "trace-terminal")

    assert error.kind is ParentWorkflowFailureKind.INTERNAL_ERROR
    assert error.cause_code == "missing_typed_terminal_result"
    assert error.recovery is None


def test_create_calibration_is_receipt_first(
    database_path: Path,
) -> None:
    caller_key = "calibration-create-key-0001"
    calibration_id = derive_calibration_id(caller_key)
    callback_calls = 0

    def inspect_persisted_receipt(_: httpx.Request) -> None:
        nonlocal callback_calls
        callback_calls += 1
        if callback_calls != 1:
            return
        recovery = FamilyContextRepository(database_path).get_calibration_recovery(calibration_id)
        assert recovery.latest_checkpoint.state is CalibrationState.INPUT_SAVED
        assert recovery.receipt.raw_text == "Synthetic parent observation"
        assert recovery.directive is RecoveryDirective.INITIAL_INFERENCE

    transport = _QueuedTransport(
        [_tool_call_response(), _text_response()],
        callback=inspect_persisted_receipt,
    )
    service = _service(database_path, transport)

    result = service.create_calibration(
        CalibrationCreateRequest(
            text="Synthetic parent observation",
            expected_calibration_version=0,
            expected_profile_version=0,
        ),
        caller_idempotency_key=caller_key,
        trace_id="trace-receipt-first",
    )

    assert callback_calls == 1
    assert result.calibration_id == calibration_id
    assert result.stage is CalibrationState.NEEDS_CONFIRMATION
    assert result.trace_id == "trace-receipt-first"
    assert result.data.kind == "profile_patch_proposal"
    assert len(transport.payloads) == 1
    assert result.data.narration is None
    assert result.data.narration_status is NarrationStatus.NOT_REQUESTED


def _create_request(
    *,
    text: str = "Synthetic parent observation",
    expected_profile_version: int = 0,
) -> CalibrationCreateRequest:
    return CalibrationCreateRequest(
        text=text,
        expected_calibration_version=0,
        expected_profile_version=expected_profile_version,
    )


@pytest.mark.parametrize(
    "exception_type",
    [httpx.ReadTimeout, httpx.ReadError, httpx.ConnectError],
    ids=["timeout", "read-error", "connect-error"],
)
def test_proposal_unavailable_is_recoverable_and_create_replay_does_not_reinfer(
    database_path: Path,
    exception_type: type[httpx.HTTPError],
) -> None:
    caller_key = "calibration-create-key-unavailable"
    calibration_id = derive_calibration_id(caller_key)
    transport = _QueuedTransport(
        [
            exception_type(
                "synthetic transport failure",
                request=httpx.Request("POST", f"{BASE_URL}/chat/completions"),
            )
        ]
    )
    repository = FamilyContextRepository(database_path)
    service = _service(database_path, transport, repository=repository)

    with pytest.raises(ParentWorkflowError) as raised:
        service.create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id="trace-proposal-unavailable",
        )

    assert raised.value.kind is ParentWorkflowFailureKind.MODEL_UNAVAILABLE
    assert raised.value.recovery is not None
    assert raised.value.recovery.directive is RecoveryDirective.EXPLICIT_RETRY_ALLOWED
    assert raised.value.recovery.receipt.raw_text == _create_request().text
    assert raised.value.recovery.pending_draft is None
    assert repository.get_current_profile_version() == 0
    assert _count_rows(database_path, "calibration_drafts") == 0
    assert _count_rows(database_path, "profile_observation_events") == 0
    calls_before_replay = len(transport.payloads)

    with pytest.raises(ParentWorkflowError) as replayed:
        _service(
            database_path,
            transport,
            repository=FamilyContextRepository(database_path),
        ).create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id="trace-proposal-unavailable-replay",
        )

    assert replayed.value.kind is ParentWorkflowFailureKind.MODEL_UNAVAILABLE
    assert replayed.value.trace_id == "trace-proposal-unavailable-replay"
    assert replayed.value.recovery is not None
    assert replayed.value.recovery.calibration_id == calibration_id
    assert replayed.value.recovery.calibration_version == 2
    assert len(transport.payloads) == calls_before_replay == 1


def test_proposal_unavailable_explicit_retry_can_infer_once(
    database_path: Path,
) -> None:
    caller_key = "calibration-create-key-explicit-retry"
    calibration_id = derive_calibration_id(caller_key)
    repository = FamilyContextRepository(database_path)
    failed_transport = _QueuedTransport(
        [
            httpx.ReadTimeout(
                "synthetic timeout",
                request=httpx.Request("POST", f"{BASE_URL}/chat/completions"),
            )
        ]
    )
    with pytest.raises(ParentWorkflowError):
        _service(database_path, failed_transport, repository=repository).create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id="trace-proposal-failed",
        )

    retry_transport = _QueuedTransport([_tool_call_response(), _text_response()])
    response = _service(
        database_path,
        retry_transport,
        repository=FamilyContextRepository(database_path),
    ).retry_calibration(
        calibration_id,
        CalibrationRetryRequest(expected_calibration_version=2),
        caller_idempotency_key="proposal-retry-http-key",
        trace_id="trace-proposal-retry",
    )

    assert response.stage is CalibrationState.NEEDS_CONFIRMATION
    assert response.calibration_version == 4
    assert response.profile_version == 0
    assert len(retry_transport.payloads) == 1
    recovery = repository.get_calibration_recovery(calibration_id)
    assert recovery.pending_draft is not None
    assert recovery.latest_checkpoint.state is CalibrationState.NEEDS_CONFIRMATION
    calls_before_replay = len(retry_transport.payloads)

    replay = _service(
        database_path,
        retry_transport,
        repository=FamilyContextRepository(database_path),
    ).retry_calibration(
        calibration_id,
        CalibrationRetryRequest(expected_calibration_version=2),
        caller_idempotency_key="proposal-retry-http-key",
        trace_id="trace-proposal-retry-replay",
    )

    assert replay.stage is CalibrationState.NEEDS_CONFIRMATION
    assert replay.delivery.replayed is True
    assert len(retry_transport.payloads) == calls_before_replay


def test_model_failure_can_use_simplified_calibration_without_model_call(
    database_path: Path,
) -> None:
    caller_key = "calibration-create-key-simplified"
    calibration_id = derive_calibration_id(caller_key)
    transport = _QueuedTransport(
        [
            httpx.ReadTimeout(
                "synthetic timeout",
                request=httpx.Request("POST", f"{BASE_URL}/chat/completions"),
            )
        ]
    )
    repository = FamilyContextRepository(database_path)
    service = _service(database_path, transport, repository=repository)
    with pytest.raises(ParentWorkflowError):
        service.create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id="trace-simplified-failure",
        )

    request = CalibrationSimplifyRequest(
        expected_calibration_version=2,
        duration_groups=(
            {
                "subject": "mathematics",
                "task_type": "written",
                "conservative_minutes": 34,
            },
            {
                "subject": "chinese",
                "task_type": "reading",
                "conservative_minutes": 26,
            },
            {
                "subject": "english",
                "task_type": "recitation",
                "conservative_minutes": 30,
            },
            {
                "subject": "geography",
                "task_type": "map_reading",
                "conservative_minutes": 21,
            },
        ),
    )
    response = service.simplify_calibration(
        calibration_id,
        request,
        caller_idempotency_key="simplify-key-0001",
        trace_id="trace-simplified",
    )

    assert len(transport.payloads) == 1
    assert response.stage is CalibrationState.NEEDS_CONFIRMATION
    assert response.calibration_version == 3
    assert response.profile_version == 0
    assert response.data.kind == "profile_patch_proposal"
    assert {
        item.subject: item.value_number for item in response.data.diff_preview
    } == {
        "mathematics": 1.7,
        "chinese": 1.3,
        "english": 1.5,
        "geography": 0.84,
    }
    assert all(item.sample_count == 1 for item in response.data.diff_preview)
    assert all(item.confidence == 0.7 for item in response.data.diff_preview)

    replay = service.simplify_calibration(
        calibration_id,
        request,
        caller_idempotency_key="simplify-key-0001",
        trace_id="trace-simplified-replay",
    )
    assert replay.delivery.replayed is True
    assert replay.data == response.data
    assert _count_rows(database_path, "calibration_drafts") == 1


def test_model_failure_read_projects_sanitized_failure_code(
    database_path: Path,
) -> None:
    caller_key = "calibration-create-key-failure-code"
    calibration_id = derive_calibration_id(caller_key)
    transport = _QueuedTransport(
        [
            httpx.ReadTimeout(
                "private timeout detail",
                request=httpx.Request("POST", f"{BASE_URL}/chat/completions"),
            )
        ]
    )
    service = _service(database_path, transport)
    with pytest.raises(ParentWorkflowError):
        service.create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id="trace-failure-code",
        )

    response = service.get_calibration(calibration_id, trace_id="trace-failure-read")

    assert response.stage is CalibrationState.MODEL_UNAVAILABLE
    assert response.data.kind == "calibration_recovery"
    assert response.data.failure_code == "model_timeout"


def test_retry_lineage_replay_distinguishes_direct_failure_from_later_attempt(
    database_path: Path,
) -> None:
    caller_key = "retry-lineage-version-key"
    calibration_id = derive_calibration_id(caller_key)
    repository = FamilyContextRepository(database_path)

    def timeout_transport(label: str) -> _QueuedTransport:
        return _QueuedTransport(
            [
                httpx.ReadTimeout(
                    label,
                    request=httpx.Request("POST", f"{BASE_URL}/chat/completions"),
                )
            ]
        )

    initial_transport = timeout_transport("initial failure")
    with pytest.raises(ParentWorkflowError):
        _service(database_path, initial_transport, repository=repository).create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id="trace-lineage-initial-failure",
        )

    first_retry_key = "retry-lineage-first-key"
    first_retry_transport = timeout_transport("first retry failure")
    with pytest.raises(ParentWorkflowError) as direct_failure:
        _service(
            database_path,
            first_retry_transport,
            repository=FamilyContextRepository(database_path),
        ).retry_calibration(
            calibration_id,
            CalibrationRetryRequest(expected_calibration_version=2),
            caller_idempotency_key=first_retry_key,
            trace_id="trace-lineage-first-retry",
        )
    assert direct_failure.value.recovery is not None
    assert direct_failure.value.recovery.calibration_version == 4
    calls_before_direct_replay = len(first_retry_transport.payloads)

    with pytest.raises(ParentWorkflowError) as direct_replay:
        _service(
            database_path,
            first_retry_transport,
            repository=FamilyContextRepository(database_path),
        ).retry_calibration(
            calibration_id,
            CalibrationRetryRequest(expected_calibration_version=2),
            caller_idempotency_key=first_retry_key,
            trace_id="trace-lineage-direct-failure-replay",
        )
    assert direct_replay.value.kind is ParentWorkflowFailureKind.MODEL_UNAVAILABLE
    assert len(first_retry_transport.payloads) == calls_before_direct_replay

    second_retry_transport = timeout_transport("second retry failure")
    with pytest.raises(ParentWorkflowError) as later_failure:
        _service(
            database_path,
            second_retry_transport,
            repository=FamilyContextRepository(database_path),
        ).retry_calibration(
            calibration_id,
            CalibrationRetryRequest(expected_calibration_version=4),
            caller_idempotency_key="retry-lineage-second-key",
            trace_id="trace-lineage-second-retry",
        )
    assert later_failure.value.recovery is not None
    assert later_failure.value.recovery.calibration_version == 6
    calls_before_old_replay = len(first_retry_transport.payloads)

    with pytest.raises(ParentWorkflowError) as old_replay:
        _service(
            database_path,
            first_retry_transport,
            repository=FamilyContextRepository(database_path),
        ).retry_calibration(
            calibration_id,
            CalibrationRetryRequest(expected_calibration_version=2),
            caller_idempotency_key=first_retry_key,
            trace_id="trace-lineage-old-replay",
        )
    assert old_replay.value.kind is ParentWorkflowFailureKind.RETRY_LINEAGE_CONFLICT
    assert old_replay.value.cause_code == "retry_lineage_mismatch"
    assert len(first_retry_transport.payloads) == calls_before_old_replay
    assert (
        _count_rows(
            database_path,
            "calibration_checkpoints",
            where="WHERE state = 'model_unavailable'",
        )
        == 3
    )


@pytest.mark.parametrize(
    "mutation",
    ["extra_data", "different_entity", "different_calibration"],
)
def test_retry_lineage_rejects_malformed_begin_result_before_model(
    database_path: Path,
    mutation: str,
) -> None:
    caller_key = f"retry-lineage-malformed-{mutation}"
    calibration_id = derive_calibration_id(caller_key)
    repository = FamilyContextRepository(database_path)
    receipt = repository.save_calibration_input(
        calibration_id,
        "Synthetic retry lineage input",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_parent_context("trace-lineage-input", caller_key),
    ).receipt
    repository.mark_calibration_model_unavailable(
        calibration_id,
        receipt.id,
        expected_calibration_version=1,
        error_code="model_timeout",
        context=_parent_context("trace-lineage-failure", "lineage-failure-key"),
    )
    begin = repository.begin_calibration_retry(
        calibration_id,
        expected_calibration_version=2,
        context=_parent_context("trace-lineage-begin", "lineage-begin-key"),
    )
    data = dict(begin.outcome.data)
    outcome_update: dict[str, object] = {}
    if mutation == "extra_data":
        data["unexpected"] = "value"
    elif mutation == "different_entity":
        data["pending_entity_id"] = "different-receipt"
    else:
        outcome_update["calibration_id"] = "different-calibration"
    outcome_update["data"] = data
    malformed = begin.model_copy(
        update={"outcome": begin.outcome.model_copy(update=outcome_update)}
    )
    recovery = repository.get_calibration_recovery(calibration_id)
    transport = _QueuedTransport([])

    with pytest.raises(ParentWorkflowError) as raised:
        _service(database_path, transport, repository=repository)._continue_from_recovery(
            recovery,
            authorization=InferenceAuthorization.EXPLICIT_RETRY,
            retry_begin_result=malformed,
            initial_commit_input=None,
            caller_idempotency_key="lineage-begin-key",
            trace_id=f"trace-lineage-malformed-{mutation}",
            delivery_replayed=True,
        )

    assert raised.value.kind is ParentWorkflowFailureKind.RETRY_LINEAGE_CONFLICT
    assert raised.value.cause_code == "retry_lineage_mismatch"
    assert transport.payloads == []
    assert (
        repository.get_calibration_recovery(calibration_id).latest_checkpoint.state
        is CalibrationState.RETRY_PENDING
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "profile_version",
        "resume_stage",
        "pending_entity_id",
        "receipt_id",
        "recovery_directive",
        "allowed_actions",
        "trace_id",
        "extra_data",
    ],
)
def test_retry_pending_rejects_mismatched_stored_outcome_before_model(
    database_path: Path,
    mutation: str,
) -> None:
    caller_key = f"retry-lineage-outcome-{mutation}"
    calibration_id = derive_calibration_id(caller_key)
    repository = FamilyContextRepository(database_path)
    receipt = repository.save_calibration_input(
        calibration_id,
        "Synthetic retry outcome identity input",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_parent_context("trace-outcome-input", caller_key),
    ).receipt
    repository.mark_calibration_model_unavailable(
        calibration_id,
        receipt.id,
        expected_calibration_version=1,
        error_code="model_timeout",
        context=_parent_context("trace-outcome-failure", "outcome-failure-key"),
    )
    retry_key = "outcome-begin-key"
    begin = repository.begin_calibration_retry(
        calibration_id,
        expected_calibration_version=2,
        context=_parent_context("trace-outcome-begin", retry_key),
    )
    recovery = repository.get_calibration_recovery(calibration_id)
    assert recovery.last_outcome == begin.outcome

    outcome_payload = begin.outcome.model_dump(mode="python")
    data = dict(begin.outcome.data)
    if mutation == "profile_version":
        outcome_payload["profile_version"] = begin.outcome.profile_version + 1
    elif mutation == "resume_stage":
        data["resume_stage"] = "profile_commit"
    elif mutation == "pending_entity_id":
        data["pending_entity_id"] = "different-pending-entity"
    elif mutation == "receipt_id":
        data["receipt_id"] = "different-receipt"
    elif mutation == "recovery_directive":
        data["recovery_directive"] = "return_stored"
    elif mutation == "allowed_actions":
        outcome_payload["allowed_actions"] = ("different-action",)
    elif mutation == "trace_id":
        outcome_payload["trace_id"] = "trace-different-stored-outcome"
    else:
        data["unexpected"] = "schema-valid-extra-data"
    outcome_payload["data"] = data
    mismatched_outcome = CalibrationWorkflowResult.model_validate(outcome_payload)
    assert mismatched_outcome != begin.outcome
    mismatched_recovery = type(recovery).model_validate(
        {
            **recovery.model_dump(mode="python"),
            "last_outcome": mismatched_outcome,
        }
    )
    checkpoint_count = _count_rows(database_path, "calibration_checkpoints")
    transport = _QueuedTransport(
        [
            httpx.ReadTimeout(
                "model must not be called for mismatched retry outcome",
                request=httpx.Request("POST", f"{BASE_URL}/chat/completions"),
            )
        ]
    )

    with pytest.raises(ParentWorkflowError) as raised:
        _service(
            database_path,
            transport,
            repository=repository,
        )._continue_from_recovery(
            mismatched_recovery,
            authorization=InferenceAuthorization.EXPLICIT_RETRY,
            retry_begin_result=begin,
            initial_commit_input=None,
            caller_idempotency_key=retry_key,
            trace_id=f"trace-outcome-mismatch-{mutation}",
            delivery_replayed=begin.delivery.replayed,
        )

    assert raised.value.kind is ParentWorkflowFailureKind.RETRY_LINEAGE_CONFLICT
    assert raised.value.cause_code == "retry_lineage_mismatch"
    assert transport.payloads == []
    assert _count_rows(database_path, "calibration_checkpoints") == checkpoint_count
    assert (
        repository.get_calibration_recovery(calibration_id).latest_checkpoint.state
        is CalibrationState.RETRY_PENDING
    )


def test_proposal_replay_after_restart_returns_stored_without_inference(
    database_path: Path,
) -> None:
    caller_key = "calibration-create-key-0001"
    transport = _QueuedTransport([_tool_call_response(), _text_response()])
    first = _service(database_path, transport).create_calibration(
        _create_request(),
        caller_idempotency_key=caller_key,
        trace_id="trace-proposal-first",
    )
    restarted_repository = FamilyContextRepository(database_path)
    restarted = _service(
        database_path,
        transport,
        repository=restarted_repository,
    )

    replay = restarted.create_calibration(
        _create_request(),
        caller_idempotency_key=caller_key,
        trace_id="trace-proposal-replay",
    )

    assert first.delivery.replayed is False
    assert replay.delivery.replayed is True
    assert replay.stage is CalibrationState.NEEDS_CONFIRMATION
    assert replay.data.kind == "profile_patch_proposal"
    assert replay.trace_id == "trace-proposal-replay"
    assert len(transport.payloads) == 1
    assert restarted_repository.get_current_profile_version() == 0


@pytest.mark.parametrize(
    "changed_request",
    [
        _create_request(text="Different synthetic parent observation"),
        _create_request(expected_profile_version=1),
    ],
    ids=["text", "expected-profile"],
)
def test_restart_proposal_same_key_changed_request_is_idempotency_conflict(
    database_path: Path,
    changed_request: CalibrationCreateRequest,
) -> None:
    caller_key = "calibration-create-key-0001"
    transport = _QueuedTransport([_tool_call_response(), _text_response()])
    _service(database_path, transport).create_calibration(
        _create_request(),
        caller_idempotency_key=caller_key,
        trace_id="trace-proposal-first",
    )
    repository = FamilyContextRepository(database_path)
    recovery_before = repository.get_calibration_recovery(derive_calibration_id(caller_key))

    with pytest.raises(IdempotencyConflictError):
        _service(database_path, transport, repository=repository).create_calibration(
            changed_request,
            caller_idempotency_key=caller_key,
            trace_id="trace-proposal-conflict",
        )

    recovery_after = repository.get_calibration_recovery(derive_calibration_id(caller_key))
    assert recovery_after.receipt == recovery_before.receipt
    assert recovery_after.pending_draft == recovery_before.pending_draft
    assert len(transport.payloads) == 1
    with connect_database(database_path) as connection:
        assert (
            connection.execute("SELECT count(*) FROM calibration_turn_receipts").fetchone()[0] == 1
        )
        assert connection.execute("SELECT count(*) FROM calibration_drafts").fetchone()[0] == 1


class _ConcurrentProposalTransport:
    def __init__(self, barrier: Barrier) -> None:
        self.barrier = barrier
        self.payloads: list[dict[str, Any]] = []
        self._lock = Lock()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        with self._lock:
            self.payloads.append(payload)
        if payload["tool_choice"] == "required":
            self.barrier.wait()
            response = _tool_call_response(call_id=f"proposal-call-{len(self.payloads)}")
        else:
            response = _text_response()
        return httpx.Response(200, json=response)


def test_concurrent_proposal_same_key_same_body_preserves_winner_trace(
    database_path: Path,
) -> None:
    caller_key = "calibration-create-key-concurrent"
    transport = _ConcurrentProposalTransport(Barrier(2))
    traces = ("trace-concurrent-0", "trace-concurrent-1")
    services = [
        ParentCalibrationService(
            repository=FamilyContextRepository(database_path),
            client=_mock_client(transport),
            trace_repository=RunTraceRepository(database_path),
        )
        for _ in range(2)
    ]

    def create(index: int):
        return services[index].create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id=traces[index],
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create, range(2)))

    assert {result.trace_id for result in results} == set(traces)
    assert sum(not result.delivery.replayed for result in results) == 1
    assert sum(result.delivery.replayed for result in results) == 1
    assert all(result.stage is CalibrationState.NEEDS_CONFIRMATION for result in results)
    repository = FamilyContextRepository(database_path)
    recovery = repository.get_calibration_recovery(derive_calibration_id(caller_key))
    assert recovery.pending_draft is not None
    assert recovery.pending_draft_result is not None
    assert recovery.pending_draft_result.trace_id in traces
    assert recovery.last_outcome == recovery.pending_draft_result
    assert repository.get_current_profile_version() == 0
    assert len(transport.payloads) == 2
    with connect_database(database_path) as connection:
        assert connection.execute("SELECT count(*) FROM calibration_drafts").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT count(*) FROM calibration_checkpoints WHERE state = 'needs_confirmation'"
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT count(*) FROM profile_observation_events").fetchone()[0] == 0
        )


def test_concurrency_winner_for_proposal_returns_conflict_without_failure_checkpoint(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caller_key = "proposal-concurrent-winner-loser-key"
    calibration_id = derive_calibration_id(caller_key)
    repository = FamilyContextRepository(database_path)
    failure_writes = 0
    original_mark = repository.mark_calibration_model_unavailable

    def track_failure_write(*args: object, **kwargs: object):
        nonlocal failure_writes
        failure_writes += 1
        return original_mark(*args, **kwargs)

    monkeypatch.setattr(
        repository,
        "mark_calibration_model_unavailable",
        track_failure_write,
    )

    def persist_winner(_: httpx.Request) -> None:
        repository.propose_profile_patch(
            calibration_id,
            repository.get_calibration_recovery(calibration_id).receipt.id,
            (_revised_observation(),),
            expected_calibration_version=1,
            context=_parent_context(
                "trace-proposal-concurrent-winner",
                "proposal-concurrent-winner-storage-key",
            ),
        )

    transport = _QueuedTransport(
        [
            httpx.ReadTimeout(
                "losing request timeout",
                request=httpx.Request("POST", f"{BASE_URL}/chat/completions"),
            )
        ],
        callback=persist_winner,
    )

    with pytest.raises(ParentWorkflowError) as raised:
        _service(database_path, transport, repository=repository).create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id="trace-proposal-concurrent-loser",
        )

    assert raised.value.kind is ParentWorkflowFailureKind.VERSION_CONFLICT
    assert raised.value.cause_code == "failure_source_conflict"
    assert failure_writes == 0
    recovery = repository.get_calibration_recovery(calibration_id)
    assert recovery.latest_checkpoint.state is CalibrationState.NEEDS_CONFIRMATION
    assert recovery.pending_draft is not None
    assert recovery.pending_draft_result is not None
    assert recovery.pending_draft_result.trace_id == "trace-proposal-concurrent-winner"
    assert (
        _count_rows(
            database_path,
            "calibration_checkpoints",
            where="WHERE state = 'model_unavailable'",
        )
        == 0
    )


def _prepare_proposal(
    database_path: Path,
    *,
    caller_key: str = "calibration-create-key-for-commit",
    trace_id: str = "trace-proposal-for-commit",
):
    transport = _QueuedTransport([_tool_call_response(), _text_response()])
    repository = FamilyContextRepository(database_path)
    proposal = _service(
        database_path,
        transport,
        repository=repository,
    ).create_calibration(
        _create_request(),
        caller_idempotency_key=caller_key,
        trace_id=trace_id,
    )
    assert proposal.data.kind == "profile_patch_proposal"
    return repository, proposal


def _commit_request(proposal) -> CalibrationCommitRequest:
    assert proposal.data.kind == "profile_patch_proposal"
    draft = proposal.data.draft
    return CalibrationCommitRequest(
        expected_calibration_version=proposal.calibration_version,
        draft_id=draft.id,
        draft_digest=draft.draft_digest,
        accepted_operation_ids=tuple(item.operation_id for item in draft.observations),
    )


def test_parent_commit_is_deterministic_and_does_not_call_model(
    database_path: Path,
) -> None:
    repository, proposal = _prepare_proposal(
        database_path,
        caller_key="prepare-deterministic-commit",
    )
    request = _commit_request(proposal)
    transport = _QueuedTransport([])
    service = _service(database_path, transport, repository=repository)

    response = service.commit_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key="deterministic-commit-key",
        trace_id="trace-deterministic-commit",
    )

    assert transport.payloads == []
    assert response.stage is CalibrationState.COMMITTED
    assert response.profile_version == 1
    assert response.data.narration_status is NarrationStatus.NOT_REQUESTED
    with connect_database(database_path) as connection:
        trace_count = connection.execute(
            "SELECT count(*) FROM harness_traces WHERE trace_id = ?",
            ("trace-deterministic-commit",),
        ).fetchone()[0]
    assert trace_count == 0


def _commit_tool_response(request: CalibrationCommitRequest) -> dict[str, object]:
    return _tool_call_response(
        name="commit_profile_patch",
        arguments={
            "draft_id": request.draft_id,
            "draft_digest": request.draft_digest,
            "accepted_operation_ids": list(request.accepted_operation_ids),
        },
        call_id="commit-call-1",
    )


def _count_rows(
    database_path: Path,
    table: str,
    *,
    where: str = "",
) -> int:
    with connect_database(database_path) as connection:
        row = connection.execute(f'SELECT count(*) FROM "{table}" {where}').fetchone()
    assert row is not None
    return int(row[0])


def test_concurrency_winner_for_exact_commit_returns_success_without_failure_checkpoint(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, proposal = _prepare_proposal(
        database_path,
        caller_key="prepare-concurrent-commit-winner",
    )
    request = _commit_request(proposal)
    caller_key = "concurrent-commit-winner-http-key"
    hidden_key = derive_write_idempotency_key(
        caller_key,
        WorkflowPhase.PROFILE_COMMIT,
        "commit_profile_patch",
    )
    failure_writes = 0
    original_mark = repository.mark_calibration_model_unavailable

    def track_failure_write(*args: object, **kwargs: object):
        nonlocal failure_writes
        failure_writes += 1
        return original_mark(*args, **kwargs)

    monkeypatch.setattr(
        repository,
        "mark_calibration_model_unavailable",
        track_failure_write,
    )

    def persist_exact_winner(_: httpx.Request) -> None:
        repository.commit_profile_patch(
            proposal.calibration_id,
            request.draft_id,
            request.accepted_operation_ids,
            draft_digest=request.draft_digest,
            expected_calibration_version=request.expected_calibration_version,
            context=_parent_context(
                "trace-concurrent-commit-winner",
                hidden_key,
            ),
        )

    transport = _QueuedTransport(
        [
            httpx.ReadTimeout(
                "losing narration request timeout",
                request=httpx.Request("POST", f"{BASE_URL}/chat/completions"),
            )
        ],
        callback=persist_exact_winner,
    )

    response = _service(
        database_path,
        transport,
        repository=repository,
    ).commit_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key=caller_key,
        trace_id="trace-concurrent-commit-request",
    )

    assert response.stage is CalibrationState.COMMITTED
    assert response.data.narration is None
    assert response.data.narration_status is NarrationStatus.NOT_REQUESTED
    assert failure_writes == 0
    assert repository.get_current_profile_version() == 1
    assert _count_rows(database_path, "calibration_commits") == 1
    assert (
        _count_rows(
            database_path,
            "calibration_checkpoints",
            where="WHERE state = 'model_unavailable'",
        )
        == 0
    )


@pytest.mark.parametrize("failure_case", POST_WRITE_FAILURE_CASES)
@pytest.mark.parametrize("phase", ["proposal", "commit"])
def test_narration_failure_after_business_write_returns_db_truth(
    database_path: Path,
    phase: str,
    failure_case: str,
) -> None:
    if phase == "proposal":
        repository = FamilyContextRepository(database_path)
        caller_key = f"post-write-proposal-{failure_case}"
        calibration_id = derive_calibration_id(caller_key)
        arguments = _proposal_arguments()
        first_call_id = "proposal-write-call"
        transport = _QueuedTransport(
            [
                _tool_call_response(
                    arguments=arguments,
                    call_id=first_call_id,
                ),
                *_post_write_failure_tail(
                    failure_case,
                    tool_name="extract_calibration_evidence",
                    arguments=arguments,
                    first_call_id=first_call_id,
                ),
            ]
        )
        response = _service(
            database_path,
            transport,
            repository=repository,
        ).create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id=f"trace-post-write-proposal-{failure_case}",
        )
        expected_state = CalibrationState.NEEDS_CONFIRMATION
        business_table = "calibration_drafts"
    else:
        repository, proposal = _prepare_proposal(
            database_path,
            caller_key=f"prepare-post-write-commit-{failure_case}",
        )
        request = _commit_request(proposal)
        calibration_id = proposal.calibration_id
        arguments = {
            "draft_id": request.draft_id,
            "draft_digest": request.draft_digest,
            "accepted_operation_ids": list(request.accepted_operation_ids),
        }
        first_call_id = "commit-write-call"
        transport = _QueuedTransport(
            [
                _tool_call_response(
                    name="commit_profile_patch",
                    arguments=arguments,
                    call_id=first_call_id,
                ),
                *_post_write_failure_tail(
                    failure_case,
                    tool_name="commit_profile_patch",
                    arguments=arguments,
                    first_call_id=first_call_id,
                ),
            ]
        )
        response = _service(
            database_path,
            transport,
            repository=repository,
        ).commit_calibration(
            calibration_id,
            request,
            caller_idempotency_key=f"post-write-commit-{failure_case}",
            trace_id=f"trace-post-write-commit-{failure_case}",
        )
        expected_state = CalibrationState.COMMITTED
        business_table = "calibration_commits"

    assert response.stage is expected_state
    assert response.data.narration is None
    assert response.data.narration_status is NarrationStatus.NOT_REQUESTED
    assert (
        repository.get_calibration_recovery(calibration_id).latest_checkpoint.state
        is expected_state
    )
    assert _count_rows(database_path, business_table) == 1
    assert (
        _count_rows(
            database_path,
            "calibration_checkpoints",
            where="WHERE state = 'model_unavailable'",
        )
        == 0
    )


@pytest.mark.parametrize("phase", ["proposal", "commit"])
def test_narration_cached_repeat_preserves_first_success_and_available_text(
    database_path: Path,
    phase: str,
) -> None:
    trace_id = f"trace-narration-cache-{phase}"
    if phase == "proposal":
        repository = FamilyContextRepository(database_path)
        caller_key = "narration-cache-proposal"
        calibration_id = derive_calibration_id(caller_key)
        arguments = _proposal_arguments()
        transport = _QueuedTransport(
            [
                _tool_call_response(arguments=arguments, call_id="write-1"),
                _tool_call_response(arguments=arguments, call_id="write-2"),
                _text_response("Proposal narration available."),
            ]
        )
        response = _service(
            database_path,
            transport,
            repository=repository,
        ).create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id=trace_id,
        )
        business_table = "calibration_drafts"
    else:
        repository, proposal = _prepare_proposal(
            database_path,
            caller_key="prepare-narration-cache-commit",
        )
        request = _commit_request(proposal)
        calibration_id = proposal.calibration_id
        arguments = {
            "draft_id": request.draft_id,
            "draft_digest": request.draft_digest,
            "accepted_operation_ids": list(request.accepted_operation_ids),
        }
        transport = _QueuedTransport(
            [
                _tool_call_response(
                    name="commit_profile_patch",
                    arguments=arguments,
                    call_id="write-1",
                ),
                _tool_call_response(
                    name="commit_profile_patch",
                    arguments=arguments,
                    call_id="write-2",
                ),
                _text_response("Commit narration available."),
            ]
        )
        response = _service(
            database_path,
            transport,
            repository=repository,
        ).commit_calibration(
            calibration_id,
            request,
            caller_idempotency_key="narration-cache-commit",
            trace_id=trace_id,
        )
        business_table = "calibration_commits"

    assert response.data.narration_status is NarrationStatus.NOT_REQUESTED
    assert response.data.narration is None
    assert _count_rows(database_path, business_table) == 1
    if phase == "proposal":
        stored_trace = RunTraceRepository(database_path).get_trace(trace_id)
        assert stored_trace.trace.handler_executions == 1
        assert stored_trace.trace.cache_hits == 0
    else:
        with connect_database(database_path) as connection:
            assert connection.execute(
                "SELECT count(*) FROM harness_traces WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()[0] == 0


def test_protocol_required_tool_not_called_persists_recoverable_failure(
    database_path: Path,
) -> None:
    caller_key = "protocol-required-tool-key"
    transport = _QueuedTransport([_text_response("   ")])
    repository = FamilyContextRepository(database_path)

    with pytest.raises(ParentWorkflowError) as raised:
        _service(database_path, transport, repository=repository).create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id="trace-required-tool-missing",
        )

    assert raised.value.kind is ParentWorkflowFailureKind.MODEL_PROTOCOL_ERROR
    assert raised.value.cause_code == "required_tool_not_called"
    assert raised.value.recovery is not None
    assert raised.value.recovery.latest_checkpoint.state is (CalibrationState.MODEL_UNAVAILABLE)
    assert repository.get_current_profile_version() == 0
    assert _count_rows(database_path, "calibration_drafts") == 0
    trace = RunTraceRepository(database_path).get_trace("trace-required-tool-missing")
    assert trace.trace.handler_executions == 0


def test_protocol_proposal_invalid_terminal_persists_recoverable_failure(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caller_key = "protocol-proposal-invalid-key"
    calibration_id = derive_calibration_id(caller_key)
    repository = FamilyContextRepository(database_path)

    def reject_proposal(*args: object, **kwargs: object) -> None:
        raise ProfileProposalInvalidError("synthetic_invalid_proposal")

    monkeypatch.setattr(repository, "propose_profile_patch", reject_proposal)
    transport = _QueuedTransport([_tool_call_response(), _text_response()])

    with pytest.raises(ParentWorkflowError) as raised:
        _service(database_path, transport, repository=repository).create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id="trace-proposal-invalid",
        )

    assert raised.value.kind is ParentWorkflowFailureKind.MODEL_PROTOCOL_ERROR
    assert raised.value.cause_code == "proposal_invalid"
    assert raised.value.recovery is not None
    assert raised.value.recovery.calibration_id == calibration_id
    assert raised.value.recovery.latest_checkpoint.state is (CalibrationState.MODEL_UNAVAILABLE)
    assert _count_rows(database_path, "calibration_drafts") == 0


def test_commit_uses_parent_request_and_ignores_unread_model_response(
    database_path: Path,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    request = _commit_request(proposal)
    mismatch = {
        "draft_id": request.draft_id,
        "draft_digest": request.draft_digest,
        "accepted_operation_ids": ["different-operation"],
    }
    transport = _QueuedTransport(
        [
            _tool_call_response(
                name="commit_profile_patch",
                arguments=mismatch,
                call_id="mismatch-call",
            ),
            _text_response(),
        ]
    )

    result = _service(
        database_path,
        transport,
        repository=repository,
    ).commit_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key="confirmation-mismatch-key",
        trace_id="trace-confirmation-mismatch",
    )

    assert result.stage is CalibrationState.COMMITTED
    assert transport.payloads == []
    assert repository.get_current_profile_version() == 1


@pytest.mark.parametrize(
    ("repository_error", "expected_kind"),
    [
        (
            NotFoundError("calibration", "synthetic-missing"),
            ParentWorkflowFailureKind.NOT_FOUND,
        ),
        (
            VersionConflictError("calibration", "synthetic", 1, 2),
            ParentWorkflowFailureKind.VERSION_CONFLICT,
        ),
        (
            IdempotencyConflictError("propose_profile_patch", "<redacted>"),
            ParentWorkflowFailureKind.IDEMPOTENCY_CONFLICT,
        ),
        (
            InvalidTransitionError("input_saved", "committed"),
            ParentWorkflowFailureKind.INVALID_TRANSITION,
        ),
    ],
)
def test_terminal_failure_from_proposal_repository_never_marks_model_unavailable(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repository_error: Exception,
    expected_kind: ParentWorkflowFailureKind,
) -> None:
    caller_key = f"terminal-failure-proposal-{expected_kind.value}"
    calibration_id = derive_calibration_id(caller_key)
    repository = FamilyContextRepository(database_path)

    def fail_repository(*args: object, **kwargs: object) -> None:
        raise repository_error

    monkeypatch.setattr(repository, "propose_profile_patch", fail_repository)
    transport = _QueuedTransport([_tool_call_response(), _text_response()])

    with pytest.raises(ParentWorkflowError) as raised:
        _service(database_path, transport, repository=repository).create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id=f"trace-terminal-failure-{expected_kind.value}",
        )

    assert raised.value.kind is expected_kind
    assert raised.value.recovery is None
    assert (
        repository.get_calibration_recovery(calibration_id).latest_checkpoint.state
        is CalibrationState.INPUT_SAVED
    )
    assert (
        _count_rows(
            database_path,
            "calibration_checkpoints",
            where="WHERE state = 'model_unavailable'",
        )
        == 0
    )


@pytest.mark.parametrize(
    ("repository_error", "expected_kind"),
    [
        (
            DraftDigestMismatchError("synthetic-draft"),
            ParentWorkflowFailureKind.DRAFT_DIGEST_MISMATCH,
        ),
        (
            CommitCommandInvalidError("synthetic-command-invalid"),
            ParentWorkflowFailureKind.COMMIT_COMMAND_INVALID,
        ),
    ],
)
def test_terminal_failure_from_commit_repository_preserves_draft_without_checkpoint(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repository_error: Exception,
    expected_kind: ParentWorkflowFailureKind,
) -> None:
    repository, proposal = _prepare_proposal(
        database_path,
        caller_key=f"prepare-terminal-commit-{expected_kind.value}",
    )
    request = _commit_request(proposal)

    def fail_repository(*args: object, **kwargs: object) -> None:
        raise repository_error

    monkeypatch.setattr(repository, "commit_profile_patch", fail_repository)
    transport = _QueuedTransport([_commit_tool_response(request), _text_response()])

    with pytest.raises(ParentWorkflowError) as raised:
        _service(database_path, transport, repository=repository).commit_calibration(
            proposal.calibration_id,
            request,
            caller_idempotency_key=f"terminal-commit-{expected_kind.value}",
            trace_id=f"trace-terminal-commit-{expected_kind.value}",
        )

    assert raised.value.kind is expected_kind
    assert raised.value.recovery is None
    recovery = repository.get_calibration_recovery(proposal.calibration_id)
    assert recovery.latest_checkpoint.state is CalibrationState.NEEDS_CONFIRMATION
    assert recovery.pending_draft == proposal.data.draft
    assert repository.get_current_profile_version() == 0
    assert (
        _count_rows(
            database_path,
            "calibration_checkpoints",
            where="WHERE state = 'model_unavailable'",
        )
        == 0
    )


def test_unknown_handler_failure_is_internal_and_sanitized_without_checkpoint(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caller_key = "unknown-handler-key"
    calibration_id = derive_calibration_id(caller_key)
    repository = FamilyContextRepository(database_path)

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret python exception text")

    monkeypatch.setattr(repository, "propose_profile_patch", explode)
    transport = _QueuedTransport([_tool_call_response()])

    with pytest.raises(ParentWorkflowError) as raised:
        _service(database_path, transport, repository=repository).create_calibration(
            _create_request(),
            caller_idempotency_key=caller_key,
            trace_id="trace-unknown-handler",
        )

    assert raised.value.kind is ParentWorkflowFailureKind.INTERNAL_ERROR
    assert raised.value.cause_code == "tool_handler_failed"
    assert raised.value.recovery is None
    assert "secret python exception text" not in str(raised.value)
    assert (
        _count_rows(
            database_path,
            "calibration_checkpoints",
            where="WHERE state = 'model_unavailable'",
        )
        == 0
    )
    assert (
        repository.get_calibration_recovery(calibration_id).latest_checkpoint.state
        is CalibrationState.INPUT_SAVED
    )


def test_protocol_harness_code_classification_is_exhaustive_and_disjoint() -> None:
    unavailable = frozenset(
        {
            "model_timeout",
            "model_connection_refused",
            "model_transport_error",
            "model_http_error",
            "model_not_found",
            "model_not_loaded",
            "model_tool_use_missing",
        }
    )
    protocol = frozenset(
        {
            "malformed_json_response",
            "malformed_response_envelope",
            "malformed_model_metadata",
            "model_output_truncated",
            "model_id_mismatch",
            "missing_choice",
            "malformed_choice",
            "invalid_tool_call",
            "invalid_tool_arguments_type",
            "unsupported_finish_reason",
            "unexpected_tool_calls",
            "required_tool_not_called",
            "tool_schema_invalid",
            "tool_schema_repair_exhausted",
            "multiple_tool_calls",
            "duplicate_tool_call_id",
            "disallowed_tool",
            "repeated_read_limit",
            "model_confirmation_mismatch",
            "proposal_invalid",
        }
    )
    post_write = frozenset({"idempotency_conflict", "tool_loop_limit", "empty_final_content"})
    internal = frozenset(
        {
            "invalid_model_base_url",
            "unsupported_model_id",
            "remote_model_host_forbidden",
            "mock_model_forbidden",
            "missing_idempotency_key",
            "tool_handler_failed",
            "tool_result_not_object",
            "tool_result_not_serializable",
            "harness_internal_error",
        }
    )
    actual_sets = (
        getattr(parent_module, "MODEL_UNAVAILABLE_CODES"),
        getattr(parent_module, "MODEL_PROTOCOL_CODES"),
        getattr(parent_module, "POST_WRITE_ONLY_CODES"),
        getattr(parent_module, "INTERNAL_RUNTIME_CODES"),
    )

    assert actual_sets == (unavailable, protocol, post_write, internal)
    for index, left in enumerate(actual_sets):
        for right in actual_sets[index + 1 :]:
            assert left.isdisjoint(right)
    assert set().union(*actual_sets) == unavailable | protocol | post_write | internal
    for code in unavailable:
        assert parent_module._classify_harness_code(code) is (
            ParentWorkflowFailureKind.MODEL_UNAVAILABLE
        )
    for code in protocol:
        assert parent_module._classify_harness_code(code) is (
            ParentWorkflowFailureKind.MODEL_PROTOCOL_ERROR
        )
    for code in internal | post_write | {"unknown_future_code"}:
        assert parent_module._classify_harness_code(code) is (
            ParentWorkflowFailureKind.INTERNAL_ERROR
        )


def test_legacy_commit_failure_retry_commits_without_model(
    database_path: Path,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    request = _commit_request(proposal)
    commit_input = repository.save_profile_commit_input(
        proposal.calibration_id,
        request.draft_id,
        request.accepted_operation_ids,
        draft_digest=request.draft_digest,
        expected_calibration_version=request.expected_calibration_version,
        context=_parent_context("trace-legacy-input", "legacy-input-key"),
    ).input
    repository.mark_calibration_model_unavailable(
        proposal.calibration_id,
        repository.get_calibration_recovery(proposal.calibration_id).receipt.id,
        expected_calibration_version=request.expected_calibration_version,
        error_code="model_timeout",
        resume_stage="profile_commit",
        pending_entity_id=commit_input.id,
        context=_parent_context("trace-legacy-failure", "legacy-failure-key"),
    )
    transport = _QueuedTransport([])

    committed = _service(
        database_path,
        transport,
        repository=FamilyContextRepository(database_path),
    ).retry_calibration(
        proposal.calibration_id,
        CalibrationRetryRequest(expected_calibration_version=3),
        caller_idempotency_key="legacy-retry-key",
        trace_id="trace-legacy-retry",
    )

    assert committed.stage is CalibrationState.COMMITTED
    assert committed.calibration_version == 5
    assert committed.profile_version == 1
    assert committed.data.narration_status is NarrationStatus.NOT_REQUESTED
    assert transport.payloads == []
    assert repository.get_current_profile_version() == 1
    assert _count_rows(database_path, "calibration_commits") == 1


def test_commit_replay_after_restart_is_inference_free(
    database_path: Path,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    request = _commit_request(proposal)
    commit_key = "commit-http-key-0001"
    transport = _QueuedTransport([_commit_tool_response(request), _text_response("Committed.")])
    first = _service(
        database_path,
        transport,
        repository=repository,
    ).commit_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key=commit_key,
        trace_id="trace-commit-first",
    )
    calls_before_replay = len(transport.payloads)
    restarted_repository = FamilyContextRepository(database_path)

    replay = _service(
        database_path,
        transport,
        repository=restarted_repository,
    ).commit_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key=commit_key,
        trace_id="trace-commit-replay",
    )

    assert first.delivery.replayed is False
    assert replay.delivery.replayed is True
    assert replay.stage is CalibrationState.COMMITTED
    assert replay.trace_id == "trace-commit-replay"
    assert len(transport.payloads) == calls_before_replay == 0
    assert restarted_repository.get_current_profile_version() == 1


@pytest.mark.parametrize("changed_field", ["digest", "accepted_ids"])
def test_commit_replay_changed_command_is_idempotency_conflict_before_lm(
    database_path: Path,
    changed_field: str,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    request = _commit_request(proposal)
    commit_key = "commit-http-key-0001"
    transport = _QueuedTransport([_commit_tool_response(request), _text_response("Committed.")])
    service = _service(database_path, transport, repository=repository)
    service.commit_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key=commit_key,
        trace_id="trace-commit-first",
    )
    changed = request.model_copy(
        update=(
            {"draft_digest": "0" * 64}
            if changed_field == "digest"
            else {"accepted_operation_ids": ("different-operation",)}
        )
    )
    calls_before = len(transport.payloads)
    audit_before = _count_rows(
        database_path,
        "calibration_audit_events",
        where="WHERE event_type = 'profile_commit_input_saved'",
    )

    with pytest.raises(IdempotencyConflictError):
        service.commit_calibration(
            proposal.calibration_id,
            changed,
            caller_idempotency_key=commit_key,
            trace_id="trace-commit-conflict",
        )

    assert len(transport.payloads) == calls_before
    assert (
        _count_rows(
            database_path,
            "calibration_audit_events",
            where="WHERE event_type = 'profile_commit_input_saved'",
        )
        == audit_before
    )
    assert repository.get_current_profile_version() == 1


def test_commit_replay_new_key_with_stale_version_conflicts_before_lm(
    database_path: Path,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    request = _commit_request(proposal)
    transport = _QueuedTransport([_commit_tool_response(request), _text_response("Committed.")])
    service = _service(database_path, transport, repository=repository)
    service.commit_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key="commit-http-key-0001",
        trace_id="trace-commit-first",
    )
    calls_before = len(transport.payloads)

    with pytest.raises(VersionConflictError):
        service.commit_calibration(
            proposal.calibration_id,
            request,
            caller_idempotency_key="commit-http-key-new-stale",
            trace_id="trace-commit-stale",
        )

    assert len(transport.payloads) == calls_before
    assert repository.get_current_profile_version() == 1


def test_commit_before_proposal_is_not_found_before_recovery_or_lm(
    database_path: Path,
) -> None:
    caller_key = "input-only-calibration-key"
    calibration_id = derive_calibration_id(caller_key)
    repository = FamilyContextRepository(database_path)
    repository.save_calibration_input(
        calibration_id,
        "Input saved without proposal",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_parent_context("trace-input-only", caller_key),
    )
    request = CalibrationCommitRequest(
        expected_calibration_version=1,
        draft_id="missing-draft",
        draft_digest="0" * 64,
        accepted_operation_ids=("missing-operation",),
    )
    transport = _QueuedTransport([])

    with pytest.raises(NotFoundError):
        _service(database_path, transport, repository=repository).commit_calibration(
            calibration_id,
            request,
            caller_idempotency_key="commit-missing-draft-key",
            trace_id="trace-commit-missing",
        )

    assert transport.payloads == []
    assert (
        _count_rows(
            database_path,
            "calibration_audit_events",
            where="WHERE event_type = 'profile_commit_input_saved'",
        )
        == 0
    )
    assert _count_rows(database_path, "profile_observation_events") == 0


def test_commit_foreign_draft_classifies_new_and_existing_keys_before_lm(
    database_path: Path,
) -> None:
    repository, proposal = _prepare_proposal(
        database_path,
        caller_key="calibration-owner-a-key",
    )
    request = _commit_request(proposal)
    other_key = "calibration-owner-b-key"
    other_id = derive_calibration_id(other_key)
    repository.save_calibration_input(
        other_id,
        "Second calibration input",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_parent_context("trace-owner-b", other_key),
    )
    foreign_request = request.model_copy(update={"expected_calibration_version": 1})
    no_call_transport = _QueuedTransport([])
    other_service = _service(
        database_path,
        no_call_transport,
        repository=repository,
    )

    with pytest.raises(NotFoundError):
        other_service.commit_calibration(
            other_id,
            foreign_request,
            caller_idempotency_key="new-foreign-commit-key",
            trace_id="trace-foreign-new",
        )

    commit_key = "commit-http-key-owner-a"
    commit_transport = _QueuedTransport(
        [_commit_tool_response(request), _text_response("Committed.")]
    )
    _service(
        database_path,
        commit_transport,
        repository=repository,
    ).commit_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key=commit_key,
        trace_id="trace-owner-a-commit",
    )
    audit_before = _count_rows(
        database_path,
        "calibration_audit_events",
        where="WHERE event_type = 'profile_commit_input_saved'",
    )

    with pytest.raises(IdempotencyConflictError):
        other_service.commit_calibration(
            other_id,
            foreign_request,
            caller_idempotency_key=commit_key,
            trace_id="trace-foreign-existing",
        )

    assert no_call_transport.payloads == []
    assert (
        _count_rows(
            database_path,
            "calibration_audit_events",
            where="WHERE event_type = 'profile_commit_input_saved'",
        )
        == audit_before
    )
    assert repository.get_current_profile_version() == 1


def _revised_observation() -> ProposedObservationInput:
    return ProposedObservationInput(
        action=ProfilePatchAction.ASSERT,
        category=MemoryCategory.SUBJECT_PERFORMANCE,
        subject="Mathematics",
        task_type="written",
        metric="assessment_level",
        value_text="developing",
        value_number=None,
        unit=None,
        confidence=0.8,
        sample_count=None,
        observed_at=OBSERVED_AT,
        target_event_id=None,
    )


def test_commit_superseded_draft_is_invalid_transition_before_lm(
    database_path: Path,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    request = _commit_request(proposal)
    repository.revise_profile_patch(
        proposal.calibration_id,
        request.draft_id,
        (_revised_observation(),),
        expected_calibration_version=proposal.calibration_version,
        context=_parent_context("trace-revise-direct", "revise-direct-key"),
    )
    current = repository.get_calibration_recovery(proposal.calibration_id)
    stale_request = request.model_copy(
        update={"expected_calibration_version": current.calibration_version}
    )
    transport = _QueuedTransport([])

    with pytest.raises(InvalidTransitionError):
        _service(database_path, transport, repository=repository).commit_calibration(
            proposal.calibration_id,
            stale_request,
            caller_idempotency_key="commit-superseded-key",
            trace_id="trace-commit-superseded",
        )

    assert transport.payloads == []
    assert (
        _count_rows(
            database_path,
            "calibration_audit_events",
            where="WHERE event_type = 'profile_commit_input_saved'",
        )
        == 0
    )
    assert repository.get_current_profile_version() == 0


class _ProcessCrash(BaseException):
    pass


def test_commit_crash_resume_reuses_receipt_then_replays_without_inference(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    request = _commit_request(proposal)
    commit_key = "commit-http-key-crash-resume"
    transport = _QueuedTransport(
        [_commit_tool_response(request), _text_response("Committed after restart.")]
    )
    crashing = _service(database_path, transport, repository=repository)

    def crash_after_receipt(*args: object, **kwargs: object) -> None:
        raise _ProcessCrash

    monkeypatch.setattr(crashing, "_continue_from_recovery", crash_after_receipt)

    with pytest.raises(_ProcessCrash):
        crashing.commit_calibration(
            proposal.calibration_id,
            request,
            caller_idempotency_key=commit_key,
            trace_id="trace-commit-crash",
        )

    assert transport.payloads == []
    recovery_after_crash = repository.get_calibration_recovery(proposal.calibration_id)
    assert recovery_after_crash.latest_checkpoint.state is (CalibrationState.NEEDS_CONFIRMATION)
    assert recovery_after_crash.pending_draft is not None
    assert recovery_after_crash.last_outcome == (recovery_after_crash.pending_draft_result)
    assert (
        _count_rows(
            database_path,
            "calibration_audit_events",
            where="WHERE event_type = 'profile_commit_input_saved'",
        )
        == 1
    )
    assert (
        _count_rows(
            database_path,
            "idempotency_records",
            where="WHERE operation = 'save_profile_commit_input'",
        )
        == 1
    )
    assert (
        _count_rows(
            database_path,
            "calibration_checkpoints",
            where=("WHERE state IN ('model_unavailable', 'retry_pending', 'committed')"),
        )
        == 0
    )
    assert repository.get_current_profile_version() == 0

    restarted_repository = FamilyContextRepository(database_path)
    restarted = _service(
        database_path,
        transport,
        repository=restarted_repository,
    )
    committed = restarted.commit_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key=commit_key,
        trace_id="trace-commit-resume",
    )

    assert committed.delivery.replayed is False
    assert committed.stage is CalibrationState.COMMITTED
    assert len(transport.payloads) == 0
    assert restarted_repository.get_current_profile_version() == 1
    assert _count_rows(database_path, "calibration_commits") == 1
    assert _count_rows(database_path, "profile_observation_events") == len(
        request.accepted_operation_ids
    )
    calls_before_replay = len(transport.payloads)

    replay = _service(
        database_path,
        transport,
        repository=FamilyContextRepository(database_path),
    ).commit_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key=commit_key,
        trace_id="trace-commit-after-success",
    )

    assert replay.delivery.replayed is True
    assert replay.stage is CalibrationState.COMMITTED
    assert len(transport.payloads) == calls_before_replay
    assert _count_rows(database_path, "calibration_commits") == 1
    assert _count_rows(database_path, "profile_observation_events") == len(
        request.accepted_operation_ids
    )


def test_get_calibration_returns_db_proposal_without_lm(
    database_path: Path,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    transport = _QueuedTransport([])

    stored = _service(
        database_path,
        transport,
        repository=repository,
    ).get_calibration(
        proposal.calibration_id,
        trace_id="trace-get-proposal",
    )

    assert stored.trace_id == "trace-get-proposal"
    assert stored.stage is CalibrationState.NEEDS_CONFIRMATION
    assert stored.delivery.replayed is True
    assert stored.data.kind == "profile_patch_proposal"
    assert stored.data.diff_preview == stored.data.draft.observations
    assert stored.data.narration is None
    assert transport.payloads == []


def test_revise_calibration_and_replay_are_deterministic_without_lm(
    database_path: Path,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    assert proposal.data.kind == "profile_patch_proposal"
    request = CalibrationReviseRequest(
        expected_calibration_version=proposal.calibration_version,
        draft_id=proposal.data.draft.id,
        revised_observations=(_revised_observation(),),
    )
    transport = _QueuedTransport([])
    service = _service(database_path, transport, repository=repository)

    revised = service.revise_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key="revise-http-key-0001",
        trace_id="trace-revise-first",
    )
    replay = _service(
        database_path,
        transport,
        repository=FamilyContextRepository(database_path),
    ).revise_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key="revise-http-key-0001",
        trace_id="trace-revise-replay",
    )

    assert revised.delivery.replayed is False
    assert revised.calibration_version == proposal.calibration_version + 1
    assert revised.data.kind == "profile_patch_proposal"
    assert revised.data.draft.revises_draft_id == request.draft_id
    assert replay.delivery.replayed is True
    assert replay.trace_id == "trace-revise-replay"
    assert replay.data == revised.model_copy(update={"trace_id": "trace-revise-replay"}).data
    assert transport.payloads == []
    assert repository.get_current_profile_version() == 0
    assert _count_rows(database_path, "calibration_drafts") == 2


def test_revise_calibration_preserves_direct_profile_proposal_invalid_error(
    database_path: Path,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    assert proposal.data.kind == "profile_patch_proposal"
    invalid = ProposedObservationInput(
        action=ProfilePatchAction.REVOKE,
        category=MemoryCategory.SUBJECT_PERFORMANCE,
        subject="Mathematics",
        task_type="written",
        metric="assessment_level",
        value_text=None,
        value_number=None,
        unit=None,
        confidence=0.8,
        sample_count=None,
        observed_at=OBSERVED_AT,
        target_event_id="missing-event",
    )
    request = CalibrationReviseRequest(
        expected_calibration_version=proposal.calibration_version,
        draft_id=proposal.data.draft.id,
        revised_observations=(invalid,),
    )
    transport = _QueuedTransport([])

    with pytest.raises(ProfileProposalInvalidError) as captured:
        _service(
            database_path,
            transport,
            repository=repository,
        ).revise_calibration(
            proposal.calibration_id,
            request,
            caller_idempotency_key="revise-invalid-key",
            trace_id="trace-revise-invalid",
        )

    assert captured.value.reason_code == "unsupported_target"
    assert transport.payloads == []
    assert _count_rows(database_path, "calibration_drafts") == 1


def test_abandon_calibration_and_get_return_recovery_without_lm(
    database_path: Path,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    request = CalibrationAbandonRequest(expected_calibration_version=proposal.calibration_version)
    transport = _QueuedTransport([])

    abandoned = _service(
        database_path,
        transport,
        repository=repository,
    ).abandon_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key="abandon-http-key-0001",
        trace_id="trace-abandon-first",
    )
    stored = _service(
        database_path,
        transport,
        repository=FamilyContextRepository(database_path),
    ).get_calibration(
        proposal.calibration_id,
        trace_id="trace-get-abandoned",
    )

    assert abandoned.delivery.replayed is False
    assert abandoned.stage is CalibrationState.ABANDONED
    assert abandoned.data.kind == "calibration_recovery"
    assert abandoned.data.resume_stage is None
    assert abandoned.data.pending_kind is None
    assert abandoned.data.pending_entity_id is None
    assert stored.delivery.replayed is True
    assert stored.stage is CalibrationState.ABANDONED
    assert stored.trace_id == "trace-get-abandoned"
    assert stored.data == abandoned.data
    assert transport.payloads == []
    assert repository.get_current_profile_version() == 0


def _prepare_commit_gate(
    database_path: Path,
):
    repository, proposal = _prepare_proposal(database_path)
    request = _commit_request(proposal)
    commit_input = repository.save_profile_commit_input(
        proposal.calibration_id,
        request.draft_id,
        request.accepted_operation_ids,
        draft_digest=request.draft_digest,
        expected_calibration_version=request.expected_calibration_version,
        context=_parent_context(
            "trace-gate-command",
            "commit-http-key-gate",
        ),
    )
    recovery = repository.get_calibration_recovery(proposal.calibration_id)
    transport = _QueuedTransport([])
    service = _service(database_path, transport, repository=repository)
    return repository, service, transport, recovery, commit_input


def _insert_commit_attempt_checkpoint(
    database_path: Path,
    *,
    recovery,
    commit_input_id: str,
    state: CalibrationState,
    update_session: bool,
) -> None:
    now = datetime.now(UTC).isoformat()
    with connect_database(database_path) as connection:
        if update_session:
            connection.execute(
                """
                UPDATE calibration_sessions
                SET calibration_version = ?, state = ?, pending_kind = ?,
                    pending_entity_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    recovery.calibration_version + 1,
                    state.value,
                    "model_retry",
                    commit_input_id,
                    now,
                    recovery.calibration_id,
                ),
            )
        connection.execute(
            """
            INSERT INTO calibration_checkpoints (
                id, calibration_id, calibration_version, profile_version,
                state, resume_stage, pending_kind, pending_entity_id,
                last_stable_calibration_version, last_stable_profile_version,
                input_receipt_id, trace_id, outcome_json, occurred_at
            ) VALUES (?, ?, ?, ?, ?, 'profile_commit', 'model_retry', ?,
                      ?, ?, ?, ?, NULL, ?)
            """,
            (
                f"checkpoint-service-gate-{state.value}",
                recovery.calibration_id,
                recovery.calibration_version + 1,
                recovery.profile_version,
                state.value,
                commit_input_id,
                recovery.calibration_version,
                recovery.profile_version,
                recovery.receipt.id,
                f"trace-gate-{state.value}",
                now,
            ),
        )


def _forbid_profile_handlers(
    repository: FamilyContextRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    calls: list[str] = []

    def forbid_proposal(*args: object, **kwargs: object) -> None:
        calls.append("proposal")
        raise AssertionError("proposal handler must not run")

    def forbid_commit(*args: object, **kwargs: object) -> None:
        calls.append("commit")
        raise AssertionError("commit handler must not run")

    monkeypatch.setattr(repository, "propose_profile_patch", forbid_proposal)
    monkeypatch.setattr(repository, "commit_profile_patch", forbid_commit)
    return calls


def test_exact_commit_attempt_checkpoint_blocks_initial_crash_resume(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, service, transport, recovery, commit_input = _prepare_commit_gate(database_path)
    _insert_commit_attempt_checkpoint(
        database_path,
        recovery=recovery,
        commit_input_id=commit_input.input.id,
        state=CalibrationState.MODEL_UNAVAILABLE,
        update_session=False,
    )
    calls = _forbid_profile_handlers(repository, monkeypatch)

    with pytest.raises(ParentWorkflowError) as captured:
        service._continue_from_recovery(
            recovery,
            authorization=InferenceAuthorization.INITIAL_REQUEST,
            initial_commit_input=commit_input,
            caller_idempotency_key="commit-http-key-gate",
            trace_id="trace-gate-attempt-checkpoint",
            delivery_replayed=True,
        )

    assert captured.value.kind is ParentWorkflowFailureKind.INVALID_TRANSITION
    assert captured.value.cause_code == "initial_commit_input_not_authorized"
    assert captured.value.recovery == recovery
    assert calls == []
    assert transport.payloads == []


@pytest.mark.parametrize(
    ("state", "without_receipt_kind", "without_receipt_cause"),
    [
        (
            CalibrationState.MODEL_UNAVAILABLE,
            ParentWorkflowFailureKind.MODEL_UNAVAILABLE,
            "stored_model_unavailable",
        ),
        (
            CalibrationState.RETRY_PENDING,
            ParentWorkflowFailureKind.INVALID_TRANSITION,
            "initial_request_cannot_resume_retry",
        ),
    ],
)
def test_commit_input_model_failure_or_retry_pending_never_resumes_inference(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: CalibrationState,
    without_receipt_kind: ParentWorkflowFailureKind,
    without_receipt_cause: str,
) -> None:
    repository, service, transport, stable, commit_input = _prepare_commit_gate(database_path)
    _insert_commit_attempt_checkpoint(
        database_path,
        recovery=stable,
        commit_input_id=commit_input.input.id,
        state=state,
        update_session=True,
    )
    recovery = repository.get_calibration_recovery(stable.calibration_id)
    calls = _forbid_profile_handlers(repository, monkeypatch)

    with pytest.raises(ParentWorkflowError) as commit_error:
        service._continue_from_recovery(
            recovery,
            authorization=InferenceAuthorization.INITIAL_REQUEST,
            initial_commit_input=commit_input,
            caller_idempotency_key="commit-http-key-gate",
            trace_id=f"trace-gate-{state.value}-commit",
            delivery_replayed=True,
        )

    assert commit_error.value.kind is ParentWorkflowFailureKind.INVALID_TRANSITION
    assert commit_error.value.cause_code == "initial_commit_input_not_authorized"
    with pytest.raises(ParentWorkflowError) as no_receipt_error:
        service._continue_from_recovery(
            recovery,
            authorization=InferenceAuthorization.INITIAL_REQUEST,
            initial_commit_input=None,
            caller_idempotency_key="calibration-create-key-for-commit",
            trace_id=f"trace-gate-{state.value}-stored",
            delivery_replayed=True,
        )

    assert no_receipt_error.value.kind is without_receipt_kind
    assert no_receipt_error.value.cause_code == without_receipt_cause
    assert calls == []
    assert transport.payloads == []


@pytest.mark.parametrize("failure_kind", ["authorization", "resume_stage"])
def test_initial_inference_requires_authorization_and_profile_propose_resume_stage(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
) -> None:
    caller_key = f"initial-gate-{failure_kind}-key"
    calibration_id = derive_calibration_id(caller_key)
    repository = FamilyContextRepository(database_path)
    repository.save_calibration_input(
        calibration_id,
        "Input awaiting gated inference",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_parent_context("trace-initial-gate", caller_key),
    )
    recovery = repository.get_calibration_recovery(calibration_id)
    authorization: object = InferenceAuthorization.INITIAL_REQUEST
    if failure_kind == "authorization":
        authorization = object()
    else:
        recovery = recovery.model_copy(
            update={
                "latest_checkpoint": recovery.latest_checkpoint.model_copy(
                    update={"resume_stage": "profile_commit"}
                )
            }
        )
    transport = _QueuedTransport([])
    service = _service(database_path, transport, repository=repository)
    calls = _forbid_profile_handlers(repository, monkeypatch)

    with pytest.raises(ParentWorkflowError) as captured:
        service._continue_from_recovery(
            recovery,
            authorization=authorization,  # type: ignore[arg-type]
            initial_commit_input=None,
            caller_idempotency_key=caller_key,
            trace_id=f"trace-initial-gate-{failure_kind}",
            delivery_replayed=False,
        )

    expected_kind = (
        ParentWorkflowFailureKind.RETRY_LINEAGE_CONFLICT
        if failure_kind == "authorization"
        else ParentWorkflowFailureKind.INVALID_TRANSITION
    )
    expected_cause = (
        "retry_authorization_invalid"
        if failure_kind == "authorization"
        else "initial_request_cannot_resume_retry"
    )
    assert captured.value.kind is expected_kind
    assert captured.value.cause_code == expected_cause
    assert calls == []
    assert transport.payloads == []


@pytest.mark.parametrize("corruption", ["missing", "extra", "wrong_type"])
def test_stored_commit_outcome_corruption_is_sanitized_without_raw_leakage(
    database_path: Path,
    corruption: str,
) -> None:
    repository, proposal = _prepare_proposal(database_path)
    request = _commit_request(proposal)
    transport = _QueuedTransport([_commit_tool_response(request), _text_response("Committed.")])
    _service(database_path, transport, repository=repository).commit_calibration(
        proposal.calibration_id,
        request,
        caller_idempotency_key="commit-corruption-setup-key",
        trace_id="trace-commit-corruption-setup",
    )
    recovery = repository.get_calibration_recovery(proposal.calibration_id)
    outcome = recovery.last_outcome
    assert outcome is not None
    corrupt_data = dict(outcome.data)
    if corruption == "missing":
        corrupt_data.pop("commit")
    elif corruption == "extra":
        corrupt_data["private-marker"] = "must-not-leak"
    else:
        corrupt_data["accepted_observations"] = "must-not-leak"
    corrupt = recovery.model_copy(
        update={"last_outcome": outcome.model_copy(update={"data": corrupt_data})}
    )
    calls_before = len(transport.payloads)

    with pytest.raises(ParentWorkflowError) as captured:
        _present_recovery(
            corrupt,
            delivery_replayed=True,
            narration=None,
            narration_status=NarrationStatus.NOT_REQUESTED,
            request_trace_id=f"trace-corrupt-{corruption}",
        )

    error = captured.value
    assert error.kind is ParentWorkflowFailureKind.INTERNAL_ERROR
    assert error.cause_code == "stored_commit_outcome_invalid"
    assert error.trace_id == f"trace-corrupt-{corruption}"
    assert error.recovery is None
    assert str(error) == "internal_error"
    assert "must-not-leak" not in repr(error)
    assert error.__cause__ is None
    assert len(transport.payloads) == calls_before
