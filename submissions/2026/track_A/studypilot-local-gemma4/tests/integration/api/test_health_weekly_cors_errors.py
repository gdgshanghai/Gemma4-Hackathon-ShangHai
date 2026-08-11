from __future__ import annotations

import importlib
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import Settings, load_settings
from backend.orchestration.lm_studio import LMStudioClient


MODEL = "gemma-4-26b-a4b-it"
BASE_URL = "http://127.0.0.1:1234/v1"
METADATA_URL = "http://127.0.0.1:1234/api/v0/models"
WEEK_START = "2026-07-06"
NO_DATA_METRIC = {
    "value": None,
    "numerator": 0,
    "denominator": 0,
    "status": "no_data",
}
ALLOWED_ORIGINS = (
    "http://127.0.0.1:8041",
    "http://localhost:8041",
    "http://127.0.0.1:8042",
    "http://localhost:8042",
)


def _settings(project_root: Path) -> Settings:
    return load_settings(project_root=project_root, environ={})


def _app(
    project_root: Path,
    database_path: Path,
    handler: Callable[[httpx.Request], httpx.Response],
) -> FastAPI:
    return create_app(
        _settings(project_root),
        database_path=database_path,
        lm_client=LMStudioClient(
            BASE_URL,
            MODEL,
            transport=httpx.MockTransport(handler),
        ),
    )


def _loaded_metadata() -> dict[str, Any]:
    return {
        "data": [
            {
                "id": MODEL,
                "state": "loaded",
                "capabilities": ["tool_use"],
                "quantization": "Q4_K_M",
            }
        ]
    }


def _assert_request_trace(response: httpx.Response) -> dict[str, Any]:
    body = response.json()
    assert response.headers.get_list("x-trace-id") == [body["trace_id"]]
    return body


@pytest.mark.parametrize(
    ("metadata_payload", "expected_ready", "expected_status", "expected_error"),
    [
        (_loaded_metadata(), True, "ok", None),
        (
            {
                "data": [
                    {
                        "id": MODEL,
                        "state": "not-loaded",
                        "capabilities": ["tool_use"],
                    }
                ]
            },
            False,
            "degraded",
            "model_not_loaded",
        ),
        ({"data": []}, False, "degraded", "model_not_found"),
        (
            {
                "data": [
                    {
                        "id": MODEL,
                        "state": "loaded",
                        "capabilities": ["vision"],
                    }
                ]
            },
            False,
            "degraded",
            "model_tool_use_missing",
        ),
    ],
)
def test_health_uses_only_v0_metadata_and_projects_model_state(
    tmp_path: Path,
    metadata_payload: dict[str, Any],
    expected_ready: bool,
    expected_status: str,
    expected_error: str | None,
) -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json=metadata_payload)

    app = _app(tmp_path, tmp_path / "health-model.db", handler)
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert client.app.state.runtime.lm_client.evidence_provenance == ("synthetic_transport")

    assert response.status_code == 200
    body = _assert_request_trace(response)
    assert body["ready"] is expected_ready
    assert body["api"] == {"status": "ok", "error_code": None}
    assert body["sqlite"] == {"status": "ok", "error_code": None}
    assert body["model"]["status"] == expected_status
    assert body["model"]["model_id"] == MODEL
    assert body["model"]["loaded"] is expected_ready
    assert body["model"]["tool_use"] is expected_ready
    assert body["model"]["error_code"] == expected_error
    assert all("/v1/models" not in url for url in urls)
    assert all("/chat/completions" not in url for url in urls)
    assert urls == [METADATA_URL]


def test_health_sanitizes_model_transport_failure_and_stays_http_200(
    tmp_path: Path,
) -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        raise httpx.ConnectError("private transport detail", request=request)

    app = _app(tmp_path, tmp_path / "health-transport.db", handler)
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert client.app.state.runtime.lm_client.evidence_provenance == ("synthetic_transport")

    assert response.status_code == 200
    body = _assert_request_trace(response)
    assert body["ready"] is False
    assert body["model"] == {
        "status": "degraded",
        "model_id": MODEL,
        "loaded": False,
        "tool_use": False,
        "quantization": None,
        "error_code": "model_connection_refused",
    }
    assert "private transport detail" not in str(body)
    assert all("/v1/models" not in url for url in urls)
    assert all("/chat/completions" not in url for url in urls)
    assert urls == [METADATA_URL]


