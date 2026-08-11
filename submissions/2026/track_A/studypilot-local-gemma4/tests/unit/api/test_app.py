from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated
from unittest.mock import Mock

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi import Request
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.app import create_app
from backend.api.run import run_api
from backend.api.runtime import IdempotencyKeyHeader, get_runtime, get_trace_id
from backend.config import Settings, load_settings
from backend.contracts.api import ErrorEnvelope
from backend.contracts.family import (
    CalibrationCheckpoint,
    CalibrationRecoverySnapshot,
    CalibrationState,
    CalibrationTurnReceipt,
    PendingKind,
    RecoveryDirective,
)
from backend.contracts.models import StrictModel
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
from backend.services.parent_calibration import (
    ParentWorkflowError,
    ParentWorkflowFailureKind,
)
from backend.storage.database import connect_database


MODEL = "gemma-4-26b-a4b-it"
BASE_URL = "http://127.0.0.1:1234/v1"
VALID_IDEMPOTENCY_KEY = "parent-request:key-0001"


class _ProbeBody(StrictModel):
    label: str


def _settings(tmp_path: Path) -> Settings:
    return load_settings(project_root=tmp_path, environ={})


def _synthetic_client() -> LMStudioClient:
    return LMStudioClient(
        BASE_URL,
        MODEL,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(500, json={"error": "unused synthetic transport"})
        ),
    )


def _migration_versions(database_path: Path) -> list[int]:
    with connect_database(database_path) as connection:
        rows = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    return [int(row[0]) for row in rows]


def test_create_app_builds_injected_runtime_and_runs_migrations(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database_path = tmp_path / "api.db"
    synthetic_client = _synthetic_client()
    app = create_app(
        settings,
        database_path=database_path,
        lm_client=synthetic_client,
    )

    with TestClient(app) as client:
        runtime = client.app.state.runtime
        assert runtime.settings is settings
        assert runtime.database_path == database_path.resolve()
        assert runtime.lm_client is synthetic_client
        assert runtime.lm_client.evidence_provenance == "synthetic_transport"
        assert runtime.family_repository.database_path == database_path.resolve()
        assert runtime.trace_repository.database_path == database_path.resolve()
        assert runtime.parent_service.client is synthetic_client

    assert _migration_versions(database_path) == [1, 2, 3, 4, 5, 6, 7, 8]


def test_create_app_lifespan_migrations_are_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "api-restart.db"
    app = create_app(
        _settings(tmp_path),
        database_path=database_path,
        lm_client=_synthetic_client(),
    )

    with TestClient(app):
        pass
    first_versions = _migration_versions(database_path)
    with TestClient(app):
        pass

    assert first_versions == [1, 2, 3, 4, 5, 6, 7, 8]
    assert _migration_versions(database_path) == first_versions


def test_create_app_uses_production_client_factory_when_client_is_omitted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    synthetic_client = _synthetic_client()
    factory = Mock(return_value=synthetic_client)
    monkeypatch.setattr(LMStudioClient, "from_settings", factory)

    app = create_app(settings, database_path=tmp_path / "production-api.db")
    with TestClient(app) as client:
        assert client.app.state.runtime.lm_client is synthetic_client

    factory.assert_called_once_with(settings)


def test_create_app_never_calls_production_factory_for_injected_client(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    synthetic_client = _synthetic_client()
    factory = Mock(side_effect=AssertionError("production factory must not be called"))
    monkeypatch.setattr(LMStudioClient, "from_settings", factory)

    app = create_app(
        settings,
        database_path=tmp_path / "injected-api.db",
        lm_client=synthetic_client,
    )
    with TestClient(app) as client:
        assert client.app.state.runtime.lm_client is synthetic_client

    factory.assert_not_called()


def test_idempotency_header_dependency_accepts_only_the_public_contract() -> None:
    app = FastAPI()

    @app.post("/probe")
    def probe(idempotency_key: IdempotencyKeyHeader) -> dict[str, str]:
        return {"idempotency_key": idempotency_key}

    with TestClient(app) as client:
        valid = client.post(
            "/probe",
            headers={"Idempotency-Key": "parent-request:key-0001"},
        )
        missing = client.post("/probe")
        too_short = client.post(
            "/probe",
            headers={"Idempotency-Key": "short"},
        )
        illegal = client.post(
            "/probe",
            headers={"Idempotency-Key": "parent request key 0001"},
        )

    assert valid.status_code == 200
    assert valid.json() == {"idempotency_key": "parent-request:key-0001"}
    assert missing.status_code == 422
    assert too_short.status_code == 422
    assert illegal.status_code == 422


def _app_with_probes(tmp_path: Path) -> FastAPI:
    app = create_app(
        _settings(tmp_path),
        database_path=tmp_path / "probe-api.db",
        lm_client=_synthetic_client(),
    )

    @app.post("/validation-probe")
    def validation_probe(
        payload: _ProbeBody,
        day: date,
        idempotency_key: IdempotencyKeyHeader,
    ) -> dict[str, str]:
        return {
            "label": payload.label,
            "day": day.isoformat(),
            "idempotency_key": idempotency_key,
        }

    @app.get("/method-probe")
    def method_probe() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/unknown-error")
    def unknown_error() -> None:
        raise RuntimeError("secret Python exception text")

    @app.get("/unsupported-starlette-error")
    def unsupported_starlette_error() -> None:
        raise StarletteHTTPException(
            status_code=418,
            detail="secret Starlette detail",
        )

    return app


def _assert_error_envelope(
    response: httpx.Response,
    *,
    status_code: int,
    code: str,
) -> dict[str, object]:
    assert response.status_code == status_code
    body = response.json()
    envelope = ErrorEnvelope.model_validate_json(response.content)
    assert envelope.model_dump(mode="json") == body
    assert body["error"]["code"] == code
    trace_id = body["trace_id"]
    assert isinstance(trace_id, str)
    assert trace_id
    assert response.headers.get_list("x-trace-id") == [trace_id]
    return body


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Idempotency-Key": "short"},
        {"Idempotency-Key": "parent request key 0001"},
    ],
)
def test_validation_error_sanitizes_missing_or_illegal_idempotency_key(
    tmp_path: Path,
    headers: dict[str, str],
) -> None:
    app = _app_with_probes(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/validation-probe",
            params={"day": "2026-07-12"},
            headers=headers,
            json={"label": "safe"},
        )

    body = _assert_error_envelope(response, status_code=422, code="schema_invalid")
    assert body["error"]["message"] == "Request schema is invalid."
    assert all(set(issue) == {"location", "type"} for issue in body["error"]["issues"])


