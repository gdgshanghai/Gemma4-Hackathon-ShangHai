from datetime import time

import pytest
from pydantic import ValidationError

from backend.contracts.evening import (
    EveningCreateRequest,
    EveningPlanRequest,
    EveningTimeBoundaryRequest,
    PlanView,
    SaveIntakeDraftArguments,
)


def test_evening_time_window_is_derived_from_start_and_sleep() -> None:
    body = EveningCreateRequest(
        start_time=time(19, 30),
        sleep_time=time(22, 20),
        expected_version=0,
    )

    assert body.window_minutes == 170


def test_time_boundary_accepts_the_maximum_family_window() -> None:
    body = EveningTimeBoundaryRequest(
        start_time=time(18, 45),
        sleep_time=time(22, 20),
        expected_version=1,
    )

    assert body.window_minutes == 215


def test_time_boundary_rejects_a_non_forward_window() -> None:
    with pytest.raises(ValidationError):
        EveningTimeBoundaryRequest(
            start_time=time(22, 30),
            sleep_time=time(19, 30),
            expected_version=1,
        )


@pytest.mark.parametrize(
    ("start_time", "sleep_time"),
    [
        (time(18, 44), time(22, 20)),
        (time(18, 45), time(22, 21)),
    ],
)
def test_time_boundary_rejects_values_outside_family_limits(
    start_time: time,
    sleep_time: time,
) -> None:
    with pytest.raises(ValidationError):
        EveningTimeBoundaryRequest(
            start_time=start_time,
            sleep_time=sleep_time,
            expected_version=1,
        )


def test_manual_deadline_risk_requires_explicit_ids() -> None:
    body = EveningPlanRequest(
        expected_version=4,
        reason="manual_deadline_risk",
        deadline_risk_task_ids=["task-1"],
    )

    assert body.deadline_risk_task_ids == ["task-1"]


def test_old_unsafe_capacity_adjustment_shape_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EveningPlanRequest.model_validate(
            {
                "expected_version": 4,
                "reason": "capacity_adjustment",
                "deferred_task_ids": ["task-1"],
            }
        )


def test_plan_view_exposes_recovery_without_legacy_auto_deferral_advice() -> None:
    properties = PlanView.model_json_schema()["properties"]

    assert "baseline_capacity" in properties
    assert "capacity_recovery" in properties
    assert "pace_targets" in properties
    assert "future_scheduled_task_ids" in properties
    assert "deadline_risk_task_ids" in properties
    assert "capacity_advice" not in properties


def test_intake_tool_schema_leaves_policy_fields_to_the_program() -> None:
    schema = SaveIntakeDraftArguments.model_json_schema()
    task_schema = schema["$defs"]["IntakeDraftTask"]["properties"]

    assert "deadline_text" in task_schema
    assert "total_units" in task_schema
    assert "completed_units" in task_schema
    assert "task_type" not in task_schema
    assert "priority" not in task_schema
    assert "must_do_tonight" not in task_schema
    assert "due_date" not in task_schema
