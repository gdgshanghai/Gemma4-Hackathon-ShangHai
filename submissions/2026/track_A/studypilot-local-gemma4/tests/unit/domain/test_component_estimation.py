from __future__ import annotations

from backend.contracts.evening import IntakeDraftTask
from backend.contracts.models import TaskCompletionState
from backend.domain.estimate_components import (
    estimate_component_snapshot,
    estimate_task_components,
)
from backend.domain.family_calibration import (
    RatioObservation,
    build_family_calibration,
)


def _english_task(*, child_minutes: int | None = None) -> IntakeDraftTask:
    return IntakeDraftTask(
        title="Unit 2词汇20个，背诵课文一段，完成练习册2页",
        subject="英语",
        completion_state=TaskCompletionState.PARTIAL,
        child_estimate_minutes=child_minutes,
        notes="练习册做完1页，词汇和课文背诵都没做",
    )


def test_uncalibrated_task_uses_component_reference_total() -> None:
    result = estimate_task_components(
        _english_task(),
        calibration=build_family_calibration(()),
    )

    assert result.minutes == 30
    assert [item.calibrated_minutes for item in result.breakdown] == [20, 10]
    assert result.source == "domain_default"


def test_recitation_calibration_changes_recitation_but_not_workbook() -> None:
    calibration = build_family_calibration(
        (RatioObservation("english", "recitation", 0.5, 5),)
    )

    result = estimate_task_components(_english_task(), calibration=calibration)

    assert [item.calibrated_minutes for item in result.breakdown] == [15, 10]
    assert [item.source for item in result.breakdown] == [
        "parent_range",
        "domain_default",
    ]
    assert result.minutes == 25


def test_three_exact_signature_samples_override_family_calibration_with_p80() -> None:
    calibration = build_family_calibration(
        (RatioObservation("english", "recitation", 0.5, 5),)
    )

    result = estimate_task_components(
        _english_task(),
        calibration=calibration,
        history_minutes=(40, 45, 50),
    )

    assert result.minutes == 50
    assert sum(item.calibrated_minutes for item in result.breakdown) == 50
    assert {item.source for item in result.breakdown} == {"history_p80"}
    assert result.confidence == "medium"


def test_fewer_than_three_history_samples_do_not_override_reference() -> None:
    result = estimate_task_components(
        _english_task(),
        calibration=build_family_calibration(()),
        history_minutes=(50, 60),
    )

    assert result.minutes == 30
    assert result.source == "domain_default"


def test_child_remaining_minutes_are_a_floor_not_an_override() -> None:
    result = estimate_task_components(
        _english_task(child_minutes=36),
        calibration=build_family_calibration(()),
    )

    assert result.minutes == 40
    assert sum(item.calibrated_minutes for item in result.breakdown) == 40
    assert result.source == "child_adjusted"


def test_stored_future_components_use_the_current_family_calibration() -> None:
    original = estimate_task_components(
        _english_task(),
        calibration=build_family_calibration(()),
    )
    calibration = build_family_calibration(
        (RatioObservation("english", "recitation", 0.5, 5),)
    )

    updated = estimate_component_snapshot(
        subject="english",
        breakdown=original.breakdown,
        calibration=calibration,
    )

    assert [item.calibrated_minutes for item in updated.breakdown] == [15, 10]
    assert updated.minutes == 25
