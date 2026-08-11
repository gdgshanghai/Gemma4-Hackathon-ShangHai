from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from math import ceil

from hypothesis import given, settings, strategies as st

from backend.contracts.models import FixedBlock, Source, TaskCompletionState, TaskItem
from backend.domain.capacity_recovery import build_capacity_recovery
from backend.domain.planning import PlanningRequest, build_plan


TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 11, 20, 0, tzinfo=TZ)


@settings(max_examples=80, deadline=None)
@given(
    task_specs=st.lists(
        st.tuples(
            st.integers(min_value=5, max_value=60),
            st.booleans(),
            st.booleans(),
            st.integers(min_value=0, max_value=3),
        ),
        min_size=0,
        max_size=8,
    ),
    fixed_specs=st.lists(
        st.tuples(
            st.integers(min_value=-30, max_value=200),
            st.integers(min_value=1, max_value=90),
        ),
        min_size=0,
        max_size=6,
    ),
    adaptation_mode=st.booleans(),
)
def test_planning_invariants_hold_for_generated_inventory(
    task_specs: list[tuple[int, bool, bool, int]],
    fixed_specs: list[tuple[int, int]],
    adaptation_mode: bool,
) -> None:
    tasks = [
        TaskItem(
            id=f"task-{index}",
            session_id="session-property",
            title=f"Task {index}",
            subject=("mathematics", "english", "chinese")[index % 3],
            task_type="written",
            source=Source.SCHOOL,
            completion_state=(
                TaskCompletionState.COMPLETED
                if completed
                else TaskCompletionState.PENDING
            ),
            estimated_minutes=minutes,
            conservative_minutes=minutes,
            priority=0,
            must_do_tonight=must_do,
            child_estimate_minutes=minutes,
            estimate_source="child_adjusted",
            estimate_confidence="low",
            avoidance_score=avoidance,
            preference_score=0,
            created_at=NOW,
            updated_at=NOW,
        )
        for index, (minutes, must_do, completed, avoidance) in enumerate(task_specs)
    ]
    fixed_blocks = [
        FixedBlock(
            id=f"fixed-{index}",
            label=f"Fixed {index}",
            starts_at=NOW + timedelta(minutes=start),
            ends_at=NOW + timedelta(minutes=start + duration),
            source=Source.PARENT,
        )
        for index, (start, duration) in enumerate(fixed_specs)
    ]
    sleep_at = NOW + timedelta(minutes=180)
    result = build_plan(
        PlanningRequest(
            session_id="session-property",
            now=NOW,
            sleep_at=sleep_at,
            tasks=tasks,
            fixed_blocks=fixed_blocks,
            adaptation_mode=adaptation_mode,
            reason="initial",
        )
    )

    task_blocks = [block for block in result.blocks if block.block_type == "task"]
    fixed_plan_blocks = [
        block for block in result.blocks if block.block_type == "fixed"
    ]
    for task_block in task_blocks:
        for fixed_block in fixed_plan_blocks:
            assert (
                task_block.ends_at <= fixed_block.starts_at
                or task_block.starts_at >= fixed_block.ends_at
            )
    assert all(
        NOW <= block.starts_at < block.ends_at <= sleep_at for block in result.blocks
    )
    capacity = result.capacity
    assert capacity.required_minutes == (
        capacity.fixed_minutes + capacity.task_minutes + capacity.buffer_minutes
    )
    assert capacity.remaining_minutes == max(
        capacity.available_minutes - capacity.required_minutes,
        0,
    )
    assert capacity.shortfall_minutes == max(
        capacity.required_minutes - capacity.available_minutes,
        0,
    )
    ordered = set(result.ordered_task_ids)
    deferred = set(result.deferred_task_ids)
    completed = set(result.completed_task_ids)
    assert ordered.isdisjoint(deferred)
    assert ordered.isdisjoint(completed)
    assert deferred.isdisjoint(completed)
    assert ordered | deferred | completed == {task.id for task in tasks}
    if result.stage == "plan_draft":
        assert capacity.shortfall_minutes == 0
        assert capacity.feasible is True


@settings(max_examples=80, deadline=None)
@given(
    minutes=st.lists(
        st.integers(min_value=5, max_value=180),
        min_size=1,
        max_size=8,
    ),
    fixed_minutes=st.integers(min_value=0, max_value=60),
    buffer_minutes=st.integers(min_value=15, max_value=60),
)
def test_capacity_recovery_never_crosses_policy_limits(
    minutes: list[int],
    fixed_minutes: int,
    buffer_minutes: int,
) -> None:
    tasks = [
        TaskItem(
            id=f"recovery-{index}",
            session_id="session-recovery-property",
            title=f"Recovery {index}",
            subject="mathematics",
            task_type="written",
            source=Source.SCHOOL,
            completion_state=TaskCompletionState.PENDING,
            estimated_minutes=value,
            conservative_minutes=value,
            priority=index,
            must_do_tonight=True,
            estimate_source="domain_default",
            estimate_confidence="low",
            created_at=NOW,
            updated_at=NOW,
        )
        for index, value in enumerate(minutes)
    ]
    originals = [task.model_copy(deep=True) for task in tasks]
    start_at = NOW.replace(hour=19, minute=30)
    end_at = NOW.replace(hour=22, minute=20)

    recovery = build_capacity_recovery(
        start_at=start_at,
        end_at=end_at,
        required_tasks=tasks,
        fixed_minutes=fixed_minutes,
        buffer_minutes=buffer_minutes,
    )

    assert tasks == originals
    if recovery is None:
        return
    assert time(18, 45) <= recovery.recommended_start_time < end_at.time()
    assert 0 <= recovery.speedup_percent <= 20
    assert (
        recovery.recovered_minutes + recovery.residual_shortfall_minutes
        == recovery.baseline_shortfall_minutes
    )
    assert all(
        target.target_minutes >= ceil(target.conservative_minutes * 0.80)
        for target in recovery.pace_targets
    )
