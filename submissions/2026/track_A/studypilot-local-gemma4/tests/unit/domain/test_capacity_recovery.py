from __future__ import annotations

from datetime import datetime, time
from math import ceil
from zoneinfo import ZoneInfo

import pytest

from backend.contracts.models import Source, TaskCompletionState, TaskItem
from backend.domain.capacity_recovery import build_capacity_recovery


TZ = ZoneInfo("Asia/Shanghai")
START_AT = datetime(2026, 10, 12, 19, 30, tzinfo=TZ)
END_AT = datetime(2026, 10, 12, 22, 20, tzinfo=TZ)


def _task(task_id: str, minutes: int) -> TaskItem:
    return TaskItem(
        id=task_id,
        session_id="session-1",
        title=task_id,
        subject="mathematics",
        task_type="written",
        source=Source.SCHOOL,
        completion_state=TaskCompletionState.PENDING,
        estimated_minutes=minutes,
        conservative_minutes=minutes,
        priority=0,
        must_do_tonight=True,
        estimate_source="domain_default",
        estimate_confidence="low",
        created_at=START_AT,
        updated_at=START_AT,
    )


def _recover(
    task_minutes: int,
    buffer_minutes: int,
    *,
    fixed_minutes: int = 0,
):
    return build_capacity_recovery(
        start_at=START_AT,
        end_at=END_AT,
        required_tasks=[_task("required", task_minutes)],
        fixed_minutes=fixed_minutes,
        buffer_minutes=buffer_minutes,
    )


def test_feasible_baseline_needs_no_recovery() -> None:
    assert _recover(task_minutes=135, buffer_minutes=25) is None


def test_185_minutes_recommends_1915_without_speedup() -> None:
    recovery = _recover(task_minutes=160, buffer_minutes=25)

    assert recovery is not None
    assert recovery.mode == "start_earlier"
    assert recovery.baseline_shortfall_minutes == 15
    assert recovery.recommended_start_time == time(19, 15)
    assert recovery.speedup_percent == 0
    assert recovery.pace_targets == []
    assert recovery.recovered_minutes == 15
    assert recovery.residual_shortfall_minutes == 0


def test_policy_uses_smallest_speedup_that_fits_after_1845() -> None:
    recovery = _recover(task_minutes=220, buffer_minutes=35)

    assert recovery is not None
    assert recovery.mode == "focus_pace"
    assert recovery.recommended_start_time == time(18, 45)
    assert recovery.speedup_percent == 18
    assert recovery.pace_targets[0].conservative_minutes == 220
    assert recovery.pace_targets[0].target_minutes == 180
    assert recovery.recovered_minutes == 85
    assert recovery.residual_shortfall_minutes == 0


def test_fixed_minutes_are_not_compressed() -> None:
    recovery = _recover(task_minutes=190, buffer_minutes=30, fixed_minutes=20)

    assert recovery is not None
    assert recovery.mode == "focus_pace"
    assert recovery.speedup_percent == 13
    assert recovery.pace_targets[0].target_minutes == 165


def test_policy_stops_recommending_when_twenty_percent_still_does_not_fit() -> None:
    recovery = _recover(task_minutes=240, buffer_minutes=40)

    assert recovery is not None
    assert recovery.mode == "manual_choice"
    assert recovery.recommended_start_time == time(18, 45)
    assert recovery.speedup_percent == 20
    assert recovery.pace_targets[0].target_minutes == 192
    assert recovery.recovered_minutes == 93
    assert recovery.residual_shortfall_minutes == 17
    assert (
        recovery.recovered_minutes + recovery.residual_shortfall_minutes
        == recovery.baseline_shortfall_minutes
    )


def test_multiple_targets_preserve_inputs_and_never_drop_below_eighty_percent() -> None:
    tasks = [_task("a", 37), _task("b", 83), _task("c", 120)]
    originals = [task.model_copy(deep=True) for task in tasks]

    recovery = build_capacity_recovery(
        start_at=START_AT,
        end_at=END_AT,
        required_tasks=tasks,
        fixed_minutes=0,
        buffer_minutes=40,
    )

    assert recovery is not None
    assert tasks == originals
    assert all(
        target.target_minutes >= ceil(target.conservative_minutes * 0.80)
        for target in recovery.pace_targets
    )
    assert 0 <= recovery.speedup_percent <= 20
    assert recovery.recommended_start_time >= time(18, 45)


def test_policy_rejects_a_start_before_the_family_earliest_boundary() -> None:
    with pytest.raises(ValueError, match="earliest start"):
        build_capacity_recovery(
            start_at=START_AT.replace(hour=18, minute=44),
            end_at=END_AT,
            required_tasks=[_task("required", 220)],
            fixed_minutes=0,
            buffer_minutes=35,
        )
