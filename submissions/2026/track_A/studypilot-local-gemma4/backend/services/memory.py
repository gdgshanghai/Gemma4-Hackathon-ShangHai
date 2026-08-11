"""Deterministic projection and retrieval for confirmed family Memory."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from backend.contracts.family import (
    MemoryCategory,
    MemoryEvidenceSummary,
    MemoryObservation,
    MemoryQuery,
    MemoryRelevanceReason,
    ObservationEvidenceLevel,
    ProfilePatchAction,
    ProfileVersion,
    normalize_family_text,
)
from backend.domain.estimation import estimation_key


class ProfileHistoryReader(Protocol):
    def list_profile_history(
        self,
        up_to_profile_version: int | None = None,
    ) -> tuple[tuple[ProfileVersion, ...], tuple[MemoryObservation, ...]]: ...


def project_profile(
    events: Iterable[MemoryObservation],
    profile_versions: Iterable[ProfileVersion],
    as_of: datetime,
) -> tuple[MemoryObservation, ...]:
    """Fold the known committed version prefix into its active observations."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")

    versions = sorted(profile_versions, key=lambda item: item.profile_version)
    version_numbers = [version.profile_version for version in versions]
    if len(version_numbers) != len(set(version_numbers)):
        raise ValueError("duplicate profile version")

    included_versions: set[int] = set()
    expected_version = 1
    for version in versions:
        if version.profile_version != expected_version:
            raise ValueError("profile versions must form a contiguous prefix")
        if version.committed_at > as_of:
            break
        included_versions.add(version.profile_version)
        expected_version += 1

    included_events = sorted(
        (
            event
            for event in events
            if event.profile_version in included_versions
        ),
        key=lambda item: (item.profile_version, item.canonical_order, item.id),
    )
    _validate_event_identifiers(included_events)
    _validate_no_target_cycles(included_events)

    active: dict[str, MemoryObservation] = {}
    consumed_targets: set[str] = set()
    for event in included_events:
        if event.action is ProfilePatchAction.ASSERT:
            active[event.id] = event
            continue

        target_id = event.target_event_id
        if target_id is None:
            raise ValueError("non-assert event requires an active target")
        if target_id in consumed_targets:
            raise ValueError("profile target was consumed more than once")
        target = active.get(target_id)
        if target is None:
            raise ValueError("profile event requires an active target")
        if _observation_identity(event) != _observation_identity(target):
            raise ValueError("replacement identity does not match target")

        consumed_targets.add(target_id)
        del active[target_id]
        if event.action is ProfilePatchAction.SUPERSEDE:
            active[event.id] = event

    return tuple(
        sorted(
            active.values(),
            key=lambda item: (item.profile_version, item.canonical_order, item.id),
        )
    )


def retrieve_memory(
    repository: ProfileHistoryReader,
    query: MemoryQuery,
) -> tuple[MemoryEvidenceSummary, ...]:
    """Return confirmed active evidence using exact deterministic relevance tiers."""
    profile_versions, events = repository.list_profile_history()
    active = project_profile(events, profile_versions, query.as_of)
    requested_categories = set(query.categories)
    requested_subjects = {
        normalized
        for subject in query.subjects
        if (normalized := normalize_family_text(subject)) is not None
    }
    requested_task_types = {
        normalized
        for task_type in query.task_types
        if (normalized := normalize_family_text(task_type)) is not None
    }

    ranked: list[tuple[int, MemoryObservation, MemoryRelevanceReason]] = []
    for observation in active:
        if observation.category not in requested_categories:
            continue
        if observation.observed_at > query.as_of:
            continue
        if (
            observation.category is MemoryCategory.TASK_SPEED
            and observation.evidence_level is ObservationEvidenceLevel.INFERRED_BY_EXCLUSION
        ):
            continue
        relevance = _relevance_tier(
            observation,
            requested_subjects,
            requested_task_types,
        )
        if relevance is not None:
            tier, reason = relevance
            ranked.append((tier, observation, reason))

    ranked.sort(key=_retrieval_sort_key)
    return tuple(
        MemoryEvidenceSummary(
            observation=observation,
            source=observation.source,
            observed_at=observation.observed_at,
            confidence=observation.confidence,
            sample_count=observation.sample_count,
            relevance_reason=reason,
        )
        for _, observation, reason in ranked[: query.limit]
    )


def _validate_event_identifiers(events: list[MemoryObservation]) -> None:
    ids = [event.id for event in events]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate event id in profile history")
    orders = [(event.profile_version, event.canonical_order) for event in events]
    if len(orders) != len(set(orders)):
        raise ValueError("duplicate canonical order in profile version")


def _validate_no_target_cycles(events: list[MemoryObservation]) -> None:
    targets = {
        event.id: event.target_event_id
        for event in events
        if event.target_event_id is not None
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(event_id: str) -> None:
        if event_id in visiting:
            raise ValueError("cycle in profile event targets")
        if event_id in visited:
            return
        visiting.add(event_id)
        target_id = targets.get(event_id)
        if target_id is not None and target_id in targets:
            visit(target_id)
        visiting.remove(event_id)
        visited.add(event_id)

    for event_id in targets:
        visit(event_id)


def _observation_identity(
    observation: MemoryObservation,
) -> tuple[MemoryCategory, str | None, str | None, str]:
    return (
        observation.category,
        normalize_family_text(observation.subject),
        normalize_family_text(observation.task_type),
        observation.metric,
    )


def _relevance_tier(
    observation: MemoryObservation,
    requested_subjects: set[str],
    requested_task_types: set[str],
) -> tuple[int, MemoryRelevanceReason] | None:
    if observation.category is MemoryCategory.TASK_SPEED:
        subject, task_type = estimation_key(
            observation.subject,
            observation.task_type,
        )
        requested_subjects = {
            canonical
            for value in requested_subjects
            if (canonical := estimation_key(value, None)[0]) is not None
        }
        requested_task_types = {
            canonical
            for value in requested_task_types
            if (canonical := estimation_key(None, value)[1]) is not None
        }
    else:
        subject = normalize_family_text(observation.subject)
        task_type = normalize_family_text(observation.task_type)
    if requested_subjects and subject is not None and subject not in requested_subjects:
        return None
    if requested_task_types and task_type is not None and task_type not in requested_task_types:
        return None

    subject_matches = subject is not None and subject in requested_subjects
    task_type_matches = task_type is not None and task_type in requested_task_types
    if subject_matches and task_type_matches:
        return 4, MemoryRelevanceReason.SUBJECT_AND_TASK_TYPE_MATCH
    if subject_matches:
        return 3, MemoryRelevanceReason.SUBJECT_MATCH
    if task_type_matches:
        return 2, MemoryRelevanceReason.TASK_TYPE_MATCH
    if subject is None and task_type is None:
        return 1, MemoryRelevanceReason.GENERAL_CATEGORY_MATCH
    return None


def _retrieval_sort_key(
    ranked: tuple[int, MemoryObservation, MemoryRelevanceReason],
) -> tuple[float | int | bool | str, ...]:
    tier, observation, _ = ranked
    sample_count = observation.sample_count
    return (
        -tier,
        -observation.confidence,
        sample_count is None,
        -(sample_count or 0),
        -observation.observed_at.timestamp(),
        observation.id,
    )
