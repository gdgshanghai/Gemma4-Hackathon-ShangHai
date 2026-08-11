from __future__ import annotations

import json
import sqlite3
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier, Lock
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import load_settings
from backend.contracts.api import (
    CalibrationCommitRequest,
    CalibrationResponseEnvelope,
    CalibrationRetryRequest,
    ErrorEnvelope,
)
from backend.contracts.family import (
    CalibrationState,
    MemoryCategory,
    ProfilePatchAction,
    ProposedObservationInput,
)
from backend.orchestration.lm_studio import LMStudioClient
from backend.services.parent_calibration import (
    ParentCalibrationService,
    _parent_context,
    derive_calibration_id,
)
from backend.storage.family_context import FamilyContextRepository
from backend.storage.run_traces import RunTraceRepository


MODEL = "gemma-4-26b-a4b-it"
BASE_URL = "http://127.0.0.1:1234/v1"
CREATE_KEY = "calibration-create-key-0001"
CREATE_TEXT = "Synthetic parent observation"
OBSERVED_AT = "2026-07-10T12:00:00+08:00"

COMMAND_ROUTE_CASES = (
    ("retry", "retry_calibration", "retry"),
    ("commit", "commit_calibration", "commit"),
    ("revise", "revise_calibration", "revise"),
    ("abandon", "abandon_calibration", "abandon"),
)


def _proposal_arguments() -> dict[str, object]:
    return {
        "duration_groups": [
            {
                "subject": "english",
                "task_type": "recitation",
                "minutes": [28, 30],
            }
        ],
        "unapplied_notes": [],
    }


def _tool_call_response(
    *,
    name: str = "extract_calibration_evidence",
    arguments: dict[str, object] | None = None,
    call_id: str = "call-propose",
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
        payload = json.loads(request.content)
        self.payloads.append(payload)
        if self.callback is not None:
            self.callback(request)
        if not self.responses:
            raise AssertionError("unexpected model request")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, httpx.Response):
            return response
        return httpx.Response(200, json=response)


def _settings(project_root: Path):
    return load_settings(
        project_root=project_root,
        environ={},
        env_file=project_root / "missing.env",
    )


def _lm_client(settings, transport) -> LMStudioClient:
    client = LMStudioClient.from_settings(
        settings,
        transport=httpx.MockTransport(transport),
    )
    assert client.evidence_provenance == "synthetic_transport"
    return client


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _app(
    project_root: Path,
    database_path: Path,
    transport: Any,
):
    settings = _settings(project_root)
    return create_app(
        settings,
        database_path=database_path,
        lm_client=_lm_client(settings, transport),
    )


def _create_body(
    *,
    text: str = CREATE_TEXT,
    expected_profile_version: int = 0,
) -> dict[str, object]:
    return {
        "text": text,
        "expected_calibration_version": 0,
        "expected_profile_version": expected_profile_version,
    }


def _commit_body(proposal: dict[str, Any]) -> dict[str, object]:
    draft = proposal["data"]["draft"]
    return {
        "expected_calibration_version": proposal["calibration_version"],
        "draft_id": draft["id"],
        "draft_digest": draft["draft_digest"],
        "accepted_operation_ids": [
            observation["operation_id"] for observation in draft["observations"]
        ],
    }


def _commit_arguments(body: dict[str, object]) -> dict[str, object]:
    return {
        "draft_id": body["draft_id"],
        "draft_digest": body["draft_digest"],
        "accepted_operation_ids": body["accepted_operation_ids"],
    }


def _commit_tool_response(
    body: dict[str, object],
    *,
    call_id: str = "call-commit",
) -> dict[str, object]:
    return _tool_call_response(
        name="commit_profile_patch",
        arguments=_commit_arguments(body),
        call_id=call_id,
    )


def _count_rows(
    database_path: Path,
    table: str,
    *,
    where: str = "",
) -> int:
    allowed = {
        "calibration_audit_events",
        "calibration_checkpoints",
        "calibration_commits",
        "calibration_drafts",
        "calibration_turn_receipts",
        "harness_traces",
        "idempotency_records",
        "profile_observation_events",
    }
    if table not in allowed or (where and not where.startswith("WHERE ")):
        raise AssertionError("unsafe row-count query")
    with sqlite3.connect(database_path) as connection:
        return int(connection.execute(f"SELECT count(*) FROM {table} {where}").fetchone()[0])


def _assert_synthetic(client: TestClient) -> None:
    assert client.app.state.runtime.lm_client.evidence_provenance == (
        "synthetic_transport"
    )