class _SQLiteProbeConnection:
    def __init__(self, error: sqlite3.Error | None = None) -> None:
        self.error = error
        self.closed = False

    def execute(self, sql: str) -> _SQLiteProbeConnection:
        assert sql == "SELECT 1"
        if self.error is not None:
            raise self.error
        return self

    def fetchone(self) -> tuple[int]:
        return (1,)

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("sqlite_fails", [False, True])
def test_health_closes_sqlite_connection_and_sanitizes_sqlite_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sqlite_fails: bool,
) -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json=_loaded_metadata())

    app = _app(tmp_path, tmp_path / f"health-sqlite-{sqlite_fails}.db", handler)
    with TestClient(app) as client:
        route_probe = client.get("/api/v1/health")
        assert route_probe.status_code == 200

        health_module = importlib.import_module("backend.api.routes.health")
        connection = _SQLiteProbeConnection(
            sqlite3.OperationalError("private sqlite detail") if sqlite_fails else None
        )
        monkeypatch.setattr(
            health_module,
            "connect_database",
            lambda _database_path: connection,
        )
        urls.clear()
        response = client.get("/api/v1/health")
        assert client.app.state.runtime.lm_client.evidence_provenance == ("synthetic_transport")

    assert response.status_code == 200
    body = _assert_request_trace(response)
    assert connection.closed is True
    if sqlite_fails:
        assert body["ready"] is False
        assert body["sqlite"] == {
            "status": "degraded",
            "error_code": "sqlite_unavailable",
        }
        assert "private sqlite detail" not in str(body)
    else:
        assert body["ready"] is True
        assert body["sqlite"] == {"status": "ok", "error_code": None}
    assert urls == [METADATA_URL]


def test_health_route_is_registered_once(tmp_path: Path) -> None:
    app = _app(
        tmp_path,
        tmp_path / "health-registration.db",
        lambda _: httpx.Response(200, json=_loaded_metadata()),
    )

    assert sum(route.path == "/api/v1/health" for route in app.routes) == 1


def test_weekly_router_registration_is_exactly_once(tmp_path: Path) -> None:
    app = _app(
        tmp_path,
        tmp_path / "weekly-registration.db",
        lambda _: httpx.Response(200, json=_loaded_metadata()),
    )

    assert sum(route.path == "/api/v1/parent/weekly-summary" for route in app.routes) == 1


