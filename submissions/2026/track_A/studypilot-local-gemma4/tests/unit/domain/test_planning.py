from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from backend.contracts.models import FixedBlock, Source, TaskCompletionState, TaskItem
from backend.domain.planning import PlanningRequest, build_plan
from backend.domain.policy import order_tasks


TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 11, 20, 0, tzinfo=TZ)


def _task(
    task_id: str,
    minutes: int,
    *,
    must_do: bool = True,
    subject: str = "mathematics",
    due_offset: int | None = None,
    avoidance: int = 0,
    preference: int = 0,
    completion: TaskCompletionState = TaskCompletionState.PENDING,
) -> TaskItem:
    return TaskItem(
        id=task_id,
        session_id="session-1",
        title=task_id,
        subject=subject,
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
        avoidance_score=avoidance,
        preference_score=preference,
        due_at=NOW + timedelta(minutes=due_offset) if due_offset is not None else None,
        created_at=NOW,
        updated_at=NOW,
    )


def _fixed(block_id: str, start: int, end: int) -> FixedBlock:
    return FixedBlock(
        id=block_id,
        label=block_id,
        starts_at=NOW + timedelta(minutes=start),
        ends_at=NOW + timedelta(minutes=end),
        source=Source.PARENT,
    )


def _request(
    tasks: list[TaskItem],
    *,
    horizon: int = 120,
    fixed_blocks: list[FixedBlock] | None = None,
    adaptation_mode: bool = False,
    preferred_order: list[str] | None = None,
    deadline_risk_task_ids: list[str] | None = None,
    reason: str = "initial",
    now: datetime = NOW,
    sleep_at: datetime | None = None,
) -> PlanningRequest:
    return PlanningRequest(
        session_id="session-1",
        now=now,
        sleep_at=sleep_at or NOW + timedelta(minutes=horizon),
        tasks=tasks,
        fixed_blocks=fixed_blocks or [],
        adaptation_mode=adaptation_mode,
        preferred_order=preferred_order,
        deadline_risk_task_ids=deadline_risk_task_ids or [],
        reason=reason,
    )