def _assert_success(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200
    body = response.json()
    CalibrationResponseEnvelope.model_validate_json(response.content)
    assert set(body) == {
        "calibration_id",
        "calibration_version",
        "profile_version",
        "stage",
        "allowed_actions",
        "trace_id",
        "data",
        "delivery",
    }
    assert response.headers.get_list("x-trace-id") == [body["trace_id"]]
    assert not _contains_key(body, "provenance")
    return body


def _assert_error(
    response: httpx.Response,
    status_code: int,
    code: str,
    *,
    secrets: tuple[str, ...] = (),
) -> dict[str, Any]:
    assert response.status_code == status_code
    body = response.json()
    ErrorEnvelope.model_validate_json(response.content)
    assert set(body) == {"error", "trace_id", "recovery"}
    assert set(body["error"]) == {"code", "message", "issues"}
    assert body["error"]["code"] == code
    assert response.headers.get_list("x-trace-id") == [body["trace_id"]]
    serialized = json.dumps(body, ensure_ascii=False, sort_keys=True)
    for secret in secrets:
        assert secret not in serialized
    assert not _contains_key(body, "provenance")
    return body


def _post_create(
    client: TestClient,
    *,
    key: str = CREATE_KEY,
    body: dict[str, object] | None = None,
) -> httpx.Response:
    return client.post(
        "/api/v1/parent/calibrations",
        headers={"Idempotency-Key": key},
        json=body or _create_body(),
    )


def _prepare_http_proposal(
    client: TestClient,
    *,
    key: str = CREATE_KEY,
    body: dict[str, object] | None = None,
) -> dict[str, Any]:
    proposal = _assert_success(_post_create(client, key=key, body=body))
    assert proposal["stage"] == "needs_confirmation"
    return proposal


class _ProcessCrash(BaseException):
    pass


@pytest.fixture
def fresh_route_probe_app(tmp_path: Path):
    transport_calls: list[str] = []

    def reject_model_access(request: httpx.Request) -> httpx.Response:
        transport_calls.append(str(request.url))
        raise AssertionError("command route declaration probe called model")

    settings = _settings(tmp_path)
    lm_client = _lm_client(settings, reject_model_access)
    app = create_app(
        settings,
        database_path=tmp_path / "route-probe.db",
        lm_client=lm_client,
    )
    with TestClient(app) as client:
        yield (
            client,
            client.app.state.runtime.family_repository,
            transport_calls,
        )


def test_proposal_success_is_receipt_first_and_correlated_through_http(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "proposal-success.db"
    callback_count = 0

    def inspect_request(request: httpx.Request) -> None:
        nonlocal callback_count
        callback_count += 1
        payload = json.loads(request.content)
        if callback_count == 1:
            with sqlite3.connect(database_path) as connection:
                receipt = connection.execute(
                    "SELECT raw_text, actor, role FROM calibration_turn_receipts"
                ).fetchone()
                checkpoint = connection.execute(
                    "SELECT state, resume_stage FROM calibration_checkpoints "
                    "ORDER BY calibration_version DESC LIMIT 1"
                ).fetchone()
                assert receipt == (CREATE_TEXT, "local-parent", "parent")
                assert checkpoint == ("input_saved", "profile_propose")
            assert payload["tool_choice"] == "required"
            assert [tool["function"]["name"] for tool in payload["tools"]] == [
                "extract_calibration_evidence"
            ]
            return

        assert payload["tool_choice"] == "auto"
        assert payload["messages"][-2]["tool_calls"][0]["id"] == "call-propose"
        tool_message = payload["messages"][-1]
        assert tool_message["role"] == "tool"
        assert tool_message["tool_call_id"] == "call-propose"
        assert tool_message["name"] == "extract_calibration_evidence"
        result = json.loads(tool_message["content"])
        assert result["ok"] is True
        assert result["operation"] == "profile_patch_proposed"
        assert result["outcome"]["state"] == "needs_confirmation"

    transport = _QueuedTransport(
        [_tool_call_response(), _text_response()],
        callback=inspect_request,
    )
    settings = _settings(tmp_path)
    app = create_app(
        settings,
        database_path=database_path,
        lm_client=_lm_client(settings, transport),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/parent/calibrations",
            headers={"Idempotency-Key": CREATE_KEY},
            json={
                "text": CREATE_TEXT,
                "expected_calibration_version": 0,
                "expected_profile_version": 0,
            },
        )
        assert client.app.state.runtime.lm_client.evidence_provenance == (
            "synthetic_transport"
        )

    assert response.status_code == 200
    body = response.json()
    CalibrationResponseEnvelope.model_validate_json(response.content)
    assert response.headers["x-trace-id"] == body["trace_id"]
    assert body["calibration_version"] == 2
    assert body["profile_version"] == 0
    assert body["stage"] == "needs_confirmation"
    assert body["data"]["kind"] == "profile_patch_proposal"
    assert body["data"]["draft"]["base_profile_version"] == 0
    assert len(body["data"]["draft"]["draft_digest"]) == 64
    assert body["data"]["diff_preview"] == body["data"]["draft"]["observations"]
    assert body["data"]["narration"] is None
    assert body["data"]["narration_status"] == "not_requested"
    assert body["delivery"] == {"replayed": False}
    assert callback_count == 1
    assert len(transport.payloads) == 1
    assert not _contains_key(body, "provenance")


@pytest.mark.parametrize(
    ("suffix", "method_name", "body_kind"),
    COMMAND_ROUTE_CASES,
)
def test_command_route_declaration_is_bound(
    suffix: str,
    method_name: str,
    body_kind: str,
    fresh_route_probe_app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, repository, transport_calls = fresh_route_probe_app
    calibration_id = f"calibration-route-probe-{body_kind}"
    observation = ProposedObservationInput(
        action=ProfilePatchAction.ASSERT,
        category=MemoryCategory.SUBJECT_PERFORMANCE,
        subject="english",
        task_type=None,
        metric="assessment_level",
        value_text="secure",
        value_number=None,
        unit=None,
        confidence=0.85,
        sample_count=None,
        observed_at=datetime.fromisoformat(OBSERVED_AT),
        target_event_id=None,
    )
    receipt = repository.save_calibration_input(
        calibration_id,
        "Synthetic route declaration probe",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_parent_context(
            "trace-route-input",
            "route-input-key-0001",
        ),
    ).receipt
    repository.propose_profile_patch(
        calibration_id,
        receipt.id,
        (observation,),
        expected_calibration_version=1,
        context=_parent_context(
            "trace-route-proposal",
            "route-propose-key-01",
        ),
    )
    draft = repository.get_calibration_recovery(calibration_id).pending_draft
    assert draft is not None
    operation_id = draft.observations[0].operation_id

    body_by_kind = {
        "retry": {"expected_calibration_version": 2},
        "commit": {
            "expected_calibration_version": 2,
            "draft_id": draft.id,
            "draft_digest": draft.draft_digest,
            "accepted_operation_ids": [operation_id],
        },
        "revise": {
            "expected_calibration_version": 2,
            "draft_id": draft.id,
            "revised_observations": [observation.model_dump(mode="json")],
        },
        "abandon": {"expected_calibration_version": 2},
    }
    body = body_by_kind[body_kind]
    calls: list[str] = []

    def route_probe(
        self,
        requested_calibration_id,
        request,
        *,
        caller_idempotency_key,
        trace_id,
    ):
        calls.append(method_name)
        return self.get_calibration(
            requested_calibration_id,
            trace_id=trace_id,
        )

    monkeypatch.setattr(
        ParentCalibrationService,
        method_name,
        route_probe,
    )
    response = client.post(
        f"/api/v1/parent/calibrations/{calibration_id}/{suffix}",
        headers={"Idempotency-Key": f"route-probe-{suffix}-0001"},
        json=body,
    )
    assert response.status_code == 200
    assert calls == [method_name]
    assert transport_calls == []


def test_create_replay_and_changed_body_conflict_before_model(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "create-replay.db"
    key = "create-replay-key-0001"
    transport = _QueuedTransport([_tool_call_response(), _text_response()])
    app = _app(tmp_path, database_path, transport)

    with TestClient(app) as client:
        first = _prepare_http_proposal(client, key=key)
        calls_after_first = len(transport.payloads)
        rows_after_first = (
            _count_rows(database_path, "calibration_turn_receipts"),
            _count_rows(database_path, "calibration_drafts"),
            _count_rows(database_path, "calibration_checkpoints"),
        )

        replay = _assert_success(_post_create(client, key=key))
        assert replay["calibration_id"] == first["calibration_id"]
        assert replay["stage"] == "needs_confirmation"
        assert replay["delivery"] == {"replayed": True}
        assert replay["data"]["narration_status"] == "not_requested"
        assert len(transport.payloads) == calls_after_first == 1

        for changed in (
            _create_body(text="Changed synthetic parent observation"),
            _create_body(expected_profile_version=1),
        ):
            conflict = _post_create(client, key=key, body=changed)
            _assert_error(
                conflict,
                409,
                "idempotency_conflict",
                secrets=(key, hashlib.sha256(key.encode()).hexdigest()),
            )
            assert len(transport.payloads) == calls_after_first
        _assert_synthetic(client)

    assert rows_after_first == (
        _count_rows(database_path, "calibration_turn_receipts"),
        _count_rows(database_path, "calibration_drafts"),
        _count_rows(database_path, "calibration_checkpoints"),
    )
    assert key.encode() not in database_path.read_bytes()
    assert not list(tmp_path.glob("*evidence*.json"))


def test_unavailable_create_replay_and_explicit_retry_are_recoverable(
    tmp_path: Path,
) -> None:
    expected_trace_code = "model_transport_error"
    database_path = tmp_path / f"unavailable-{expected_trace_code}.db"
    key = f"create-unavailable-{expected_trace_code}-key"
    exception_marker = f"private-{expected_trace_code}-exception"
    request = httpx.Request("POST", f"{BASE_URL}/chat/completions")
    transport = _QueuedTransport([httpx.ReadError(exception_marker, request=request)])
    app = _app(tmp_path, database_path, transport)

    with TestClient(app) as client:
        failed = _post_create(client, key=key)
        failed_body = _assert_error(
            failed,
            503,
            "model_unavailable",
            secrets=(
                CREATE_TEXT,
                key,
                hashlib.sha256(key.encode()).hexdigest(),
                "Prompt",
                "LM response",
                exception_marker,
                "Python exception",
            ),
        )
        recovery = failed_body["recovery"]
        assert recovery is not None
        assert recovery["stage"] == "model_unavailable"
        assert recovery["calibration_version"] == 2
        assert recovery["profile_version"] == 0
        assert recovery["input_saved"] is True
        assert recovery["resume_stage"] == "profile_propose"
        assert recovery["pending_kind"] == "model_retry"
        assert recovery["allowed_actions"] == [
            "retry_last_turn",
            "use_simplified_calibration",
            "abandon_profile_patch",
        ]
        assert recovery["failure_code"] == expected_trace_code
        assert _count_rows(database_path, "calibration_drafts") == 0
        assert _count_rows(database_path, "profile_observation_events") == 0
        stored_trace = RunTraceRepository(database_path).get_trace(failed_body["trace_id"])
        assert stored_trace.trace.final_error_code == expected_trace_code

        calls_after_failure = len(transport.payloads)
        replay = _post_create(client, key=key)
        replay_body = _assert_error(
            replay,
            503,
            "model_unavailable",
            secrets=(CREATE_TEXT, key, exception_marker),
        )
        assert replay_body["trace_id"] != failed_body["trace_id"]
        assert replay_body["recovery"] == recovery
        assert len(transport.payloads) == calls_after_failure == 1

        transport.responses.extend([_tool_call_response(), _text_response()])
        retry_key = f"retry-{expected_trace_code}-key-0001"
        retried = client.post(
            f"/api/v1/parent/calibrations/{recovery['calibration_id']}/retry",
            headers={"Idempotency-Key": retry_key},
            json={"expected_calibration_version": recovery["calibration_version"]},
        )
        retried_body = _assert_success(retried)
        assert retried_body["stage"] == "needs_confirmation"
        assert retried_body["calibration_version"] == 4
        assert retried_body["profile_version"] == 0
        assert len(transport.payloads) == 2

        retry_replay = client.post(
            f"/api/v1/parent/calibrations/{recovery['calibration_id']}/retry",
            headers={"Idempotency-Key": retry_key},
            json={"expected_calibration_version": recovery["calibration_version"]},
        )
        retry_replay_body = _assert_success(retry_replay)
        assert retry_replay_body["delivery"] == {"replayed": True}
        assert retry_replay_body["stage"] == "needs_confirmation"
        assert len(transport.payloads) == 2
        _assert_synthetic(client)

    assert _count_rows(database_path, "calibration_drafts") == 1
    assert _count_rows(database_path, "profile_observation_events") == 0
    assert not list(tmp_path.glob("*evidence*.json"))


def test_failed_calibration_can_simplify_and_commit_without_more_model_calls(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "simplify-and-commit.db"
    transport = _QueuedTransport(
        [
            httpx.ReadTimeout(
                "synthetic timeout",
                request=httpx.Request("POST", f"{BASE_URL}/chat/completions"),
            )
        ]
    )
    app = _app(tmp_path, database_path, transport)
    create_key = "simplify-create-key"
    calibration_id = derive_calibration_id(create_key)
    simplify_body = {
        "expected_calibration_version": 2,
        "duration_groups": [
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
        ],
    }

    with TestClient(app) as client:
        failed = _post_create(client, key=create_key)
        failure = _assert_error(failed, 503, "model_unavailable")
        assert failure["recovery"]["failure_code"] == "model_timeout"

        simplified = _assert_success(
            client.post(
                f"/api/v1/parent/calibrations/{calibration_id}/simplify",
                headers={"Idempotency-Key": "simplify-key-0001"},
                json=simplify_body,
            )
        )
        assert simplified["stage"] == "needs_confirmation"
        assert {
            item["subject"]: item["value_number"]
            for item in simplified["data"]["diff_preview"]
        } == {
            "mathematics": 1.7,
            "chinese": 1.3,
            "english": 1.5,
            "geography": 0.84,
        }
        replay = _assert_success(
            client.post(
                f"/api/v1/parent/calibrations/{calibration_id}/simplify",
                headers={"Idempotency-Key": "simplify-key-0001"},
                json=simplify_body,
            )
        )
        assert replay["delivery"] == {"replayed": True}

        committed = _assert_success(
            client.post(
                f"/api/v1/parent/calibrations/{calibration_id}/commit",
                headers={"Idempotency-Key": "simplified-commit-key"},
                json=_commit_body(simplified),
            )
        )
        assert committed["stage"] == "committed"
        assert committed["profile_version"] == 1
        assert committed["data"]["narration_status"] == "not_requested"
        assert len(transport.payloads) == 1

def test_retry_begin_crash_restarts_from_exact_checkpoint_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "retry-crash.db"
    create_key = "retry-crash-create-key-0001"
    request = httpx.Request("POST", f"{BASE_URL}/chat/completions")
    transport = _QueuedTransport(
        [httpx.ReadTimeout("private initial timeout", request=request)]
    )
    first_app = _app(tmp_path, database_path, transport)

    with TestClient(first_app) as client:
        failed = _post_create(client, key=create_key)
        recovery = _assert_error(failed, 503, "model_unavailable")["recovery"]
        assert recovery is not None
        service = client.app.state.runtime.parent_service

        def crash_after_retry_begin(*args: object, **kwargs: object) -> None:
            raise _ProcessCrash

        monkeypatch.setattr(service, "_continue_from_recovery", crash_after_retry_begin)
        retry_key = "retry-crash-command-key-0001"
        with pytest.raises(_ProcessCrash):
            service.retry_calibration(
                recovery["calibration_id"],
                CalibrationRetryRequest(expected_calibration_version=2),
                caller_idempotency_key=retry_key,
                trace_id="trace-retry-crash",
            )
        assert len(transport.payloads) == 1
        pending = client.app.state.runtime.family_repository.get_calibration_recovery(
            recovery["calibration_id"]
        )
        assert pending.latest_checkpoint.state is CalibrationState.RETRY_PENDING
        assert pending.calibration_version == 3

    transport.responses.extend([_tool_call_response(), _text_response()])
    restarted_app = _app(tmp_path, database_path, transport)
    with TestClient(restarted_app) as client:
        resumed = client.post(
            f"/api/v1/parent/calibrations/{recovery['calibration_id']}/retry",
            headers={"Idempotency-Key": retry_key},
            json={"expected_calibration_version": 2},
        )
        resumed_body = _assert_success(resumed)
        assert resumed_body["stage"] == "needs_confirmation"
        assert resumed_body["calibration_version"] == 4
        assert len(transport.payloads) == 2
        _assert_synthetic(client)

    assert _count_rows(database_path, "calibration_drafts") == 1
    assert (
        _count_rows(
            database_path,
            "calibration_checkpoints",
            where="WHERE state = 'retry_pending'",
        )
        == 1
    )


def test_commit_success_exact_replay_and_conflicts_are_premodel(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "commit-success.db"
    transport = _QueuedTransport([_tool_call_response(), _text_response()])
    app = _app(tmp_path, database_path, transport)
    commit_key = "commit-success-key-0001"

    with TestClient(app) as client:
        proposal = _prepare_http_proposal(client, key="commit-setup-key-0001")
        body = _commit_body(proposal)
        transport.responses.extend(
            [_commit_tool_response(body), _text_response("Profile committed.")]
        )
        response = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
            headers={"Idempotency-Key": commit_key},
            json=body,
        )
        committed = _assert_success(response)
        assert committed["stage"] == "committed"
        assert committed["calibration_version"] == proposal["calibration_version"] + 1
        assert committed["profile_version"] == proposal["profile_version"] + 1
        assert committed["data"]["draft_digest"] == body["draft_digest"]
        assert committed["data"]["accepted_operation_ids"] == body[
            "accepted_operation_ids"
        ]
        assert set(committed["data"]["observation_event_ids"])
        assert committed["data"]["narration_status"] == "not_requested"
        repository = client.app.state.runtime.family_repository
        assert len(repository.list_profile_history()[1]) == len(
            body["accepted_operation_ids"]
        )

        calls_after_commit = len(transport.payloads)
        replay = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
            headers={"Idempotency-Key": commit_key},
            json=body,
        )
        replay_body = _assert_success(replay)
        assert replay_body["delivery"] == {"replayed": True}
        assert replay_body["stage"] == "committed"
        assert len(transport.payloads) == calls_after_commit == 1

        changed_digest = {**body, "draft_digest": "f" * 64}
        changed_ids = {**body, "accepted_operation_ids": ["different-operation"]}
        for changed in (changed_digest, changed_ids):
            conflict = client.post(
                f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
                headers={"Idempotency-Key": commit_key},
                json=changed,
            )
            _assert_error(conflict, 409, "idempotency_conflict", secrets=(commit_key,))
            assert len(transport.payloads) == calls_after_commit

        stale = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
            headers={"Idempotency-Key": "commit-stale-new-key-0001"},
            json=body,
        )
        _assert_error(stale, 409, "version_conflict")
        assert len(transport.payloads) == calls_after_commit

        abandon = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/abandon",
            headers={"Idempotency-Key": "abandon-committed-key-0001"},
            json={"expected_calibration_version": committed["calibration_version"]},
        )
        _assert_error(abandon, 409, "invalid_transition")
        assert len(transport.payloads) == calls_after_commit
        _assert_synthetic(client)

    assert _count_rows(database_path, "calibration_commits") == 1
    assert _count_rows(database_path, "profile_observation_events") == len(
        body["accepted_operation_ids"]
    )
    restarted = _app(tmp_path, database_path, transport)
    with TestClient(restarted) as client:
        stored = client.get(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}"
        )
        stored_body = _assert_success(stored)
        assert stored_body["stage"] == "committed"
        assert stored_body["profile_version"] == 1
        assert stored_body["delivery"] == {"replayed": True}
        assert len(transport.payloads) == 1
        _assert_synthetic(client)


def test_commit_does_not_consult_model_confirmation_output(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "commit-confirmation-mismatch.db"
    transport = _QueuedTransport([_tool_call_response(), _text_response()])
    app = _app(tmp_path, database_path, transport)

    with TestClient(app) as client:
        proposal = _prepare_http_proposal(client, key="commit-mismatch-setup-key")
        body = _commit_body(proposal)
        mismatch = {
            **_commit_arguments(body),
            "accepted_operation_ids": ["different-operation"],
        }
        transport.responses.append(
            _tool_call_response(
                name="commit_profile_patch",
                arguments=mismatch,
                call_id="commit-mismatch-call",
            )
        )
        response = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
            headers={"Idempotency-Key": "commit-mismatch-key-0001"},
            json=body,
        )
        committed = _assert_success(response)
        assert committed["stage"] == "committed"
        assert len(transport.payloads) == 1
        stored = client.app.state.runtime.family_repository.get_calibration_recovery(
            proposal["calibration_id"]
        )
        assert stored.pending_draft is None
        assert stored.latest_checkpoint.state is CalibrationState.COMMITTED
        assert _count_rows(database_path, "calibration_commits") == 1
        assert _count_rows(database_path, "profile_observation_events") > 0
        _assert_synthetic(client)


def test_commit_premodel_state_and_command_failures_are_typed(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "commit-premodel.db"
    transport = _QueuedTransport([_tool_call_response(), _text_response()])
    app = _app(tmp_path, database_path, transport)

    with TestClient(app) as client:
        unknown_body = {
            "expected_calibration_version": 1,
            "draft_id": "missing-draft",
            "draft_digest": "0" * 64,
            "accepted_operation_ids": ["missing-operation"],
        }
        unknown = client.post(
            "/api/v1/parent/calibrations/missing-calibration/commit",
            headers={"Idempotency-Key": "commit-before-proposal-key"},
            json=unknown_body,
        )
        _assert_error(unknown, 404, "not_found")
        assert transport.payloads == []

        input_only_id = "input-only-calibration-http"
        repository = client.app.state.runtime.family_repository
        repository.save_calibration_input(
            input_only_id,
            "Private input-only calibration text",
            expected_calibration_version=0,
            expected_profile_version=0,
            context=_parent_context(
                "trace-input-only-http",
                "input-only-storage-key",
            ),
        )
        input_only = client.post(
            f"/api/v1/parent/calibrations/{input_only_id}/commit",
            headers={"Idempotency-Key": "input-only-commit-key-0001"},
            json=unknown_body,
        )
        _assert_error(
            input_only,
            404,
            "not_found",
            secrets=("Private input-only calibration text",),
        )
        assert transport.payloads == []

        proposal = _prepare_http_proposal(client, key="commit-premodel-setup-key")
        body = _commit_body(proposal)
        calls_after_proposal = len(transport.payloads)
        receipt_rows = _count_rows(
            database_path,
            "calibration_audit_events",
            where="WHERE event_type = 'profile_commit_input_saved'",
        )

        wrong_digest = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
            headers={"Idempotency-Key": "commit-wrong-digest-key-01"},
            json={**body, "draft_digest": "f" * 64},
        )
        _assert_error(wrong_digest, 409, "draft_digest_mismatch")

        out_of_subset = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
            headers={"Idempotency-Key": "commit-invalid-subset-key"},
            json={**body, "accepted_operation_ids": ["missing-operation"]},
        )
        _assert_error(out_of_subset, 409, "commit_command_invalid")
        assert len(transport.payloads) == calls_after_proposal
        assert _count_rows(database_path, "profile_observation_events") == 0
        assert _count_rows(
            database_path,
            "calibration_audit_events",
            where="WHERE event_type = 'profile_commit_input_saved'",
        ) == receipt_rows

        revised_observation = {
            key: value
            for key, value in proposal["data"]["diff_preview"][0].items()
            if key != "operation_id"
        }
        revised_observation["value_number"] = 1.75
        revised = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/revise",
            headers={"Idempotency-Key": "commit-supersede-revise-key"},
            json={
                "expected_calibration_version": proposal["calibration_version"],
                "draft_id": body["draft_id"],
                "revised_observations": [revised_observation],
            },
        )
        revised_body = _assert_success(revised)
        assert revised_body["calibration_version"] == 3
        superseded = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
            headers={"Idempotency-Key": "commit-superseded-key-01"},
            json={**body, "expected_calibration_version": 3},
        )
        _assert_error(superseded, 409, "invalid_transition")
        assert len(transport.payloads) == calls_after_proposal
        _assert_synthetic(client)