def test_validation_error_sanitizes_body_extras_and_input(tmp_path: Path) -> None:
    app = _app_with_probes(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/validation-probe",
            params={"day": "2026-07-12"},
            headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
            json={"label": "safe", "private_note": "secret parent text"},
        )

    body = _assert_error_envelope(response, status_code=422, code="schema_invalid")
    serialized = json.dumps(body, ensure_ascii=False)
    assert all(set(issue) == {"location", "type"} for issue in body["error"]["issues"])
    assert "input" not in serialized
    assert "ctx" not in serialized
    assert "secret parent text" not in serialized


def test_validation_error_sanitizes_malformed_query_date(tmp_path: Path) -> None:
    app = _app_with_probes(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/validation-probe",
            params={"day": "secret-not-a-date"},
            headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
            json={"label": "safe"},
        )

    body = _assert_error_envelope(response, status_code=422, code="schema_invalid")
    serialized = json.dumps(body, ensure_ascii=False)
    assert all(set(issue) == {"location", "type"} for issue in body["error"]["issues"])
    assert "secret-not-a-date" not in serialized
    assert "input" not in serialized
    assert "ctx" not in serialized


@pytest.mark.parametrize(
    ("path", "method", "status_code", "code", "message"),
    [
        (
            "/private-missing-route?note=secret-parent-content",
            "GET",
            404,
            "not_found",
            "The requested resource was not found.",
        ),
        (
            "/method-probe",
            "POST",
            405,
            "method_not_allowed",
            "The requested method is not allowed.",
        ),
    ],
)
def test_starlette_error_uses_strict_safe_envelope(
    tmp_path: Path,
    path: str,
    method: str,
    status_code: int,
    code: str,
    message: str,
) -> None:
    app = _app_with_probes(tmp_path)
    with TestClient(app) as client:
        response = client.request(
            method,
            path,
            json={"private": "secret parent text"},
        )

    body = _assert_error_envelope(response, status_code=status_code, code=code)
    assert body["error"]["message"] == message
    serialized = json.dumps(body, ensure_ascii=False)
    assert "detail" not in serialized
    assert "secret" not in serialized
    assert "Not Found" not in serialized
    assert "Method Not Allowed" not in serialized


