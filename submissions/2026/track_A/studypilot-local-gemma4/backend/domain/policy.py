"""Deterministic task-ordering policy."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from itertools import groupby

from backend.contracts.models import TaskItem


_SECONDS_PER_DAY = 86_400
_MICROSECONDS_PER_SECOND = 1_000_000


def order_tasks(
    tasks: Sequence[TaskItem],
    preferred_order: Sequence[str] | None = None,
) -> list[TaskItem]:
    """Order tasks without allowing preferences to cross hard policy groups."""
    manual_rank = {
        task_id: index for index, task_id in enumerate(preferred_order or ())
    }
    ordered: list[TaskItem] = []
    previous_subject: str | None = None
    by_hard_group = sorted(tasks, key=lambda task: (_hard_group_key(task), task.id))

    for _, grouped in groupby(by_hard_group, key=_hard_group_key):
        group = list(grouped)
        manual = sorted(
            (task for task in group if task.id in manual_rank),
            key=lambda task: manual_rank[task.id],
        )
        remaining = [task for task in group if task.id not in manual_rank]
        group_order = manual + _order_policy_ties(
            remaining,
            _subject(manual[-1]) if manual else previous_subject,
        )
        ordered.extend(group_order)
        if group_order:
            previous_subject = _subject(group_order[-1])

    return ordered


def _hard_group_key(task: TaskItem) -> tuple[int, int, int, int]:
    deadline_key = 0
    if task.due_at is not None:
        deadline_key = _utc_microsecond_key(task.due_at)
    return (
        0 if task.must_do_tonight else 1,
        1 if task.due_at is None else 0,
        deadline_key,
        -task.avoidance_score,
    )


def _utc_microsecond_key(value: datetime) -> int:
    offset = value.utcoffset()
    if offset is None:
        raise ValueError("task deadlines must be timezone-aware")
    wall_seconds = (
        (value.toordinal() - 1) * _SECONDS_PER_DAY
        + value.hour * 3_600
        + value.minute * 60
        + value.second
    )
    wall_microseconds = (
        wall_seconds * _MICROSECONDS_PER_SECOND + value.microsecond
    )
    offset_microseconds = (
        (offset.days * _SECONDS_PER_DAY + offset.seconds)
        * _MICROSECONDS_PER_SECOND
        + offset.microseconds
    )
    return wall_microseconds - offset_microseconds


def _order_policy_ties(
    tasks: Sequence[TaskItem],
    previous_subject: str | None,
) -> list[TaskItem]:
    ordered: list[TaskItem] = []
    for preference_score in sorted(
        {task.preference_score for task in tasks},
        reverse=True,
    ):
        pool = [task for task in tasks if task.preference_score == preference_score]
        while pool:
            same_subject = [
                task for task in pool if _subject(task) == previous_subject
            ]
            if same_subject and previous_subject is not None:
                selected = min(same_subject, key=lambda task: task.id)
            else:
                subject_counts = {
                    subject: sum(_subject(task) == subject for task in pool)
                    for subject in {_subject(task) for task in pool}
                }
                selected_subject = min(
                    subject_counts,
                    key=lambda subject: (-subject_counts[subject], subject),
                )
                selected = min(
                    (task for task in pool if _subject(task) == selected_subject),
                    key=lambda task: task.id,
                )
            ordered.append(selected)
            pool.remove(selected)
            previous_subject = _subject(selected)
    return ordered


def _subject(task: TaskItem) -> str:
    return (task.subject or "").strip().casefold()