def test_commit_receipt_crash_restarts_and_commits_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "commit-crash.db"
    transport = _QueuedTransport([_tool_call_response(), _text_response()])
    first_app = _app(tmp_path, database_path, transport)
    commit_key = "commit-crash-resume-key-0001"

    with TestClient(first_app) as client:
        proposal = _prepare_http_proposal(client, key="commit-crash-setup-key")
        body = _commit_body(proposal)
        service = client.app.state.runtime.parent_service

        def crash_after_receipt(*args: object, **kwargs: object) -> None:
            raise _ProcessCrash

        monkeypatch.setattr(service, "_continue_from_recovery", crash_after_receipt)
        with pytest.raises(_ProcessCrash):
            service.commit_calibration(
                proposal["calibration_id"],
                CalibrationCommitRequest.model_validate_json(json.dumps(body)),
                caller_idempotency_key=commit_key,
                trace_id="trace-commit-crash",
            )
        assert len(transport.payloads) == 1
        assert _count_rows(
            database_path,
            "calibration_audit_events",
            where="WHERE event_type = 'profile_commit_input_saved'",
        ) == 1
        assert _count_rows(database_path, "calibration_commits") == 0

    transport.responses.extend(
        [_commit_tool_response(body), _text_response("Committed after restart.")]
    )
    restarted_app = _app(tmp_path, database_path, transport)
    with TestClient(restarted_app) as client:
        resumed = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
            headers={"Idempotency-Key": commit_key},
            json=body,
        )
        resumed_body = _assert_success(resumed)
        assert resumed_body["stage"] == "committed"
        assert resumed_body["delivery"] == {"replayed": False}
        calls_after_resume = len(transport.payloads)
        replay = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
            headers={"Idempotency-Key": commit_key},
            json=body,
        )
        replay_body = _assert_success(replay)
        assert replay_body["delivery"] == {"replayed": True}
        assert len(transport.payloads) == calls_after_resume == 1
        _assert_synthetic(client)

    assert _count_rows(database_path, "calibration_commits") == 1
    assert _count_rows(database_path, "profile_observation_events") == len(
        body["accepted_operation_ids"]
    )