def test_starlette_error_with_other_status_fails_closed(tmp_path: Path) -> None:
    app = _app_with_probes(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/unsupported-starlette-error")

    body = _assert_error_envelope(response, status_code=500, code="internal_error")
    assert body["error"]["message"] == "An internal error occurred."
    serialized = json.dumps(body, ensure_ascii=False)
    assert "secret Starlette detail" not in serialized
    assert "detail" not in serialized


def test_unknown_error_is_static_sanitized_and_has_one_matching_trace_header(
    tmp_path: Path,
) -> None:
    app = _app_with_probes(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/unknown-error")

    body = _assert_error_envelope(response, status_code=500, code="internal_error")
    assert body["error"]["message"] == "An internal error occurred."
    serialized = json.dumps(body, ensure_ascii=False)
    assert "secret Python exception text" not in serialized
    assert "RuntimeError" not in serialized


def test_trace_header_is_owned_by_direct_unknown_exception_handler(tmp_path: Path) -> None:
    app = _app_with_probes(tmp_path)
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/direct-handler",
            "raw_path": b"/direct-handler",
            "query_string": b"",
            "headers": [],
            "client": ("test-client", 123),
            "server": ("test-server", 80),
            "root_path": "",
            "app": app,
        }
    )
    handler = app.exception_handlers[Exception]

    response = asyncio.run(handler(request, RuntimeError("secret direct exception")))
    body = json.loads(response.body)

    assert response.status_code == 500
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "An internal error occurred."
    assert body["trace_id"].startswith("trace-")
    assert response.headers.getlist("x-trace-id") == [body["trace_id"]]
    assert "secret direct exception" not in json.dumps(body)


DIRECT_ERROR_CASES = [
    pytest.param(
        NotFoundError("secret entity", "secret-id"),
        404,
        "not_found",
        id="not-found",
    ),
    pytest.param(
        VersionConflictError("secret entity", "secret-id", 1, 2),
        409,
        "version_conflict",
        id="version-conflict",
    ),
    pytest.param(
        IdempotencyConflictError("secret operation", "secret-key"),
        409,
        "idempotency_conflict",
        id="idempotency-conflict",
    ),
    pytest.param(
        InvalidTransitionError("secret-current", "secret-requested"),
        409,
        "invalid_transition",
        id="invalid-transition",
    ),
    pytest.param(
        DraftDigestMismatchError("secret-draft"),
        409,
        "draft_digest_mismatch",
        id="draft-digest-mismatch",
    ),
    pytest.param(
        CommitCommandInvalidError("secret-reason"),
        409,
        "commit_command_invalid",
        id="commit-command-invalid",
    ),
    pytest.param(
        ProfileProposalInvalidError("secret-reason"),
        409,
        "profile_proposal_invalid",
        id="profile-proposal-invalid",
    ),
]


