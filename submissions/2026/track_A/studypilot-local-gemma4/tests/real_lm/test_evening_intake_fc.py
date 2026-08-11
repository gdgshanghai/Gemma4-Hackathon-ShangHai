from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import load_settings
from backend.storage.database import connect_database
from backend.storage.run_traces import RunTraceRepository


pytestmark = pytest.mark.real_lm

MODEL_ID = "gemma-4-26b-a4b-it"
CHINESE_INTAKE = (
    "今晚一共有三项作业：数学练习册第12页，预计30分钟；"
    "英语背诵课文第三段，预计15分钟；语文阅读《朝花夕拾》20分钟。"
    "以上就是全部作业，目前都还没有完成。"
)
SCHOOL_BRIEF = "数学：完成练习册第12页\n英语：背诵课文第三段"
SCHOOL_CHILD_INTAKE = (
    "数学练习册第12页已经做了一半，预计还要20分钟。"
    "另外有科学观察记录，预计10分钟。没有别的作业。"
)


def _task_search_text(task: dict[str, object]) -> str:
    return "\n".join(str(task.get(field) or "") for field in ("title", "subject", "notes"))


def test_real_gemma_saves_chinese_evening_intake_draft(tmp_path: Path) -> None:
    database_path = tmp_path / "real-evening-intake.db"
    app = create_app(load_settings(), database_path=database_path)

    with TestClient(app) as client:
        runtime_client = client.app.state.runtime.lm_client
        assert runtime_client.is_production_real_lm is True
        assert runtime_client.evidence_provenance == "real_lm_native_fc"
        metadata = runtime_client.get_model_metadata()
        assert metadata.id == MODEL_ID
        assert metadata.state == "loaded"
        assert "tool_use" in metadata.capabilities

        created_response = client.post(
            "/api/v1/evenings",
            headers={"Idempotency-Key": "real-evening-create-0001"},
            json={
                "start_time": "19:30:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        assert created_response.status_code == 200, created_response.text
        session_id = created_response.json()["session_id"]

        intake_response = client.post(
            f"/api/v1/evenings/{session_id}/intake-turns",
            headers={"Idempotency-Key": "real-evening-intake-0001"},
            json={"text": CHINESE_INTAKE, "expected_version": 1},
        )
        assert intake_response.status_code == 200, intake_response.text
        intake = intake_response.json()
        assert intake["session_id"] == session_id
        assert intake["version"] == 2
        assert intake["stage"] == "intake_draft"
        assert intake["data"]["narration"].strip()
        tasks = intake["data"]["intake_draft"]["tasks"]
        assert len(tasks) == 3
        assert sorted(task["child_estimate_minutes"] for task in tasks) == [15, 20, 30]
        assert all(task["completion_state"] == "pending" for task in tasks)
        assert intake["data"]["intake_draft"]["fixed_blocks"] == []
        trace_id = intake["trace_id"]

    with connect_database(database_path) as connection:
        raw_payload = json.loads(
            connection.execute(
                """
                SELECT payload_json FROM observation_events
                WHERE session_id = ? AND event_type = 'intake_raw'
                """,
                (session_id,),
            ).fetchone()[0]
        )
        draft_count = connection.execute(
            """
            SELECT COUNT(*) FROM observation_events
            WHERE session_id = ? AND event_type = 'intake_draft'
            """,
            (session_id,),
        ).fetchone()[0]
    assert raw_payload["text"] == CHINESE_INTAKE
    assert draft_count == 1

    trace = RunTraceRepository(database_path).get_trace(trace_id)
    assert trace.trace.status == "completed"
    assert trace.trace.model_calls == 1
    assert trace.trace.handler_executions == 1
    assert [run.tool_name for run in trace.tool_runs] == ["save_intake_draft"]


def test_real_gemma_merges_school_brief_omission(tmp_path: Path) -> None:
    database_path = tmp_path / "real-school-coverage.db"
    app = create_app(load_settings(), database_path=database_path)
    session_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()

    with TestClient(app) as client:
        runtime_client = client.app.state.runtime.lm_client
        assert runtime_client.is_production_real_lm is True
        assert runtime_client.evidence_provenance == "real_lm_native_fc"
        metadata = runtime_client.get_model_metadata()
        assert metadata.id == MODEL_ID
        assert metadata.state == "loaded"
        assert "tool_use" in metadata.capabilities

        school_response = client.post(
            "/api/v1/school-briefs",
            headers={"Idempotency-Key": "real-school-coverage-write-0001"},
            json={
                "brief_date": session_date,
                "raw_text": SCHOOL_BRIEF,
                "expected_revision": 0,
            },
        )
        assert school_response.status_code == 200, school_response.text
        school_brief_id = school_response.json()["data"]["record"]["id"]

        created_response = client.post(
            "/api/v1/evenings",
            headers={"Idempotency-Key": "real-school-coverage-create-0001"},
            json={
                "start_time": "19:30:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        assert created_response.status_code == 200, created_response.text
        session_id = created_response.json()["session_id"]

        intake_response = client.post(
            f"/api/v1/evenings/{session_id}/intake-turns",
            headers={"Idempotency-Key": "real-school-coverage-intake-0001"},
            json={"text": SCHOOL_CHILD_INTAKE, "expected_version": 1},
        )
        assert intake_response.status_code == 200, intake_response.text
        intake = intake_response.json()
        draft = intake["data"]["intake_draft"]
        tasks = draft["tasks"]
        assert len(tasks) == 3
        math = next(task for task in tasks if "第12页" in _task_search_text(task))
        english = next(task for task in tasks if "第三段" in _task_search_text(task))
        science = next(task for task in tasks if "观察记录" in _task_search_text(task))
        assert math["completion_state"] == "partial"
        assert math["child_estimate_minutes"] == 20
        assert english["completion_state"] == "pending"
        assert english["child_estimate_minutes"] is None
        assert science["child_estimate_minutes"] == 10
        coverage_notes = "\n".join(draft["coverage_notes"])
        assert "英语" in coverage_notes
        assert "科学" in coverage_notes
        trace_id = intake["trace_id"]

        confirmed_response = client.post(
            f"/api/v1/evenings/{session_id}/inventory/confirm",
            headers={"Idempotency-Key": "real-school-coverage-confirm-0001"},
            json={"expected_version": 2},
        )
        assert confirmed_response.status_code == 200, confirmed_response.text
        confirmed = confirmed_response.json()
        assert confirmed["data"]["coverage_mode"] == "school_verified"
        assert len(confirmed["data"]["inventory"]) == 3

    with connect_database(database_path) as connection:
        stored = connection.execute(
            """
            SELECT source, payload_json FROM observation_events
            WHERE session_id = ? AND event_type = 'intake_draft'
            """,
            (session_id,),
        ).fetchone()
    assert stored is not None
    assert stored["source"] == "both"
    stored_payload = json.loads(stored["payload_json"])
    assert stored_payload["school_brief_id"] == school_brief_id
    assert stored_payload["coverage_mode"] == "school_verified"

    trace = RunTraceRepository(database_path).get_trace(trace_id)
    assert trace.trace.status == "completed"
    assert trace.trace.model_calls == 1
    assert trace.trace.handler_executions == 1
    assert [run.tool_name for run in trace.tool_runs] == ["save_intake_draft"]
