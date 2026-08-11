from __future__ import annotations

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
BRIEF_DATE = "2026-07-11"


class RejectingModelTransport:
    def __init__(self) -> None:
        self.call_count = 0

    def __call__(self, _request: httpx.Request) -> httpx.Response:
        self.call_count += 1
        raise AssertionError("school brief routes must not call the language model")


def _settings(project_root: Path) -> Settings:
    return load_settings(project_root=project_root, environ={})


def _school_app(
    project_root: Path,
    database_path: Path,
) -> tuple[FastAPI, RejectingModelTransport]:
    transport = RejectingModelTransport()
    lm_client = LMStudioClient(
        BASE_URL,
        MODEL,
        transport=httpx.MockTransport(transport),
    )
    app = create_app(
        _settings(project_root),
        database_path=database_path,
        lm_client=lm_client,
    )
    return app, transport


def _assert_request_trace(response: httpx.Response) -> dict[str, Any]:
    body = response.json()
    assert response.headers.get_list("x-trace-id") == [body["trace_id"]]
    return body


def _assert_no_model_calls(
    client: TestClient,
    transport: RejectingModelTransport,
) -> None:
    assert transport.call_count == 0
    assert client.app.state.runtime.lm_client.evidence_provenance == "synthetic_transport"


def _write(
    client: TestClient,
    *,
    key: str,
    raw_text: str,
    expected_revision: int,
) -> httpx.Response:
    return client.post(
        "/api/v1/school-briefs",
        headers={"Idempotency-Key": key},
        json={
            "brief_date": BRIEF_DATE,
            "raw_text": raw_text,
            "expected_revision": expected_revision,
        },
    )


def _assert_error(
    response: httpx.Response,
    *,
    status_code: int,
    code: str,
) -> dict[str, Any]:
    assert response.status_code == status_code
    body = _assert_request_trace(response)
    assert body["error"]["code"] == code
    return body


def test_empty_manual_text_creates_revision_one_through_real_app(tmp_path: Path) -> None:
    app, transport = _school_app(tmp_path, tmp_path / "school-api.db")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/school-briefs",
            headers={"Idempotency-Key": "school-write-key-0001"},
            json={
                "brief_date": BRIEF_DATE,
                "raw_text": "",
                "expected_revision": 0,
            },
        )
        _assert_no_model_calls(client, transport)

    assert response.status_code == 200
    body = _assert_request_trace(response)
    assert body["data"]["record"]["source"] == "manual-paste"
    assert body["data"]["record"]["raw_text"] == ""
    assert body["data"]["revision"] == 1
    assert body["delivery"]["replayed"] is False


def test_versioned_writes_no_op_and_replay_preserve_trace_provenance(
    tmp_path: Path,
) -> None:
    app, transport = _school_app(tmp_path, tmp_path / "school-versioned.db")

    with TestClient(app) as client:
        first = _write(
            client,
            key="school-version-key-0001",
            raw_text="Mathematics exercise set",
            expected_revision=0,
        )
        second = _write(
            client,
            key="school-version-key-0002",
            raw_text="Mathematics exercise set\nEnglish reading",
            expected_revision=1,
        )
        no_op = _write(
            client,
            key="school-version-key-0003",
            raw_text="Mathematics exercise set\nEnglish reading",
            expected_revision=2,
        )
        replay = _write(
            client,
            key="school-version-key-0001",
            raw_text="Mathematics exercise set",
            expected_revision=0,
        )
        _assert_no_model_calls(client, transport)

    for response in (first, second, no_op, replay):
        assert response.status_code == 200
    first_body = _assert_request_trace(first)
    second_body = _assert_request_trace(second)
    no_op_body = _assert_request_trace(no_op)
    replay_body = _assert_request_trace(replay)

    assert first_body["data"]["revision"] == 1
    assert first_body["data"]["no_op"] is False
    assert second_body["data"]["revision"] == 2
    assert second_body["data"]["record"]["raw_text"].endswith("English reading")
    assert no_op_body["data"]["revision"] == 2
    assert no_op_body["data"]["no_op"] is True
    assert no_op_body["data"]["record"] == second_body["data"]["record"]
    assert replay_body["delivery"]["replayed"] is True
    assert replay_body["data"] == first_body["data"]
    assert replay_body["trace_id"] != first_body["trace_id"]
    assert replay_body["data"]["trace_id"] == first_body["trace_id"]
    assert replay_body["data"]["trace_id"] != replay_body["trace_id"]


