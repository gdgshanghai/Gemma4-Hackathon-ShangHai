from __future__ import annotations

import pytest

from backend.domain.family_calibration import (
    RatioObservation,
    build_family_calibration,
    shrink_weight,
)


@pytest.mark.parametrize(
    ("samples", "expected"),
    [(1, 0.25), (2, 0.40), (3, 0.60), (4, 0.60), (5, 0.80), (20, 0.80)],
)
def test_shrink_weight_increases_with_evidence(samples: int, expected: float) -> None:
    assert shrink_weight(samples) == expected


def test_empty_profile_keeps_reference_baseline() -> None:
    profile = build_family_calibration(())

    assert profile.factor_for("mathematics", "written") == 1.0


def test_one_observation_changes_matching_pair_without_tripling() -> None:
    profile = build_family_calibration(
        (
            RatioObservation(
                subject="mathematics",
                task_type="written",
                ratio=1.4,
                sample_count=1,
            ),
        )
    )

    assert profile.overall == pytest.approx(1.1)
    assert 1.1 < profile.factor_for("mathematics", "written") < 1.4
    assert profile.factor_for("english", "written") == 1.0


def test_specific_evidence_does_not_leak_to_other_component_types() -> None:
    profile = build_family_calibration(
        (
            RatioObservation("english", "recitation", 1.5, 3),
            RatioObservation("mathematics", "written", 1.4, 3),
        )
    )

    assert profile.factor_for("english", "written") == 1.0
    assert profile.factor_for("mathematics", "correction") == 1.0
    assert profile.sample_count_for("english", "recitation") == 3
    assert profile.sample_count_for("english", "written") == 0


def test_unrelated_subject_and_task_type_do_not_receive_specific_residuals() -> None:
    profile = build_family_calibration(
        (
            RatioObservation("mathematics", "written", 1.5, 3),
            RatioObservation("english", "recitation", 0.8, 2),
        )
    )

    unrelated = profile.factor_for("biology", "preparation")
    mathematics = profile.factor_for("mathematics", "written")
    english = profile.factor_for("english", "recitation")
    assert mathematics != unrelated
    assert english != unrelated


def test_combined_factor_is_clamped() -> None:
    slow = build_family_calibration(
        (RatioObservation("english", "recitation", 5.0, 10),)
    )
    fast = build_family_calibration(
        (RatioObservation("mathematics", "written", 0.1, 10),)
    )

    assert slow.factor_for("english", "recitation") == 1.8
    assert fast.factor_for("mathematics", "written") == 0.7