@pytest.mark.parametrize("phase", ("proposal", "commit"))
def test_post_write_transport_failure_returns_stored_business_truth(
    tmp_path: Path,
    phase: str,
) -> None:
    database_path = tmp_path / f"post-write-{phase}.db"
    private_marker = f"private-{phase}-narration-read-error"
    request = httpx.Request("POST", f"{BASE_URL}/chat/completions")

    if phase == "proposal":
        key = "post-write-proposal-key-0001"
        transport = _QueuedTransport(
            [
                _tool_call_response(call_id="proposal-business-write"),
                httpx.ReadError(private_marker, request=request),
            ]
        )
        app = _app(tmp_path, database_path, transport)
        with TestClient(app) as client:
            response = _post_create(client, key=key)
            body = _assert_success(response)
            assert body["stage"] == "needs_confirmation"
            assert body["data"]["narration"] is None
            assert body["data"]["narration_status"] == "not_requested"
            calls_after_write = len(transport.payloads)
            replay = _assert_success(_post_create(client, key=key))
            assert replay["delivery"] == {"replayed": True}
            assert len(transport.payloads) == calls_after_write == 1
            _assert_synthetic(client)
        business_table = "calibration_drafts"
    else:
        transport = _QueuedTransport([_tool_call_response(), _text_response()])
        app = _app(tmp_path, database_path, transport)
        key = "post-write-commit-key-0001"
        with TestClient(app) as client:
            proposal = _prepare_http_proposal(
                client,
                key="post-write-commit-setup-key",
            )
            command = _commit_body(proposal)
            transport.responses.extend(
                [
                    _commit_tool_response(command, call_id="commit-business-write"),
                    httpx.ReadError(private_marker, request=request),
                ]
            )
            response = client.post(
                f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
                headers={"Idempotency-Key": key},
                json=command,
            )
            body = _assert_success(response)
            assert body["stage"] == "committed"
            assert body["data"]["narration"] is None
            assert body["data"]["narration_status"] == "not_requested"
            calls_after_write = len(transport.payloads)
            replay = client.post(
                f"/api/v1/parent/calibrations/{proposal['calibration_id']}/commit",
                headers={"Idempotency-Key": key},
                json=command,
            )
            replay_body = _assert_success(replay)
            assert replay_body["delivery"] == {"replayed": True}
            assert len(transport.payloads) == calls_after_write == 1
            _assert_synthetic(client)
        business_table = "calibration_commits"

    if phase == "proposal":
        stored_trace = RunTraceRepository(database_path).get_trace(body["trace_id"])
        assert stored_trace.trace.final_error_code is None
        assert stored_trace.trace.handler_executions == 1
    else:
        with sqlite3.connect(database_path) as connection:
            assert connection.execute(
                "SELECT count(*) FROM harness_traces WHERE trace_id = ?",
                (body["trace_id"],),
            ).fetchone()[0] == 0
    assert _count_rows(database_path, business_table) == 1
    assert (
        _count_rows(
            database_path,
            "calibration_checkpoints",
            where="WHERE state = 'model_unavailable'",
        )
        == 0
    )
    assert private_marker not in json.dumps(body)