def _duration_minutes(blocks: list[object], block_type: str) -> int:
    return sum(
        int((block.ends_at - block.starts_at).total_seconds() // 60)
        for block in blocks
        if block.block_type == block_type
    )


def test_fixed_blocks_are_clipped_merged_and_deducted_once() -> None:
    request = _request(
        [],
        fixed_blocks=[
            _fixed("early", -10, 20),
            _fixed("overlap", 10, 40),
            _fixed("late", 110, 140),
            _fixed("outside", 130, 150),
        ],
    )

    result = build_plan(request)

    fixed = [block for block in result.blocks if block.block_type == "fixed"]
    assert result.capacity.available_minutes == 120
    assert result.capacity.fixed_minutes == 50
    assert [(block.starts_at, block.ends_at) for block in fixed] == [
        (NOW, NOW + timedelta(minutes=40)),
        (NOW + timedelta(minutes=110), NOW + timedelta(minutes=120)),
    ]


def test_disjoint_sub_minute_fixed_blocks_round_only_after_totaling() -> None:
    fixed_blocks = [
        FixedBlock(
            id=f"second-{index}",
            label=f"Second {index}",
            starts_at=NOW + timedelta(seconds=start),
            ends_at=NOW + timedelta(seconds=start + 1),
            source=Source.PARENT,
        )
        for index, start in enumerate((5, 10))
    ]

    result = build_plan(
        _request(
            [_task("must", 30)],
            horizon=46,
            fixed_blocks=fixed_blocks,
        )
    )

    assert result.stage == "plan_draft"
    assert result.capacity.fixed_minutes == 1
    assert result.capacity.required_minutes == 46
    assert result.capacity.shortfall_minutes == 0


def test_merged_fixed_id_sets_have_unambiguous_stable_block_ids() -> None:
    fixed_blocks = [
        _fixed("a", 0, 10),
        _fixed("b|c", 0, 10),
        _fixed("a|b", 20, 30),
        _fixed("c", 20, 30),
    ]

    result = build_plan(_request([], fixed_blocks=fixed_blocks))

    ids = [block.id for block in result.blocks if block.block_type == "fixed"]
    assert len(ids) == len(set(ids)) == 2


def test_exact_capacity_boundary_is_feasible() -> None:
    result = build_plan(_request([_task("must", 45)], horizon=60))

    assert result.stage == "plan_draft"
    assert result.capacity.required_minutes == 60
    assert result.capacity.remaining_minutes == 0
    assert result.capacity.shortfall_minutes == 0
    assert result.ordered_task_ids == ["must"]
    assert _duration_minutes(result.blocks, "task") == 45
    assert _duration_minutes(result.blocks, "buffer") == 15


def test_busy_thursday_workload_fits_the_170_minute_study_window() -> None:
    result = build_plan(_request([_task("demo-required", 135)], horizon=170))

    assert result.stage == "plan_draft"
    assert result.capacity.available_minutes == 170
    assert result.capacity.task_minutes == 135
    assert result.capacity.buffer_minutes == 25
    assert result.capacity.required_minutes == 160
    assert result.capacity.remaining_minutes == 10
    assert max(block.ends_at for block in result.blocks) <= NOW + timedelta(minutes=170)


@pytest.mark.parametrize(
    ("adaptation_mode", "expected_buffer"),
    [(False, 20), (True, 20)],
)
def test_buffer_rounds_up_to_five_minute_boundary(
    adaptation_mode: bool,
    expected_buffer: int,
) -> None:
    result = build_plan(
        _request(
            [_task("must", 101)],
            horizon=180,
            adaptation_mode=adaptation_mode,
        )
    )

    assert result.capacity.buffer_minutes == expected_buffer


def test_no_task_night_has_no_buffer() -> None:
    result = build_plan(_request([], horizon=45))

    assert result.stage == "plan_draft"
    assert result.capacity.task_minutes == 0
    assert result.capacity.buffer_minutes == 0
    assert result.ordered_task_ids == []
    assert result.deferred_task_ids == []


def test_optional_tasks_use_only_true_surplus_after_must_and_buffer() -> None:
    tasks = [
        _task("must", 30, subject="english"),
        _task("optional-first", 20, must_do=False, due_offset=10),
        _task("optional-deferred", 15, must_do=False, due_offset=20),
    ]

    result = build_plan(_request(tasks, horizon=75))

    assert result.ordered_task_ids == ["must", "optional-first"]
    assert result.deferred_task_ids == ["optional-deferred"]
    assert result.capacity.remaining_minutes == 30
    assert _duration_minutes(result.blocks, "buffer") == 15


def test_future_scheduled_task_is_not_pulled_into_a_roomy_evening() -> None:
    required = _task("tomorrow", 30)
    future = _task("friday", 20, must_do=False)
    future.planning_bucket = "future_scheduled"

    result = build_plan(_request([required, future], horizon=100))

    assert result.ordered_task_ids == ["tomorrow"]
    assert result.future_scheduled_task_ids == ["friday"]
    assert result.capacity.remaining_minutes == 55


def test_optional_mathematics_cannot_displace_required_language_task() -> None:
    language = _task("language-must", 30, subject="english")
    extra_math = _task("extra-math", 30, must_do=False, subject="mathematics")

    result = build_plan(
        _request(
            [extra_math, language],
            horizon=60,
            preferred_order=["extra-math", "language-must"],
        )
    )

    assert result.ordered_task_ids == ["language-must"]
    assert result.deferred_task_ids == ["extra-math"]


def test_earlier_deadline_then_higher_avoidance_controls_order() -> None:
    tasks = [
        _task("later", 10, due_offset=90, avoidance=3),
        _task("low-avoidance", 10, due_offset=30, avoidance=1),
        _task("high-avoidance", 10, due_offset=30, avoidance=3),
        _task("unknown", 10, avoidance=3),
    ]

    result = build_plan(_request(tasks, horizon=120))

    assert result.ordered_task_ids == [
        "high-avoidance",
        "low-avoidance",
        "later",
        "unknown",
    ]


def test_far_future_deadline_microseconds_remain_a_hard_ordering_boundary() -> None:
    earlier_deadline = datetime(9999, 1, 1, tzinfo=timezone.utc)
    earlier = _task("earlier-deadline", 10, avoidance=0)
    later = _task("later-deadline", 10, avoidance=3)
    earlier.due_at = earlier_deadline
    later.due_at = earlier_deadline + timedelta(microseconds=1)

    ordered = order_tasks([later, earlier])

    assert [task.id for task in ordered] == ["earlier-deadline", "later-deadline"]


def test_dst_fold_deadlines_are_ordered_on_the_utc_timeline() -> None:
    timezone_with_fold = ZoneInfo("America/New_York")
    earlier_deadline = datetime(
        2026,
        11,
        1,
        1,
        30,
        tzinfo=timezone_with_fold,
        fold=0,
    )
    later_deadline = earlier_deadline.replace(fold=1)
    earlier = _task("earlier-fold", 10, avoidance=0)
    later = _task("later-fold", 10, avoidance=3)
    earlier.due_at = earlier_deadline
    later.due_at = later_deadline

    assert later_deadline.astimezone(timezone.utc) - earlier_deadline.astimezone(
        timezone.utc
    ) == timedelta(hours=1)

    ordered = order_tasks([later, earlier])

    assert [task.id for task in ordered] == ["earlier-fold", "later-fold"]


def test_subject_switches_are_reduced_only_after_hard_ties() -> None:
    tasks = [
        _task("math-2", 10, subject="mathematics", due_offset=30),
        _task("english", 10, subject="english", due_offset=30),
        _task("math-1", 10, subject="mathematics", due_offset=30),
    ]

    result = build_plan(_request(tasks, horizon=90))

    assert result.ordered_task_ids == ["math-1", "math-2", "english"]


def test_manual_order_applies_inside_but_not_across_hard_groups() -> None:
    tasks = [
        _task("must-a", 10, due_offset=30, avoidance=2),
        _task("must-b", 10, due_offset=30, avoidance=2),
        _task("must-higher-avoidance", 10, due_offset=30, avoidance=3),
        _task("optional", 10, must_do=False, due_offset=10),
    ]

    result = build_plan(
        _request(
            tasks,
            horizon=90,
            preferred_order=["optional", "must-b", "must-a", "must-higher-avoidance"],
        )
    )

    assert result.ordered_task_ids == [
        "must-higher-avoidance",
        "must-b",
        "must-a",
        "optional",
    ]


def test_preference_score_never_moves_optional_ahead_of_must() -> None:
    tasks = [
        _task("must", 10, preference=0),
        _task("preferred-optional", 10, must_do=False, preference=3),
        _task("plain-optional", 10, must_do=False, preference=0),
    ]

    result = build_plan(_request(tasks, horizon=75))

    assert result.ordered_task_ids == ["must", "preferred-optional", "plain-optional"]


def test_identical_input_produces_identical_stable_block_ids() -> None:
    request = _request(
        [_task("must", 30)],
        fixed_blocks=[_fixed("dinner", 30, 45)],
        horizon=90,
    )

    first = build_plan(request)
    second = build_plan(request)

    assert first == second
    assert [block.id for block in first.blocks] == [block.id for block in second.blocks]
    assert all("session-1" not in block.id for block in first.blocks)


def test_completed_and_no_task_items_are_preserved_but_never_scheduled() -> None:
    tasks = [
        _task("pending", 10),
        _task("optional", 60, must_do=False),
        _task("completed", 20, completion=TaskCompletionState.COMPLETED),
        _task("no-task", 0, completion=TaskCompletionState.NO_TASK),
    ]

    result = build_plan(_request(tasks, horizon=45))

    assert set(result.ordered_task_ids) == {"pending"}
    assert set(result.deferred_task_ids) == {"optional"}
    assert set(result.completed_task_ids) == {"completed", "no-task"}
    assert (
        set(result.ordered_task_ids)
        | set(result.deferred_task_ids)
        | set(result.completed_task_ids)
    ) == {task.id for task in tasks}
    assert {block.task_id for block in result.blocks if block.task_id} == {"pending"}


def test_capacity_conflict_recommends_an_exact_earlier_start() -> None:
    start_at = NOW.replace(hour=19, minute=30)
    end_at = NOW.replace(hour=22, minute=20)

    conflict = build_plan(
        _request([_task("required", 160)], now=start_at, sleep_at=end_at)
    )

    assert conflict.stage == "capacity_conflict"
    assert conflict.capacity.shortfall_minutes == 15
    assert conflict.capacity_recovery is not None
    assert conflict.capacity_recovery.mode == "start_earlier"
    assert conflict.capacity_recovery.recommended_start_time == time(19, 15)
    assert conflict.deadline_risk_task_ids == []
    assert conflict.pace_targets == []


def test_focus_pace_uses_targets_without_rewriting_conservative_estimates() -> None:
    start_at = NOW.replace(hour=18, minute=45)
    end_at = NOW.replace(hour=22, minute=20)
    task = _task("required", 220)

    plan = build_plan(
        _request(
            [task],
            now=start_at,
            sleep_at=end_at,
            reason="focus_pace",
        )
    )

    assert plan.stage == "plan_draft"
    assert plan.baseline_capacity.required_minutes == 255
    assert plan.baseline_capacity.feasible is False
    assert plan.capacity.required_minutes == 215
    assert plan.capacity.feasible is True
    assert plan.capacity_recovery is not None
    assert plan.capacity_recovery.speedup_percent == 18
    assert plan.pace_targets[0].target_minutes == 180
    assert _duration_minutes(plan.blocks, "task") == 180
    assert task.conservative_minutes == 220


def test_extreme_conflict_requires_unselected_manual_deadline_risk() -> None:
    start_at = NOW.replace(hour=18, minute=45)
    end_at = NOW.replace(hour=22, minute=20)
    tasks = [_task("large", 200), _task("small", 40)]

    conflict = build_plan(
        _request(tasks, now=start_at, sleep_at=end_at)
    )

    assert conflict.stage == "capacity_conflict"
    assert conflict.capacity_recovery is not None
    assert conflict.capacity_recovery.mode == "manual_choice"
    assert conflict.capacity_recovery.speedup_percent == 20
    assert conflict.capacity_recovery.residual_shortfall_minutes == 17
    assert conflict.deadline_risk_task_ids == []

    manual = build_plan(
        _request(
            tasks,
            now=start_at,
            sleep_at=end_at,
            reason="manual_deadline_risk",
            deadline_risk_task_ids=["small"],
        )
    )

    assert manual.stage == "plan_draft"
    assert manual.deadline_risk_task_ids == ["small"]
    assert manual.ordered_task_ids == ["large"]
    assert manual.pace_targets[0].target_minutes == 184
    assert manual.capacity.feasible is True
    assert tasks[0].conservative_minutes == 200


def test_result_exposes_estimate_details_and_reason() -> None:
    task = _task("must", 20)

    result = build_plan(_request([task]))

    assert result.reason == "initial"
    assert [candidate.model_dump() for candidate in result.estimate_details] == [
        {
            "task_id": "must",
            "minutes": 20,
            "source": "child_adjusted",
            "confidence": "low",
            "must_do_tonight": True,
        }
    ]


@pytest.mark.parametrize(
    ("now", "sleep_at"),
    [
        (NOW.replace(tzinfo=None), (NOW + timedelta(hours=1)).replace(tzinfo=None)),
        (NOW, (NOW + timedelta(hours=1)).astimezone(timezone.utc)),
        (NOW, NOW),
        (NOW, NOW - timedelta(minutes=1)),
    ],
)
def test_request_rejects_invalid_horizon_datetimes(
    now: datetime,
    sleep_at: datetime,
) -> None:
    with pytest.raises(ValidationError):
        PlanningRequest(
            session_id="session-1",
            now=now,
            sleep_at=sleep_at,
            tasks=[],
            fixed_blocks=[],
            adaptation_mode=False,
            reason="invalid",
        )


@pytest.mark.parametrize(
    "preferred_order",
    [["missing"], ["task", "task"]],
)
def test_request_rejects_unknown_or_duplicate_manual_ids(
    preferred_order: list[str],
) -> None:
    with pytest.raises(ValidationError):
        _request([_task("task", 10)], preferred_order=preferred_order)


def test_request_rejects_duplicate_inventory_ids() -> None:
    task = _task("task", 10)

    with pytest.raises(ValidationError):
        _request([task, task])
