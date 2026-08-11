"""Atomic SQLite aggregate repository for the lean evening workflow."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.contracts.evening import (
    IntakeDraftTask,
    IntakeFixedBlock,
    LargestDeviationInput,
    SaveIntakeDraftArguments,
)
from backend.contracts.models import (
    CoverageMode,
    EstimateBreakdownItem,
    FixedBlock,
    SessionStage,
    Source,
    TaskCompletionState,
    TaskItem,
)
from backend.domain.estimation import (
    EstimateEvidence,
    conservative_estimate,
    estimation_key,
)
from backend.domain.estimate_components import (
    build_reference_components,
    component_signature,
    estimate_component_snapshot,
    estimate_task_components,
)
from backend.domain.family_calibration import (
    FamilyCalibration,
    RatioObservation,
    build_family_calibration,
)
from backend.domain.deadlines import resolve_deadline
from backend.domain.evening_workflow import (
    must_do_tonight,
    plan_scoped_blocks,
    planning_horizon,
    predicted_finish_at,
)
from backend.domain.planning import PlanningActionError, PlanningRequest, build_plan
from backend.errors import (
    IdempotencyConflictError,
    InvalidTransitionError,
    NotFoundError,
    VersionConflictError,
)
from backend.storage.database import connect_database


Mutation = Callable[[sqlite3.Connection], dict[str, Any]]


class EveningWorkflowRepository:
    def __init__(
        self,
        database_path: str | Path,
        *,
        current_date: Callable[[], date] | None = None,
    ) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.current_date = current_date

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        connection = connect_database(self.database_path)
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def get(self, session_id: str) -> dict[str, Any]:
        with self._read_connection() as connection:
            return _load_view(connection, session_id)

    def get_latest(self, session_date: date) -> dict[str, Any]:
        with self._read_connection() as connection:
            row = connection.execute(
                """
                SELECT session_id AS id
                FROM daily_evening_sessions
                WHERE session_date = ?
                """,
                (session_date.isoformat(),),
            ).fetchone()
            if row is None:
                raise NotFoundError("evening_session", session_date.isoformat())
            return _load_view(connection, str(row["id"]))

    def get_session_date(self, session_id: str) -> date:
        with self._read_connection() as connection:
            session = _load_session(connection, session_id)
            return date.fromisoformat(str(session["session_date"]))

    def get_planning_date(self, session_id: str) -> date:
        with self._read_connection() as connection:
            session = _load_session(connection, session_id)
            return date.fromisoformat(
                str(session["planning_date"] or session["session_date"])
            )

    def _load_writable_session(
        self,
        connection: sqlite3.Connection,
        session_id: str,
    ) -> sqlite3.Row:
        session = _load_session(connection, session_id)
        authority = connection.execute(
            """
            SELECT session_id FROM daily_evening_sessions
            WHERE session_date = ?
            """,
            (str(session["session_date"]),),
        ).fetchone()
        is_authoritative = (
            authority is not None and str(authority["session_id"]) == session_id
        )
        is_current = (
            self.current_date is None
            or date.fromisoformat(str(session["session_date"])) == self.current_date()
        )
        if not is_authoritative or not is_current:
            raise InvalidTransitionError(
                str(session["stage"]),
                SessionStage.CLOSED.value,
            )
        return session

    def create(
        self,
        *,
        session_date: str,
        planning_date: str | None = None,
        timezone: str,
        sleep_time: str,
        available_minutes: int,
        expected_version: int,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> dict[str, Any]:
        if expected_version != 0:
            raise VersionConflictError("evening_session", session_date, 0, expected_version)
        key_hash = _sha256_text(session_date + chr(0) + caller_idempotency_key)
        session_id = f"evening-{key_hash[:24]}"
        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT session_id FROM daily_evening_sessions
                WHERE session_date = ?
                """,
                (session_date,),
            ).fetchone()
            if existing is not None:
                return {
                    "trace_id": trace_id,
                    "view": _load_view(connection, str(existing["session_id"])),
                }
            now = _now_text()
            effective_planning_date = planning_date or session_date
            connection.execute(
                """
                INSERT INTO evening_sessions (
                    id, session_date, planning_date, timezone, sleep_time, stage,
                    version, available_minutes, school_brief_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'created', 1, ?, NULL, ?, ?)
                """,
                (
                    session_id,
                    session_date,
                    effective_planning_date,
                    timezone,
                    sleep_time,
                    available_minutes,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO daily_evening_sessions (
                    session_date, session_id, registered_at
                ) VALUES (?, ?, ?)
                """,
                (session_date, session_id, now),
            )
            return {"trace_id": trace_id, "view": _load_view(connection, session_id)}

    def reset_demo_today(
        self,
        *,
        session_date: str,
        planning_date: str | None = None,
        timezone: str,
        sleep_time: str,
        available_minutes: int,
        expected_session_id: str | None,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> dict[str, Any]:
        request = {
            "session_date": session_date,
            "planning_date": planning_date or session_date,
            "timezone": timezone,
            "sleep_time": sleep_time,
            "available_minutes": available_minutes,
            "expected_session_id": expected_session_id,
        }
        key_hash = _sha256_text(caller_idempotency_key)
        session_id = f"evening-demo-{_sha256_text(session_date + chr(0) + key_hash)[:19]}"

        def mutate(connection: sqlite3.Connection) -> dict[str, Any]:
            authority = connection.execute(
                """
                SELECT session_id FROM daily_evening_sessions
                WHERE session_date = ?
                """,
                (session_date,),
            ).fetchone()
            actual_session_id = (
                None if authority is None else str(authority["session_id"])
            )
            if actual_session_id != expected_session_id:
                raise InvalidTransitionError(
                    "demo_session_changed",
                    "demo_reset",
                )

            now = _now_text()
            effective_planning_date = planning_date or session_date
            connection.execute(
                """
                INSERT INTO evening_sessions (
                    id, session_date, planning_date, timezone, sleep_time, stage,
                    version, available_minutes, school_brief_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'created', 1, ?, NULL, ?, ?)
                """,
                (
                    session_id,
                    session_date,
                    effective_planning_date,
                    timezone,
                    sleep_time,
                    available_minutes,
                    now,
                    now,
                ),
            )
            if authority is None:
                connection.execute(
                    """
                    INSERT INTO daily_evening_sessions (
                        session_date, session_id, registered_at
                    ) VALUES (?, ?, ?)
                    """,
                    (session_date, session_id, now),
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE daily_evening_sessions
                    SET session_id = ?, registered_at = ?
                    WHERE session_date = ? AND session_id = ?
                    """,
                    (session_id, now, session_date, expected_session_id),
                )
                if cursor.rowcount != 1:
                    raise InvalidTransitionError(
                        "demo_session_changed",
                        "demo_reset",
                    )
            return {
                "trace_id": trace_id,
                "view": _load_view(connection, session_id),
            }

        return self._idempotent(
            operation=f"demo:reset:{session_date}",
            caller_key=caller_idempotency_key,
            request=request,
            mutate=mutate,
        )

    def append_raw_intake(
        self,
        *,
        session_id: str,
        text: str,
        expected_version: int,
        caller_idempotency_key: str,
    ) -> None:
        key_hash = _sha256_text(caller_idempotency_key)
        event_id = f"intake-raw-{_sha256_text(session_id + chr(0) + key_hash)[:24]}"
        payload = {
            "text": text,
            "caller_idempotency_sha256": key_hash,
        }
        encoded = _canonical_json(payload)
        with self._transaction() as connection:
            session = self._load_writable_session(connection, session_id)
            _require_version(session, expected_version)
            _require_stage(
                session,
                {
                    SessionStage.CREATED,
                    SessionStage.INTAKE_DRAFT,
                    SessionStage.MODEL_UNAVAILABLE,
                },
                SessionStage.INTAKE_DRAFT,
            )
            existing = connection.execute(
                "SELECT payload_json FROM observation_events WHERE id = ?",
                (event_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["payload_json"]) != encoded:
                    raise IdempotencyConflictError(
                        f"evening:intake-raw:{session_id}", key_hash
                    )
                return
            now = _now_text()
            connection.execute(
                """
                INSERT INTO observation_events (
                    id, session_id, event_type, source, payload_json,
                    occurred_at, created_at
                ) VALUES (?, ?, 'intake_raw', 'child', ?, ?, ?)
                """,
                (event_id, session_id, encoded, now, now),
            )

    def save_intake_draft(
        self,
        *,
        session_id: str,
        arguments: SaveIntakeDraftArguments,
        expected_version: int,
        hidden_idempotency_key: str,
        coverage_mode: CoverageMode = CoverageMode.CHILD_REPORTED,
        school_brief_id: str | None = None,
    ) -> dict[str, Any]:
        if (coverage_mode is CoverageMode.SCHOOL_VERIFIED) != bool(school_brief_id):
            raise ValueError("school coverage provenance must be server-aligned")
        request = {
            "session_id": session_id,
            "expected_version": expected_version,
            "arguments": arguments.model_dump(mode="json"),
            "coverage_mode": coverage_mode.value,
            "school_brief_id": school_brief_id,
        }

        def mutate(connection: sqlite3.Connection) -> dict[str, Any]:
            session = self._load_writable_session(connection, session_id)
            _require_version(session, expected_version)
            _require_stage(
                session,
                {
                    SessionStage.CREATED,
                    SessionStage.INTAKE_DRAFT,
                    SessionStage.MODEL_UNAVAILABLE,
                },
                SessionStage.INTAKE_DRAFT,
            )
            draft_id = f"intake-draft-{uuid4()}"
            dumped_arguments = arguments.model_dump(mode="json")
            payload = {
                "id": draft_id,
                "tasks": dumped_arguments["tasks"],
                "fixed_blocks": dumped_arguments["fixed_blocks"],
                "coverage_notes": dumped_arguments["coverage_notes"],
                "coverage_mode": coverage_mode.value,
                "school_brief_id": school_brief_id,
            }
            now = _now_text()
            connection.execute(
                """
                INSERT INTO observation_events (
                    id, session_id, event_type, source, payload_json,
                    occurred_at, created_at
                ) VALUES (?, ?, 'intake_draft', ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    session_id,
                    (
                        Source.BOTH.value
                        if coverage_mode is CoverageMode.SCHOOL_VERIFIED
                        else Source.CHILD.value
                    ),
                    _canonical_json(payload),
                    now,
                    now,
                ),
            )
            _advance_session(
                connection,
                session_id,
                expected_version,
                SessionStage.INTAKE_DRAFT,
                now,
            )
            return {
                "draft": payload,
                "version": expected_version + 1,
                "stage": SessionStage.INTAKE_DRAFT.value,
            }

        return self._idempotent(
            operation=f"evening:intake-tool:{session_id}",
            caller_key=hidden_idempotency_key,
            request=request,
            mutate=mutate,
        )

    def get_intake_transcript(self, session_id: str) -> str:
        with self._read_connection() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM observation_events
                WHERE session_id = ? AND event_type = 'intake_raw'
                ORDER BY occurred_at, id
                """,
                (session_id,),
            ).fetchall()
        turns = [str(json.loads(row["payload_json"])["text"]) for row in rows]
        return "\n".join(
            f"<child_turn index=\"{index}\">{text}</child_turn>"
            for index, text in enumerate(turns, start=1)
        )

    def mark_model_unavailable(
        self,
        *,
        session_id: str,
        expected_version: int,
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            session = self._load_writable_session(connection, session_id)
            _require_version(session, expected_version)
            _require_stage(
                session,
                {
                    SessionStage.CREATED,
                    SessionStage.INTAKE_DRAFT,
                    SessionStage.MODEL_UNAVAILABLE,
                },
                SessionStage.MODEL_UNAVAILABLE,
            )
            _advance_session(
                connection,
                session_id,
                expected_version,
                SessionStage.MODEL_UNAVAILABLE,
                _now_text(),
            )
            return _load_view(connection, session_id)

    def confirm_inventory(
        self,
        *,
        session_id: str,
        expected_version: int,
        profile_version: int,
        parent_high_minutes: tuple[int | None, ...],
        family_ratio_observations: tuple[RatioObservation, ...] = (),
        caller_idempotency_key: str,
        trace_id: str,
    ) -> dict[str, Any]:
        request = {"session_id": session_id, "expected_version": expected_version}

        def mutate(connection: sqlite3.Connection) -> dict[str, Any]:
            session = self._load_writable_session(connection, session_id)
            _require_version(session, expected_version)
            _require_stage(
                session,
                {SessionStage.INTAKE_DRAFT},
                SessionStage.INVENTORY_CONFIRMED,
            )
            draft = _load_latest_draft(connection, session_id)
            if draft is None:
                raise InvalidTransitionError(
                    SessionStage.INTAKE_DRAFT.value,
                    SessionStage.INVENTORY_CONFIRMED.value,
                )
            if len(parent_high_minutes) != len(draft["tasks"]):
                raise ValueError("parent estimation evidence must align with draft tasks")
            now = _now()
            calibration = build_family_calibration(family_ratio_observations)
            planning_date = date.fromisoformat(
                str(session["planning_date"] or session["session_date"])
            )
            for index, raw_task in enumerate(draft["tasks"]):
                task_input = IntakeDraftTask.model_validate_json(
                    _canonical_json(raw_task)
                )
                task_id = _stable_id("task", session_id, draft["id"], str(index))
                deadline_text = task_input.deadline_text
                deadline = resolve_deadline(
                    deadline_text,
                    planning_date,
                    str(session["timezone"]),
                )
                active = must_do_tonight(task_input.completion_state)
                task_must_do = deadline.must_do_tonight and active
                remaining_percent = _remaining_percent(task_input)
                _, task_type = estimation_key(
                    task_input.subject,
                    None,
                    title=task_input.title,
                )
                planning_bucket = (
                    "future_scheduled"
                    if active and deadline.planned_evening_date is not None
                    else "tonight_required" if task_must_do else "tonight_advance"
                )
                assignment_id = (
                    _stable_id("assignment", session_id, task_id) if active else None
                )
                task = TaskItem(
                    id=task_id,
                    session_id=session_id,
                    title=task_input.title,
                    subject=task_input.subject,
                    task_type=task_type,
                    source=Source.CHILD,
                    completion_state=task_input.completion_state,
                    estimated_minutes=task_input.child_estimate_minutes or 0,
                    conservative_minutes=0,
                    priority=index,
                    must_do_tonight=task_must_do,
                    child_estimate_minutes=task_input.child_estimate_minutes,
                    estimate_source="domain_default",
                    estimate_confidence="low",
                    avoidance_score=0,
                    preference_score=0,
                    due_at=deadline.due_at,
                    school_brief_id=None,
                    notes=task_input.notes,
                    assignment_id=assignment_id,
                    deadline_text=deadline_text,
                    remaining_percent=remaining_percent,
                    planning_bucket=planning_bucket,
                    planned_evening_date=deadline.planned_evening_date,
                    created_at=now,
                    updated_at=now,
                )
                reference_breakdown = build_reference_components(task_input)
                estimate_signature = (
                    component_signature(reference_breakdown)
                    if reference_breakdown
                    else None
                )
                estimate = estimate_task_components(
                    task_input,
                    calibration=calibration,
                    history_minutes=_completed_history_minutes(
                        connection,
                        subject=task.subject,
                        estimate_signature=estimate_signature,
                        before_date=date.fromisoformat(str(session["session_date"])),
                    ),
                    legacy_parent_minutes=parent_high_minutes[index],
                )
                estimated_minutes = (
                    task_input.child_estimate_minutes
                    if task_input.child_estimate_minutes is not None
                    else sum(
                        component.reference_minutes
                        for component in estimate.breakdown
                    )
                )
                estimate_breakdown_json = _canonical_json(
                    [
                        component.model_dump(mode="json")
                        for component in estimate.breakdown
                    ]
                )
                if assignment_id is not None:
                    connection.execute(
                        """
                        INSERT INTO assignment_obligations (
                            id, origin_session_id, title, subject, task_type,
                            deadline_text, due_at, latest_safe_evening,
                            planned_evening_date, remaining_percent, status,
                            created_at, updated_at, estimate_breakdown_json,
                            estimate_signature
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 'open', ?, ?, ?, ?)
                        """,
                        (
                            assignment_id,
                            session_id,
                            task.title,
                            task.subject,
                            task_type,
                            deadline_text,
                            _iso(task.due_at) if task.due_at is not None else None,
                            (
                                deadline.latest_safe_evening.isoformat()
                                if deadline.latest_safe_evening is not None
                                else None
                            ),
                            remaining_percent,
                            _iso(now),
                            _iso(now),
                            estimate_breakdown_json,
                            estimate.signature,
                        ),
                    )
                connection.execute(
                    """
                    INSERT INTO task_items (
                        id, session_id, school_brief_id, title, subject, source,
                        completion_state, estimated_minutes, conservative_minutes,
                        priority, due_at, notes, created_at, updated_at, task_type,
                        must_do_tonight, child_estimate_minutes, estimate_source,
                        estimate_confidence, avoidance_score, preference_score,
                        assignment_id, deadline_text, remaining_percent, planning_bucket,
                        planned_evening_date, estimate_breakdown_json, estimate_signature
                    ) VALUES (?, ?, NULL, ?, ?, 'child', ?, ?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        session_id,
                        task_input.title,
                        task_input.subject,
                        task_input.completion_state.value,
                        estimated_minutes,
                        estimate.minutes,
                        index,
                        _iso(task.due_at) if task.due_at is not None else None,
                        task_input.notes,
                        _iso(now),
                        _iso(now),
                        task_type,
                        int(task.must_do_tonight),
                        task_input.child_estimate_minutes,
                        estimate.source,
                        estimate.confidence,
                        assignment_id,
                        deadline_text,
                        remaining_percent,
                        planning_bucket,
                        (
                            deadline.planned_evening_date.isoformat()
                            if deadline.planned_evening_date is not None
                            else None
                        ),
                        estimate_breakdown_json,
                        estimate.signature,
                    ),
                )
            _carry_due_assignments(
                connection,
                session=session,
                session_id=session_id,
                planning_date=planning_date,
                now=now,
                calibration=calibration,
            )
            _advance_session(
                connection,
                session_id,
                expected_version,
                SessionStage.INVENTORY_CONFIRMED,
                _iso(now),
            )
            return {
                "trace_id": trace_id,
                "estimation_context": {
                    "profile_version": profile_version,
                    "parent_high_minutes": list(parent_high_minutes),
                    "family_ratio_observations": len(family_ratio_observations),
                },
                "view": _load_view(connection, session_id),
            }

        return self._idempotent(
            operation=f"evening:confirm:{session_id}",
            caller_key=caller_idempotency_key,
            request=request,
            mutate=mutate,
        )

    def build_plan(
        self,
        *,
        session_id: str,
        expected_version: int,
        reason: str,
        preferred_order: list[str] | None,
        deadline_risk_task_ids: list[str],
        caller_idempotency_key: str,
        trace_id: str,
    ) -> dict[str, Any]:
        request = {
            "session_id": session_id,
            "expected_version": expected_version,
            "reason": reason,
            "preferred_order": preferred_order,
            "deadline_risk_task_ids": deadline_risk_task_ids,
        }

        def mutate(connection: sqlite3.Connection) -> dict[str, Any]:
            session = self._load_writable_session(connection, session_id)
            _require_version(session, expected_version)
            _require_stage(
                session,
                {
                    SessionStage.INVENTORY_CONFIRMED,
                    SessionStage.PLAN_DRAFT,
                    SessionStage.CAPACITY_CONFLICT,
                },
                SessionStage.PLAN_DRAFT,
            )
            current_plan_version = int(
                connection.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM plans WHERE session_id = ?",
                    (session_id,),
                ).fetchone()[0]
            )
            tasks = _load_task_models(connection, session_id)
            sleep_at = _sleep_at(session)
            draft = _load_latest_draft(connection, session_id)
            try:
                result = build_plan(
                    PlanningRequest(
                        session_id=session_id,
                        now=planning_horizon(
                            sleep_at,
                            int(session["available_minutes"]),
                        ),
                        sleep_at=sleep_at,
                        tasks=tasks,
                        fixed_blocks=_fixed_block_models(session_id, session, draft),
                        adaptation_mode=True,
                        preferred_order=preferred_order,
                        deadline_risk_task_ids=deadline_risk_task_ids,
                        reason=reason,
                    )
                )
            except PlanningActionError as error:
                raise InvalidTransitionError(str(session["stage"]), reason) from error
            ordered_ids = set(result.ordered_task_ids)
            for task in tasks:
                if task.must_do_tonight:
                    bucket = "tonight_required"
                elif task.id in ordered_ids:
                    bucket = "tonight_advance"
                elif task.planned_evening_date is not None:
                    bucket = "future_scheduled"
                else:
                    bucket = "tonight_advance"
                connection.execute(
                    "UPDATE task_items SET planning_bucket = ? WHERE id = ?",
                    (bucket, task.id),
                )
            plan_version = current_plan_version + 1
            plan_id = _stable_id("plan", session_id, str(plan_version))
            blocks = plan_scoped_blocks(plan_id, result.blocks)
            task_lookup = {task.id: task for task in tasks}
            scheduled_optional_minutes = sum(
                task_lookup[task_id].conservative_minutes
                for task_id in result.ordered_task_ids
                if not task_lookup[task_id].must_do_tonight
            )
            true_surplus_minutes = max(
                result.capacity.remaining_minutes - scheduled_optional_minutes,
                0,
            )
            metadata = {
                "capacity": result.capacity.model_dump(mode="json"),
                "baseline_capacity": result.baseline_capacity.model_dump(mode="json"),
                "ordered_task_ids": result.ordered_task_ids,
                "deferred_task_ids": result.deferred_task_ids,
                "future_scheduled_task_ids": result.future_scheduled_task_ids,
                "deadline_risk_task_ids": result.deadline_risk_task_ids,
                "capacity_recovery": (
                    result.capacity_recovery.model_dump(mode="json")
                    if result.capacity_recovery is not None
                    else None
                ),
                "pace_targets": [
                    target.model_dump(mode="json") for target in result.pace_targets
                ],
                "scheduled_optional_minutes": scheduled_optional_minutes,
                "true_surplus_minutes": true_surplus_minutes,
                "predicted_finish_at": (
                    _iso(predicted_finish_at(blocks))
                    if predicted_finish_at(blocks) is not None
                    else None
                ),
            }
            now = _now_text()
            connection.execute(
                """
                INSERT INTO plans (
                    id, session_id, version, stage, capacity_json, reason,
                    committed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    plan_id,
                    session_id,
                    plan_version,
                    result.stage,
                    _canonical_json(metadata),
                    reason,
                    now,
                ),
            )
            for block in blocks:
                connection.execute(
                    """
                    INSERT INTO plan_blocks (
                        id, plan_id, task_id, block_type, label,
                        starts_at, ends_at, ordinal, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        block.id,
                        plan_id,
                        block.task_id,
                        block.block_type,
                        block.label,
                        _iso(block.starts_at),
                        _iso(block.ends_at),
                        block.ordinal,
                        now,
                    ),
                )
            stage = SessionStage(result.stage)
            _advance_session(
                connection,
                session_id,
                expected_version,
                stage,
                now,
            )
            return {"trace_id": trace_id, "view": _load_view(connection, session_id)}

        return self._idempotent(
            operation=f"evening:plan:{session_id}",
            caller_key=caller_idempotency_key,
            request=request,
            mutate=mutate,
        )

    def update_time_boundary(
        self,
        *,
        session_id: str,
        expected_version: int,
        sleep_time: str,
        available_minutes: int,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> dict[str, Any]:
        request = {
            "session_id": session_id,
            "expected_version": expected_version,
            "sleep_time": sleep_time,
            "available_minutes": available_minutes,
        }

        def mutate(connection: sqlite3.Connection) -> dict[str, Any]:
            session = self._load_writable_session(connection, session_id)
            _require_version(session, expected_version)
            stage = SessionStage(str(session["stage"]))
            allowed = {
                SessionStage.CREATED,
                SessionStage.INTAKE_DRAFT,
                SessionStage.INVENTORY_CONFIRMED,
                SessionStage.PLAN_DRAFT,
                SessionStage.CAPACITY_CONFLICT,
                SessionStage.MODEL_UNAVAILABLE,
            }
            if stage not in allowed:
                raise InvalidTransitionError(stage.value, "update_time_boundary")
            next_stage = (
                SessionStage.INVENTORY_CONFIRMED
                if stage in {SessionStage.PLAN_DRAFT, SessionStage.CAPACITY_CONFLICT}
                else stage
            )
            plan_ids = [
                str(row["id"])
                for row in connection.execute(
                    "SELECT id FROM plans WHERE session_id = ? AND committed = 0",
                    (session_id,),
                )
            ]
            for plan_id in plan_ids:
                connection.execute("DELETE FROM plan_blocks WHERE plan_id = ?", (plan_id,))
            connection.execute(
                "DELETE FROM plans WHERE session_id = ? AND committed = 0",
                (session_id,),
            )
            now = _now_text()
            connection.execute(
                """
                UPDATE evening_sessions
                SET sleep_time = ?, available_minutes = ?, stage = ?,
                    version = version + 1, updated_at = ?
                WHERE id = ? AND version = ?
                """,
                (
                    sleep_time,
                    available_minutes,
                    next_stage.value,
                    now,
                    session_id,
                    expected_version,
                ),
            )
            return {"trace_id": trace_id, "view": _load_view(connection, session_id)}

        return self._idempotent(
            operation=f"evening:time-boundary:{session_id}",
            caller_key=caller_idempotency_key,
            request=request,
            mutate=mutate,
        )

    def commit_plan(
        self,
        *,
        session_id: str,
        plan_id: str,
        expected_version: int,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> dict[str, Any]:
        request = {
            "session_id": session_id,
            "plan_id": plan_id,
            "expected_version": expected_version,
        }

        def mutate(connection: sqlite3.Connection) -> dict[str, Any]:
            session = self._load_writable_session(connection, session_id)
            _require_version(session, expected_version)
            _require_stage(
                session,
                {SessionStage.PLAN_DRAFT},
                SessionStage.COMMITTED,
            )
            latest = _load_latest_plan_row(connection, session_id)
            if latest is None or str(latest["id"]) != plan_id:
                raise NotFoundError("plan", plan_id)
            planning_date = date.fromisoformat(
                str(session["planning_date"] or session["session_date"])
            )
            now = _now_text()
            future_rows = connection.execute(
                """
                SELECT tasks.assignment_id, obligations.planned_evening_date,
                       obligations.latest_safe_evening
                FROM task_items AS tasks
                JOIN assignment_obligations AS obligations
                  ON obligations.id = tasks.assignment_id
                WHERE tasks.session_id = ?
                  AND tasks.planning_bucket = 'future_scheduled'
                  AND obligations.status = 'open'
                ORDER BY tasks.id
                """,
                (session_id,),
            ).fetchall()
            for row in future_rows:
                latest_safe = (
                    date.fromisoformat(str(row["latest_safe_evening"]))
                    if row["latest_safe_evening"] is not None
                    else None
                )
                planned_date = _provisional_evening(planning_date, latest_safe)
                if planned_date is None:
                    continue
                assignment_id = str(row["assignment_id"])
                connection.execute(
                    """
                    INSERT INTO assignment_schedule_events (
                        id, assignment_id, session_id, from_evening_date,
                        to_evening_date, reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _stable_id("assignment-schedule", plan_id, assignment_id),
                        assignment_id,
                        session_id,
                        row["planned_evening_date"],
                        planned_date.isoformat(),
                        "今晚容量优先留给更早截止任务",
                        now,
                    ),
                )
                connection.execute(
                    """
                    UPDATE assignment_obligations
                    SET planned_evening_date = ?, updated_at = ?
                    WHERE id = ? AND status = 'open'
                    """,
                    (planned_date.isoformat(), now, assignment_id),
                )
            connection.execute(
                "UPDATE plans SET committed = 1 WHERE id = ?",
                (plan_id,),
            )
            _advance_session(
                connection,
                session_id,
                expected_version,
                SessionStage.COMMITTED,
                now,
            )
            return {"trace_id": trace_id, "view": _load_view(connection, session_id)}

        return self._idempotent(
            operation=f"evening:commit:{session_id}:{plan_id}",
            caller_key=caller_idempotency_key,
            request=request,
            mutate=mutate,
        )

    def close(
        self,
        *,
        session_id: str,
        expected_version: int,
        unfinished_task_ids: list[str],
        largest_deviation: LargestDeviationInput | None,
        note: str | None,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> dict[str, Any]:
        request = {
            "session_id": session_id,
            "expected_version": expected_version,
            "unfinished_task_ids": unfinished_task_ids,
            "largest_deviation": (
                largest_deviation.model_dump(mode="json")
                if largest_deviation is not None
                else None
            ),
            "note": note,
        }

        def mutate(connection: sqlite3.Connection) -> dict[str, Any]:
            session = self._load_writable_session(connection, session_id)
            _require_version(session, expected_version)
            _require_stage(
                session,
                {SessionStage.COMMITTED},
                SessionStage.CLOSED,
            )
            latest = _load_latest_plan_row(connection, session_id)
            if latest is None or not bool(latest["committed"]):
                raise InvalidTransitionError(
                    SessionStage.COMMITTED.value,
                    SessionStage.CLOSED.value,
                )
            scheduled_ids = {
                str(row["task_id"])
                for row in connection.execute(
                    """
                    SELECT DISTINCT task_id FROM plan_blocks
                    WHERE plan_id = ? AND block_type = 'task' AND task_id IS NOT NULL
                    """,
                    (str(latest["id"]),),
                )
            }
            unfinished = set(unfinished_task_ids)
            if len(unfinished) != len(unfinished_task_ids) or not unfinished <= scheduled_ids:
                raise InvalidTransitionError(
                    SessionStage.COMMITTED.value,
                    SessionStage.CLOSED.value,
                )
            if (
                largest_deviation is not None
                and largest_deviation.task_id not in scheduled_ids
            ):
                raise InvalidTransitionError(
                    SessionStage.COMMITTED.value,
                    SessionStage.CLOSED.value,
                )
            now = _now_text()
            for task_id in sorted(scheduled_ids):
                is_unfinished = task_id in unfinished
                actual_minutes = (
                    largest_deviation.actual_minutes
                    if largest_deviation is not None
                    and largest_deviation.task_id == task_id
                    else None
                )
                connection.execute(
                    """
                    INSERT INTO task_outcomes (
                        id, session_id, task_id, completion_state,
                        actual_minutes, note, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _stable_id("outcome", session_id, task_id),
                        session_id,
                        task_id,
                        "pending" if is_unfinished else "completed",
                        actual_minutes,
                        note if is_unfinished else None,
                        now,
                    ),
                )
                task_row = connection.execute(
                    "SELECT assignment_id FROM task_items WHERE id = ?",
                    (task_id,),
                ).fetchone()
                assignment_id = (
                    None if task_row is None else task_row["assignment_id"]
                )
                if assignment_id is not None and not is_unfinished:
                    connection.execute(
                        """
                        UPDATE assignment_obligations
                        SET status = 'completed', remaining_percent = 0,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (now, assignment_id),
                    )
                elif assignment_id is not None:
                    planning_date = date.fromisoformat(
                        str(session["planning_date"] or session["session_date"])
                    )
                    next_candidate = planning_date + timedelta(days=1)
                    previous = connection.execute(
                        "SELECT planned_evening_date, latest_safe_evening "
                        "FROM assignment_obligations WHERE id = ?",
                        (assignment_id,),
                    ).fetchone()
                    latest_safe = (
                        date.fromisoformat(str(previous["latest_safe_evening"]))
                        if previous is not None
                        and previous["latest_safe_evening"] is not None
                        else None
                    )
                    has_deadline_risk = (
                        latest_safe is not None and next_candidate > latest_safe
                    )
                    next_date = latest_safe if has_deadline_risk else next_candidate
                    schedule_reason = (
                        "今晚未完成，已到最晚安全晚；标记截止风险并在下一晚优先复核"
                        if has_deadline_risk
                        else "今晚未完成，下一晚优先复核"
                    )
                    connection.execute(
                        """
                        UPDATE assignment_obligations
                        SET planned_evening_date = ?, updated_at = ?
                        WHERE id = ? AND status = 'open'
                        """,
                        (next_date.isoformat(), now, assignment_id),
                    )
                    connection.execute(
                        """
                        INSERT INTO assignment_schedule_events (
                            id, assignment_id, session_id, from_evening_date,
                            to_evening_date, reason, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _stable_id("assignment-unfinished", session_id, str(assignment_id)),
                            assignment_id,
                            session_id,
                            (
                                None
                                if previous is None
                                else previous["planned_evening_date"]
                            ),
                            next_date.isoformat(),
                            schedule_reason,
                            now,
                        ),
                    )
            _advance_session(
                connection,
                session_id,
                expected_version,
                SessionStage.CLOSED,
                now,
            )
            return {"trace_id": trace_id, "view": _load_view(connection, session_id)}

        return self._idempotent(
            operation=f"evening:close:{session_id}",
            caller_key=caller_idempotency_key,
            request=request,
            mutate=mutate,
        )

    def _idempotent(
        self,
        *,
        operation: str,
        caller_key: str,
        request: dict[str, Any],
        mutate: Mutation,
    ) -> dict[str, Any]:
        key_hash = _sha256_text(caller_key)
        request_hash = _sha256_text(_canonical_json(request))
        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT request_hash, response_json FROM idempotency_records
                WHERE operation = ? AND idempotency_key = ?
                """,
                (operation, key_hash),
            ).fetchone()
            if existing is not None:
                if str(existing["request_hash"]) != request_hash:
                    raise IdempotencyConflictError(operation, key_hash)
                response = json.loads(str(existing["response_json"]))
                if not isinstance(response, dict):
                    raise TypeError("stored evening response must be an object")
                return response
            response = mutate(connection)
            connection.execute(
                """
                INSERT INTO idempotency_records (
                    operation, idempotency_key, request_hash, response_json
                ) VALUES (?, ?, ?, ?)
                """,
                (operation, key_hash, request_hash, _canonical_json(response)),
            )
            return response


def _load_view(connection: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    session = _load_session(connection, session_id)
    stage = SessionStage(str(session["stage"]))
    inventory = [_task_view(row) for row in _load_task_rows(connection, session_id)]
    draft = _load_latest_draft(connection, session_id)
    coverage_mode = None
    if inventory:
        stored_mode = draft.get("coverage_mode") if draft is not None else None
        coverage_mode = CoverageMode(
            stored_mode or CoverageMode.CHILD_REPORTED.value
        ).value
    available_minutes = int(session["available_minutes"])
    sleep_value = time.fromisoformat(str(session["sleep_time"]))
    sleep_minutes = sleep_value.hour * 60 + sleep_value.minute
    start_minutes = sleep_minutes - available_minutes
    start_value = time(start_minutes // 60, start_minutes % 60)
    fixed_minutes = _fixed_minutes_for_view(
        draft,
        start_minutes=start_minutes,
        sleep_minutes=sleep_minutes,
    )
    return {
        "session_id": session_id,
        "session_date": str(session["session_date"]),
        "planning_date": str(session["planning_date"] or session["session_date"]),
        "version": int(session["version"]),
        "stage": stage.value,
        "intake_draft": draft,
        "coverage_mode": coverage_mode,
        "inventory": inventory,
        "plan": _load_latest_plan(connection, session_id),
        "outcomes": [
            {
                "id": str(row["id"]),
                "task_id": str(row["task_id"]),
                "completion_state": str(row["completion_state"]),
                "actual_minutes": row["actual_minutes"],
                "note": row["note"],
            }
            for row in connection.execute(
                """
                SELECT id, task_id, completion_state, actual_minutes, note
                FROM task_outcomes WHERE session_id = ? ORDER BY task_id
                """,
                (session_id,),
            )
        ],
        "time_boundary": {
            "start_time": start_value.isoformat(),
            "sleep_time": sleep_value.isoformat(),
            "gross_minutes": available_minutes,
            "fixed_minutes": fixed_minutes,
            "net_minutes": max(available_minutes - fixed_minutes, 0),
        },
        "future_assignments": _load_future_assignments(connection, session),
    }


def _load_future_assignments(
    connection: sqlite3.Connection,
    session: sqlite3.Row,
) -> list[dict[str, Any]]:
    planning_date = str(session["planning_date"] or session["session_date"])
    session_id = str(session["id"])
    demo_only = int(session_id.startswith("evening-demo-"))
    return [
        {
            "assignment_id": str(row["id"]),
            "title": str(row["title"]),
            "subject": row["subject"],
            "deadline_text": row["deadline_text"],
            "due_at": row["due_at"],
            "planned_evening_date": str(row["planned_evening_date"]),
            "remaining_percent": int(row["remaining_percent"]),
            "latest_change_reason": row["latest_change_reason"],
        }
        for row in connection.execute(
            """
            SELECT assignments.*,
                   (
                       SELECT events.reason
                       FROM assignment_schedule_events AS events
                       WHERE events.assignment_id = assignments.id
                       ORDER BY events.created_at DESC, events.rowid DESC
                       LIMIT 1
                   ) AS latest_change_reason
            FROM assignment_obligations AS assignments
            JOIN evening_sessions AS origin
              ON origin.id = assignments.origin_session_id
            JOIN daily_evening_sessions AS authority
              ON authority.session_date = origin.session_date
             AND authority.session_id = origin.id
            WHERE assignments.status = 'open'
              AND assignments.planned_evening_date > ?
              AND (? = 0 OR assignments.origin_session_id = ?)
            ORDER BY assignments.planned_evening_date, assignments.due_at,
                     assignments.id
            """,
            (planning_date, demo_only, session_id),
        )
    ]


def _fixed_minutes_for_view(
    draft: dict[str, Any] | None,
    *,
    start_minutes: int,
    sleep_minutes: int,
) -> int:
    if draft is None:
        return 0
    intervals: list[tuple[int, int]] = []
    for raw in draft.get("fixed_blocks", []):
        block = IntakeFixedBlock.model_validate_json(_canonical_json(raw))
        block_start = block.start_time.hour * 60 + block.start_time.minute
        block_end = block.end_time.hour * 60 + block.end_time.minute
        clipped = (max(block_start, start_minutes), min(block_end, sleep_minutes))
        if clipped[0] < clipped[1]:
            intervals.append(clipped)
    merged: list[list[int]] = []
    for interval_start, interval_end in sorted(intervals):
        if not merged or interval_start > merged[-1][1]:
            merged.append([interval_start, interval_end])
        else:
            merged[-1][1] = max(merged[-1][1], interval_end)
    return sum(interval_end - interval_start for interval_start, interval_end in merged)


def _load_session(connection: sqlite3.Connection, session_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM evening_sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("evening_session", session_id)
    return row


def _load_latest_draft(
    connection: sqlite3.Connection,
    session_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT payload_json FROM observation_events
        WHERE session_id = ? AND event_type = 'intake_draft'
        ORDER BY created_at DESC, rowid DESC LIMIT 1
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    value = json.loads(str(row["payload_json"]))
    if not isinstance(value, dict):
        raise TypeError("stored intake draft must be an object")
    return value


def _completed_history_minutes(
    connection: sqlite3.Connection,
    *,
    subject: str | None,
    estimate_signature: str | None,
    before_date: date,
) -> tuple[int, ...]:
    target_subject, _ = estimation_key(subject, None)
    if target_subject is None or estimate_signature is None:
        return ()
    rows = connection.execute(
        """
        SELECT tasks.subject, tasks.estimate_signature, outcomes.actual_minutes
        FROM task_outcomes AS outcomes
        JOIN task_items AS tasks ON tasks.id = outcomes.task_id
        JOIN evening_sessions AS sessions ON sessions.id = outcomes.session_id
        JOIN daily_evening_sessions AS daily
          ON daily.session_id = sessions.id
         AND daily.session_date = sessions.session_date
        WHERE outcomes.completion_state = 'completed'
          AND outcomes.actual_minutes IS NOT NULL
          AND sessions.stage = 'closed'
          AND sessions.session_date < ?
        ORDER BY outcomes.created_at, outcomes.id
        """,
        (before_date.isoformat(),),
    ).fetchall()
    return tuple(
        int(row["actual_minutes"])
        for row in rows
        if estimation_key(row["subject"], None)[0] == target_subject
        and row["estimate_signature"] == estimate_signature
    )


def _load_task_rows(
    connection: sqlite3.Connection,
    session_id: str,
) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT tasks.*,
                   obligations.latest_safe_evening AS obligation_latest_safe_evening,
                   sessions.planning_date AS current_planning_date
            FROM task_items AS tasks
            JOIN evening_sessions AS sessions ON sessions.id = tasks.session_id
            LEFT JOIN assignment_obligations AS obligations
              ON obligations.id = tasks.assignment_id
            WHERE tasks.session_id = ?
            ORDER BY tasks.priority, tasks.created_at, tasks.id
            """,
            (session_id,),
        )
    )


def _load_task_models(
    connection: sqlite3.Connection,
    session_id: str,
) -> list[TaskItem]:
    zone = ZoneInfo(str(_load_session(connection, session_id)["timezone"]))
    return [
        TaskItem(
            id=str(row["id"]),
            session_id=str(row["session_id"]),
            title=str(row["title"]),
            subject=row["subject"],
            task_type=row["task_type"],
            source=Source(str(row["source"])),
            completion_state=TaskCompletionState(str(row["completion_state"])),
            estimated_minutes=int(row["estimated_minutes"]),
            conservative_minutes=int(row["conservative_minutes"]),
            priority=int(row["priority"]),
            must_do_tonight=bool(row["must_do_tonight"]),
            child_estimate_minutes=row["child_estimate_minutes"],
            estimate_source=str(row["estimate_source"]),
            estimate_confidence=str(row["estimate_confidence"]),
            avoidance_score=int(row["avoidance_score"]),
            preference_score=int(row["preference_score"]),
            due_at=_parse_task_deadline(row["due_at"], zone),
            school_brief_id=row["school_brief_id"],
            notes=row["notes"],
            assignment_id=row["assignment_id"],
            deadline_text=row["deadline_text"],
            remaining_percent=int(row["remaining_percent"]),
            planning_bucket=str(row["planning_bucket"]),
            planned_evening_date=(
                date.fromisoformat(str(row["planned_evening_date"]))
                if row["planned_evening_date"] is not None
                else None
            ),
            estimate_breakdown=tuple(
                json.loads(str(row["estimate_breakdown_json"]))
            ),
            estimate_signature=row["estimate_signature"],
            created_at=_parse_datetime(str(row["created_at"])),
            updated_at=_parse_datetime(str(row["updated_at"])),
        )
        for row in _load_task_rows(connection, session_id)
    ]


def _task_view(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "subject": row["subject"],
        "task_type": row["task_type"],
        "completion_state": str(row["completion_state"]),
        "estimated_minutes": int(row["estimated_minutes"]),
        "conservative_minutes": int(row["conservative_minutes"]),
        "priority": int(row["priority"]),
        "must_do_tonight": bool(row["must_do_tonight"]),
        "due_at": row["due_at"],
        "child_estimate_minutes": row["child_estimate_minutes"],
        "estimate_source": str(row["estimate_source"]),
        "estimate_confidence": str(row["estimate_confidence"]),
        "notes": row["notes"],
        "assignment_id": row["assignment_id"],
        "deadline_text": row["deadline_text"],
        "remaining_percent": int(row["remaining_percent"]),
        "planning_bucket": str(row["planning_bucket"]),
        "planned_evening_date": row["planned_evening_date"],
        "estimate_breakdown": json.loads(str(row["estimate_breakdown_json"])),
        "estimate_signature": row["estimate_signature"],
    }


def _load_latest_plan_row(
    connection: sqlite3.Connection,
    session_id: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM plans WHERE session_id = ?
        ORDER BY version DESC LIMIT 1
        """,
        (session_id,),
    ).fetchone()


def _load_latest_plan(
    connection: sqlite3.Connection,
    session_id: str,
) -> dict[str, Any] | None:
    row = _load_latest_plan_row(connection, session_id)
    if row is None:
        return None
    metadata = json.loads(str(row["capacity_json"]))
    blocks = [
        {
            "id": str(block["id"]),
            "block_type": str(block["block_type"]),
            "label": str(block["label"]),
            "starts_at": str(block["starts_at"]),
            "ends_at": str(block["ends_at"]),
            "ordinal": int(block["ordinal"]),
            "task_id": block["task_id"],
        }
        for block in connection.execute(
            """
            SELECT id, block_type, label, starts_at, ends_at, ordinal, task_id
            FROM plan_blocks WHERE plan_id = ? ORDER BY ordinal
            """,
            (str(row["id"]),),
        )
    ]
    return {
        "id": str(row["id"]),
        "plan_version": int(row["version"]),
        "capacity": metadata["capacity"],
        "baseline_capacity": metadata.get("baseline_capacity", metadata["capacity"]),
        "blocks": blocks,
        "ordered_task_ids": metadata["ordered_task_ids"],
        "deferred_task_ids": metadata["deferred_task_ids"],
        "future_scheduled_task_ids": metadata.get("future_scheduled_task_ids", []),
        "deadline_risk_task_ids": metadata.get("deadline_risk_task_ids", []),
        "capacity_recovery": metadata.get("capacity_recovery"),
        "pace_targets": metadata.get("pace_targets", []),
        "reason": str(row["reason"]),
        "committed": bool(row["committed"]),
        "scheduled_optional_minutes": metadata["scheduled_optional_minutes"],
        "true_surplus_minutes": metadata["true_surplus_minutes"],
        "predicted_finish_at": metadata["predicted_finish_at"],
    }


def _require_version(row: sqlite3.Row, expected_version: int) -> None:
    actual_version = int(row["version"])
    if actual_version != expected_version:
        raise VersionConflictError(
            "evening_session",
            str(row["id"]),
            expected_version,
            actual_version,
        )


def _require_stage(
    row: sqlite3.Row,
    allowed: set[SessionStage],
    requested: SessionStage,
) -> None:
    current = SessionStage(str(row["stage"]))
    if current not in allowed:
        raise InvalidTransitionError(current.value, requested.value)


def _advance_session(
    connection: sqlite3.Connection,
    session_id: str,
    expected_version: int,
    stage: SessionStage,
    updated_at: str,
) -> None:
    cursor = connection.execute(
        """
        UPDATE evening_sessions SET stage = ?, version = version + 1, updated_at = ?
        WHERE id = ? AND version = ?
        """,
        (stage.value, updated_at, session_id, expected_version),
    )
    if cursor.rowcount != 1:
        row = _load_session(connection, session_id)
        _require_version(row, expected_version)


def _sleep_at(session: sqlite3.Row) -> datetime:
    try:
        zone = ZoneInfo(str(session["timezone"]))
    except ZoneInfoNotFoundError as error:
        raise ValueError("unknown evening timezone") from error
    session_date = datetime.fromisoformat(str(session["session_date"])).date()
    sleep_time = datetime.fromisoformat(
        f"{session_date.isoformat()}T{session['sleep_time']}"
    ).time()
    return datetime.combine(session_date, sleep_time, tzinfo=zone)


def _task_due_at(session: sqlite3.Row, due_date: date | None) -> datetime | None:
    if due_date is None:
        return None
    zone = ZoneInfo(str(session["timezone"]))
    return datetime.combine(due_date, time(23, 59), tzinfo=zone)


def _remaining_percent(task: IntakeDraftTask) -> int:
    if task.completion_state in {
        TaskCompletionState.COMPLETED,
        TaskCompletionState.NO_TASK,
    }:
        return 0
    if task.total_units is not None and task.completed_units is not None:
        remaining = task.total_units - task.completed_units
        return (remaining * 100 + task.total_units - 1) // task.total_units
    if task.completion_state is TaskCompletionState.PARTIAL:
        return 50
    return 100


def _provisional_evening(
    planning_date: date,
    latest_safe_evening: date | None,
) -> date | None:
    if latest_safe_evening is None or latest_safe_evening <= planning_date:
        return None
    return max(
        planning_date + timedelta(days=1),
        latest_safe_evening - timedelta(days=1),
    )


def _carry_due_assignments(
    connection: sqlite3.Connection,
    *,
    session: sqlite3.Row,
    session_id: str,
    planning_date: date,
    now: datetime,
    calibration: FamilyCalibration,
) -> None:
    if session_id.startswith("evening-demo-"):
        return
    rows = connection.execute(
        """
        SELECT assignments.*
        FROM assignment_obligations AS assignments
        JOIN evening_sessions AS origin
          ON origin.id = assignments.origin_session_id
        JOIN daily_evening_sessions AS authority
          ON authority.session_date = origin.session_date
         AND authority.session_id = origin.id
        WHERE assignments.status = 'open'
          AND assignments.planned_evening_date IS NOT NULL
          AND assignments.planned_evening_date <= ?
          AND assignments.origin_session_id <> ?
          AND NOT EXISTS (
              SELECT 1 FROM task_items AS existing
              WHERE existing.session_id = ?
                AND existing.assignment_id = assignments.id
          )
        ORDER BY assignments.due_at, assignments.created_at, assignments.id
        """,
        (planning_date.isoformat(), session_id, session_id),
    ).fetchall()
    zone = ZoneInfo(str(session["timezone"]))
    for row in rows:
        task_id = _stable_id("task-carry", session_id, str(row["id"]))
        completion_state = (
            TaskCompletionState.PARTIAL
            if int(row["remaining_percent"]) < 100
            else TaskCompletionState.PENDING
        )
        task = TaskItem(
            id=task_id,
            session_id=session_id,
            title=str(row["title"]),
            subject=row["subject"],
            task_type=row["task_type"],
            source=Source.SYSTEM,
            completion_state=completion_state,
            estimated_minutes=0,
            conservative_minutes=0,
            priority=0,
            must_do_tonight=True,
            child_estimate_minutes=None,
            estimate_source="domain_default",
            estimate_confidence="low",
            due_at=_parse_task_deadline(row["due_at"], zone),
            notes="由后续安排自动带入",
            assignment_id=str(row["id"]),
            deadline_text=row["deadline_text"],
            remaining_percent=int(row["remaining_percent"]),
            planning_bucket="tonight_required",
            planned_evening_date=planning_date,
            estimate_breakdown=tuple(
                json.loads(str(row["estimate_breakdown_json"]))
            ),
            estimate_signature=row["estimate_signature"],
            created_at=now,
            updated_at=now,
        )
        stored_breakdown = tuple(
            EstimateBreakdownItem.model_validate(item)
            for item in json.loads(str(row["estimate_breakdown_json"]))
        )
        if stored_breakdown:
            component_estimate = estimate_component_snapshot(
                subject=task.subject,
                breakdown=stored_breakdown,
                calibration=calibration,
                history_minutes=_completed_history_minutes(
                    connection,
                    subject=task.subject,
                    estimate_signature=task.estimate_signature,
                    before_date=planning_date,
                ),
            )
            selected_minutes = component_estimate.minutes
            estimate_source = component_estimate.source
            estimate_confidence = component_estimate.confidence
            estimate_breakdown_json = _canonical_json(
                [
                    component.model_dump(mode="json")
                    for component in component_estimate.breakdown
                ]
            )
            estimate_signature = component_estimate.signature
        else:
            legacy_estimate = conservative_estimate(
                task,
                EstimateEvidence(history_minutes=(), parent_high_minutes=None),
                adaptation_mode=False,
            )
            selected_minutes = legacy_estimate.minutes
            estimate_source = legacy_estimate.source
            estimate_confidence = legacy_estimate.confidence
            estimate_breakdown_json = "[]"
            estimate_signature = None
        connection.execute(
            """
            INSERT INTO task_items (
                id, session_id, school_brief_id, title, subject, source,
                completion_state, estimated_minutes, conservative_minutes,
                priority, due_at, notes, created_at, updated_at, task_type,
                must_do_tonight, child_estimate_minutes, estimate_source,
                estimate_confidence, avoidance_score, preference_score,
                assignment_id, deadline_text, remaining_percent, planning_bucket,
                planned_evening_date, estimate_breakdown_json, estimate_signature
            ) VALUES (?, ?, NULL, ?, ?, 'system', ?, ?, ?, 0, ?, ?, ?, ?, ?,
                      1, NULL, ?, ?, 0, 0, ?, ?, ?, 'tonight_required', ?, ?, ?)
            """,
            (
                task_id,
                session_id,
                task.title,
                task.subject,
                completion_state.value,
                selected_minutes,
                selected_minutes,
                _iso(task.due_at) if task.due_at is not None else None,
                task.notes,
                _iso(now),
                _iso(now),
                task.task_type,
                estimate_source,
                estimate_confidence,
                task.assignment_id,
                task.deadline_text,
                task.remaining_percent,
                planning_date.isoformat(),
                estimate_breakdown_json,
                estimate_signature,
            ),
        )


def _fixed_block_models(
    session_id: str,
    session: sqlite3.Row,
    draft: dict[str, Any] | None,
) -> list[FixedBlock]:
    if draft is None:
        return []
    zone = ZoneInfo(str(session["timezone"]))
    session_date = date.fromisoformat(str(session["session_date"]))
    models: list[FixedBlock] = []
    for index, raw_block in enumerate(draft.get("fixed_blocks", [])):
        block = IntakeFixedBlock.model_validate_json(_canonical_json(raw_block))
        models.append(
            FixedBlock(
                id=_stable_id("fixed", session_id, str(index), block.label),
                label=block.label,
                starts_at=datetime.combine(session_date, block.start_time, tzinfo=zone),
                ends_at=datetime.combine(session_date, block.end_time, tzinfo=zone),
                source=Source.CHILD,
            )
        )
    return models


def _stable_id(prefix: str, *parts: str) -> str:
    digest = _sha256_text("\0".join(parts))[:24]
    return f"{prefix}-{digest}"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _now_text() -> str:
    return _iso(_now())


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_optional_datetime(value: object) -> datetime | None:
    return None if value is None else _parse_datetime(str(value))


def _parse_task_deadline(value: object, zone: ZoneInfo) -> datetime | None:
    parsed = _parse_optional_datetime(value)
    return None if parsed is None else parsed.astimezone(zone)