def test_required_tool_missing_is_recoverable_protocol_error_through_http(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "required-tool-missing.db"
    key = "required-tool-missing-key-0001"
    transport = _QueuedTransport([_text_response("   ")])
    app = _app(tmp_path, database_path, transport)

    with TestClient(app) as client:
        response = _post_create(client, key=key)
        body = _assert_error(
            response,
            502,
            "model_protocol_error",
            secrets=(CREATE_TEXT, key, hashlib.sha256(key.encode()).hexdigest()),
        )
        assert body["recovery"] is None
        trace = RunTraceRepository(database_path).get_trace(body["trace_id"])
        assert trace.trace.final_error_code == "required_tool_not_called"
        assert trace.trace.handler_executions == 0
        assert _count_rows(database_path, "calibration_drafts") == 0
        assert _count_rows(database_path, "profile_observation_events") == 0

        stored = client.get(
            f"/api/v1/parent/calibrations/{derive_calibration_id(key)}"
        )
        stored_body = _assert_success(stored)
        assert stored_body["stage"] == "model_unavailable"
        assert stored_body["data"]["input_saved"] is True
        assert stored_body["data"]["resume_stage"] == "profile_propose"
        _assert_synthetic(client)


def test_retry_lineage_mismatch_projects_safe_409_without_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "retry-lineage-http.db"
    request = httpx.Request("POST", f"{BASE_URL}/chat/completions")
    transport = _QueuedTransport([httpx.ReadError("initial failure", request=request)])
    app = _app(tmp_path, database_path, transport)
    key = "retry-lineage-create-key-0001"

    with TestClient(app) as client:
        failed = _assert_error(
            _post_create(client, key=key),
            503,
            "model_unavailable",
        )
        recovery = failed["recovery"]
        assert recovery is not None
        repository = client.app.state.runtime.family_repository
        original_begin = repository.begin_calibration_retry

        def malformed_begin(*args: object, **kwargs: object):
            delivered = original_begin(*args, **kwargs)
            return delivered.model_copy(
                update={
                    "outcome": delivered.outcome.model_copy(
                        update={"calibration_id": "different-calibration"}
                    )
                }
            )

        monkeypatch.setattr(repository, "begin_calibration_retry", malformed_begin)
        calls_before = len(transport.payloads)
        response = client.post(
            f"/api/v1/parent/calibrations/{recovery['calibration_id']}/retry",
            headers={"Idempotency-Key": "retry-lineage-command-key"},
            json={"expected_calibration_version": 2},
        )
        _assert_error(response, 409, "retry_lineage_conflict")
        assert len(transport.payloads) == calls_before
        _assert_synthetic(client)


@pytest.mark.parametrize(
    "field",
    (
        "actor",
        "role",
        "session_id",
        "trace_id",
        "source_path",
        "profile_version",
        "expected_version",
    ),
)
def test_create_rejects_caller_controlled_identity_and_version_fields(
    tmp_path: Path,
    field: str,
) -> None:
    transport = _QueuedTransport([])
    app = _app(tmp_path, tmp_path / f"extra-{field}.db", transport)
    marker = f"private-{field}-marker"

    with TestClient(app) as client:
        response = _post_create(
            client,
            key=f"extra-field-{field}-key-0001",
            body={**_create_body(), field: marker},
        )
        _assert_error(response, 422, "schema_invalid", secrets=(marker,))
        assert transport.payloads == []
        _assert_synthetic(client)


@pytest.mark.parametrize(
    ("header_value", "send_header"),
    (
        ("", False),
        ("too-short", True),
        ("contains whitespace key", True),
    ),
    ids=("missing", "short", "whitespace"),
)
def test_create_requires_valid_ascii_idempotency_key(
    tmp_path: Path,
    header_value: str,
    send_header: bool,
) -> None:
    transport = _QueuedTransport([])
    app = _app(tmp_path, tmp_path / f"invalid-key-{send_header}.db", transport)
    headers = {"Idempotency-Key": header_value} if send_header else {}

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/parent/calibrations",
            headers=headers,
            json=_create_body(),
        )
        _assert_error(
            response,
            422,
            "schema_invalid",
            secrets=(header_value,) if header_value else (),
        )
        assert transport.payloads == []
        _assert_synthetic(client)


