from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import load_settings
from backend.contracts.evening import SaveIntakeDraftArguments
from backend.contracts.family import (
    FamilyWriteContext,
    MemoryCategory,
    ProfilePatchAction,
    ProposedObservationInput,
)
from backend.orchestration.lm_studio import LMStudioClient
from backend.storage.database import connect_database
from backend.storage.family_context import FamilyContextRepository


MODEL = "gemma-4-26b-a4b-it"
BASE_URL = "http://127.0.0.1:1234/v1"


def _tool_response() -> dict[str, object]:
    arguments = {
        "tasks": [
            {
                "title": "完成数学练习册第12页",
                "subject": "mathematics",
                "completion_state": "pending",
                "child_estimate_minutes": 30,
            },
            {
                "title": "背诵英语课文第三段",
                "subject": "english",
                "completion_state": "pending",
                "child_estimate_minutes": 15,
            },
        ]
    }
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
                            "id": "call-save-intake",
                            "type": "function",
                            "function": {
                                "name": "save_intake_draft",
                                "arguments": json.dumps(
                                    arguments,
                                    ensure_ascii=False,
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


def _text_response() -> dict[str, object]:
    return {
        "model": MODEL,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "作业清单已整理，请确认是否完整。"},
            }
        ],
    }


def _empty_text_response() -> dict[str, object]:
    return {
        "model": MODEL,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": ""},
            }
        ],
    }


def _school_coverage_tool_response() -> dict[str, object]:
    arguments = {
        "coverage_notes": [
            "学校作业单中的英语课文第三段背诵未在孩子清单中提及。",
        ],
        "tasks": [
            {
                "title": "完成数学练习册第12页",
                "subject": "mathematics",
                "completion_state": "partial",
                "child_estimate_minutes": 20,
            },
            {
                "title": "背诵英语课文第三段",
                "subject": "english",
                "completion_state": "pending",
                "child_estimate_minutes": None,
            },
        ],
    }
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
                            "id": "call-save-school-coverage",
                            "type": "function",
                            "function": {
                                "name": "save_intake_draft",
                                "arguments": json.dumps(
                                    arguments,
                                    ensure_ascii=False,
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


def _incremental_tool_response() -> dict[str, object]:
    arguments = {
        "tasks": [
            {
                "title": "Math worksheet",
                "subject": "mathematics",
                "completion_state": "pending",
                "child_estimate_minutes": 30,
            },
            {
                "title": "English recitation",
                "subject": "english",
                "completion_state": "pending",
                "child_estimate_minutes": 15,
            },
            {
                "title": "History recitation",
                "subject": "history",
                "completion_state": "pending",
                "child_estimate_minutes": 10,
            },
        ]
    }
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
                            "id": "call-save-incremental-intake",
                            "type": "function",
                            "function": {
                                "name": "save_intake_draft",
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                },
            }
        ],
    }


class _QueueTransport:
    def __init__(self, responses: list[dict[str, object] | BaseException]) -> None:
        self.responses = list(responses)
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.payloads.append(json.loads(request.content))
        if not self.responses:
            raise AssertionError("unexpected model request")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return httpx.Response(200, json=response)


def _settings(project_root: Path):
    return load_settings(
        project_root=project_root,
        environ={},
        env_file=project_root / "missing.env",
    )


def _clock_at(session_date: str):
    return lambda: datetime.fromisoformat(f"{session_date}T12:00:00+08:00")


