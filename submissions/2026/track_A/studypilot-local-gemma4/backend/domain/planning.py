"""Pure, fixed-block-aware evening planning."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Literal

from pydantic import Field, model_validator

from backend.contracts.models import (
    CapacityProof,
    FixedBlock,
    PlanBlock,
    StrictModel,
    TaskCompletionState,
    TaskItem,
)
from backend.domain.capacity_recovery import (
    CapacityRecovery,
    PaceTarget,
    build_capacity_recovery,
)
from backend.domain.policy import order_tasks


_TERMINAL_STATES = {
    TaskCompletionState.COMPLETED,
    TaskCompletionState.NO_TASK,
}


class PlanningActionError(ValueError):
    """Raised when a requested recovery action is not currently allowed."""


class PlanCandidate(StrictModel):
    task_id: str = Field(min_length=1)
    minutes: int = Field(ge=0)
    source: Literal[
        "history_p80",
        "parent_range",
        "child_adjusted",
        "domain_default",
    ]
    confidence: Literal["low", "medium", "high"]
    must_do_tonight: bool


class PlanningRequest(StrictModel):
    session_id: str = Field(min_length=1)
    now: datetime
    sleep_at: datetime
    tasks: list[TaskItem]
    fixed_blocks: list[FixedBlock]
    adaptation_mode: bool
    preferred_order: list[str] | None = None
    deadline_risk_task_ids: list[str] = Field(default_factory=list)
    reason: Literal[
        "initial",
        "child_reorder",
        "focus_pace",
        "manual_deadline_risk",
    ]

    @model_validator(mode="after")
    def validate_inventory_and_horizon(self) -> PlanningRequest:
        _require_aware(self.now, "now")
        _require_aware(self.sleep_at, "sleep_at")
        if self.now.tzinfo != self.sleep_at.tzinfo:
            raise ValueError("now and sleep_at must use the same timezone")
        if self.sleep_at <= self.now:
            raise ValueError("sleep_at must be after now")

        task_ids = [task.id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task ids must be unique")
        if any(task.session_id != self.session_id for task in self.tasks):
            raise ValueError("every task must belong to the planning session")
        for task in self.tasks:
            if task.due_at is not None:
                _require_matching_timezone(task.due_at, self.now, "task deadline")

        fixed_ids = [block.id for block in self.fixed_blocks]
        if len(fixed_ids) != len(set(fixed_ids)):
            raise ValueError("fixed block ids must be unique")
        for block in self.fixed_blocks:
            _require_matching_timezone(block.starts_at, self.now, "fixed block")
            _require_matching_timezone(block.ends_at, self.now, "fixed block")

        if self.preferred_order is not None:
            if len(self.preferred_order) != len(set(self.preferred_order)):
                raise ValueError("preferred_order ids must be unique")
            unknown = set(self.preferred_order) - set(task_ids)
            if unknown:
                raise ValueError("preferred_order contains an unknown task id")
        if len(self.deadline_risk_task_ids) != len(set(self.deadline_risk_task_ids)):
            raise ValueError("deadline_risk_task_ids must be unique")
        unfinished_ids = {
            task.id
            for task in self.tasks
            if task.completion_state not in _TERMINAL_STATES
        }
        if set(self.deadline_risk_task_ids) - unfinished_ids:
            raise ValueError(
                "deadline_risk_task_ids contains an unknown or completed task id"
            )
        if self.reason == "manual_deadline_risk":
            if not self.deadline_risk_task_ids:
                raise ValueError("manual_deadline_risk requires an explicit task")
        elif self.deadline_risk_task_ids:
            raise ValueError("deadline risk tasks require manual_deadline_risk")
        return self


class PlanningResult(StrictModel):
    stage: Literal["plan_draft", "capacity_conflict"]
    capacity: CapacityProof
    baseline_capacity: CapacityProof
    ordered_task_ids: list[str]
    deferred_task_ids: list[str]
    future_scheduled_task_ids: list[str] = Field(default_factory=list)
    deadline_risk_task_ids: list[str] = Field(default_factory=list)
    capacity_recovery: CapacityRecovery | None = None
    pace_targets: list[PaceTarget] = Field(default_factory=list)
    completed_task_ids: list[str]
    blocks: list[PlanBlock]
    reason: str = Field(min_length=1)
    estimate_details: list[PlanCandidate]

    @property
    def capacity_proof(self) -> CapacityProof:
        return self.capacity

    @property
    def plan_blocks(self) -> list[PlanBlock]:
        return self.blocks

    @property
    def estimates(self) -> list[PlanCandidate]:
        return self.estimate_details


@dataclass(frozen=True, slots=True)
class _MergedFixed:
    starts_at: datetime
    ends_at: datetime
    ids: tuple[str, ...]
    labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _BlockDraft:
    id: str
    block_type: Literal["task", "fixed", "buffer", "break"]
    label: str
    starts_at: datetime
    ends_at: datetime
    task_id: str | None


class _FreeIntervalAllocator:
    def __init__(self, intervals: list[tuple[datetime, datetime]]) -> None:
        self._intervals = intervals
        self._index = 0
        self._cursor = intervals[0][0] if intervals else None

    def allocate(
        self,
        *,
        minutes: int,
        session_id: str,
        block_type: Literal["task", "buffer"],
        reference_id: str,
        label: str,
        task_id: str | None,
    ) -> list[_BlockDraft]:
        remaining = timedelta(minutes=minutes)
        drafts: list[_BlockDraft] = []
        segment = 0
        while remaining > timedelta(0):
            if self._index >= len(self._intervals) or self._cursor is None:
                raise ValueError("capacity arithmetic exceeded free intervals")
            interval_start, interval_end = self._intervals[self._index]
            starts_at = max(self._cursor, interval_start)
            if starts_at >= interval_end:
                self._index += 1
                if self._index < len(self._intervals):
                    self._cursor = self._intervals[self._index][0]
                continue
            duration = min(remaining, interval_end - starts_at)
            ends_at = starts_at + duration
            drafts.append(
                _BlockDraft(
                    id=_stable_block_id(
                        session_id,
                        block_type,
                        reference_id,
                        segment,
                    ),
                    block_type=block_type,
                    label=label,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    task_id=task_id,
                )
            )
            remaining -= duration
            self._cursor = ends_at
            segment += 1
        return drafts


def build_plan(request: PlanningRequest) -> PlanningResult:
    fixed = _merge_fixed_blocks(request.fixed_blocks, request.now, request.sleep_at)
    available_minutes = _whole_minutes(request.now, request.sleep_at)
    fixed_duration = sum(
        (block.ends_at - block.starts_at for block in fixed),
        start=timedelta(),
    )
    fixed_minutes = ceil(fixed_duration.total_seconds() / 60)

    completed = sorted(
        (task for task in request.tasks if task.completion_state in _TERMINAL_STATES),
        key=lambda task: task.id,
    )
    unfinished = [
        task for task in request.tasks if task.completion_state not in _TERMINAL_STATES
    ]
    ordered_inventory = order_tasks(unfinished, request.preferred_order)
    all_must_tasks = [task for task in ordered_inventory if task.must_do_tonight]
    future_tasks = [
        task
        for task in ordered_inventory
        if not task.must_do_tonight and task.planning_bucket == "future_scheduled"
    ]
    optional_tasks = [
        task
        for task in ordered_inventory
        if not task.must_do_tonight and task.planning_bucket != "future_scheduled"
    ]

    all_task_minutes = sum(task.conservative_minutes for task in all_must_tasks)
    all_buffer_minutes = _buffer_minutes(all_task_minutes, request.adaptation_mode)
    baseline_capacity = _capacity_proof(
        available_minutes=available_minutes,
        fixed_minutes=fixed_minutes,
        task_minutes=all_task_minutes,
        buffer_minutes=all_buffer_minutes,
    )
    baseline_recovery = build_capacity_recovery(
        start_at=request.now,
        end_at=request.sleep_at,
        required_tasks=all_must_tasks,
        fixed_minutes=fixed_minutes,
        buffer_minutes=all_buffer_minutes,
    )

    deadline_risk_ids = set(request.deadline_risk_task_ids)
    must_ids = {task.id for task in all_must_tasks}
    if deadline_risk_ids - must_ids:
        raise PlanningActionError(
            "deadline risk can contain only active tonight-required tasks"
        )
    if request.reason == "manual_deadline_risk" and (
        baseline_recovery is None or baseline_recovery.mode != "manual_choice"
    ):
        raise PlanningActionError(
            "manual deadline risk is allowed only at the policy limit"
        )

    must_tasks = [task for task in all_must_tasks if task.id not in deadline_risk_ids]
    task_minutes = sum(task.conservative_minutes for task in must_tasks)
    buffer_minutes = _buffer_minutes(task_minutes, request.adaptation_mode)
    capacity = _capacity_proof(
        available_minutes=available_minutes,
        fixed_minutes=fixed_minutes,
        task_minutes=task_minutes,
        buffer_minutes=buffer_minutes,
    )
    recovery = build_capacity_recovery(
        start_at=request.now,
        end_at=request.sleep_at,
        required_tasks=must_tasks,
        fixed_minutes=fixed_minutes,
        buffer_minutes=buffer_minutes,
    )
    fixed_drafts = _fixed_block_drafts(request.session_id, fixed)
    estimate_details = [_candidate(task) for task in ordered_inventory]

    apply_pace = (
        recovery is not None
        and recovery.mode == "focus_pace"
        and request.reason in {"focus_pace", "manual_deadline_risk"}
    )
    if recovery is not None and not apply_pace:
        return PlanningResult(
            stage="capacity_conflict",
            capacity=capacity,
            baseline_capacity=baseline_capacity,
            ordered_task_ids=[task.id for task in must_tasks],
            deferred_task_ids=sorted(
                deadline_risk_ids
                | {task.id for task in optional_tasks}
                | {task.id for task in future_tasks}
            ),
            future_scheduled_task_ids=[task.id for task in future_tasks],
            deadline_risk_task_ids=sorted(deadline_risk_ids),
            capacity_recovery=recovery,
            pace_targets=recovery.pace_targets,
            completed_task_ids=[task.id for task in completed],
            blocks=_finalize_blocks(fixed_drafts),
            reason=request.reason,
            estimate_details=estimate_details,
        )

    pace_targets = recovery.pace_targets if apply_pace and recovery is not None else []
    allocation_minutes = {
        target.task_id: target.target_minutes for target in pace_targets
    }
    if apply_pace:
        capacity = _capacity_proof(
            available_minutes=available_minutes,
            fixed_minutes=fixed_minutes,
            task_minutes=sum(allocation_minutes.values()),
            buffer_minutes=buffer_minutes,
        )

    optional_budget = (
        capacity.remaining_minutes
        if request.reason in {"initial", "child_reorder"}
        else 0
    )
    scheduled_optional: list[TaskItem] = []
    deferred_optional: list[TaskItem] = []
    for task in optional_tasks:
        if task.conservative_minutes <= optional_budget:
            scheduled_optional.append(task)
            optional_budget -= task.conservative_minutes
        else:
            deferred_optional.append(task)

    scheduled_tasks = must_tasks + scheduled_optional
    allocator = _FreeIntervalAllocator(
        _free_intervals(request.now, request.sleep_at, fixed)
    )
    task_drafts: list[_BlockDraft] = []
    for task in scheduled_tasks:
        task_drafts.extend(
            allocator.allocate(
                minutes=allocation_minutes.get(task.id, task.conservative_minutes),
                session_id=request.session_id,
                block_type="task",
                reference_id=task.id,
                label=task.title,
                task_id=task.id,
            )
        )
    buffer_drafts = allocator.allocate(
        minutes=buffer_minutes,
        session_id=request.session_id,
        block_type="buffer",
        reference_id="reserved-capacity",
        label="Buffer",
        task_id=None,
    )

    return PlanningResult(
        stage="plan_draft",
        capacity=capacity,
        baseline_capacity=baseline_capacity,
        ordered_task_ids=[task.id for task in scheduled_tasks],
        deferred_task_ids=sorted(
            deadline_risk_ids
            | {task.id for task in deferred_optional}
            | {task.id for task in future_tasks}
        ),
        future_scheduled_task_ids=[task.id for task in future_tasks],
        deadline_risk_task_ids=sorted(deadline_risk_ids),
        capacity_recovery=recovery if apply_pace else None,
        pace_targets=pace_targets,
        completed_task_ids=[task.id for task in completed],
        blocks=_finalize_blocks(fixed_drafts + task_drafts + buffer_drafts),
        reason=request.reason,
        estimate_details=estimate_details,
)


def _capacity_proof(
    *,
    available_minutes: int,
    fixed_minutes: int,
    task_minutes: int,
    buffer_minutes: int,
) -> CapacityProof:
    required_minutes = fixed_minutes + task_minutes + buffer_minutes
    return CapacityProof(
        available_minutes=available_minutes,
        fixed_minutes=fixed_minutes,
        task_minutes=task_minutes,
        buffer_minutes=buffer_minutes,
        required_minutes=required_minutes,
        remaining_minutes=max(available_minutes - required_minutes, 0),
        shortfall_minutes=max(required_minutes - available_minutes, 0),
        feasible=required_minutes <= available_minutes,
    )


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_matching_timezone(
    value: datetime,
    horizon_value: datetime,
    field_name: str,
) -> None:
    _require_aware(value, field_name)
    if value.tzinfo != horizon_value.tzinfo:
        raise ValueError(f"{field_name} must use the planning timezone")


def _whole_minutes(starts_at: datetime, ends_at: datetime) -> int:
    return int((ends_at - starts_at).total_seconds() // 60)


def _buffer_minutes(task_minutes: int, adaptation_mode: bool) -> int:
    if task_minutes == 0:
        return 0
    ratio_percent = 15
    rounded_to_five = ((task_minutes * ratio_percent + 499) // 500) * 5
    return max(15, rounded_to_five)


def _merge_fixed_blocks(
    blocks: list[FixedBlock],
    now: datetime,
    sleep_at: datetime,
) -> list[_MergedFixed]:
    clipped = [
        _MergedFixed(
            starts_at=max(block.starts_at, now),
            ends_at=min(block.ends_at, sleep_at),
            ids=(block.id,),
            labels=(block.label,),
        )
        for block in blocks
        if block.ends_at > now and block.starts_at < sleep_at
    ]
    clipped.sort(key=lambda block: (block.starts_at, block.ends_at, block.ids))
    merged: list[_MergedFixed] = []
    for block in clipped:
        if merged and block.starts_at < merged[-1].ends_at:
            previous = merged[-1]
            merged[-1] = _MergedFixed(
                starts_at=previous.starts_at,
                ends_at=max(previous.ends_at, block.ends_at),
                ids=tuple(sorted(set(previous.ids + block.ids))),
                labels=tuple(sorted(set(previous.labels + block.labels))),
            )
        else:
            merged.append(block)
    return merged


def _free_intervals(
    now: datetime,
    sleep_at: datetime,
    fixed: list[_MergedFixed],
) -> list[tuple[datetime, datetime]]:
    free: list[tuple[datetime, datetime]] = []
    cursor = now
    for block in fixed:
        if cursor < block.starts_at:
            free.append((cursor, block.starts_at))
        cursor = max(cursor, block.ends_at)
    if cursor < sleep_at:
        free.append((cursor, sleep_at))
    return free


def _fixed_block_drafts(
    session_id: str,
    fixed: list[_MergedFixed],
) -> list[_BlockDraft]:
    return [
        _BlockDraft(
            id=_stable_block_id(
                session_id,
                "fixed",
                "".join(f"{len(block_id)}:{block_id}" for block_id in block.ids),
                0,
            ),
            block_type="fixed",
            label=" / ".join(block.labels),
            starts_at=block.starts_at,
            ends_at=block.ends_at,
            task_id=None,
        )
        for block in fixed
    ]


def _candidate(task: TaskItem) -> PlanCandidate:
    return PlanCandidate(
        task_id=task.id,
        minutes=task.conservative_minutes,
        source=task.estimate_source,
        confidence=task.estimate_confidence,
        must_do_tonight=task.must_do_tonight,
    )


def _stable_block_id(
    session_id: str,
    block_type: str,
    reference_id: str,
    segment: int,
) -> str:
    payload = "\x00".join((session_id, block_type, reference_id, str(segment)))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{block_type}-{digest}"


def _finalize_blocks(drafts: list[_BlockDraft]) -> list[PlanBlock]:
    ordered = sorted(
        drafts,
        key=lambda block: (
            block.starts_at,
            block.ends_at,
            block.block_type,
            block.id,
        ),
    )
    return [
        PlanBlock(
            id=block.id,
            block_type=block.block_type,
            label=block.label,
            starts_at=block.starts_at,
            ends_at=block.ends_at,
            ordinal=ordinal,
            task_id=block.task_id,
        )
        for ordinal, block in enumerate(ordered)
    ]