def test_create_rejects_non_ascii_idempotency_key_at_server_boundary(
    tmp_path: Path,
) -> None:
    transport = _QueuedTransport([])
    app = _app(tmp_path, tmp_path / "invalid-key-non-ascii.db", transport)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/parent/calibrations",
            headers=[(b"Idempotency-Key", b"\xff" * 16)],
            json=_create_body(),
        )
        _assert_error(response, 422, "schema_invalid")
        assert transport.payloads == []
        _assert_synthetic(client)


@pytest.mark.parametrize("suffix", ("commit", "revise"))
def test_tuple_body_routes_reject_non_json_media_as_schema_invalid(
    tmp_path: Path,
    suffix: str,
) -> None:
    transport = _QueuedTransport([])
    app = _app(tmp_path, tmp_path / f"non-json-{suffix}.db", transport)
    private_body = b"private non-json calibration body"

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/parent/calibrations/non-json-calibration/{suffix}",
            headers={
                "Content-Type": "application/octet-stream",
                "Idempotency-Key": f"non-json-{suffix}-key-0001",
            },
            content=private_body,
        )
        _assert_error(
            response,
            422,
            "schema_invalid",
            secrets=(private_body.decode(), "TypeError"),
        )
        assert transport.payloads == []
        _assert_synthetic(client)


