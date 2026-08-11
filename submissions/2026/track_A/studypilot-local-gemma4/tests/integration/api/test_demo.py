from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import load_settings
from backend.contracts.evening import SaveIntakeDraftArguments
from backend.storage.database import connect_database


NOW = datetime.fromisoformat("2026-07-16T18:30:00+08:00")


def _settings(project_root: Path, *, demo_mode: bool):
    return load_settings(
        project_root=project_root,
        environ={"V13_DEMO_MODE": "true" if demo_mode else "false"},
        env_file=project_root / "missing.env",
    )


def _reset(
    client: TestClient,
    *,
    key: str,
    expected_session_id: str | None,
):
    return client.post(
        "/api/v1/demo/evenings/today/reset",
        headers={"Idempotency-Key": key},
        json={"expected_session_id": expected_session_id},
    )


def test_demo_routes_are_hidden_in_real_mode(tmp_path: Path) -> None:
    app = create_app(
        _settings(tmp_path, demo_mode=False),
        database_path=tmp_path / "real-mode.db",
        clock=lambda: NOW,
    )

    with TestClient(app) as client:
        scenario = client.get("/api/v1/demo/scenario")
        reset = _reset(
            client,
            key="demo-disabled-reset-0001",
            expected_session_id=None,
        )

    assert scenario.status_code == 404
    assert reset.status_code == 404


