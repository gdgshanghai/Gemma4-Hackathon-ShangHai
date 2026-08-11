"""Deterministic recovery policy for overloaded required homework."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from math import ceil, floor
from typing import Literal

from pydantic import Field

from backend.contracts.models import StrictModel, TaskItem
from backend.domain.study_time import EARLIEST_STUDY_START


MAX_FOCUS_REDUCTION_PERCENT = 20


class PaceTarget(StrictModel):
    task_id: str = Field(min_length=1)
    conservative_minutes: int = Field(ge=0)
    target_minutes: int = Field(ge=0)


class CapacityRecovery(StrictModel):
    mode: Literal["start_earlier", "focus_pace", "manual_choice"]
    baseline_shortfall_minutes: int = Field(gt=0)
    earliest_start_time: time
    recommended_start_time: time
    speedup_percent: int = Field(ge=0, le=MAX_FOCUS_REDUCTION_PERCENT)
    pace_targets: list[PaceTarget] = Field(default_factory=list)
    recovered_minutes: int = Field(ge=0)
    residual_shortfall_minutes: int = Field(ge=0)


def build_capacity_recovery(
    *,
    start_at: datetime,
    end_at: datetime,
    required_tasks: list[TaskItem],
    fixed_minutes: int,
    buffer_minutes: int,
) -> CapacityRecovery | None:
    """Return the least aggressive recovery that respects the study stop."""
    _validate_inputs(start_at, end_at, fixed_minutes, buffer_minutes)
    task_minutes = sum(task.conservative_minutes for task in required_tasks)
    baseline_required = fixed_minutes + task_minutes + buffer_minutes
    selected_window = _whole_minutes(start_at, end_at)
    baseline_shortfall = max(baseline_required - selected_window, 0)
    if baseline_shortfall == 0:
        return None

    earliest_at = datetime.combine(
        end_at.date(),
        EARLIEST_STUDY_START,
        tzinfo=end_at.tzinfo,
    )
    maximum_window = _whole_minutes(earliest_at, end_at)
    recovered_by_start = maximum_window - selected_window

    if baseline_required <= maximum_window:
        recommended = (end_at - timedelta(minutes=baseline_required)).time()
        return CapacityRecovery(
            mode="start_earlier",
            baseline_shortfall_minutes=baseline_shortfall,
            earliest_start_time=EARLIEST_STUDY_START,
            recommended_start_time=recommended,
            speedup_percent=0,
            recovered_minutes=baseline_shortfall,
            residual_shortfall_minutes=0,
        )

    targets: list[PaceTarget] = []
    for percent in range(1, MAX_FOCUS_REDUCTION_PERCENT + 1):
        targets = _pace_targets(required_tasks, percent)
        target_required = fixed_minutes + _target_total(targets) + buffer_minutes
        if target_required <= maximum_window:
            recovered = min(
                baseline_shortfall,
                recovered_by_start + task_minutes - _target_total(targets),
            )
            return CapacityRecovery(
                mode="focus_pace",
                baseline_shortfall_minutes=baseline_shortfall,
                earliest_start_time=EARLIEST_STUDY_START,
                recommended_start_time=EARLIEST_STUDY_START,
                speedup_percent=percent,
                pace_targets=targets,
                recovered_minutes=recovered,
                residual_shortfall_minutes=0,
            )

    target_required = fixed_minutes + _target_total(targets) + buffer_minutes
    residual = max(target_required - maximum_window, 0)
    return CapacityRecovery(
        mode="manual_choice",
        baseline_shortfall_minutes=baseline_shortfall,
        earliest_start_time=EARLIEST_STUDY_START,
        recommended_start_time=EARLIEST_STUDY_START,
        speedup_percent=MAX_FOCUS_REDUCTION_PERCENT,
        pace_targets=targets,
        recovered_minutes=max(baseline_shortfall - residual, 0),
        residual_shortfall_minutes=residual,
    )


def _pace_targets(tasks: list[TaskItem], percent: int) -> list[PaceTarget]:
    return [
        PaceTarget(
            task_id=task.id,
            conservative_minutes=task.conservative_minutes,
            target_minutes=max(
                ceil(task.conservative_minutes * 0.80),
                floor(task.conservative_minutes * (100 - percent) / 100),
            ),
        )
        for task in tasks
    ]


def _target_total(targets: list[PaceTarget]) -> int:
    return sum(target.target_minutes for target in targets)


def _whole_minutes(starts_at: datetime, ends_at: datetime) -> int:
    return int((ends_at - starts_at).total_seconds() // 60)


def _validate_inputs(
    start_at: datetime,
    end_at: datetime,
    fixed_minutes: int,
    buffer_minutes: int,
) -> None:
    if start_at.tzinfo is None or end_at.tzinfo is None:
        raise ValueError("capacity recovery requires timezone-aware boundaries")
    if start_at.tzinfo != end_at.tzinfo or end_at <= start_at:
        raise ValueError("capacity recovery requires one forward timezone")
    if fixed_minutes < 0 or buffer_minutes < 0:
        raise ValueError("capacity recovery minutes cannot be negative")
    if start_at.time() < EARLIEST_STUDY_START:
        raise ValueError("study start cannot precede the earliest start")
    if end_at.time() <= EARLIEST_STUDY_START:
        raise ValueError("study end must be after the earliest start")
