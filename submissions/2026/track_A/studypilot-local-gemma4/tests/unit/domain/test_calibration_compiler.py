from __future__ import annotations

import importlib
from datetime import datetime, timezone

from backend.contracts.calibration_tools import ExtractCalibrationEvidenceArgs
from backend.contracts.family import (
    CalibrationTurnReceipt,
    MemoryCategory,
    MemoryObservation,
    ObservationEvidenceLevel,
    ProfilePatchAction,
    ProfileSnapshot,
)
from backend.contracts.models import Source


NOW = datetime(2026, 7, 16, 8, 0, tzinfo=timezone.utc)


def _receipt() -> CalibrationTurnReceipt:
    return CalibrationTurnReceipt(
        id="receipt-1",
        calibration_id="calibration-1",
        actor="local-parent",
        role="parent",
        content_sha256="a" * 64,
        raw_text="本周可核对观察",
        created_at=NOW,
    )


def _evidence() -> ExtractCalibrationEvidenceArgs:
    return ExtractCalibrationEvidenceArgs(
        duration_groups=(
            {"subject": "mathematics", "task_type": "written", "minutes": (31, 34, 29)},
            {"subject": "chinese", "task_type": "reading", "minutes": (24, 26, 22)},
            {"subject": "english", "task_type": "recitation", "minutes": (28, 30)},
            {"subject": "geography", "task_type": "map_reading", "minutes": (18, 21)},
        ),
        unapplied_notes=("英语开始前需要提醒", "20:30以后背诵明显更慢"),
    )


def _compile(
    evidence: ExtractCalibrationEvidenceArgs,
    profile: ProfileSnapshot,
):
    module = importlib.import_module("backend.domain.calibration")
    return module.compile_duration_evidence(evidence, _receipt(), profile)


def _details(evidence: ExtractCalibrationEvidenceArgs):
    module = importlib.import_module("backend.domain.calibration")
    return module.describe_duration_evidence(evidence)


def test_compile_duration_evidence_creates_reference_ratios() -> None:
    observations = _compile(
        _evidence(),
        ProfileSnapshot(profile_version=0, active_observations=()),
    )

    assert [(item.subject, item.task_type, item.value_number) for item in observations] == [
        ("mathematics", "written", 1.7),
        ("chinese", "reading", 1.3),
        ("english", "recitation", 1.5),
        ("geography", "map_reading", 0.84),
    ]
    assert [item.sample_count for item in observations] == [3, 3, 2, 2]
    assert all(item.action is ProfilePatchAction.ASSERT for item in observations)
    assert all(item.category is MemoryCategory.TASK_SPEED for item in observations)
    assert all(item.metric == "estimated_actual_ratio" for item in observations)
    assert all(item.unit == "ratio" for item in observations)
    assert all(item.confidence == 0.7 for item in observations)
    assert all(item.observed_at == NOW for item in observations)


def test_duration_evidence_details_explain_the_ratio() -> None:
    details = _details(_evidence())

    assert [item.reference_minutes for item in details] == [20, 20, 20, 25]
    assert [item.observed_p80_minutes for item in details] == [34, 26, 30, 21]
    assert [item.sample_count for item in details] == [3, 3, 2, 2]
    assert [item.suggested_ratio for item in details] == [1.7, 1.3, 1.5, 0.84]
    assert all(item.workload_band.value == "medium" for item in details)


def test_unstated_workload_cannot_be_guessed_below_medium() -> None:
    evidence = ExtractCalibrationEvidenceArgs(
        duration_groups=(
            {
                "subject": "mathematics",
                "task_type": "written",
                "workload_band": "small",
                "minutes": (10,),
            },
        )
    )

    observation = _compile(
        evidence,
        ProfileSnapshot(profile_version=0, active_observations=()),
    )[0]

    assert observation.value_number == 0.5


def test_compile_duration_evidence_keeps_legacy_value_as_compatibility_fallback() -> None:
    existing = MemoryObservation(
        id="event-old",
        action=ProfilePatchAction.ASSERT,
        category=MemoryCategory.TASK_SPEED,
        subject="数学",
        task_type="书面",
        metric="typical_minutes_high",
        value_number=40,
        unit="minutes",
        confidence=0.7,
        sample_count=2,
        observed_at=NOW,
        source=Source.PARENT,
        evidence_level=ObservationEvidenceLevel.PARENT_CONFIRMED,
        confirmed_by="local-parent",
        profile_version=1,
        canonical_order=0,
        committed_at=NOW,
    )
    evidence = ExtractCalibrationEvidenceArgs(
        duration_groups=(
            {"subject": "mathematics", "task_type": "written", "minutes": (29, 34)},
        )
    )

    observation = _compile(
        evidence,
        ProfileSnapshot(profile_version=1, active_observations=(existing,)),
    )[0]

    assert observation.action is ProfilePatchAction.ASSERT
    assert observation.target_event_id is None
    assert observation.value_number == 1.7


def test_compile_duration_evidence_supersedes_matching_ratio() -> None:
    existing = MemoryObservation(
        id="event-ratio",
        action=ProfilePatchAction.ASSERT,
        category=MemoryCategory.TASK_SPEED,
        subject="mathematics",
        task_type="written",
        metric="estimated_actual_ratio",
        value_number=1.4,
        unit="ratio",
        confidence=0.7,
        sample_count=2,
        observed_at=NOW,
        source=Source.PARENT,
        evidence_level=ObservationEvidenceLevel.PARENT_CONFIRMED,
        confirmed_by="local-parent",
        profile_version=1,
        canonical_order=0,
        committed_at=NOW,
    )
    evidence = ExtractCalibrationEvidenceArgs(
        duration_groups=(
            {"subject": "mathematics", "task_type": "written", "minutes": (29, 34)},
        )
    )

    observation = _compile(
        evidence,
        ProfileSnapshot(profile_version=1, active_observations=(existing,)),
    )[0]

    assert observation.action is ProfilePatchAction.SUPERSEDE
    assert observation.target_event_id == "event-ratio"
