from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from backend.contracts.models import (
    CapacityProof,
    CoverageDiff,
    CoverageMode,
    EveningSession,
    EstimateBreakdownItem,
    FixedBlock,
    LLMRun,
    ObservationEvent,
    PlanBlock,
    PlanVersion,
    ResponseEnvelope,
    SchoolBrief,
    SessionStage,
    Source,
    TaskCompletionState,
    TaskItem,
    TaskOutcome,
    ToolRun,
)


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


def _valid_models() -> list[tuple[type[Any], dict[str, Any]]]:
    capacity = {
        "available_minutes": 180,
        "fixed_minutes": 30,
        "task_minutes": 120,
        "buffer_minutes": 15,
        "required_minutes": 165,
        "remaining_minutes": 15,
        "shortfall_minutes": 0,
        "feasible": True,
    }
    return [
        (
            SchoolBrief,
            {
                "id": "brief-1",
                "brief_date": date(2026, 7, 11),
                "source_path": "data/school/2026-07-11.md",
                "content_sha256": "a" * 64,
                "raw_text": "Math exercises 1-4",
                "created_at": NOW,
            },
        ),
        (
            EveningSession,
            {
                "id": "session-1",
                "session_date": date(2026, 7, 11),
                "timezone": "Asia/Shanghai",
                "sleep_time": time(21, 30),
                "stage": SessionStage.CREATED,
                "version": 0,
                "available_minutes": 180,
                "school_brief_id": "brief-1",
                "created_at": NOW,
                "updated_at": NOW,
            },
        ),
        (
            TaskItem,
            {
                "id": "task-1",
                "session_id": "session-1",
                "title": "Math exercises 1-4",
                "subject": "math",
                "task_type": "written",
                "source": Source.SCHOOL,
                "completion_state": TaskCompletionState.PENDING,
                "estimated_minutes": 35,
                "conservative_minutes": 45,
                "priority": 1,
                "must_do_tonight": True,
                "child_estimate_minutes": 35,
                "estimate_source": "child_adjusted",
                "estimate_confidence": "low",
                "avoidance_score": 2,
                "preference_score": 1,
                "created_at": NOW,
                "updated_at": NOW,
            },
        ),
        (
            CoverageDiff,
            {
                "id": "diff-1",
                "session_id": "session-1",
                "mode": CoverageMode.SCHOOL_VERIFIED,
                "source": Source.BOTH,
                "summary": "School brief confirms the reported task",
                "resolved": True,
                "created_at": NOW,
            },
        ),
        (CapacityProof, capacity),
        (
            FixedBlock,
            {
                "id": "fixed-1",
                "label": "Dinner",
                "starts_at": NOW,
                "ends_at": NOW.replace(hour=12, minute=30),
                "source": Source.CHILD,
            },
        ),
        (
            PlanBlock,
            {
                "id": "block-1",
                "block_type": "task",
                "label": "Math exercises 1-4",
                "starts_at": NOW,
                "ends_at": NOW.replace(hour=12, minute=45),
                "ordinal": 0,
                "task_id": "task-1",
            },
        ),
        (
            PlanVersion,
            {
                "id": "plan-1",
                "session_id": "session-1",
                "version": 1,
                "stage": SessionStage.PLAN_DRAFT,
                "capacity": CapacityProof(**capacity),
                "blocks": [],
                "reason": "Initial feasible route",
                "committed": False,
                "created_at": NOW,
            },
        ),
        (
            ObservationEvent,
            {
                "id": "observation-1",
                "session_id": "session-1",
                "event_type": "task_reported",
                "source": Source.CHILD,
                "payload": {"task_id": "task-1"},
                "occurred_at": NOW,
                "created_at": NOW,
            },
        ),
        (
            TaskOutcome,
            {
                "id": "outcome-1",
                "session_id": "session-1",
                "task_id": "task-1",
                "completion_state": TaskCompletionState.COMPLETED,
                "actual_minutes": 40,
                "created_at": NOW,
            },
        ),
        (
            LLMRun,
            {
                "id": "llm-1",
                "trace_id": "trace-1",
                "ordinal": 1,
                "session_id": "session-1",
                "model": "gemma-4-26b-a4b-it",
                "request_sha256": "b" * 64,
                "generation_parameters": {"tool_choice": "none"},
                "finish_reason": "stop",
                "status": "completed",
                "started_at": NOW,
                "completed_at": NOW,
                "latency_ms": 125,
            },
        ),
        (
            ToolRun,
            {
                "id": "tool-1",
                "trace_id": "trace-1",
                "ordinal": 1,
                "session_id": "session-1",
                "llm_run_id": "llm-1",
                "tool_name": "get_planning_context",
                "call_id": "call-1",
                "arguments": {"session_id": "session-1"},
                "result": {"tasks": []},
                "cache_hit": False,
                "handler_executed": True,
                "status": "completed",
                "started_at": NOW,
                "completed_at": NOW,
                "latency_ms": 25,
            },
        ),
        (
            ResponseEnvelope[dict[str, str]],
            {
                "session_id": "session-1",
                "version": 1,
                "stage": SessionStage.PLAN_DRAFT,
                "allowed_actions": ["commit_plan"],
                "trace_id": "trace-1",
                "data": {"plan_id": "plan-1"},
            },
        ),
    ]


