"""Deterministic compilation of parent timing evidence into profile proposals."""

from __future__ import annotations

from math import ceil

from backend.contracts.calibration_tools import (
    CalibrationEvidenceDetail,
    ExtractCalibrationEvidenceArgs,
)
from backend.contracts.family import (
    CalibrationTurnReceipt,
    MemoryCategory,
    MemoryObservation,
    ProfilePatchAction,
    ProfileSnapshot,
    ProposedObservationInput,
)
from backend.domain.estimation import estimation_key
from backend.domain.estimate_components import WorkloadBand, reference_minutes


def compile_duration_evidence(
    evidence: ExtractCalibrationEvidenceArgs,
    receipt: CalibrationTurnReceipt,
    profile_snapshot: ProfileSnapshot,
) -> tuple[ProposedObservationInput, ...]:
    existing = _active_ratio_by_key(profile_snapshot.active_observations)
    proposals: list[ProposedObservationInput] = []
    details = describe_duration_evidence(evidence, receipt_text=receipt.raw_text)
    for group, detail in zip(evidence.duration_groups, details, strict=True):
        subject, task_type = estimation_key(group.subject.value, group.task_type.value)
        if subject is None or task_type is None:
            raise ValueError("duration evidence requires a canonical subject and task type")
        current = existing.get((subject, task_type))
        proposals.append(
            ProposedObservationInput(
                action=(
                    ProfilePatchAction.SUPERSEDE
                    if current is not None
                    else ProfilePatchAction.ASSERT
                ),
                category=MemoryCategory.TASK_SPEED,
                subject=subject,
                task_type=task_type,
                metric="estimated_actual_ratio",
                value_number=detail.suggested_ratio,
                unit="ratio",
                confidence=0.7,
                sample_count=len(group.minutes),
                observed_at=receipt.created_at,
                target_event_id=current.id if current is not None else None,
            )
        )
    return tuple(proposals)


def describe_duration_evidence(
    evidence: ExtractCalibrationEvidenceArgs,
    *,
    receipt_text: str | None = None,
) -> tuple[CalibrationEvidenceDetail, ...]:
    details: list[CalibrationEvidenceDetail] = []
    for group in evidence.duration_groups:
        subject, task_type = estimation_key(group.subject.value, group.task_type.value)
        if subject is None or task_type is None:
            raise ValueError("duration evidence requires a canonical subject and task type")
        ordered_minutes = sorted(group.minutes)
        observed_p80 = ordered_minutes[ceil(len(ordered_minutes) * 0.8) - 1]
        workload_band = group.workload_band
        if receipt_text is not None and not any(
            marker in receipt_text
            for marker in ("小工作量", "中等工作量", "大工作量")
        ):
            workload_band = type(group.workload_band).MEDIUM
        reference = reference_minutes(
            subject,
            task_type,
            WorkloadBand(workload_band.value),
        )
        details.append(
            CalibrationEvidenceDetail(
                subject=group.subject,
                task_type=group.task_type,
                workload_band=workload_band,
                reference_minutes=reference,
                observed_p80_minutes=observed_p80,
                sample_count=len(group.minutes),
                suggested_ratio=round(observed_p80 / reference, 4),
            )
        )
    return tuple(details)


def _active_ratio_by_key(
    observations: tuple[MemoryObservation, ...],
) -> dict[tuple[str, str], MemoryObservation]:
    matches: dict[tuple[str, str], MemoryObservation] = {}
    ordered = sorted(
        observations,
        key=lambda item: (item.profile_version, item.canonical_order, item.id),
    )
    for observation in ordered:
        if (
            observation.category is not MemoryCategory.TASK_SPEED
            or observation.metric != "estimated_actual_ratio"
        ):
            continue
        subject, task_type = estimation_key(
            observation.subject,
            observation.task_type,
        )
        if subject is not None and task_type is not None:
            matches[(subject, task_type)] = observation
    return matches