@pytest.mark.parametrize(("error", "status_code", "code"), DIRECT_ERROR_CASES)
def test_typed_error_mapping_is_fixed_and_sanitized(
    tmp_path: Path,
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    app = create_app(
        _settings(tmp_path),
        database_path=tmp_path / f"typed-{code}.db",
        lm_client=_synthetic_client(),
    )

    def raise_typed_error() -> None:
        raise error

    app.add_api_route("/typed-error", raise_typed_error, methods=["GET"])
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/typed-error")

    body = _assert_error_envelope(response, status_code=status_code, code=code)
    assert "secret" not in json.dumps(body, ensure_ascii=False)


PARENT_ERROR_CASES = [
    pytest.param(kind, expected_status, kind.value, id=kind.value)
    for kind, expected_status in [
        (ParentWorkflowFailureKind.NOT_FOUND, 404),
        (ParentWorkflowFailureKind.VERSION_CONFLICT, 409),
        (ParentWorkflowFailureKind.IDEMPOTENCY_CONFLICT, 409),
        (ParentWorkflowFailureKind.INVALID_TRANSITION, 409),
        (ParentWorkflowFailureKind.DRAFT_DIGEST_MISMATCH, 409),
        (ParentWorkflowFailureKind.COMMIT_COMMAND_INVALID, 409),
        (ParentWorkflowFailureKind.RETRY_LINEAGE_CONFLICT, 409),
        (ParentWorkflowFailureKind.MODEL_PROTOCOL_ERROR, 502),
        (ParentWorkflowFailureKind.MODEL_UNAVAILABLE, 503),
        (ParentWorkflowFailureKind.INTERNAL_ERROR, 500),
    ]
]


@pytest.mark.parametrize(("kind", "status_code", "code"), PARENT_ERROR_CASES)
def test_parent_workflow_error_mapping_is_fixed_and_sanitized(
    tmp_path: Path,
    kind: ParentWorkflowFailureKind,
    status_code: int,
    code: str,
) -> None:
    error = ParentWorkflowError(
        kind,
        cause_code="secret-cause-code",
        trace_id="secret-stored-trace",
    )
    app = create_app(
        _settings(tmp_path),
        database_path=tmp_path / f"workflow-{code}.db",
        lm_client=_synthetic_client(),
    )

    def raise_workflow_error() -> None:
        raise error

    app.add_api_route("/workflow-error", raise_workflow_error, methods=["GET"])
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/workflow-error")

    body = _assert_error_envelope(response, status_code=status_code, code=code)
    assert "secret" not in json.dumps(body, ensure_ascii=False)


def _model_unavailable_recovery() -> CalibrationRecoverySnapshot:
    now = datetime(2026, 7, 12, 8, 0, tzinfo=UTC)
    receipt = CalibrationTurnReceipt(
        id="receipt-safe-1",
        calibration_id="calibration-safe-1",
        actor="local-parent",
        role="parent",
        content_sha256="0" * 64,
        raw_text="secret parent recovery text",
        created_at=now,
    )
    checkpoint = CalibrationCheckpoint(
        calibration_id="calibration-safe-1",
        calibration_version=2,
        profile_version=3,
        state=CalibrationState.MODEL_UNAVAILABLE,
        resume_stage="profile_propose",
        pending_kind=PendingKind.MODEL_RETRY,
        pending_entity_id="pending-safe-1",
        last_stable_calibration_version=1,
        last_stable_profile_version=3,
        input_receipt_id=receipt.id,
        trace_id="secret-checkpoint-trace",
        occurred_at=now,
    )
    return CalibrationRecoverySnapshot(
        calibration_id="calibration-safe-1",
        calibration_version=2,
        profile_version=3,
        receipt=receipt,
        latest_checkpoint=checkpoint,
        directive=RecoveryDirective.EXPLICIT_RETRY_ALLOWED,
    )


def test_model_unavailable_error_projects_only_recovery_allowlist(tmp_path: Path) -> None:
    error = ParentWorkflowError(
        ParentWorkflowFailureKind.MODEL_UNAVAILABLE,
        cause_code="secret-python-cause",
        trace_id="secret-workflow-trace",
        recovery=_model_unavailable_recovery(),
    )
    app = create_app(
        _settings(tmp_path),
        database_path=tmp_path / "model-unavailable.db",
        lm_client=_synthetic_client(),
    )

    def raise_model_unavailable() -> None:
        raise error

    app.add_api_route("/model-unavailable", raise_model_unavailable, methods=["GET"])
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/model-unavailable")

    body = _assert_error_envelope(response, status_code=503, code="model_unavailable")
    assert body["recovery"] == {
        "calibration_id": "calibration-safe-1",
        "calibration_version": 2,
        "profile_version": 3,
        "stage": "model_unavailable",
        "allowed_actions": [
            "retry_last_turn",
            "use_simplified_calibration",
            "abandon_profile_patch",
        ],
        "resume_stage": "profile_propose",
        "pending_kind": "model_retry",
        "pending_entity_id": "pending-safe-1",
        "input_receipt_id": "receipt-safe-1",
        "input_saved": True,
        "failure_code": None,
    }
    serialized = json.dumps(body, ensure_ascii=False)
    assert "secret parent recovery text" not in serialized
    assert "secret-checkpoint-trace" not in serialized
    assert "secret-python-cause" not in serialized


def test_model_unavailable_commit_recovery_projects_original_input_receipt(
    tmp_path: Path,
) -> None:
    recovery = _model_unavailable_recovery()
    recovery = recovery.model_copy(
        update={
            "latest_checkpoint": recovery.latest_checkpoint.model_copy(
                update={
                    "resume_stage": "profile_commit",
                    "pending_entity_id": "commit-input-safe-1",
                    "input_receipt_id": "commit-input-safe-1",
                }
            )
        }
    )
    error = ParentWorkflowError(
        ParentWorkflowFailureKind.MODEL_UNAVAILABLE,
        cause_code="secret-commit-cause",
        trace_id="secret-commit-trace",
        recovery=recovery,
    )
    app = create_app(
        _settings(tmp_path),
        database_path=tmp_path / "model-unavailable-commit.db",
        lm_client=_synthetic_client(),
    )

    def raise_model_unavailable() -> None:
        raise error

    app.add_api_route("/model-unavailable-commit", raise_model_unavailable, methods=["GET"])
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/model-unavailable-commit")

    body = _assert_error_envelope(response, status_code=503, code="model_unavailable")
    assert body["recovery"]["resume_stage"] == "profile_commit"
    assert body["recovery"]["pending_entity_id"] == "commit-input-safe-1"
    assert body["recovery"]["input_receipt_id"] == "receipt-safe-1"


ALLOWED_ORIGINS = [
    "http://127.0.0.1:8041",
    "http://localhost:8041",
    "http://127.0.0.1:8042",
    "http://localhost:8042",
]


def _app_with_trace_probe(tmp_path: Path) -> FastAPI:
    app = _app_with_probes(tmp_path)

    @app.get("/trace-probe")
    def trace_probe(
        trace_id: Annotated[str, Depends(get_trace_id)],
        runtime=Depends(get_runtime),
    ) -> dict[str, str]:
        return {
            "trace_id": trace_id,
            "database_path": str(runtime.database_path),
        }

    return app


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_cors_allows_only_each_configured_local_origin(
    tmp_path: Path,
    origin: str,
) -> None:
    app = _app_with_trace_probe(tmp_path)
    with TestClient(app) as client:
        response = client.options(
            "/validation-probe",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,idempotency-key",
            },
        )

    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers.get("access-control-allow-credentials") in {None, "false"}
    assert response.headers.get_list("x-trace-id")
    assert all(
        "*" not in value
        for name, value in response.headers.items()
        if name.lower().startswith("access-control-")
    )


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:8043",
        "https://localhost:8041",
    ],
)
def test_cors_rejects_unlisted_or_non_http_origins(
    tmp_path: Path,
    origin: str,
) -> None:
    app = _app_with_trace_probe(tmp_path)
    with TestClient(app) as client:
        response = client.options(
            "/validation-probe",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,idempotency-key",
            },
        )

    assert "access-control-allow-origin" not in response.headers
    assert response.headers.get("access-control-allow-credentials") in {None, "false"}
    assert response.headers.get_list("x-trace-id")
    assert all(
        "*" not in value
        for name, value in response.headers.items()
        if name.lower().startswith("access-control-")
    )


