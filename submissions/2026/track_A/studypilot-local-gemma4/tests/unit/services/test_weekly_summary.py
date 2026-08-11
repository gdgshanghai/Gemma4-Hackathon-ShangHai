from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from backend.contracts.family import (
    CalibrationState,
    FamilyWriteContext,
    MemoryCategory,
    ProfilePatchAction,
    ProposedObservationInput,
)
from backend.services.weekly_summary import build_weekly_summary
from backend.storage.database import run_migrations
from backend.storage.family_context import FamilyContextRepository


WEEK_START = date(2026, 7, 6)
SECRET_RECEIPT_TEXT = "private parent receipt must never be projected"


@pytest.fixture
def repository(tmp_path: Path) -> FamilyContextRepository:
    database_path = tmp_path / "weekly-summary.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    return FamilyContextRepository(database_path)


def _context(key: str, trace_id: str) -> FamilyWriteContext:
    return FamilyWriteContext(
        actor="parent-1",
        role="parent",
        trace_id=trace_id,
        idempotency_key=key,
    )


def _observation() -> ProposedObservationInput:
    return ProposedObservationInput(
        action=ProfilePatchAction.ASSERT,
        category=MemoryCategory.SUBJECT_PERFORMANCE,
        subject="Mathematics",
        task_type="written",
        metric="assessment_level",
        value_text="secure",
        value_number=None,
        unit=None,
        confidence=0.85,
        sample_count=None,
        observed_at=datetime(2026, 7, 6, 12, 0, tzinfo=UTC),
        target_event_id=None,
    )


def _assert_no_data_metrics(summary: object) -> None:
    for metric in (
        summary.estimate_error,
        summary.omissions,
        summary.start_confidence,
        summary.parent_interventions,
    ):
        assert metric.value is None
        assert metric.numerator == 0
        assert metric.denominator == 0
        assert metric.status == "no_data"


def test_empty_database_projects_honest_no_data(
    repository: FamilyContextRepository,
) -> None:
    summary = build_weekly_summary(repository, WEEK_START)

    assert summary.week_start == date(2026, 7, 6)
    assert summary.week_end == date(2026, 7, 12)
    assert summary.profile_version == 0
    assert summary.latest_calibration is None
    assert summary.confirmed_observation_count == 0
    _assert_no_data_metrics(summary)


def test_unconfirmed_draft_does_not_inflate_profile_or_observation_count(
    repository: FamilyContextRepository,
) -> None:
    receipt = repository.save_calibration_input(
        "calibration-weekly-1",
        SECRET_RECEIPT_TEXT,
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_context("weekly-input-key", "trace-weekly-input"),
    ).receipt
    repository.propose_profile_patch(
        "calibration-weekly-1",
        receipt.id,
        (_observation(),),
        expected_calibration_version=1,
        context=_context("weekly-proposal-key", "trace-weekly-proposal"),
    )

    summary = build_weekly_summary(repository, WEEK_START)

    assert summary.profile_version == 0
    assert summary.confirmed_observation_count == 0
    assert summary.latest_calibration is not None
    assert summary.latest_calibration.state is CalibrationState.NEEDS_CONFIRMATION
    assert SECRET_RECEIPT_TEXT not in summary.model_dump_json()
    _assert_no_data_metrics(summary)


def test_committed_observation_updates_confirmed_projection_without_receipt_text(
    repository: FamilyContextRepository,
) -> None:
    receipt = repository.save_calibration_input(
        "calibration-weekly-1",
        SECRET_RECEIPT_TEXT,
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_context("weekly-input-key", "trace-weekly-input"),
    ).receipt
    repository.propose_profile_patch(
        "calibration-weekly-1",
        receipt.id,
        (_observation(),),
        expected_calibration_version=1,
        context=_context("weekly-proposal-key", "trace-weekly-proposal"),
    )
    draft = repository.get_calibration_recovery("calibration-weekly-1").pending_draft
    assert draft is not None
    repository.commit_profile_patch(
        "calibration-weekly-1",
        draft.id,
        (draft.observations[0].operation_id,),
        draft_digest=draft.draft_digest,
        expected_calibration_version=2,
        context=_context("weekly-commit-key", "trace-weekly-commit"),
    )

    summary = build_weekly_summary(repository, WEEK_START)

    assert summary.profile_version == 1
    assert summary.confirmed_observation_count == 1
    assert summary.latest_calibration is not None
    assert summary.latest_calibration.calibration_id == "calibration-weekly-1"
    assert summary.latest_calibration.calibration_version == 3
    assert summary.latest_calibration.profile_version == 1
    assert summary.latest_calibration.state is CalibrationState.COMMITTED
    assert SECRET_RECEIPT_TEXT not in summary.model_dump_json()
    _assert_no_data_metrics(summary)
