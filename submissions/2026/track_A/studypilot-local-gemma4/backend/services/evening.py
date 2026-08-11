"""Application service for the lean child evening workflow."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from backend.contracts.evening import (
    EveningCloseRequest,
    EveningCommitRequest,
    EveningConfirmRequest,
    EveningCreateRequest,
    EveningIntakeRequest,
    EveningPlanRequest,
    EveningResponse,
    EveningTimeBoundaryRequest,
    IntakeDraftTask,
)
from backend.contracts.family import (
    MemoryCategory,
    MemoryObservation,
    MemoryQuery,
    MemoryRelevanceReason,
    ObservationEvidenceLevel,
    ProfileVersion,
)
from backend.contracts.models import SessionStage
from backend.domain.estimation import estimation_key
from backend.domain.evening_workflow import allowed_actions, must_do_tonight
from backend.domain.family_calibration import RatioObservation
from backend.orchestration.evening import EveningIntakeOrchestrator
from backend.orchestration.harness import HarnessError
from backend.services.memory import project_profile, retrieve_memory
from backend.storage.evening_workflow import EveningWorkflowRepository
from backend.storage.family_context import FamilyContextRepository


_MODEL_UNAVAILABLE_CODES = {
    "model_timeout",
    "model_connection_refused",
    "model_transport_error",
    "model_http_error",
    "model_not_found",
    "model_not_loaded",
}


class EveningModelUnavailableError(RuntimeError):
    def __init__(self, response: EveningResponse) -> None:
        self.response = response
        super().__init__("model_unavailable")


@dataclass(frozen=True, slots=True)
class _VersionedMemoryReader:
    repository: FamilyContextRepository
    profile_version: int

    def list_profile_history(
        self,
        up_to_profile_version: int | None = None,
    ) -> tuple[tuple[ProfileVersion, ...], tuple[MemoryObservation, ...]]:
        cap = self.profile_version
        if up_to_profile_version is not None:
            cap = min(cap, up_to_profile_version)
        return self.repository.list_profile_history(up_to_profile_version=cap)


class EveningService:
    def __init__(
        self,
        *,
        repository: EveningWorkflowRepository,
        family_repository: FamilyContextRepository,
        intake_orchestrator: EveningIntakeOrchestrator,
        current_date: Callable[[], date] = date.today,
        timezone: str = "Asia/Shanghai",
    ) -> None:
        self.repository = repository
        self.family_repository = family_repository
        self.intake_orchestrator = intake_orchestrator
        self.current_date = current_date
        self.timezone = timezone

    def create(
        self,
        body: EveningCreateRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> EveningResponse:
        session_date = self.current_date()
        result = self.repository.create(
            session_date=session_date.isoformat(),
            planning_date=session_date.isoformat(),
            timezone=self.timezone,
            sleep_time=body.sleep_time.isoformat(),
            available_minutes=body.window_minutes,
            expected_version=body.expected_version,
            caller_idempotency_key=caller_idempotency_key,
            trace_id=trace_id,
        )
        return _project_result(result)

    def update_time_boundary(
        self,
        session_id: str,
        body: EveningTimeBoundaryRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> EveningResponse:
        return _project_result(
            self.repository.update_time_boundary(
                session_id=session_id,
                expected_version=body.expected_version,
                sleep_time=body.sleep_time.isoformat(),
                available_minutes=body.window_minutes,
                caller_idempotency_key=caller_idempotency_key,
                trace_id=trace_id,
            )
        )

    def get_today(self, *, trace_id: str) -> EveningResponse:
        return _project_view(
            self.repository.get_latest(self.current_date()),
            trace_id=trace_id,
        )

    def reset_demo_today(
        self,
        *,
        expected_session_id: str | None,
        planning_date: date,
        start_time: time,
        sleep_time: time,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> EveningResponse:
        return _project_result(
            self.repository.reset_demo_today(
                session_date=self.current_date().isoformat(),
                planning_date=planning_date.isoformat(),
                timezone=self.timezone,
                sleep_time=sleep_time.isoformat(),
                available_minutes=(
                    sleep_time.hour * 60
                    + sleep_time.minute
                    - start_time.hour * 60
                    - start_time.minute
                ),
                expected_session_id=expected_session_id,
                caller_idempotency_key=caller_idempotency_key,
                trace_id=trace_id,
            )
        )

    def get(self, session_id: str, *, trace_id: str) -> EveningResponse:
        return _project_view(self.repository.get(session_id), trace_id=trace_id)

    def get_latest(self, session_date: date, *, trace_id: str) -> EveningResponse:
        return _project_view(
            self.repository.get_latest(session_date),
            trace_id=trace_id,
        )

    def intake(
        self,
        session_id: str,
        body: EveningIntakeRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> EveningResponse:
        self.repository.append_raw_intake(
            session_id=session_id,
            text=body.text,
            expected_version=body.expected_version,
            caller_idempotency_key=caller_idempotency_key,
        )
        school_brief = self.family_repository.get_latest_school_brief(
            self.repository.get_session_date(session_id)
        )
        if school_brief is not None and not school_brief.raw_text.strip():
            school_brief = None
        try:
            self.intake_orchestrator.run(
                session_id=session_id,
                text=self.repository.get_intake_transcript(session_id),
                school_brief=school_brief,
                expected_version=body.expected_version,
                caller_idempotency_key=caller_idempotency_key,
                trace_id=trace_id,
            )
        except HarnessError as error:
            if error.code == "empty_final_content":
                view = self.repository.get(session_id)
                if (
                    view.get("stage") == SessionStage.INTAKE_DRAFT.value
                    and view.get("version") == body.expected_version + 1
                    and isinstance(view.get("intake_draft"), dict)
                ):
                    return _project_view(view, trace_id=error.trace_id)
            if error.code not in _MODEL_UNAVAILABLE_CODES:
                raise
            view = self.repository.mark_model_unavailable(
                session_id=session_id,
                expected_version=body.expected_version,
            )
            raise EveningModelUnavailableError(
                _project_view(view, trace_id=trace_id)
            ) from error
        return _project_view(
            self.repository.get(session_id),
            trace_id=trace_id,
            narration="清单已整理，请确认是否完整。",
        )

    def confirm(
        self,
        session_id: str,
        body: EveningConfirmRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> EveningResponse:
        profile_version = self.family_repository.get_current_profile_version()
        reader = _VersionedMemoryReader(
            repository=self.family_repository,
            profile_version=profile_version,
        )
        as_of = datetime.now(UTC)
        parent_high_minutes = _inventory_parent_high_minutes(
            self.repository.get(session_id),
            reader=reader,
            as_of=as_of,
        )
        ratio_observations = _family_ratio_observations(reader, as_of=as_of)
        return _project_result(
            self.repository.confirm_inventory(
                session_id=session_id,
                expected_version=body.expected_version,
                profile_version=profile_version,
                parent_high_minutes=parent_high_minutes,
                family_ratio_observations=ratio_observations,
                caller_idempotency_key=caller_idempotency_key,
                trace_id=trace_id,
            )
        )

    def plan(
        self,
        session_id: str,
        body: EveningPlanRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> EveningResponse:
        return _project_result(
            self.repository.build_plan(
                session_id=session_id,
                expected_version=body.expected_version,
                reason=body.reason,
                preferred_order=body.preferred_order,
                deadline_risk_task_ids=body.deadline_risk_task_ids,
                caller_idempotency_key=caller_idempotency_key,
                trace_id=trace_id,
            )
        )

    def commit(
        self,
        session_id: str,
        plan_id: str,
        body: EveningCommitRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> EveningResponse:
        return _project_result(
            self.repository.commit_plan(
                session_id=session_id,
                plan_id=plan_id,
                expected_version=body.expected_version,
                caller_idempotency_key=caller_idempotency_key,
                trace_id=trace_id,
            )
        )

    def close(
        self,
        session_id: str,
        body: EveningCloseRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> EveningResponse:
        return _project_result(
            self.repository.close(
                session_id=session_id,
                expected_version=body.expected_version,
                unfinished_task_ids=body.unfinished_task_ids,
                largest_deviation=body.largest_deviation,
                note=body.note,
                caller_idempotency_key=caller_idempotency_key,
                trace_id=trace_id,
            )
        )


def _inventory_parent_high_minutes(
    view: dict[str, Any],
    *,
    reader: _VersionedMemoryReader,
    as_of: datetime,
) -> tuple[int | None, ...]:
    draft = view.get("intake_draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("tasks"), list):
        return ()
    tasks = tuple(
        IntakeDraftTask.model_validate_json(json.dumps(raw_task)) for raw_task in draft["tasks"]
    )
    return tuple(
        _parent_high_minutes(task, reader=reader, as_of=as_of)
        if must_do_tonight(task.completion_state)
        else None
        for task in tasks
    )


def _parent_high_minutes(
    task: IntakeDraftTask,
    *,
    reader: _VersionedMemoryReader,
    as_of: datetime,
) -> int | None:
    subject, task_type = estimation_key(
        task.subject,
        None,
        title=task.title,
    )
    if not subject or not task_type:
        return None
    evidence = retrieve_memory(
        reader,
        MemoryQuery(
            categories=(MemoryCategory.TASK_SPEED,),
            subjects=(subject,),
            task_types=(task_type,),
            as_of=as_of,
            limit=20,
        ),
    )
    if any(
        summary.relevance_reason
        is MemoryRelevanceReason.SUBJECT_AND_TASK_TYPE_MATCH
        and summary.observation.metric == "estimated_actual_ratio"
        for summary in evidence
    ):
        return None
    for summary in evidence:
        observation = summary.observation
        if (
            summary.relevance_reason
            is MemoryRelevanceReason.SUBJECT_AND_TASK_TYPE_MATCH
            and observation.metric == "typical_minutes_high"
            and observation.value_number is not None
        ):
            return int(observation.value_number)
    return None


def _family_ratio_observations(
    reader: _VersionedMemoryReader,
    *,
    as_of: datetime,
) -> tuple[RatioObservation, ...]:
    versions, events = reader.list_profile_history()
    active = project_profile(events, versions, as_of)
    observations: list[RatioObservation] = []
    for observation in active:
        subject, task_type = estimation_key(
            observation.subject,
            observation.task_type,
        )
        if (
            observation.category is not MemoryCategory.TASK_SPEED
            or observation.evidence_level is ObservationEvidenceLevel.INFERRED_BY_EXCLUSION
            or observation.metric != "estimated_actual_ratio"
            or observation.value_number is None
            or observation.sample_count is None
            or subject is None
            or task_type is None
        ):
            continue
        observations.append(
            RatioObservation(
                subject=subject,
                task_type=task_type,
                ratio=float(observation.value_number),
                sample_count=observation.sample_count,
            )
        )
    return tuple(observations)


def _project_result(result: dict[str, Any]) -> EveningResponse:
    view = result.get("view")
    trace_id = result.get("trace_id")
    if not isinstance(view, dict) or not isinstance(trace_id, str):
        raise TypeError("stored evening operation result is invalid")
    return _project_view(view, trace_id=trace_id)


def _project_view(
    view: dict[str, Any],
    *,
    trace_id: str,
    narration: str | None = None,
) -> EveningResponse:
    stage = SessionStage(str(view["stage"]))
    plan = view.get("plan")
    plan_version = (
        int(plan["plan_version"])
        if isinstance(plan, dict) and "plan_version" in plan
        else None
    )
    intake_draft = view.get("intake_draft")
    public_intake_draft = None
    if isinstance(intake_draft, dict):
        public_intake_draft = {
            "id": intake_draft["id"],
            "tasks": intake_draft["tasks"],
            "fixed_blocks": intake_draft.get("fixed_blocks", []),
            "coverage_notes": intake_draft.get("coverage_notes", []),
        }
    data = {
        "narration": narration,
        "intake_draft": public_intake_draft,
        "coverage_mode": view.get("coverage_mode"),
        "inventory": view.get("inventory", []),
        "plan": view.get("plan"),
        "outcomes": view.get("outcomes", []),
        "time_boundary": view["time_boundary"],
        "future_assignments": view.get("future_assignments", []),
    }
    payload = {
        "session_id": str(view["session_id"]),
        "session_date": str(view["session_date"]),
        "planning_date": str(view["planning_date"]),
        "version": int(view["version"]),
        "stage": stage.value,
        "allowed_actions": allowed_actions(stage, plan_version=plan_version),
        "trace_id": trace_id,
        "data": data,
    }
    return EveningResponse.model_validate_json(json.dumps(payload))