def test_cors_request_without_origin_reaches_route(tmp_path: Path) -> None:
    app = _app_with_trace_probe(tmp_path)
    with TestClient(app) as client:
        response = client.get("/trace-probe")

    assert response.status_code == 200
    assert response.json()["trace_id"] == response.headers["x-trace-id"]


def test_cors_allowed_origin_can_read_sanitized_unknown_error(tmp_path: Path) -> None:
    app = _app_with_trace_probe(tmp_path)
    origin = "http://127.0.0.1:8041"
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/unknown-error",
            headers={"Origin": origin},
        )

    _assert_error_envelope(response, status_code=500, code="internal_error")
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers.get("access-control-allow-credentials") in {None, "false"}
    assert all(
        "*" not in value
        for name, value in response.headers.items()
        if name.lower().startswith("access-control-")
    )


def test_trace_middleware_generates_unique_trace_and_ignores_caller_header(
    tmp_path: Path,
) -> None:
    app = _app_with_trace_probe(tmp_path)
    with TestClient(app) as client:
        first = client.get(
            "/trace-probe",
            headers={"X-Trace-Id": "caller-controlled-trace"},
        )
        second = client.get("/trace-probe")

    assert first.status_code == 200
    assert second.status_code == 200
    first_trace = first.json()["trace_id"]
    second_trace = second.json()["trace_id"]
    assert first_trace.startswith("trace-")
    assert second_trace.startswith("trace-")
    assert first_trace != "caller-controlled-trace"
    assert first_trace != second_trace
    assert first.headers.get_list("x-trace-id") == [first_trace]
    assert second.headers.get_list("x-trace-id") == [second_trace]


def test_trace_middleware_preserves_one_matching_handler_trace_header(
    tmp_path: Path,
) -> None:
    app = _app_with_trace_probe(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/unknown-error",
            headers={"X-Trace-Id": "caller-controlled-trace"},
        )

    body = _assert_error_envelope(response, status_code=500, code="internal_error")
    assert body["trace_id"] != "caller-controlled-trace"


def test_loopback_runner_uses_fixed_host_and_configured_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    captured: dict[str, object] = {}

    def capture_run(
        app: FastAPI,
        *,
        host: str,
        port: int,
        reload: bool,
    ) -> None:
        captured.update(
            app=app,
            host=host,
            port=port,
            reload=reload,
        )

    monkeypatch.setattr("backend.api.run.uvicorn.run", capture_run)

    run_api(settings)

    assert isinstance(captured["app"], FastAPI)
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == settings.backend_port
    assert captured["reload"] is False