@pytest.mark.parametrize(
    ("method", "path", "expected_status", "expected_code"),
    (
        ("GET", "/api/v1/parent/private-unknown", 404, "not_found"),
        ("PUT", "/api/v1/parent/calibrations", 405, "method_not_allowed"),
        ("POST", "/api/v1/parent/calibration-id/retry", 404, "not_found"),
        ("POST", "/api/v1/parent/calibration-id/commit", 404, "not_found"),
        ("POST", "/api/v1/parent/calibration-id/revise", 404, "not_found"),
        ("POST", "/api/v1/parent/calibration-id/abandon", 404, "not_found"),
    ),
)
def test_unknown_methods_and_forbidden_short_aliases_remain_strict(
    tmp_path: Path,
    method: str,
    path: str,
    expected_status: int,
    expected_code: str,
) -> None:
    transport = _QueuedTransport([])
    app = _app(tmp_path, tmp_path / f"route-{method}-{expected_code}.db", transport)

    with TestClient(app) as client:
        response = client.request(
            method,
            path,
            headers={"Idempotency-Key": "forbidden-route-key-0001"},
            json={"expected_calibration_version": 1},
        )
        _assert_error(response, expected_status, expected_code)
        assert transport.payloads == []
        _assert_synthetic(client)


def test_parent_route_sanitizes_unexpected_service_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = _QueuedTransport([])
    app = _app(tmp_path, tmp_path / "parent-internal-error.db", transport)
    private_marker = "private parent service exception detail"

    def fail_get(
        self: ParentCalibrationService,
        calibration_id: str,
        *,
        trace_id: str,
    ) -> CalibrationResponseEnvelope:
        raise RuntimeError(private_marker)

    monkeypatch.setattr(ParentCalibrationService, "get_calibration", fail_get)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/parent/calibrations/internal-error-calibration"
        )
        _assert_error(
            response,
            500,
            "internal_error",
            secrets=(private_marker, "RuntimeError"),
        )
        assert transport.payloads == []
        _assert_synthetic(client)