@pytest.mark.parametrize(("model_type", "payload"), _valid_models())
def test_business_models_reject_extra_fields(
    model_type: type[Any], payload: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model_type(**payload, unexpected="not allowed")


def test_capacity_proof_accepts_consistent_non_negative_arithmetic() -> None:
    proof = CapacityProof(
        available_minutes=180,
        fixed_minutes=30,
        task_minutes=120,
        buffer_minutes=15,
        required_minutes=165,
        remaining_minutes=15,
        shortfall_minutes=0,
        feasible=True,
    )

    assert proof.required_minutes == (
        proof.fixed_minutes + proof.task_minutes + proof.buffer_minutes
    )
    assert proof.remaining_minutes == 15
    assert proof.shortfall_minutes == 0


@pytest.mark.parametrize(
    "field",
    [
        "available_minutes",
        "fixed_minutes",
        "task_minutes",
        "buffer_minutes",
        "required_minutes",
        "remaining_minutes",
        "shortfall_minutes",
    ],
)
def test_capacity_proof_rejects_negative_arithmetic_fields(field: str) -> None:
    payload = {
        "available_minutes": 180,
        "fixed_minutes": 30,
        "task_minutes": 120,
        "buffer_minutes": 15,
        "required_minutes": 165,
        "remaining_minutes": 15,
        "shortfall_minutes": 0,
        "feasible": True,
    }
    payload[field] = -1

    with pytest.raises(ValidationError):
        CapacityProof(**payload)


def test_capacity_proof_rejects_inconsistent_arithmetic() -> None:
    with pytest.raises(ValidationError, match="capacity arithmetic is inconsistent"):
        CapacityProof(
            available_minutes=180,
            fixed_minutes=30,
            task_minutes=120,
            buffer_minutes=15,
            required_minutes=164,
            remaining_minutes=16,
            shortfall_minutes=0,
            feasible=True,
        )


def test_fixed_enum_values_are_exact() -> None:
    assert {item.value for item in SessionStage} == {
        "created",
        "intake_draft",
        "coverage_pending",
        "inventory_confirmed",
        "plan_draft",
        "committed",
        "closed",
        "capacity_conflict",
        "needs_confirmation",
        "model_unavailable",
    }
    assert {item.value for item in CoverageMode} == {
        "school_verified",
        "child_reported",
    }
    assert {item.value for item in TaskCompletionState} == {
        "pending",
        "partial",
        "completed",
        "uncertain",
        "no_task",
    }
    assert {item.value for item in Source} == {
        "child",
        "school",
        "both",
        "parent",
        "system",
    }


def test_task_item_accepts_planning_fields() -> None:
    payload = next(
        payload for model_type, payload in _valid_models() if model_type is TaskItem
    )

    task = TaskItem(**payload)

    assert task.task_type == "written"
    assert task.must_do_tonight is True
    assert task.child_estimate_minutes == 35
    assert task.estimate_source == "child_adjusted"
    assert task.estimate_confidence == "low"
    assert task.avoidance_score == 2
    assert task.preference_score == 1


def test_task_item_accepts_explainable_estimate_breakdown() -> None:
    payload = next(
        payload.copy()
        for model_type, payload in _valid_models()
        if model_type is TaskItem
    )
    payload["estimate_breakdown"] = (
        {
            "component": "reading_excerpt",
            "label": "阅读与摘录",
            "task_type": "reading",
            "remaining_quantity": 10,
            "unit": "页",
            "reference_minutes": 20,
            "calibrated_minutes": 25,
            "source": "parent_range",
            "confidence": "medium",
        },
    )
    payload["estimate_signature"] = "reading_excerpt"

    task = TaskItem(**payload)

    assert task.estimate_breakdown == (
        EstimateBreakdownItem(
            component="reading_excerpt",
            label="阅读与摘录",
            task_type="reading",
            remaining_quantity=10,
            unit="页",
            reference_minutes=20,
            calibrated_minutes=25,
            source="parent_range",
            confidence="medium",
        ),
    )
    assert task.estimate_signature == "reading_excerpt"


@pytest.mark.parametrize("field", ["avoidance_score", "preference_score"])
@pytest.mark.parametrize("value", [-1, 4])
def test_task_item_rejects_planning_score_outside_range(
    field: str,
    value: int,
) -> None:
    payload = next(
        payload.copy()
        for model_type, payload in _valid_models()
        if model_type is TaskItem
    )
    payload[field] = value

    with pytest.raises(ValidationError):
        TaskItem(**payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("child_estimate_minutes", -1),
        ("estimate_source", "guessed"),
        ("estimate_confidence", "certain"),
    ],
)
def test_task_item_rejects_invalid_planning_metadata(field: str, value: object) -> None:
    payload = next(
        payload.copy()
        for model_type, payload in _valid_models()
        if model_type is TaskItem
    )
    payload[field] = value

    with pytest.raises(ValidationError):
        TaskItem(**payload)
