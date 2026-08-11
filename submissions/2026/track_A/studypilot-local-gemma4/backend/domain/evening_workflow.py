"""Pure policy helpers for the lean child evening workflow."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from backend.contracts.models import PlanBlock, SessionStage, TaskCompletionState


_ACTIONS: dict[SessionStage, list[str]] = {
    SessionStage.CREATED: ["describe_homework"],
    SessionStage.INTAKE_DRAFT: ["add_intake_turn", "confirm_inventory"],
    SessionStage.INVENTORY_CONFIRMED: ["build_plan"],
    SessionStage.PLAN_DRAFT: ["reorder_plan", "commit_plan"],
    SessionStage.CAPACITY_CONFLICT: ["adjust_capacity"],
    SessionStage.COMMITTED: ["close_evening"],
    SessionStage.CLOSED: [],
    SessionStage.MODEL_UNAVAILABLE: ["add_intake_turn"],
    SessionStage.COVERAGE_PENDING: [],
    SessionStage.NEEDS_CONFIRMATION: [],
}


def allowed_actions(
    stage: SessionStage,
    *,
    plan_version: int | None = None,
) -> list[str]:
    if stage is SessionStage.PLAN_DRAFT and plan_version is not None:
        if plan_version >= 2:
            return ["commit_plan"]
    return list(_ACTIONS[stage])


def must_do_tonight(completion_state: TaskCompletionState) -> bool:
    return completion_state not in {
        TaskCompletionState.COMPLETED,
        TaskCompletionState.NO_TASK,
    }


def plan_scoped_blocks(plan_id: str, blocks: list[PlanBlock]) -> list[PlanBlock]:
    projected: list[PlanBlock] = []
    for block in blocks:
        digest = hashlib.sha256(
            f"{plan_id}\0{block.id}".encode("utf-8")
        ).hexdigest()[:24]
        projected.append(block.model_copy(update={"id": f"plan-block-{digest}"}))
    return projected


def predicted_finish_at(blocks: list[PlanBlock]) -> datetime | None:
    scheduled = [
        block.ends_at
        for block in blocks
        if block.block_type in {"task", "buffer"}
    ]
    return max(scheduled) if scheduled else None


def planning_horizon(sleep_at: datetime, available_minutes: int) -> datetime:
    return sleep_at - timedelta(minutes=available_minutes)