def test_revise_replay_invalid_revision_and_restart_get_are_deterministic(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "revise-restart.db"
    transport = _QueuedTransport([_tool_call_response(), _text_response()])
    app = _app(tmp_path, database_path, transport)
    revise_key = "revise-deterministic-key-0001"

    with TestClient(app) as client:
        proposal = _prepare_http_proposal(client, key="revise-setup-key-0001")
        revised_observation = {
            key: value
            for key, value in proposal["data"]["diff_preview"][0].items()
            if key != "operation_id"
        }
        revised_observation["value_number"] = 1.75
        request_body = {
            "expected_calibration_version": proposal["calibration_version"],
            "draft_id": proposal["data"]["draft"]["id"],
            "revised_observations": [revised_observation],
        }
        revised = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/revise",
            headers={"Idempotency-Key": revise_key},
            json=request_body,
        )
        revised_body = _assert_success(revised)
        assert revised_body["calibration_version"] == 3
        assert revised_body["profile_version"] == 0
        assert revised_body["data"]["draft"]["revises_draft_id"] == request_body[
            "draft_id"
        ]
        assert revised_body["data"]["narration_status"] == "not_requested"
        calls_after_revise = len(transport.payloads)

        replay = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/revise",
            headers={"Idempotency-Key": revise_key},
            json=request_body,
        )
        replay_body = _assert_success(replay)
        assert replay_body["delivery"] == {"replayed": True}
        assert len(transport.payloads) == calls_after_revise

        old_draft = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/revise",
            headers={"Idempotency-Key": "revise-old-draft-key-0001"},
            json={**request_body, "expected_calibration_version": 3},
        )
        _assert_error(old_draft, 409, "invalid_transition")

        current_draft = revised_body["data"]["draft"]
        invalid_observation = {
            "action": "revoke",
            "category": "subject_performance",
            "subject": "english",
            "task_type": None,
            "metric": "assessment_level",
            "value_text": None,
            "value_number": None,
            "unit": None,
            "confidence": 0.8,
            "sample_count": None,
            "observed_at": OBSERVED_AT,
            "target_event_id": "missing-event",
        }
        invalid = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/revise",
            headers={"Idempotency-Key": "revise-invalid-key-0001"},
            json={
                "expected_calibration_version": 3,
                "draft_id": current_draft["id"],
                "revised_observations": [invalid_observation],
            },
        )
        _assert_error(invalid, 409, "profile_proposal_invalid")
        assert len(transport.payloads) == calls_after_revise
        assert _count_rows(database_path, "calibration_drafts") == 2
        _assert_synthetic(client)

    restarted = _app(tmp_path, database_path, _QueuedTransport([]))
    with TestClient(restarted) as client:
        stored = client.get(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}"
        )
        stored_body = _assert_success(stored)
        assert stored_body["stage"] == "needs_confirmation"
        assert stored_body["calibration_version"] == 3
        assert stored_body["profile_version"] == 0
        assert stored_body["data"] == revised_body["data"]
        assert stored_body["delivery"] == {"replayed": True}
        _assert_synthetic(client)


def test_abandon_and_restart_get_advance_only_calibration_version(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "abandon-restart.db"
    transport = _QueuedTransport([_tool_call_response(), _text_response()])
    app = _app(tmp_path, database_path, transport)

    with TestClient(app) as client:
        proposal = _prepare_http_proposal(client, key="abandon-setup-key-0001")
        calls_before = len(transport.payloads)
        abandoned = client.post(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}/abandon",
            headers={"Idempotency-Key": "abandon-command-key-0001"},
            json={"expected_calibration_version": proposal["calibration_version"]},
        )
        abandoned_body = _assert_success(abandoned)
        assert abandoned_body["stage"] == "abandoned"
        assert abandoned_body["calibration_version"] == 3
        assert abandoned_body["profile_version"] == 0
        assert abandoned_body["data"]["pending_kind"] is None
        assert abandoned_body["data"]["pending_entity_id"] is None
        assert len(transport.payloads) == calls_before
        _assert_synthetic(client)

    restarted = _app(tmp_path, database_path, _QueuedTransport([]))
    with TestClient(restarted) as client:
        stored = client.get(
            f"/api/v1/parent/calibrations/{proposal['calibration_id']}"
        )
        stored_body = _assert_success(stored)
        assert stored_body["stage"] == "abandoned"
        assert stored_body["data"] == abandoned_body["data"]
        assert stored_body["delivery"] == {"replayed": True}
        _assert_synthetic(client)


class _ConcurrentProposalTransport:
    def __init__(self) -> None:
        self.barrier = Barrier(2)
        self._lock = Lock()
        self._required_count = 0
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        with self._lock:
            self.payloads.append(payload)
            if payload["tool_choice"] == "required":
                self._required_count += 1
                ordinal = self._required_count
            else:
                ordinal = 0
        if payload["tool_choice"] == "required":
            self.barrier.wait(timeout=10)
            response = _tool_call_response(call_id=f"concurrent-call-{ordinal}")
        else:
            response = _text_response("Concurrent proposal stored.")
        return httpx.Response(200, json=response)


def test_concurrent_same_key_http_proposals_leave_one_complete_winner(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "concurrent-proposal.db"
    key = "concurrent-proposal-key-0001"
    transport = _ConcurrentProposalTransport()
    app = _app(tmp_path, database_path, transport)

    with TestClient(app) as client:
        def submit(_: int) -> httpx.Response:
            return _post_create(client, key=key)

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(submit, range(2)))
        bodies = [_assert_success(response) for response in responses]
        assert {body["stage"] for body in bodies} == {"needs_confirmation"}
        assert sorted(body["delivery"]["replayed"] for body in bodies) == [False, True]
        assert len({body["trace_id"] for body in bodies}) == 2
        assert all(
            response.headers.get_list("x-trace-id") == [body["trace_id"]]
            for response, body in zip(responses, bodies, strict=True)
        )
        _assert_synthetic(client)

    repository = FamilyContextRepository(database_path)
    recovery = repository.get_calibration_recovery(derive_calibration_id(key))
    assert recovery.pending_draft is not None
    assert recovery.pending_draft_result is not None
    assert recovery.last_outcome == recovery.pending_draft_result
    assert _count_rows(database_path, "calibration_turn_receipts") == 1
    assert _count_rows(database_path, "calibration_drafts") == 1
    assert (
        _count_rows(
            database_path,
            "calibration_checkpoints",
            where="WHERE state = 'needs_confirmation'",
        )
        == 1
    )
    assert _count_rows(database_path, "profile_observation_events") == 0
