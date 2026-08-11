from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.contracts.models import Source, TaskCompletionState, TaskItem
from backend.domain.planning import PlanningRequest, build_plan


TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 11, 20, 0, tzinfo=TZ)


def _task(
    task_id: str,
    minutes: int,
    *,
    must_do: bool = True,
    completion: TaskCompletionState = TaskCompletionState.PENDING,
) -> TaskItem:
    return TaskItem(
        id=task_id,
        session_id="session-1",
        title=task_id,
        subject="mathematics",
        task_type="written",
        source=Source.SCHOOL,
        completion_state=completion,
        estimated_minutes=minutes,
        conservative_minutes=minutes,
        priority=0,
        must_do_tonight=must_do,
        child_estimate_minutes=minutes,
        estimate_source="child_adjusted",
        estimate_confidence="low",
        avoidance_score=0,
        preference_score=0,
        created_at=NOW,
        updated_at=NOW,
    )


def _build(tasks: list[TaskItem], *, now: datetime, sleep_at: datetime):
    return build_plan(
        PlanningRequest(
            session_id="session-1",
            now=now,
            sleep_at=sleep_at,
            tasks=tasks,
            fixed_blocks=[],
            adaptation_mode=False,
            reason="initial",
        )
    )


def test_63_hard_minutes_in_45_minute_horizon_returns_exact_conflict() -> None:
    tasks = [_task("hard-a", 33), _task("hard-b", 30)]

    result = _build(tasks, now=NOW, sleep_at=NOW + timedelta(minutes=45))

    assert result.stage == "capacity_conflict"
    assert result.capacity.available_minutes == 45
    assert result.capacity.task_minutes == 63
    assert result.capacity.buffer_minutes == 15
    assert result.capacity.required_minutes == 78
    assert result.capacity.shortfall_minutes == 33
    assert result.capacity.feasible is False
    assert result.ordered_task_ids == ["hard-a", "hard-b"]
    assert not [block for block in result.blocks if block.block_type == "task"]


def test_capacity_conflict_keeps_completed_item_in_completed_list() -> None:
    tasks = [
        _task("hard", 63),
        _task("optional", 10, must_do=False),
        _task("done", 20, completion=TaskCompletionState.COMPLETED),
    ]

    result = _build(tasks, now=NOW, sleep_at=NOW + timedelta(minutes=45))

    assert result.ordered_task_ids == ["hard"]
    assert result.deferred_task_ids == ["optional"]
    assert result.completed_task_ids == ["done"]


def test_later_now_replan_has_less_capacity_and_can_become_conflict() -> None:
    tasks = [_task("hard", 90)]
    sleep_at = NOW + timedelta(minutes=120)

    initial = _build(tasks, now=NOW, sleep_at=sleep_at)
    later = _build(tasks, now=NOW + timedelta(minutes=30), sleep_at=sleep_at)

    assert initial.stage == "plan_draft"
    assert initial.capacity.available_minutes == 120
    assert later.stage == "capacity_conflict"
    assert later.capacity.available_minutes == 90
    assert later.capacity.shortfall_minutes == 15