def test_same_key_changed_body_and_stale_revision_return_conflicts(tmp_path: Path) -> None:
    app, transport = _school_app(tmp_path, tmp_path / "school-conflicts.db")

    with TestClient(app) as client:
        created = _write(
            client,
            key="school-conflict-key-0001",
            raw_text="Original school text",
            expected_revision=0,
        )
        changed_replay = _write(
            client,
            key="school-conflict-key-0001",
            raw_text="Changed school text",
            expected_revision=0,
        )
        stale = _write(
            client,
            key="school-conflict-key-0002",
            raw_text="Another school text",
            expected_revision=0,
        )
        _assert_no_model_calls(client, transport)

    assert created.status_code == 200
    _assert_request_trace(created)
    idempotency_body = _assert_error(
        changed_replay,
        status_code=409,
        code="idempotency_conflict",
    )
    version_body = _assert_error(
        stale,
        status_code=409,
        code="version_conflict",
    )
    assert "school-conflict-key-0001" not in str(idempotency_body)
    assert "Original school text" not in str(idempotency_body)
    assert "Another school text" not in str(version_body)


def test_restart_restores_latest_and_exact_revision_history(tmp_path: Path) -> None:
    database_path = tmp_path / "school-restart.db"
    first_app, first_transport = _school_app(tmp_path, database_path)

    with TestClient(first_app) as client:
        first = _write(
            client,
            key="school-restart-key-0001",
            raw_text="Revision one",
            expected_revision=0,
        )
        second = _write(
            client,
            key="school-restart-key-0002",
            raw_text="Revision two",
            expected_revision=1,
        )
        _assert_no_model_calls(client, first_transport)

    assert first.status_code == 200
    first_body = _assert_request_trace(first)
    assert second.status_code == 200
    second_body = _assert_request_trace(second)

    restarted_app, restarted_transport = _school_app(tmp_path, database_path)
    with TestClient(restarted_app) as restarted:
        latest = restarted.get(
            "/api/v1/school-briefs",
            params={"brief_date": BRIEF_DATE},
        )
        history = restarted.get(
            "/api/v1/school-briefs/revisions",
            params={"brief_date": BRIEF_DATE},
        )
        _assert_no_model_calls(restarted, restarted_transport)

    assert latest.status_code == 200
    latest_body = _assert_request_trace(latest)
    assert latest_body["data"] == second_body["data"]["record"]
    assert history.status_code == 200
    history_body = _assert_request_trace(history)
    assert history_body["brief_date"] == BRIEF_DATE
    assert history_body["revisions"] == [
        first_body["data"]["record"],
        second_body["data"]["record"],
    ]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/school-briefs",
        "/api/v1/school-briefs/revisions",
    ],
)
def test_missing_latest_and_history_return_not_found(tmp_path: Path, path: str) -> None:
    app, transport = _school_app(tmp_path, tmp_path / "school-missing.db")

    with TestClient(app) as client:
        response = client.get(path, params={"brief_date": BRIEF_DATE})
        _assert_no_model_calls(client, transport)

    body = _assert_error(response, status_code=404, code="not_found")
    assert BRIEF_DATE not in str(body)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source", "manual-paste"),
        ("source_path", "private/school-message.txt"),
    ],
)
def test_write_rejects_caller_controlled_source_fields(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    app, transport = _school_app(tmp_path, tmp_path / f"school-{field}.db")
    payload = {
        "brief_date": BRIEF_DATE,
        "raw_text": "Manual school text",
        "expected_revision": 0,
        field: value,
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/school-briefs",
            headers={"Idempotency-Key": f"school-{field}-key-0001"},
            json=payload,
        )
        _assert_no_model_calls(client, transport)

    body = _assert_error(response, status_code=422, code="schema_invalid")
    assert value not in str(body)
