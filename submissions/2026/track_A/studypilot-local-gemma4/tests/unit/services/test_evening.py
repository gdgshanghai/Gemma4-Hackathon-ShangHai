from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Never

import pytest

from backend.contracts.evening import EveningIntakeRequest, IntakeDraftTask
from backend.contracts.family import (
    MemoryCategory,
    MemoryObservation,
    ObservationEvidenceLevel,
    ProfilePatchAction,
    ProfileVersion,
)
from backend.contracts.models import Source
from backend.orchestration.harness import HarnessError
from backend.services.evening import (
    EveningService,
    _family_ratio_observations,
    _parent_high_minutes,
)
from backend.storage.database import run_migrations
from backend.storage.evening_workflow import EveningWorkflowRepository
from backend.storage.family_context import FamilyContextRepository


class _EmptyFinalContentOrchestrator:
    def run(self, **kwargs: Any) -> Never:
        raise HarnessError("empty_final_content", str(kwargs["trace_id"]))


@dataclass(frozen=True)
class _ParentTimingReader:
    observation: MemoryObservation

    def list_profile_history(
        self,
        up_to_profile_version: int | None = None,
    ) -> tuple[tuple[ProfileVersion, ...], tuple[MemoryObservation, ...]]:
        return (
            (
                ProfileVersion(
                    profile_version=1,
                    commit_id="commit-parent-timing",
                    reason="parent_confirmed_patch",
                    committed_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
                ),
            ),
            (self.observation,),
        )


def _parent_timing_reader() -> _ParentTimingReader:
    return _ParentTimingReader(
        MemoryObservation(
            id="parent-english-recitation",
            action=ProfilePatchAction.ASSERT,
            category=MemoryCategory.TASK_SPEED,
            subject="english",
            task_type="recitation",
            metric="typical_minutes_high",
            value_text=None,
            value_number=30,
            unit="minutes",
            confidence=0.7,
            sample_count=2,
            observed_at=datetime(2026, 7, 16, 10, 0, tzinfo=UTC),
            target_event_id=None,
            source=Source.PARENT,
            evidence_level=ObservationEvidenceLevel.PARENT_CONFIRMED,
            confirmed_by="parent-1",
            profile_version=1,
            canonical_order=0,
            committed_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
        )
    )


def test_parent_high_minutes_matches_subject_and_type_inferred_from_title() -> None:
    result = _parent_high_minutes(
        IntakeDraftTask(title="Unit 2 课文背诵", subject="英语"),
        reader=_parent_timing_reader(),  # type: ignore[arg-type]
        as_of=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
    )

    assert result == 30


def test_parent_high_minutes_does_not_cross_apply_to_written_work() -> None:
    result = _parent_high_minutes(
        IntakeDraftTask(title="完成英语练习册两页", subject="英语"),
        reader=_parent_timing_reader(),  # type: ignore[arg-type]
        as_of=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
    )

    assert result is None


def test_parent_high_minutes_falls_back_when_task_type_is_unknown() -> None:
    result = _parent_high_minutes(
        IntakeDraftTask(title="完成英语任务", subject="英语"),
        reader=_parent_timing_reader(),  # type: ignore[arg-type]
        as_of=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
    )

    assert result is None


def test_family_ratio_observations_are_projected_for_component_estimation() -> None:
    ratio = _parent_timing_reader().observation.model_copy(
        update={
            "id": "parent-english-ratio",
            "metric": "estimated_actual_ratio",
            "value_number": 1.25,
            "unit": "ratio",
            "sample_count": 3,
        }
    )

    result = _family_ratio_observations(
        _ParentTimingReader(ratio),  # type: ignore[arg-type]
        as_of=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
    )

    assert len(result) == 1
    assert result[0].subject == "english"
    assert result[0].task_type == "recitation"
    assert result[0].ratio == 1.25
    assert result[0].sample_count == 3


def test_empty_final_content_without_persisted_draft_is_reraised(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evening-service.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = EveningWorkflowRepository(database_path)
    created = repository.create(
        session_date="2026-07-12",
        timezone="Asia/Shanghai",
        sleep_time="22:30:00",
        available_minutes=180,
        expected_version=0,
        caller_idempotency_key="evening-service-create-0001",
        trace_id="trace-create",
    )
    session_id = str(created["view"]["session_id"])
    service = EveningService(
        repository=repository,
        family_repository=FamilyContextRepository(database_path),
        intake_orchestrator=_EmptyFinalContentOrchestrator(),
    )

    with pytest.raises(HarnessError) as raised:
        service.intake(
            session_id,
            EveningIntakeRequest(
                text="No tool write will occur.",
                expected_version=1,
            ),
            caller_idempotency_key="evening-service-intake-0001",
            trace_id="trace-empty-final-no-write",
        )

    assert raised.value.code == "empty_final_content"
    assert raised.value.trace_id == "trace-empty-final-no-write"
    view = repository.get(session_id)
    assert view["version"] == 1
    assert view["stage"] == "created"
    assert view["intake_draft"] is None