def test_demo_scenario_returns_the_fixed_grade7_preset(tmp_path: Path) -> None:
    app = create_app(
        _settings(tmp_path, demo_mode=True),
        database_path=tmp_path / "demo-scenario.db",
        clock=lambda: NOW,
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/demo/scenario")

    assert response.status_code == 200, response.text
    scenario = response.json()
    assert scenario["scenario_id"] == "grade7-busy-monday-v2"
    assert scenario["label"] == "初一开学第六周 · 多科忙碌周一"
    assert scenario["planning_date"] == "2026-10-12"
    assert scenario["start_time"] == "19:30:00"
    assert scenario["sleep_time"] == "22:20:00"
    assert "available_minutes" not in scenario
    assert "地理（明早检查）" in scenario["school_brief_text"]
    assert "生物（周三检查）" in scenario["school_brief_text"]
    assert "历史（周五提交）" in scenario["school_brief_text"]
    assert "道德与法治（周五提交）" in scenario["school_brief_text"]
    assert "地理" not in scenario["child_report_text"]
    assert "洗澡" not in scenario["child_report_text"]
    assert "整理书包" not in scenario["child_report_text"]
    assert "28、30、29" in scenario["weekly_calibration_text"]
    assert scenario["weekly_calibration_groups"] == [
        {
            "subject": "mathematics",
            "task_type": "written",
            "conservative_minutes": 30,
        },
        {
            "subject": "chinese",
            "task_type": "reading",
            "conservative_minutes": 20,
        },
        {
            "subject": "english",
            "task_type": "recitation",
            "conservative_minutes": 15,
        },
        {
            "subject": "geography",
            "task_type": "map_reading",
            "conservative_minutes": 15,
        },
    ]


def test_demo_reset_replaces_only_the_authoritative_evening_and_is_idempotent(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "demo-reset.db"
    app = create_app(
        _settings(tmp_path, demo_mode=True),
        database_path=database_path,
        clock=lambda: NOW,
    )

    with TestClient(app) as client:
        first_response = _reset(
            client,
            key="demo-reset-first-0001",
            expected_session_id=None,
        )
        assert first_response.status_code == 200, first_response.text
        first = first_response.json()
        replay = _reset(
            client,
            key="demo-reset-first-0001",
            expected_session_id=None,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json() == first

        second_response = _reset(
            client,
            key="demo-reset-second-0001",
            expected_session_id=first["session_id"],
        )
        assert second_response.status_code == 200, second_response.text
        second = second_response.json()
        assert second["session_id"] != first["session_id"]
        assert second["stage"] == "created"
        assert second["session_date"] == "2026-07-16"
        assert second["planning_date"] == "2026-10-12"
        assert second["data"]["time_boundary"]["start_time"] == "19:30:00"
        assert second["data"]["time_boundary"]["sleep_time"] == "22:20:00"
        assert second["data"]["time_boundary"]["gross_minutes"] == 170
        assert second["data"]["time_boundary"]["fixed_minutes"] == 0

        stale = _reset(
            client,
            key="demo-reset-stale-0001",
            expected_session_id=first["session_id"],
        )
        assert stale.status_code == 409, stale.text

        third_response = _reset(
            client,
            key="demo-reset-third-0001",
            expected_session_id=second["session_id"],
        )
        assert third_response.status_code == 200, third_response.text
        third = third_response.json()

        old_write = client.post(
            f"/api/v1/evenings/{first['session_id']}/intake-turns",
            headers={"Idempotency-Key": "demo-old-write-0001"},
            json={"text": "must stay read only", "expected_version": 1},
        )
        latest = client.get(
            "/api/v1/evenings/latest",
            params={"session_date": "2026-07-16"},
        )

    assert old_write.status_code == 409, old_write.text
    assert latest.status_code == 200, latest.text
    assert latest.json()["session_id"] == third["session_id"]
    with connect_database(database_path) as connection:
        session_count = connection.execute(
            "SELECT count(*) FROM evening_sessions WHERE session_date = '2026-07-16'"
        ).fetchone()[0]
        authority = connection.execute(
            "SELECT session_id FROM daily_evening_sessions WHERE session_date = '2026-07-16'"
        ).fetchone()[0]
    assert session_count == 3
    assert authority == third["session_id"]


def test_demo_evening_can_start_earlier_without_moving_the_end_boundary(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, demo_mode=True),
        database_path=tmp_path / "demo-heavy-evening.db",
        clock=lambda: NOW,
    )

    with TestClient(app) as client:
        created_response = _reset(
            client,
            key="demo-heavy-create-0001",
            expected_session_id=None,
        )
        created = created_response.json()
        updated_response = client.put(
            f"/api/v1/evenings/{created['session_id']}/time-boundary",
            headers={"Idempotency-Key": "demo-heavy-boundary-0001"},
            json={
                "start_time": "18:45:00",
                "sleep_time": "22:20:00",
                "expected_version": 1,
            },
        )

    assert updated_response.status_code == 200, updated_response.text
    boundary = updated_response.json()["data"]["time_boundary"]
    assert boundary["start_time"] == "18:45:00"
    assert boundary["sleep_time"] == "22:20:00"
    assert boundary["gross_minutes"] == 215


def test_demo_reset_on_new_actual_date_excludes_prior_demo_assignments(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "demo-cross-date-isolation.db"
    first_app = create_app(
        _settings(tmp_path, demo_mode=True),
        database_path=database_path,
        clock=lambda: NOW,
    )

    with TestClient(first_app) as client:
        first = _reset(
            client,
            key="demo-cross-date-first-0001",
            expected_session_id=None,
        ).json()
        repository = client.app.state.runtime.evening_repository
        repository.save_intake_draft(
            session_id=first["session_id"],
            arguments=SaveIntakeDraftArguments.model_validate_json(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "title": "完成历史时间轴",
                                "subject": "history",
                                "completion_state": "pending",
                                "deadline_text": "周五提交",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            ),
            expected_version=1,
            hidden_idempotency_key="demo-cross-date-draft-0001",
        )
        repository.confirm_inventory(
            session_id=first["session_id"],
            expected_version=2,
            profile_version=0,
            parent_high_minutes=[None],
            caller_idempotency_key="demo-cross-date-confirm-0001",
            trace_id="trace-demo-cross-date-confirm-0001",
        )
        planned = repository.build_plan(
            session_id=first["session_id"],
            expected_version=3,
            reason="initial",
            preferred_order=None,
            deadline_risk_task_ids=[],
            caller_idempotency_key="demo-cross-date-plan-0001",
            trace_id="trace-demo-cross-date-plan-0001",
        )
        repository.commit_plan(
            session_id=first["session_id"],
            plan_id=planned["view"]["plan"]["id"],
            expected_version=4,
            caller_idempotency_key="demo-cross-date-commit-0001",
            trace_id="trace-demo-cross-date-commit-0001",
        )

    with connect_database(database_path) as connection:
        old_assignment_id = connection.execute(
            "SELECT id FROM assignment_obligations WHERE origin_session_id = ?",
            (first["session_id"],),
        ).fetchone()["id"]

    next_day = datetime.fromisoformat("2026-07-17T18:30:00+08:00")
    second_app = create_app(
        _settings(tmp_path, demo_mode=True),
        database_path=database_path,
        clock=lambda: next_day,
    )
    with TestClient(second_app) as client:
        second_response = _reset(
            client,
            key="demo-cross-date-second-0001",
            expected_session_id=None,
        )
        assert second_response.status_code == 200, second_response.text
        second = second_response.json()
        future_assignments = second["data"]["future_assignments"]

        with connect_database(database_path) as connection:
            connection.execute(
                "UPDATE assignment_obligations SET planned_evening_date = ? WHERE id = ?",
                ("2026-10-12", old_assignment_id),
            )

        repository = client.app.state.runtime.evening_repository
        repository.save_intake_draft(
            session_id=second["session_id"],
            arguments=SaveIntakeDraftArguments.model_validate_json(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "title": "完成数学练习",
                                "subject": "mathematics",
                                "completion_state": "pending",
                                "deadline_text": "明早检查",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            ),
            expected_version=1,
            hidden_idempotency_key="demo-cross-date-draft-0002",
        )
        confirmed = repository.confirm_inventory(
            session_id=second["session_id"],
            expected_version=2,
            profile_version=0,
            parent_high_minutes=[None],
            caller_idempotency_key="demo-cross-date-confirm-0002",
            trace_id="trace-demo-cross-date-confirm-0002",
        )

    assert future_assignments == []
    assert [task["subject"] for task in confirmed["view"]["inventory"]] == [
        "mathematics"
    ]
    assert all(
        task["assignment_id"] != old_assignment_id
        for task in confirmed["view"]["inventory"]
    )