def _post(
    client: TestClient,
    url: str,
    key: str,
    body: dict[str, object],
) -> dict[str, Any]:
    response = client.post(
        url,
        headers={"Idempotency-Key": key},
        json=body,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["session_id"]
    assert payload["trace_id"]
    assert isinstance(payload["allowed_actions"], list)
    return payload


def _commit_parent_speed_high(
    repository: FamilyContextRepository,
    *,
    high_minutes: int,
    profile_version: int,
    suffix: str,
    target_event_id: str | None = None,
) -> str:
    calibration_id = f"calibration-evening-speed-{suffix}"
    receipt = repository.save_calibration_input(
        calibration_id,
        "Synthetic confirmed task speed",
        expected_calibration_version=0,
        expected_profile_version=profile_version,
        context=FamilyWriteContext(
            actor="parent-1",
            role="parent",
            trace_id=f"trace-speed-input-{suffix}",
            idempotency_key=f"speed-input-key-{suffix}",
        ),
    ).receipt
    repository.propose_profile_patch(
        calibration_id,
        receipt.id,
        (
            ProposedObservationInput(
                action=(
                    ProfilePatchAction.ASSERT
                    if target_event_id is None
                    else ProfilePatchAction.SUPERSEDE
                ),
                category=MemoryCategory.TASK_SPEED,
                subject=" Mathematics ",
                task_type=" WRITTEN ",
                metric="typical_minutes_high",
                value_text=None,
                value_number=float(high_minutes),
                unit="minutes",
                confidence=0.9,
                sample_count=4,
                observed_at=datetime.now(UTC) - timedelta(days=1),
                target_event_id=target_event_id,
            ),
        ),
        expected_calibration_version=1,
        context=FamilyWriteContext(
            actor="parent-1",
            role="parent",
            trace_id=f"trace-speed-propose-{suffix}",
            idempotency_key=f"speed-propose-key-{suffix}",
        ),
    )
    draft = repository.get_calibration_recovery(calibration_id).pending_draft
    assert draft is not None
    committed = repository.commit_profile_patch(
        calibration_id,
        draft.id,
        (draft.observations[0].operation_id,),
        draft_digest=draft.draft_digest,
        expected_calibration_version=2,
        context=FamilyWriteContext(
            actor="parent-1",
            role="parent",
            trace_id=f"trace-speed-commit-{suffix}",
            idempotency_key=f"speed-commit-key-{suffix}",
        ),
    )
    accepted = committed.outcome.data["accepted_observations"]
    assert isinstance(accepted, list)
    event = accepted[0]
    assert isinstance(event, dict)
    event_id = event["id"]
    assert isinstance(event_id, str)
    return event_id


def _create_fixed_evening(
    client: TestClient,
    *,
    session_date: str,
    suffix: str,
) -> str:
    created = _post(
        client,
        "/api/v1/evenings",
        f"evening-create-speed-{suffix}",
        {
            "start_time": "19:30:00",
            "sleep_time": "22:20:00",
            "expected_version": 0,
        },
    )
    session_id = created["session_id"]
    client.app.state.runtime.evening_repository.save_intake_draft(
        session_id=session_id,
        arguments=SaveIntakeDraftArguments.model_validate_json(
            json.dumps(
                {
                    "tasks": [
                        {
                            "title": "Mathematics worksheet",
                            "subject": "mathematics",
                            "completion_state": "pending",
                            "child_estimate_minutes": 30,
                        },
                        {
                            "title": "English recitation",
                            "subject": "english",
                            "completion_state": "pending",
                            "child_estimate_minutes": 15,
                        },
                    ]
                }
            )
        ),
        expected_version=1,
        hidden_idempotency_key=f"evening-draft-speed-{suffix}",
    )
    assert created["session_date"] == session_date
    return session_id


def test_same_day_start_resumes_the_authoritative_session(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    current_time = [datetime(2026, 7, 12, 12, 0, tzinfo=UTC)]
    database_path = tmp_path / "latest-evening.db"
    app = create_app(
        _settings(project_root),
        database_path=database_path,
        clock=lambda: current_time[0],
    )

    with TestClient(app) as client:
        first = _post(
            client,
            "/api/v1/evenings",
            "latest-evening-first",
            {
                "start_time": "19:30:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        second = _post(
            client,
            "/api/v1/evenings",
            "latest-evening-second",
            {
                "start_time": "19:30:00",
                "sleep_time": "22:00:00",
                "expected_version": 0,
            },
        )
        response = client.get(
            "/api/v1/evenings/latest",
            params={"session_date": "2026-07-12"},
        )
        today_response = client.get("/api/v1/evenings/today")

    assert response.status_code == 200, response.text
    latest = response.json()
    assert today_response.status_code == 200, today_response.text
    assert latest["session_id"] == first["session_id"] == second["session_id"]
    assert latest["session_date"] == "2026-07-12"
    assert today_response.json()["session_id"] == first["session_id"]
    assert latest["trace_id"] == response.headers["X-Trace-Id"]
    with connect_database(database_path) as connection:
        count = connection.execute(
            "SELECT count(*) FROM evening_sessions WHERE session_date = '2026-07-12'"
        ).fetchone()[0]
    assert count == 1


def test_time_boundary_is_derived_and_can_be_updated_before_commit(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    app = create_app(
        _settings(project_root),
        database_path=tmp_path / "time-boundary.db",
        clock=lambda: datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
    )

    with TestClient(app) as client:
        created = _post(
            client,
            "/api/v1/evenings",
            "time-boundary-create",
            {
                "start_time": "19:30:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        updated = client.put(
            f"/api/v1/evenings/{created['session_id']}/time-boundary",
            headers={"Idempotency-Key": "time-boundary-update"},
            json={
                "start_time": "19:00:00",
                "sleep_time": "22:00:00",
                "expected_version": created["version"],
            },
        )
        old_shape = client.post(
            "/api/v1/evenings",
            headers={"Idempotency-Key": "time-boundary-old-shape"},
            json={
                "sleep_time": "22:30:00",
                "available_minutes": 180,
                "expected_version": 0,
            },
        )

    assert created["planning_date"] == "2026-10-15"
    assert created["data"]["time_boundary"] == {
        "start_time": "19:30:00",
        "sleep_time": "22:20:00",
        "gross_minutes": 170,
        "fixed_minutes": 0,
        "net_minutes": 170,
    }
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["time_boundary"]["gross_minutes"] == 180
    assert old_shape.status_code == 422


def test_midnight_freezes_yesterday_and_allows_a_new_evening(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    current_time = [datetime(2026, 7, 12, 15, 59, tzinfo=UTC)]
    app = create_app(
        _settings(project_root),
        database_path=tmp_path / "midnight-evening.db",
        clock=lambda: current_time[0],
    )

    with TestClient(app) as client:
        yesterday = _post(
            client,
            "/api/v1/evenings",
            "midnight-evening-first",
            {
                "start_time": "19:30:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        assert yesterday["session_date"] == "2026-07-12"

        current_time[0] = datetime(2026, 7, 12, 16, 0, tzinfo=UTC)
        stale_write = client.post(
            f"/api/v1/evenings/{yesterday['session_id']}/intake-turns",
            headers={"Idempotency-Key": "midnight-stale-write"},
            json={"text": "Late update", "expected_version": yesterday["version"]},
        )
        empty_today = client.get("/api/v1/evenings/today")
        today = _post(
            client,
            "/api/v1/evenings",
            "midnight-evening-next",
            {
                "start_time": "19:35:00",
                "sleep_time": "22:15:00",
                "expected_version": 0,
            },
        )

    assert stale_write.status_code == 409, stale_write.text
    assert empty_today.status_code == 404, empty_today.text
    assert today["session_date"] == "2026-07-13"
    assert today["session_id"] != yesterday["session_id"]


def test_confirmed_parent_speed_changes_next_evening_estimate_and_replay_stays_stored(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    database_path = tmp_path / "evening-memory.db"
    transport = _QueueTransport([])
    settings = _settings(project_root)
    current_time = [datetime.fromisoformat("2026-07-12T12:00:00+08:00")]
    app = create_app(
        settings,
        database_path=database_path,
        clock=lambda: current_time[0],
        lm_client=LMStudioClient.from_settings(
            settings,
            transport=httpx.MockTransport(transport),
        ),
    )

    with TestClient(app) as client:
        first_session_id = _create_fixed_evening(
            client,
            session_date="2026-07-12",
            suffix="first",
        )
        first_confirmed = _post(
            client,
            f"/api/v1/evenings/{first_session_id}/inventory/confirm",
            "evening-confirm-speed-first",
            {"expected_version": 2},
        )
        first_inventory = first_confirmed["data"]["inventory"]
        assert [task["estimate_source"] for task in first_inventory] == [
            "child_adjusted",
            "domain_default",
        ]
        assert [task["conservative_minutes"] for task in first_inventory] == [30, 20]
        first_planned = _post(
            client,
            f"/api/v1/evenings/{first_session_id}/plans",
            "evening-plan-speed-first",
            {"expected_version": 3, "reason": "initial"},
        )

        family_repository = client.app.state.runtime.family_repository
        first_speed_event_id = _commit_parent_speed_high(
            family_repository,
            high_minutes=60,
            profile_version=0,
            suffix="first",
        )

        current_time[0] = datetime.fromisoformat("2026-07-13T12:00:00+08:00")
        second_session_id = _create_fixed_evening(
            client,
            session_date="2026-07-13",
            suffix="second",
        )
        second_confirm_url = f"/api/v1/evenings/{second_session_id}/inventory/confirm"
        second_confirm_body = {"expected_version": 2}
        second_confirmed = _post(
            client,
            second_confirm_url,
            "evening-confirm-speed-second",
            second_confirm_body,
        )
        second_inventory = second_confirmed["data"]["inventory"]
        assert second_inventory[0]["conservative_minutes"] == 60
        assert second_inventory[0]["estimate_source"] == "parent_range"
        assert second_inventory[0]["estimate_confidence"] == "medium"
        assert second_inventory[1]["conservative_minutes"] == 20
        assert second_inventory[1]["estimate_source"] == "domain_default"
        second_planned = _post(
            client,
            f"/api/v1/evenings/{second_session_id}/plans",
            "evening-plan-speed-second",
            {"expected_version": 3, "reason": "initial"},
        )
        first_finish = datetime.fromisoformat(first_planned["data"]["plan"]["predicted_finish_at"])
        second_finish = datetime.fromisoformat(
            second_planned["data"]["plan"]["predicted_finish_at"]
        )
        assert first_finish.strftime("%H:%M") == "20:35"
        assert second_finish.strftime("%H:%M") == "21:05"

        _commit_parent_speed_high(
            family_repository,
            high_minutes=90,
            profile_version=1,
            suffix="revised",
            target_event_id=first_speed_event_id,
        )
        replay = _post(
            client,
            second_confirm_url,
            "evening-confirm-speed-second",
            second_confirm_body,
        )
        assert replay == second_confirmed
        assert transport.payloads == []


def test_child_evening_main_path_persists_reorder_commit_and_close(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    database_path = tmp_path / "evening.db"
    transport = _QueueTransport([_tool_response()])
    settings = _settings(project_root)
    lm_client = LMStudioClient.from_settings(
        settings,
        transport=httpx.MockTransport(transport),
    )
    app = create_app(
        settings,
        database_path=database_path,
        lm_client=lm_client,
        clock=_clock_at("2026-07-12"),
    )

    with TestClient(app) as client:
        created = _post(
            client,
            "/api/v1/evenings",
            "evening-create-main-0001",
            {
                "start_time": "19:30:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        assert created["version"] == 1
        assert created["stage"] == "created"
        assert created["allowed_actions"] == ["describe_homework"]
        session_id = created["session_id"]

        intake = _post(
            client,
            f"/api/v1/evenings/{session_id}/intake-turns",
            "evening-intake-main-0001",
            {
                "text": "今晚数学练习册第12页大约30分钟，英语第三段背诵大约15分钟，就这些。",
                "expected_version": 1,
            },
        )
        assert intake["version"] == 2
        assert intake["stage"] == "intake_draft"
        assert intake["allowed_actions"] == ["add_intake_turn", "confirm_inventory"]
        assert intake["data"]["narration"] == "清单已整理，请确认是否完整。"
        assert len(transport.payloads) == 1
        assert [task["title"] for task in intake["data"]["intake_draft"]["tasks"]] == [
            "完成数学练习册第12页",
            "背诵英语课文第三段",
        ]
        assert transport.payloads[0]["tool_choice"] == "required"
        assert transport.payloads[0]["max_tokens"] == 4_096
        assert transport.payloads[0]["tools"][0]["function"]["name"] == (
            "save_intake_draft"
        )

        confirmed = _post(
            client,
            f"/api/v1/evenings/{session_id}/inventory/confirm",
            "evening-confirm-main-0001",
            {"expected_version": 2},
        )
        assert confirmed["version"] == 3
        assert confirmed["stage"] == "inventory_confirmed"
        assert confirmed["data"]["coverage_mode"] == "child_reported"
        inventory = confirmed["data"]["inventory"]
        assert len(inventory) == 2
        assert all(task["must_do_tonight"] is True for task in inventory)
        assert [task["conservative_minutes"] for task in inventory] == [30, 15]

        initial_plan = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans",
            "evening-plan-main-0001",
            {"expected_version": 3, "reason": "initial"},
        )
        assert initial_plan["version"] == 4
        assert initial_plan["stage"] == "plan_draft"
        first_plan = initial_plan["data"]["plan"]
        assert first_plan["plan_version"] == 1
        assert first_plan["capacity"]["feasible"] is True
        assert first_plan["scheduled_optional_minutes"] == 0
        assert first_plan["true_surplus_minutes"] == 110
        assert first_plan["predicted_finish_at"] == "2026-07-12T20:30:00+08:00"

        reversed_ids = list(reversed(first_plan["ordered_task_ids"]))
        reordered = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans",
            "evening-plan-reorder-0001",
            {
                "expected_version": 4,
                "reason": "child_reorder",
                "preferred_order": reversed_ids,
            },
        )
        assert reordered["version"] == 5
        assert reordered["allowed_actions"] == ["commit_plan"]
        second_plan = reordered["data"]["plan"]
        assert second_plan["plan_version"] == 2
        assert second_plan["ordered_task_ids"] == reversed_ids
        first_block_ids = {block["id"] for block in first_plan["blocks"]}
        second_block_ids = {block["id"] for block in second_plan["blocks"]}
        assert first_block_ids.isdisjoint(second_block_ids)

        committed = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans/{second_plan['id']}/commit",
            "evening-commit-main-0001",
            {"expected_version": 5},
        )
        assert committed["version"] == 6
        assert committed["stage"] == "committed"
        assert committed["data"]["plan"]["committed"] is True

        unfinished_id = inventory[1]["id"]
        completed_id = inventory[0]["id"]
        close_url = f"/api/v1/evenings/{session_id}/close-turns"
        close_body = {
            "expected_version": 6,
            "unfinished_task_ids": [unfinished_id],
            "largest_deviation": {
                "task_id": completed_id,
                "actual_minutes": 47,
            },
            "note": "英语背诵还没完成",
        }
        closed = _post(
            client,
            close_url,
            "evening-close-main-0001",
            close_body,
        )
        assert closed["version"] == 7
        assert closed["stage"] == "closed"
        outcomes = {item["task_id"]: item for item in closed["data"]["outcomes"]}
        assert outcomes[unfinished_id]["completion_state"] == "pending"
        assert outcomes[completed_id]["completion_state"] == "completed"
        assert outcomes[completed_id]["actual_minutes"] == 47

        replay = _post(
            client,
            close_url,
            "evening-close-main-0001",
            close_body,
        )
        assert replay == closed

        resumed_closed = _post(
            client,
            "/api/v1/evenings",
            "evening-create-main-after-close",
            {
                "start_time": "20:15:00",
                "sleep_time": "21:45:00",
                "expected_version": 0,
            },
        )
        assert resumed_closed["session_id"] == session_id
        assert resumed_closed["version"] == 7
        assert resumed_closed["stage"] == "closed"

        restored_response = client.get(f"/api/v1/evenings/{session_id}")
        assert restored_response.status_code == 200, restored_response.text
        restored = restored_response.json()
        assert restored["version"] == 7
        assert restored["stage"] == "closed"
        assert restored["data"]["inventory"] == inventory
        assert restored["data"]["plan"] == committed["data"]["plan"]
        assert restored["data"]["outcomes"] == closed["data"]["outcomes"]

    with connect_database(database_path) as connection:
        caller_keys = [
            row[0]
            for row in connection.execute(
                "SELECT idempotency_key FROM idempotency_records"
            ).fetchall()
        ]
        raw_intake_count = connection.execute(
            "SELECT COUNT(*) FROM observation_events WHERE event_type = 'intake_raw'"
        ).fetchone()[0]
        draft_count = connection.execute(
            "SELECT COUNT(*) FROM observation_events WHERE event_type = 'intake_draft'"
        ).fetchone()[0]
    assert raw_intake_count == 1
    assert draft_count == 1
    assert "evening-intake-main-0001" not in caller_keys
    assert all(len(value) == 64 for value in caller_keys)
    assert transport.responses == []


def test_valid_intake_write_finishes_without_a_narration_call(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    database_path = tmp_path / "empty-final-content.db"
    transport = _QueueTransport([_tool_response()])
    settings = _settings(project_root)
    app = create_app(
        settings,
        database_path=database_path,
        clock=_clock_at("2026-07-12"),
        lm_client=LMStudioClient.from_settings(
            settings,
            transport=httpx.MockTransport(transport),
        ),
    )

    with TestClient(app) as client:
        created = _post(
            client,
            "/api/v1/evenings",
            "evening-create-empty-final-0001",
            {
                "start_time": "19:30:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        response = client.post(
            f"/api/v1/evenings/{created['session_id']}/intake-turns",
            headers={"Idempotency-Key": "evening-intake-empty-final-0001"},
            json={"text": "Two homework tasks tonight.", "expected_version": 1},
        )

        assert response.status_code == 200, response.text
        intake = response.json()
        assert intake["version"] == 2
        assert intake["stage"] == "intake_draft"
        assert intake["allowed_actions"] == ["add_intake_turn", "confirm_inventory"]
        assert intake["data"]["narration"] == "清单已整理，请确认是否完整。"
        assert len(transport.payloads) == 1
        draft = intake["data"]["intake_draft"]
        assert [task["subject"] for task in draft["tasks"]] == [
            "mathematics",
            "english",
        ]
        assert intake["trace_id"] == response.headers["X-Trace-Id"]

        stored_trace = client.app.state.runtime.trace_repository.get_trace(
            intake["trace_id"]
        )
        assert stored_trace.trace.status == "completed"
        assert stored_trace.trace.final_error_code is None
        assert stored_trace.trace.handler_executions == 1
        assert [run.tool_name for run in stored_trace.tool_runs] == [
            "save_intake_draft"
        ]

    assert transport.responses == []


def test_school_brief_omission_is_merged_and_persists_through_confirmation(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    database_path = tmp_path / "school-coverage.db"
    transport = _QueueTransport([_school_coverage_tool_response(), _text_response()])
    settings = _settings(project_root)
    app = create_app(
        settings,
        database_path=database_path,
        clock=_clock_at("2026-07-12"),
        lm_client=LMStudioClient.from_settings(
            settings,
            transport=httpx.MockTransport(transport),
        ),
    )

    with TestClient(app) as client:
        school_response = client.post(
            "/api/v1/school-briefs",
            headers={"Idempotency-Key": "school-coverage-write-0001"},
            json={
                "brief_date": "2026-07-12",
                "raw_text": "数学：练习册第12页\n英语：背诵课文第三段",
                "expected_revision": 0,
            },
        )
        assert school_response.status_code == 200, school_response.text
        school_brief_id = school_response.json()["data"]["record"]["id"]

        created = _post(
            client,
            "/api/v1/evenings",
            "school-coverage-create-0001",
            {
                "start_time": "19:30:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        session_id = created["session_id"]
        child_report = "数学练习册第12页做了一半，我估计还要20分钟。就这些。"
        intake = _post(
            client,
            f"/api/v1/evenings/{session_id}/intake-turns",
            "school-coverage-intake-0001",
            {"text": child_report, "expected_version": 1},
        )

        assert intake["data"]["coverage_mode"] is None
        draft = intake["data"]["intake_draft"]
        assert [task["title"] for task in draft["tasks"]] == [
            "完成数学练习册第12页",
            "背诵英语课文第三段",
        ]
        assert draft["tasks"][0]["child_estimate_minutes"] == 20
        assert draft["tasks"][0]["completion_state"] == "partial"
        assert draft["tasks"][1]["child_estimate_minutes"] is None
        assert draft["coverage_notes"] == [
            "学校作业单中的英语课文第三段背诵未在孩子清单中提及。"
        ]

        model_request = transport.payloads[0]
        assert [tool["function"]["name"] for tool in model_request["tools"]] == [
            "save_intake_draft"
        ]
        system_prompt = model_request["messages"][0]["content"]
        assert "<school_brief>" in system_prompt
        assert "<child_report>" in system_prompt
        assert "不可信" in system_prompt
        assert "忽略" in system_prompt
        untrusted_input = model_request["messages"][1]["content"]
        assert "<school_brief>" in untrusted_input
        assert "数学：练习册第12页" in untrusted_input
        assert "<child_report>" in untrusted_input
        assert child_report in untrusted_input
        tool_parameters = model_request["tools"][0]["function"]["parameters"]
        assert "coverage_mode" not in tool_parameters["properties"]
        assert "school_brief_id" not in tool_parameters["properties"]

        confirmed = _post(
            client,
            f"/api/v1/evenings/{session_id}/inventory/confirm",
            "school-coverage-confirm-0001",
            {"expected_version": 2},
        )
        assert confirmed["data"]["coverage_mode"] == "school_verified"
        assert [task["title"] for task in confirmed["data"]["inventory"]] == [
            "完成数学练习册第12页",
            "背诵英语课文第三段",
        ]
        assert confirmed["data"]["inventory"][0]["completion_state"] == "partial"
        assert confirmed["data"]["inventory"][0]["child_estimate_minutes"] == 20

        restored_response = client.get(f"/api/v1/evenings/{session_id}")
        assert restored_response.status_code == 200, restored_response.text
        restored = restored_response.json()
        assert restored["data"]["coverage_mode"] == "school_verified"
        assert restored["data"]["inventory"] == confirmed["data"]["inventory"]

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


def test_second_intake_turn_sends_cumulative_child_report_to_model(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    database_path = tmp_path / "cumulative-intake.db"
    transport = _QueueTransport([_tool_response(), _incremental_tool_response()])
    settings = _settings(project_root)
    lm_client = LMStudioClient.from_settings(
        settings,
        transport=httpx.MockTransport(transport),
    )
    app = create_app(
        settings,
        database_path=database_path,
        lm_client=lm_client,
        clock=_clock_at("2026-07-12"),
    )

    with TestClient(app) as client:
        created = _post(
            client,
            "/api/v1/evenings",
            "cumulative-create-0001",
            {
                "start_time": "19:30:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        session_id = created["session_id"]
        first_text = "Math worksheet and English recitation."
        first = _post(
            client,
            f"/api/v1/evenings/{session_id}/intake-turns",
            "cumulative-intake-0001",
            {"text": first_text, "expected_version": 1},
        )
        second_text = "Add history recitation."
        second = _post(
            client,
            f"/api/v1/evenings/{session_id}/intake-turns",
            "cumulative-intake-0002",
            {"text": second_text, "expected_version": first["version"]},
        )

    assert len(transport.payloads) == 2
    second_model_request = transport.payloads[1]
    user_content = second_model_request["messages"][1]["content"]
    assert first_text in user_content
    assert second_text in user_content
    assert [task["subject"] for task in second["data"]["intake_draft"]["tasks"]] == [
        "mathematics",
        "english",
        "history",
    ]


def test_fixed_arrangements_and_optional_tasks_flow_into_capacity(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    database_path = tmp_path / "fixed-arrangements.db"
    settings = _settings(project_root)
    app = create_app(
        settings,
        database_path=database_path,
        clock=_clock_at("2026-07-12"),
    )

    with TestClient(app) as client:
        created = _post(
            client,
            "/api/v1/evenings",
            "fixed-create-0001",
            {
                "start_time": "19:30:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        session_id = created["session_id"]
        app.state.runtime.evening_repository.save_intake_draft(
            session_id=session_id,
            arguments=SaveIntakeDraftArguments.model_validate_json(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "title": "Math worksheet",
                                "subject": "数学",
                                "completion_state": "pending",
                                "child_estimate_minutes": 30,
                                "deadline_text": "明早检查",
                            },
                            {
                                "title": "History extra reading",
                                "subject": "历史",
                                "completion_state": "pending",
                                "child_estimate_minutes": 15,
                                "deadline_text": "下周三提交",
                            },
                        ],
                        "fixed_blocks": [
                            {
                                "label": "Dinner",
                                "start_time": "20:00:00",
                                "end_time": "20:30:00",
                            }
                        ],
                    }
                )
            ),
            expected_version=1,
            hidden_idempotency_key="fixed-draft-0001",
        )
        confirmed = _post(
            client,
            f"/api/v1/evenings/{session_id}/inventory/confirm",
            "fixed-confirm-0001",
            {"expected_version": 2},
        )
        planned = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans",
            "fixed-plan-evening-0001",
            {"expected_version": confirmed["version"], "reason": "initial"},
        )

    assert confirmed["data"]["time_boundary"] == {
        "start_time": "19:30:00",
        "sleep_time": "22:20:00",
        "gross_minutes": 170,
        "fixed_minutes": 30,
        "net_minutes": 140,
    }
    inventory = confirmed["data"]["inventory"]
    assert inventory[0]["must_do_tonight"] is True
    assert inventory[0]["due_at"].startswith("2026-07-13")
    assert inventory[1]["must_do_tonight"] is False
    plan = planned["data"]["plan"]
    assert plan["capacity"]["fixed_minutes"] == 30
    assert any(block["block_type"] == "fixed" and block["label"] == "Dinner" for block in plan["blocks"])


def test_capacity_conflict_recommends_earlier_start_and_replans_without_parent(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    database_path = tmp_path / "capacity.db"
    transport = _QueueTransport([_tool_response()])
    settings = _settings(project_root)
    app = create_app(
        settings,
        database_path=database_path,
        clock=_clock_at("2026-07-12"),
        lm_client=LMStudioClient.from_settings(
            settings,
            transport=httpx.MockTransport(transport),
        ),
    )

    with TestClient(app) as client:
        created = _post(
            client,
            "/api/v1/evenings",
            "evening-create-capacity-0001",
            {
                "start_time": "21:35:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        session_id = created["session_id"]
        _post(
            client,
            f"/api/v1/evenings/{session_id}/intake-turns",
            "evening-intake-capacity-0001",
            {"text": "数学和英语作业都要做完。", "expected_version": 1},
        )
        confirmed = _post(
            client,
            f"/api/v1/evenings/{session_id}/inventory/confirm",
            "evening-confirm-capacity-0001",
            {"expected_version": 2},
        )
        conflict = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans",
            "evening-plan-capacity-0001",
            {"expected_version": 3, "reason": "initial"},
        )

        assert conflict["version"] == 4
        assert conflict["stage"] == "capacity_conflict"
        assert conflict["allowed_actions"] == ["adjust_capacity"]
        plan = conflict["data"]["plan"]
        assert plan["capacity"] == {
            "available_minutes": 45,
            "fixed_minutes": 0,
            "task_minutes": 45,
            "buffer_minutes": 15,
            "required_minutes": 60,
            "remaining_minutes": 0,
            "shortfall_minutes": 15,
            "feasible": False,
        }
        assert plan["scheduled_optional_minutes"] == 0
        assert plan["true_surplus_minutes"] == 0
        assert plan["predicted_finish_at"] is None
        assert plan["committed"] is False
        assert plan["baseline_capacity"] == plan["capacity"]
        assert plan["deadline_risk_task_ids"] == []
        assert plan["pace_targets"] == []
        recovery = plan["capacity_recovery"]
        assert recovery["mode"] == "start_earlier"
        assert recovery["baseline_shortfall_minutes"] == 15
        assert recovery["recommended_start_time"] == "21:20:00"
        assert recovery["speedup_percent"] == 0

        premature_manual = client.post(
            f"/api/v1/evenings/{session_id}/plans",
            headers={"Idempotency-Key": "evening-premature-manual-0001"},
            json={
                "expected_version": conflict["version"],
                "reason": "manual_deadline_risk",
                "deadline_risk_task_ids": [confirmed["data"]["inventory"][0]["id"]],
            },
        )
        assert premature_manual.status_code == 409
        assert premature_manual.json()["error"]["code"] == "invalid_transition"

        rejected_commit = client.post(
            f"/api/v1/evenings/{session_id}/plans/{plan['id']}/commit",
            headers={"Idempotency-Key": "evening-commit-capacity-0001"},
            json={"expected_version": 4},
        )
        assert rejected_commit.status_code == 409
        assert rejected_commit.json()["error"]["code"] == "invalid_transition"

        updated_boundary = client.put(
            f"/api/v1/evenings/{session_id}/time-boundary",
            headers={"Idempotency-Key": "evening-boundary-capacity-0001"},
            json={
                "start_time": "21:20:00",
                "sleep_time": "22:20:00",
                "expected_version": conflict["version"],
            },
        )
        assert updated_boundary.status_code == 200, updated_boundary.text
        updated = updated_boundary.json()
        assert updated["stage"] == "inventory_confirmed"

        adjusted = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans",
            "evening-adjust-capacity-0001",
            {
                "expected_version": updated["version"],
                "reason": "initial",
            },
        )
        assert adjusted["stage"] == "plan_draft"
        assert adjusted["data"]["plan"]["capacity"]["feasible"] is True
        assert adjusted["data"]["plan"]["capacity_recovery"] is None
        assert adjusted["data"]["plan"]["deadline_risk_task_ids"] == []

        accepted_plan = adjusted["data"]["plan"]
        committed_response = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans/{accepted_plan['id']}/commit",
            "evening-commit-adjusted-0001",
            {"expected_version": adjusted["version"]},
        )
        assert committed_response["stage"] == "committed"

    with connect_database(database_path) as connection:
        rows = connection.execute(
            "SELECT id, committed FROM plans WHERE session_id = ? ORDER BY version",
            (session_id,),
        ).fetchall()
    assert [(row["id"], row["committed"]) for row in rows] == [
        (accepted_plan["id"], 1),
    ]


def test_focus_pace_plan_uses_targets_and_keeps_baseline_minutes(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    database_path = tmp_path / "focus-capacity.db"
    settings = _settings(project_root)
    app = create_app(
        settings,
        database_path=database_path,
        clock=_clock_at("2026-07-12"),
        lm_client=LMStudioClient.from_settings(
            settings,
            transport=httpx.MockTransport(_QueueTransport([_tool_response()])),
        ),
    )

    with TestClient(app) as client:
        created = _post(
            client,
            "/api/v1/evenings",
            "evening-create-focus-0001",
            {
                "start_time": "18:45:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        session_id = created["session_id"]
        _post(
            client,
            f"/api/v1/evenings/{session_id}/intake-turns",
            "evening-intake-focus-0001",
            {"text": "两项明早作业。", "expected_version": 1},
        )
        confirmed = _post(
            client,
            f"/api/v1/evenings/{session_id}/inventory/confirm",
            "evening-confirm-focus-0001",
            {"expected_version": 2},
        )
        task_ids = [task["id"] for task in confirmed["data"]["inventory"]]
        with connect_database(database_path) as connection:
            connection.execute(
                "UPDATE task_items SET conservative_minutes = 205 WHERE id = ?",
                (task_ids[0],),
            )
            connection.execute(
                "UPDATE task_items SET conservative_minutes = 15 WHERE id = ?",
                (task_ids[1],),
            )
            connection.commit()

        conflict = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans",
            "evening-plan-focus-0001",
            {"expected_version": 3, "reason": "initial"},
        )
        assert conflict["stage"] == "capacity_conflict"
        assert conflict["data"]["plan"]["capacity_recovery"]["mode"] == "focus_pace"

        focused = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans",
            "evening-accept-focus-0001",
            {"expected_version": conflict["version"], "reason": "focus_pace"},
        )

    plan = focused["data"]["plan"]
    assert focused["stage"] == "plan_draft"
    assert plan["baseline_capacity"]["task_minutes"] == 220
    assert plan["baseline_capacity"]["required_minutes"] == 255
    assert plan["capacity"]["task_minutes"] == 180
    assert plan["capacity"]["required_minutes"] == 215
    assert plan["capacity"]["feasible"] is True
    assert plan["capacity_recovery"]["speedup_percent"] == 18
    assert sum(item["target_minutes"] for item in plan["pace_targets"]) == 180


def test_manual_deadline_risk_has_no_default_selection_and_preserves_assignment(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    database_path = tmp_path / "manual-capacity.db"
    settings = _settings(project_root)
    app = create_app(
        settings,
        database_path=database_path,
        clock=_clock_at("2026-07-12"),
        lm_client=LMStudioClient.from_settings(
            settings,
            transport=httpx.MockTransport(_QueueTransport([_tool_response()])),
        ),
    )

    with TestClient(app) as client:
        created = _post(
            client,
            "/api/v1/evenings",
            "evening-create-manual-0001",
            {
                "start_time": "18:45:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        session_id = created["session_id"]
        _post(
            client,
            f"/api/v1/evenings/{session_id}/intake-turns",
            "evening-intake-manual-0001",
            {"text": "两项明早作业。", "expected_version": 1},
        )
        confirmed = _post(
            client,
            f"/api/v1/evenings/{session_id}/inventory/confirm",
            "evening-confirm-manual-0001",
            {"expected_version": 2},
        )
        task_ids = [task["id"] for task in confirmed["data"]["inventory"]]
        with connect_database(database_path) as connection:
            connection.execute(
                "UPDATE task_items SET conservative_minutes = 200 WHERE id = ?",
                (task_ids[0],),
            )
            connection.execute(
                "UPDATE task_items SET conservative_minutes = 40 WHERE id = ?",
                (task_ids[1],),
            )
            connection.commit()

        conflict = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans",
            "evening-plan-manual-0001",
            {"expected_version": 3, "reason": "initial"},
        )
        conflict_plan = conflict["data"]["plan"]
        assert conflict_plan["capacity_recovery"]["mode"] == "manual_choice"
        assert conflict_plan["capacity_recovery"]["residual_shortfall_minutes"] == 17
        assert conflict_plan["deadline_risk_task_ids"] == []

        manual = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans",
            "evening-accept-manual-0001",
            {
                "expected_version": conflict["version"],
                "reason": "manual_deadline_risk",
                "deadline_risk_task_ids": [task_ids[1]],
            },
        )
        manual_replay = _post(
            client,
            f"/api/v1/evenings/{session_id}/plans",
            "evening-accept-manual-0001",
            {
                "expected_version": conflict["version"],
                "reason": "manual_deadline_risk",
                "deadline_risk_task_ids": [task_ids[1]],
            },
        )
        assert manual_replay == manual

    plan = manual["data"]["plan"]
    assert manual["stage"] == "plan_draft"
    assert plan["deadline_risk_task_ids"] == [task_ids[1]]
    assert plan["ordered_task_ids"] == [task_ids[0]]
    assert plan["capacity"]["feasible"] is True
    assert plan["pace_targets"][0]["target_minutes"] == 184
    with connect_database(database_path) as connection:
        obligation = connection.execute(
            "SELECT status FROM assignment_obligations WHERE id = ("
            "SELECT assignment_id FROM task_items WHERE id = ?)",
            (task_ids[1],),
        ).fetchone()
    assert obligation["status"] == "open"


def test_model_unavailable_returns_503_after_raw_input_is_persisted(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    database_path = tmp_path / "unavailable.db"
    transport = _QueueTransport([httpx.ConnectError("local model offline")])
    settings = _settings(project_root)
    app = create_app(
        settings,
        database_path=database_path,
        clock=_clock_at("2026-07-12"),
        lm_client=LMStudioClient.from_settings(
            settings,
            transport=httpx.MockTransport(transport),
        ),
    )
    raw_text = "今晚有数学卷子两页，大约四十分钟。"

    with TestClient(app) as client:
        created = _post(
            client,
            "/api/v1/evenings",
            "evening-create-unavailable-0001",
            {
                "start_time": "20:30:00",
                "sleep_time": "22:20:00",
                "expected_version": 0,
            },
        )
        session_id = created["session_id"]
        response = client.post(
            f"/api/v1/evenings/{session_id}/intake-turns",
            headers={"Idempotency-Key": "evening-intake-unavailable-0001"},
            json={"text": raw_text, "expected_version": 1},
        )

        assert response.status_code == 503, response.text
        unavailable = response.json()
        assert unavailable["session_id"] == session_id
        assert unavailable["version"] == 2
        assert unavailable["stage"] == "model_unavailable"
        assert unavailable["allowed_actions"] == ["add_intake_turn"]
        assert unavailable["trace_id"]
        assert unavailable["error"]["code"] == "model_unavailable"

    with connect_database(database_path) as connection:
        raw_events = connection.execute(
            """
            SELECT payload_json FROM observation_events
            WHERE session_id = ? AND event_type = 'intake_raw'
            """,
            (session_id,),
        ).fetchall()
        draft_count = connection.execute(
            """
            SELECT COUNT(*) FROM observation_events
            WHERE session_id = ? AND event_type = 'intake_draft'
            """,
            (session_id,),
        ).fetchone()[0]
    assert len(raw_events) == 1
    raw_payload = json.loads(raw_events[0]["payload_json"])
    assert raw_payload["text"] == raw_text
    assert raw_payload["caller_idempotency_sha256"] != (
        "evening-intake-unavailable-0001"
    )
    assert len(raw_payload["caller_idempotency_sha256"]) == 64
    assert draft_count == 0
