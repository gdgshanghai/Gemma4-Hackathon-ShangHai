"""Hierarchical, shrinkage-based family pace calibration."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from backend.domain.estimation import estimation_key


@dataclass(frozen=True, slots=True)
class RatioObservation:
    subject: str
    task_type: str
    ratio: float
    sample_count: int


@dataclass(frozen=True, slots=True)
class FamilyCalibration:
    overall: float
    subject_residuals: dict[str, float]
    task_type_residuals: dict[str, float]
    sample_count: int
    pair_sample_counts: dict[tuple[str, str], int]

    def factor_for(self, subject: str | None, task_type: str | None) -> float:
        canonical_subject, canonical_type = estimation_key(subject, task_type)
        if (
            canonical_subject is None
            or canonical_type is None
            or (canonical_subject, canonical_type) not in self.pair_sample_counts
        ):
            return 1.0
        factor = self.overall
        factor *= self.subject_residuals.get(canonical_subject, 1.0)
        factor *= self.task_type_residuals.get(canonical_type, 1.0)
        return min(1.8, max(0.7, factor))

    def sample_count_for(self, subject: str | None, task_type: str | None) -> int:
        canonical_subject, canonical_type = estimation_key(subject, task_type)
        if canonical_subject is None or canonical_type is None:
            return 0
        return self.pair_sample_counts.get((canonical_subject, canonical_type), 0)


def shrink_weight(sample_count: int) -> float:
    if sample_count <= 0:
        return 0.0
    if sample_count == 1:
        return 0.25
    if sample_count == 2:
        return 0.40
    if sample_count <= 4:
        return 0.60
    return 0.80


def build_family_calibration(
    observations: tuple[RatioObservation, ...],
) -> FamilyCalibration:
    normalized = tuple(_normalize_observation(item) for item in observations)
    if not normalized:
        return FamilyCalibration(1.0, {}, {}, 0, {})

    overall = _shrunken_p80(
        tuple((item.ratio, item.sample_count) for item in normalized)
    )
    subject_residuals: dict[str, float] = {}
    subjects = sorted({item.subject for item in normalized})
    for subject in subjects:
        grouped = tuple(
            (item.ratio / overall, item.sample_count)
            for item in normalized
            if item.subject == subject
        )
        subject_residuals[subject] = _shrunken_p80(grouped)

    task_type_residuals: dict[str, float] = {}
    task_types = sorted({item.task_type for item in normalized})
    for task_type in task_types:
        grouped = tuple(
            (
                item.ratio
                / (overall * subject_residuals.get(item.subject, 1.0)),
                item.sample_count,
            )
            for item in normalized
            if item.task_type == task_type
        )
        task_type_residuals[task_type] = _shrunken_p80(grouped)

    return FamilyCalibration(
        overall=overall,
        subject_residuals=subject_residuals,
        task_type_residuals=task_type_residuals,
        sample_count=sum(item.sample_count for item in normalized),
        pair_sample_counts={
            (subject, task_type): sum(
                item.sample_count
                for item in normalized
                if item.subject == subject and item.task_type == task_type
            )
            for subject, task_type in {
                (item.subject, item.task_type) for item in normalized
            }
        },
    )


def calibrated_minutes(reference: int, factor: float) -> int:
    return max(5, ((ceil(reference * factor) + 4) // 5) * 5)


def _normalize_observation(item: RatioObservation) -> RatioObservation:
    subject, task_type = estimation_key(item.subject, item.task_type)
    if subject is None or task_type is None:
        raise ValueError("ratio observation requires canonical subject and task type")
    if not 0.1 <= item.ratio <= 10:
        raise ValueError("ratio observation is outside the supported range")
    if item.sample_count < 1:
        raise ValueError("ratio observation requires a positive sample count")
    return RatioObservation(subject, task_type, item.ratio, item.sample_count)


def _shrunken_p80(values: tuple[tuple[float, int], ...]) -> float:
    expanded = sorted(
        ratio
        for ratio, count in values
        for _ in range(count)
    )
    rank = max(1, ceil(len(expanded) * 0.8))
    raw = expanded[rank - 1]
    weight = shrink_weight(len(expanded))
    return 1.0 + weight * (raw - 1.0)