def test_shared_parent_router_preserves_task_8_routes_exactly_once(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def reject_model(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        raise AssertionError("shared parent router guard must not call the model")

    app = _app(tmp_path, tmp_path / "shared-parent-router.db", reject_model)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/parent/weekly-summary",
            params={"week_start": WEEK_START},
        )
        assert client.app.state.runtime.lm_client.evidence_provenance == (
            "synthetic_transport"
        )

    assert response.status_code == 200
    body = _assert_request_trace(response)
    assert set(body) == {"trace_id", "data"}
    assert sum(route.path == "/api/v1/health" for route in app.routes) == 1
    assert sum(route.path == "/api/v1/parent/weekly-summary" for route in app.routes) == 1
    assert calls == []


def test_weekly_route_returns_strict_no_data_without_model_calls(
    tmp_path: Path,
) -> None:
    urls: list[str] = []

    def reject_model(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        raise AssertionError("weekly summary must not call the language model")

    app = _app(tmp_path, tmp_path / "weekly-route.db", reject_model)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/parent/weekly-summary",
            params={"week_start": WEEK_START},
        )
        assert client.app.state.runtime.lm_client.evidence_provenance == ("synthetic_transport")

    assert response.status_code == 200
    body = _assert_request_trace(response)
    assert body["data"] == {
        "week_start": "2026-07-06",
        "week_end": "2026-07-12",
        "profile_version": 0,
        "latest_calibration": None,
        "confirmed_observation_count": 0,
        "estimate_error": NO_DATA_METRIC,
        "omissions": NO_DATA_METRIC,
        "start_confidence": NO_DATA_METRIC,
        "parent_interventions": NO_DATA_METRIC,
    }
    assert urls == []


def test_weekly_route_sanitizes_malformed_week_start(
    tmp_path: Path,
) -> None:
    urls: list[str] = []

    def reject_model(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        raise AssertionError("validation must not call the language model")

    app = _app(tmp_path, tmp_path / "weekly-validation.db", reject_model)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/parent/weekly-summary",
            params={"week_start": "private-invalid-week-start"},
        )
        assert client.app.state.runtime.lm_client.evidence_provenance == ("synthetic_transport")

    assert response.status_code == 422
    body = _assert_request_trace(response)
    assert body["error"]["code"] == "schema_invalid"
    assert body["error"]["message"] == "Request schema is invalid."
    assert body["error"]["issues"]
    assert "private-invalid-week-start" not in str(body)
    assert urls == []


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_weekly_cors_allows_each_local_origin_without_credentials_or_wildcard(
    tmp_path: Path,
    origin: str,
) -> None:
    urls: list[str] = []

    def reject_model(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        raise AssertionError("weekly CORS reads must not call the language model")

    app = _app(tmp_path, tmp_path / "weekly-cors-allowed.db", reject_model)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/parent/weekly-summary",
            params={"week_start": WEEK_START},
            headers={"Origin": origin},
        )
        assert client.app.state.runtime.lm_client.evidence_provenance == ("synthetic_transport")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers.get("access-control-allow-credentials") in {None, "false"}
    assert all(
        "*" not in value
        for name, value in response.headers.items()
        if name.lower().startswith("access-control-")
    )
    assert urls == []


def test_cors_preflight_allows_browser_put_with_idempotency_key(
    tmp_path: Path,
) -> None:
    app = _app(
        tmp_path,
        tmp_path / "cors-put-preflight.db",
        lambda request: (_ for _ in ()).throw(
            AssertionError(f"CORS preflight must not call the model: {request.url}")
        ),
    )

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/evenings/example/time-boundary",
            headers={
                "Origin": "http://127.0.0.1:8041",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type,idempotency-key",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8041"
    assert "PUT" in response.headers["access-control-allow-methods"].split(", ")


@pytest.mark.parametrize(
    "origin",
    [
        "http://192.168.1.20:8042",
        "https://study.example:8042",
    ],
)
def test_weekly_cors_rejects_remote_origins(
    tmp_path: Path,
    origin: str,
) -> None:
    app = _app(
        tmp_path,
        tmp_path / "weekly-cors-rejected.db",
        lambda request: (_ for _ in ()).throw(
            AssertionError(f"unexpected model call: {request.url}")
        ),
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/parent/weekly-summary",
            params={"week_start": WEEK_START},
            headers={"Origin": origin},
        )
        assert client.app.state.runtime.lm_client.evidence_provenance == ("synthetic_transport")

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert response.headers.get("access-control-allow-credentials") in {None, "false"}


def test_weekly_get_without_origin_or_authentication_headers_succeeds(
    tmp_path: Path,
) -> None:
    app = _app(
        tmp_path,
        tmp_path / "weekly-no-origin.db",
        lambda request: (_ for _ in ()).throw(
            AssertionError(f"unexpected model call: {request.url}")
        ),
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/parent/weekly-summary",
            params={"week_start": WEEK_START},
        )
        assert client.app.state.runtime.lm_client.evidence_provenance == ("synthetic_transport")

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert response.json()["data"]["week_start"] == WEEK_START


def test_weekly_data_is_byte_equivalent_after_app_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "weekly-restart.db"
    urls: list[str] = []

    def reject_model(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        raise AssertionError("weekly restart reads must not call the language model")

    first_app = _app(tmp_path, database_path, reject_model)
    with TestClient(first_app) as client:
        first = client.get(
            "/api/v1/parent/weekly-summary",
            params={"week_start": WEEK_START},
        )
        assert client.app.state.runtime.lm_client.evidence_provenance == ("synthetic_transport")

    restarted_app = _app(tmp_path, database_path, reject_model)
    with TestClient(restarted_app) as client:
        restarted = client.get(
            "/api/v1/parent/weekly-summary",
            params={"week_start": WEEK_START},
        )
        assert client.app.state.runtime.lm_client.evidence_provenance == ("synthetic_transport")

    assert first.status_code == 200
    assert restarted.status_code == 200
    first_bytes = json.dumps(first.json()["data"], sort_keys=True, separators=(",", ":")).encode()
    restarted_bytes = json.dumps(
        restarted.json()["data"], sort_keys=True, separators=(",", ":")
    ).encode()
    assert restarted_bytes == first_bytes
    assert urls == []
