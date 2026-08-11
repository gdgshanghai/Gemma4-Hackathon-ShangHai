from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import load_settings
from backend.storage.database import connect_database
from backend.storage.run_traces import RunTraceRepository


pytestmark = pytest.mark.real_lm

COMPLEX_PARENT_TEXT = (
    "本周可核对观察：最近三次数学书面作业分别用时31、34、29分钟；"
    "最近三次语文阅读分别用时24、26、22分钟；"
    "两次英语背诵分别用时28、30分钟，开始前都需要提醒一次；"
    "两次地理读图任务分别用时18、21分钟；"
    "20:30以后开始背诵类任务时明显更慢。"
    "以上只作为本周观察，请先生成建议，由家长确认后再更新规划参数。"
)
MODEL_ID = "gemma-4-26b-a4b-it"


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def test_real_parent_calibration_extracts_complex_preset_once_and_commits_without_lm(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "real-parent.db"
    app = create_app(load_settings(), database_path=database_path)

    with TestClient(app) as client:
        runtime_client = client.app.state.runtime.lm_client
        assert runtime_client.is_production_real_lm is True
        assert runtime_client.evidence_provenance == "real_lm_native_fc"
        metadata = runtime_client.get_model_metadata()
        assert metadata.id == MODEL_ID
        assert metadata.state == "loaded"
        assert "tool_use" in metadata.capabilities

        proposal_response = client.post(
            "/api/v1/parent/calibrations",
            headers={"Idempotency-Key": "real-proposal-synthetic-0001"},
            json={
                    "text": COMPLEX_PARENT_TEXT,
                "expected_calibration_version": 0,
                "expected_profile_version": 0,
            },
        )
        assert proposal_response.status_code == 200, proposal_response.text
        proposal = proposal_response.json()
        assert proposal["stage"] == "needs_confirmation"
        assert not _contains_key(proposal, "provenance")
        proposal_trace_id = proposal["trace_id"]
        assert isinstance(proposal_trace_id, str) and proposal_trace_id

        observations = proposal["data"]["draft"]["observations"]
        assert {
            (
                observation["subject"],
                observation["task_type"],
                observation["value_number"],
                observation["sample_count"],
            )
            for observation in observations
        } == {
            ("mathematics", "written", 1.7, 3),
            ("chinese", "reading", 1.3, 3),
            ("english", "recitation", 1.5, 2),
            ("geography", "map_reading", 0.84, 2),
        }
        assert all(
            observation["category"] == "task_speed"
            and observation["metric"] == "estimated_actual_ratio"
            and observation["unit"] == "ratio"
            and observation["confidence"] == 0.7
            for observation in observations
        )
        assert [
            item["reference_minutes"]
            for item in proposal["data"]["calibration_details"]
        ] == [20, 20, 20, 25]

        proposal_trace = RunTraceRepository(database_path).get_trace(proposal_trace_id)
        assert proposal_trace.trace.status == "completed"
        assert proposal_trace.trace.model_calls == 1
        assert proposal_trace.trace.schema_repair_used is False
        assert len(proposal_trace.llm_runs) == 1
        assert len(proposal_trace.tool_runs) == 1
        tool_run = proposal_trace.tool_runs[0]
        assert tool_run.tool_name == "extract_calibration_evidence"
        assert set(tool_run.arguments) == {"duration_groups", "unapplied_notes"}
        assert all(
            {"subject", "task_type", "minutes"} <= set(group)
            and set(group) <= {"subject", "task_type", "workload_band", "minutes"}
            for group in tool_run.arguments["duration_groups"]
        )

        with connect_database(database_path) as connection:
            confirmed_after_proposal = connection.execute(
                "SELECT COUNT(*) FROM profile_observation_events"
            ).fetchone()[0]
            llm_calls_after_proposal = connection.execute(
                "SELECT COUNT(*) FROM llm_runs"
            ).fetchone()[0]
        assert confirmed_after_proposal == 0
        assert llm_calls_after_proposal == 1

        calibration_id = proposal["calibration_id"]
        draft = proposal["data"]["draft"]
        accepted_operation_ids = [
            observation["operation_id"] for observation in draft["observations"]
        ]
        assert accepted_operation_ids
        commit_url = f"/api/v1/parent/calibrations/{calibration_id}/commit"
        commit_headers = {"Idempotency-Key": "real-commit-synthetic-0001"}
        commit_body = {
            "expected_calibration_version": proposal["calibration_version"],
            "draft_id": draft["id"],
            "draft_digest": draft["draft_digest"],
            "accepted_operation_ids": accepted_operation_ids,
        }
        commit_response = client.post(
            commit_url,
            headers=commit_headers,
            json=commit_body,
        )
        assert commit_response.status_code == 200, commit_response.text
        committed = commit_response.json()
        assert committed["stage"] == "committed"
        assert committed["delivery"]["replayed"] is False
        assert committed["data"]["accepted_operation_ids"] == accepted_operation_ids
        assert len(committed["data"]["observation_event_ids"]) == len(
            accepted_operation_ids
        )
        commit_trace_id = committed["trace_id"]
        assert isinstance(commit_trace_id, str) and commit_trace_id
        assert commit_trace_id != proposal_trace_id

        with connect_database(database_path) as connection:
            confirmed_operations = connection.execute(
                "SELECT operation_id, COUNT(*) FROM profile_observation_events "
                "GROUP BY operation_id ORDER BY operation_id"
            ).fetchall()
            llm_calls_after_commit = connection.execute(
                "SELECT COUNT(*) FROM llm_runs"
            ).fetchone()[0]
            commit_harness_trace_count = connection.execute(
                "SELECT COUNT(*) FROM harness_traces WHERE trace_id = ?",
                (commit_trace_id,),
            ).fetchone()[0]
        assert [tuple(row) for row in confirmed_operations] == sorted(
            (operation_id, 1) for operation_id in accepted_operation_ids
        )
        assert llm_calls_after_commit == llm_calls_after_proposal
        assert commit_harness_trace_count == 0

        replay = client.post(commit_url, headers=commit_headers, json=commit_body)
        with connect_database(database_path) as connection:
            llm_calls_after_replay = connection.execute(
                "SELECT COUNT(*) FROM llm_runs"
            ).fetchone()[0]
        assert replay.status_code == 200, replay.text
        assert replay.json()["delivery"]["replayed"] is True
        assert llm_calls_after_replay == llm_calls_after_commit

    assert proposal_trace.trace.trace_id == proposal_trace_id
