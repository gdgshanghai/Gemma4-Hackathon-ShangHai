from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from backend.contracts.family import (
    MemoryCategory,
    MemoryObservation,
    MemoryQuery,
    MemoryRelevanceReason,
    ObservationEvidenceLevel,
    ProfilePatchAction,
    ProfileSnapshot,
    ProfileVersion,
)
from backend.contracts.models import Source
from backend.services.memory import project_profile, retrieve_memory


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


def _profile_version(
    profile_version: int,
    *,
    committed_at: datetime | None = None,
) -> ProfileVersion:
    return ProfileVersion(
        profile_version=profile_version,
        commit_id=f"commit-{profile_version}",
        reason="parent_confirmed_patch",
        committed_at=committed_at or NOW + timedelta(minutes=profile_version),
    )


def _event(
    event_id: str,
    *,
    profile_version: int = 1,
    canonical_order: int = 0,
    action: ProfilePatchAction = ProfilePatchAction.ASSERT,
    category: MemoryCategory = MemoryCategory.SUBJECT_PERFORMANCE,
    subject: str | None = "General subject",
    task_type: str | None = "written",
    metric: str = "assessment_level",
    value_text: str | None = "developing",
    value_number: float | None = None,
    unit: str | None = None,
    confidence: float = 0.8,
    sample_count: int | None = None,
    observed_at: datetime | None = None,
    target_event_id: str | None = None,
    evidence_level: ObservationEvidenceLevel = ObservationEvidenceLevel.PARENT_CONFIRMED,
    committed_at: datetime | None = None,
) -> MemoryObservation:
    if action is ProfilePatchAction.REVOKE:
        value_text = None
        value_number = None
        unit = None
        sample_count = None
    return MemoryObservation(
        id=event_id,
        action=action,
        category=category,
        subject=subject,
        task_type=task_type,
        metric=metric,
        value_text=value_text,
        value_number=value_number,
        unit=unit,
        confidence=confidence,
        sample_count=sample_count,
        observed_at=observed_at or NOW,
        target_event_id=target_event_id,
        source=Source.PARENT,
        evidence_level=evidence_level,
        confirmed_by="parent-1",
        profile_version=profile_version,
        canonical_order=canonical_order,
        committed_at=committed_at or NOW + timedelta(minutes=profile_version),
    )


def _numeric_event(
    event_id: str,
    *,
    category: MemoryCategory,
    metric: str,
    value_number: float,
    unit: str,
    sample_count: int,
    **overrides: Any,
) -> MemoryObservation:
    return _event(
        event_id,
        category=category,
        metric=metric,
        value_text=None,
        value_number=value_number,
        unit=unit,
        sample_count=sample_count,
        **overrides,
    )


@dataclass
class _HistoryRepository:
    versions: tuple[ProfileVersion, ...]
    events: tuple[MemoryObservation, ...]
    unconfirmed_drafts: tuple[object, ...] = ()
    history_reads: int = 0

    def list_profile_history(
        self,
        up_to_profile_version: int | None = None,
    ) -> tuple[tuple[ProfileVersion, ...], tuple[MemoryObservation, ...]]:
        self.history_reads += 1
        if up_to_profile_version is None:
            return self.versions, self.events
        return (
            tuple(
                version
                for version in self.versions
                if version.profile_version <= up_to_profile_version
            ),
            tuple(
                event
                for event in self.events
                if event.profile_version <= up_to_profile_version
            ),
        )


def _query(**overrides: Any) -> MemoryQuery:
    payload: dict[str, Any] = {
        "categories": (MemoryCategory.SUBJECT_PERFORMANCE,),
        "subjects": ("General subject",),
        "task_types": ("written",),
        "as_of": NOW + timedelta(hours=1),
        "limit": 10,
    }
    payload.update(overrides)
    return MemoryQuery(**payload)


def test_project_profile_applies_assert_supersede_and_revoke_append_only() -> None:
    assertion = _event("event-assert", profile_version=1)
    replacement = _event(
        "event-supersede",
        profile_version=2,
        action=ProfilePatchAction.SUPERSEDE,
        value_text="secure",
        target_event_id=assertion.id,
    )
    revocation = _event(
        "event-revoke",
        profile_version=3,
        action=ProfilePatchAction.REVOKE,
        target_event_id=replacement.id,
    )

    after_replacement = project_profile(
        (assertion, replacement, revocation),
        (_profile_version(1), _profile_version(2), _profile_version(3)),
        NOW + timedelta(minutes=2, seconds=30),
    )
    after_revocation = project_profile(
        (assertion, replacement, revocation),
        (_profile_version(1), _profile_version(2), _profile_version(3)),
        NOW + timedelta(minutes=4),
    )

    assert after_replacement == (replacement,)
    assert after_revocation == ()
    assert assertion.action is ProfilePatchAction.ASSERT
    assert replacement.target_event_id == assertion.id


def test_revoke_committed_after_historical_as_of_does_not_change_history() -> None:
    assertion = _event(
        "event-assert",
        profile_version=1,
        committed_at=NOW,
    )
    revocation = _event(
        "event-revoke",
        profile_version=2,
        action=ProfilePatchAction.REVOKE,
        target_event_id=assertion.id,
        committed_at=NOW + timedelta(days=2),
    )
    versions = (
        _profile_version(1, committed_at=NOW),
        _profile_version(2, committed_at=NOW + timedelta(days=2)),
    )

    historical = project_profile(
        (assertion, revocation),
        versions,
        NOW + timedelta(days=1),
    )

    assert historical == (assertion,)


def test_profile_version_prefix_stops_at_first_future_commit() -> None:
    first = _event("event-1", profile_version=1)
    future = _event("event-2", profile_version=2, canonical_order=0)
    invalid_later = _event("event-3", profile_version=3, canonical_order=0)
    versions = (
        _profile_version(1, committed_at=NOW),
        _profile_version(2, committed_at=NOW + timedelta(days=2)),
        _profile_version(3, committed_at=NOW + timedelta(hours=1)),
    )

    projection = project_profile(
        (first, future, invalid_later),
        versions,
        NOW + timedelta(days=1),
    )

    assert projection == (first,)


@pytest.mark.parametrize(
    ("events", "message"),
    [
        (
            (
                _event("duplicate"),
                _event("duplicate", profile_version=2),
            ),
            "duplicate event id",
        ),
        (
            (
                _event(
                    "broken",
                    action=ProfilePatchAction.REVOKE,
                    target_event_id="missing",
                ),
            ),
            "active target",
        ),
        (
            (
                _event(
                    "cycle-a",
                    action=ProfilePatchAction.SUPERSEDE,
                    target_event_id="cycle-b",
                ),
                _event(
                    "cycle-b",
                    canonical_order=1,
                    action=ProfilePatchAction.SUPERSEDE,
                    target_event_id="cycle-a",
                ),
            ),
            "cycle",
        ),
    ],
)
def test_project_profile_rejects_duplicate_broken_and_cyclic_chains(
    events: tuple[MemoryObservation, ...],
    message: str,
) -> None:
    versions = tuple(
        _profile_version(profile_version)
        for profile_version in sorted({event.profile_version for event in events})
    )
    with pytest.raises(ValueError, match=message):
        project_profile(events, versions, NOW + timedelta(days=1))


def test_project_profile_rejects_duplicate_target_consumption() -> None:
    assertion = _event("event-assert", canonical_order=0)
    first_revoke = _event(
        "event-revoke-1",
        canonical_order=1,
        action=ProfilePatchAction.REVOKE,
        target_event_id=assertion.id,
    )
    second_revoke = _event(
        "event-revoke-2",
        canonical_order=2,
        action=ProfilePatchAction.REVOKE,
        target_event_id=assertion.id,
    )
    with pytest.raises(ValueError, match="consumed more than once"):
        project_profile(
            (assertion, first_revoke, second_revoke),
            (_profile_version(1),),
            NOW + timedelta(hours=1),
        )


def test_project_profile_rejects_replacement_identity_mismatch() -> None:
    assertion = _event("event-assert", canonical_order=0, subject="Subject A")
    replacement = _event(
        "event-supersede",
        canonical_order=1,
        action=ProfilePatchAction.SUPERSEDE,
        subject="Subject B",
        target_event_id=assertion.id,
    )
    with pytest.raises(ValueError, match="identity"):
        project_profile(
            (assertion, replacement),
            (_profile_version(1),),
            NOW + timedelta(hours=1),
        )


def test_retrieve_memory_never_reads_unconfirmed_drafts() -> None:
    repository = _HistoryRepository(
        versions=(_profile_version(1),),
        events=(_event("confirmed"),),
        unconfirmed_drafts=(object(),),
    )

    result = retrieve_memory(repository, _query())

    assert [summary.observation.id for summary in result] == ["confirmed"]
    assert repository.history_reads == 1


def test_retrieve_memory_uses_exact_relevance_tiers_and_reasons() -> None:
    events = (
        _event("tier-4", subject="Target subject", task_type="written"),
        _event("tier-3", subject="Target subject", task_type=None, canonical_order=1),
        _event("tier-2", subject=None, task_type="written", canonical_order=2),
        _event("tier-1", subject=None, task_type=None, canonical_order=3),
        _event("wrong-subject", subject="Other subject", task_type="written", canonical_order=4),
        _event("wrong-task", subject="Target subject", task_type="oral", canonical_order=5),
    )
    repository = _HistoryRepository((_profile_version(1),), events)

    result = retrieve_memory(
        repository,
        _query(subjects=("Target subject",), task_types=("written",)),
    )

    assert [summary.observation.id for summary in result] == [
        "tier-4",
        "tier-3",
        "tier-2",
        "tier-1",
    ]
    assert [summary.relevance_reason for summary in result] == [
        MemoryRelevanceReason.SUBJECT_AND_TASK_TYPE_MATCH,
        MemoryRelevanceReason.SUBJECT_MATCH,
        MemoryRelevanceReason.TASK_TYPE_MATCH,
        MemoryRelevanceReason.GENERAL_CATEGORY_MATCH,
    ]


def test_retrieve_memory_normalizes_nfkc_trim_and_casefold_for_matching() -> None:
    event = _event(
        "normalized",
        subject=" ＭＡＴＨ ",
        task_type=" WRITTEN ",
    )
    repository = _HistoryRepository((_profile_version(1),), (event,))

    result = retrieve_memory(
        repository,
        _query(subjects=("math",), task_types=("written",)),
    )

    assert result[0].observation.subject == " ＭＡＴＨ "
    assert result[0].relevance_reason is MemoryRelevanceReason.SUBJECT_AND_TASK_TYPE_MATCH


def test_task_speed_memory_matches_legacy_chinese_to_canonical_query() -> None:
    event = _numeric_event(
        "legacy-chinese-speed",
        category=MemoryCategory.TASK_SPEED,
        subject="英语",
        task_type="背诵",
        metric="typical_minutes_high",
        value_number=30,
        unit="minutes",
        sample_count=2,
    )
    repository = _HistoryRepository((_profile_version(1),), (event,))

    result = retrieve_memory(
        repository,
        _query(
            categories=(MemoryCategory.TASK_SPEED,),
            subjects=("english",),
            task_types=("recitation",),
        ),
    )

    assert [item.observation.id for item in result] == ["legacy-chinese-speed"]
    assert result[0].relevance_reason is MemoryRelevanceReason.SUBJECT_AND_TASK_TYPE_MATCH


@pytest.mark.parametrize(
    ("categories", "subjects", "task_types"),
    [
        ((MemoryCategory.BEHAVIOR,), ("General subject",), ("written",)),
        ((MemoryCategory.BEHAVIOR,), ("General subject",), ()),
        ((MemoryCategory.BEHAVIOR,), (), ("written",)),
        ((MemoryCategory.BEHAVIOR,), (), ()),
    ],
)
def test_category_not_requested_excludes_candidates_at_every_tier(
    categories: tuple[MemoryCategory, ...],
    subjects: tuple[str, ...],
    task_types: tuple[str, ...],
) -> None:
    repository = _HistoryRepository((_profile_version(1),), (_event("subject-performance"),))
    assert retrieve_memory(
        repository,
        _query(categories=categories, subjects=subjects, task_types=task_types),
    ) == ()


def test_retrieve_memory_excludes_future_evidence_without_breaking_projection() -> None:
    future = _event("future", observed_at=NOW + timedelta(days=1))
    repository = _HistoryRepository((_profile_version(1, committed_at=NOW),), (future,))

    assert project_profile((future,), repository.versions, NOW + timedelta(hours=1)) == (future,)
    assert retrieve_memory(repository, _query(as_of=NOW + timedelta(hours=1))) == ()


def test_inferred_by_exclusion_is_never_task_speed_evidence() -> None:
    inferred_speed = _numeric_event(
        "inferred-speed",
        category=MemoryCategory.TASK_SPEED,
        metric="typical_minutes_low",
        value_number=30,
        unit="minutes",
        sample_count=1,
        evidence_level=ObservationEvidenceLevel.INFERRED_BY_EXCLUSION,
    )
    repository = _HistoryRepository((_profile_version(1),), (inferred_speed,))

    result = retrieve_memory(
        repository,
        _query(categories=(MemoryCategory.TASK_SPEED,)),
    )

    assert result == ()


def test_retrieve_memory_sort_is_deterministic_and_limit_is_applied() -> None:
    events = (
        _numeric_event(
            "later-id",
            category=MemoryCategory.SUBJECT_PERFORMANCE,
            metric="score",
            value_number=80,
            unit="points",
            sample_count=3,
            confidence=0.9,
            observed_at=NOW,
            subject=None,
            task_type=None,
            canonical_order=0,
        ),
        _numeric_event(
            "first-id",
            category=MemoryCategory.SUBJECT_PERFORMANCE,
            metric="score",
            value_number=81,
            unit="points",
            sample_count=3,
            confidence=0.9,
            observed_at=NOW,
            subject=None,
            task_type=None,
            canonical_order=1,
        ),
        _numeric_event(
            "lower-sample",
            category=MemoryCategory.SUBJECT_PERFORMANCE,
            metric="score",
            value_number=82,
            unit="points",
            sample_count=2,
            confidence=0.9,
            observed_at=NOW + timedelta(minutes=1),
            subject=None,
            task_type=None,
            canonical_order=2,
        ),
        _event(
            "none-sample",
            subject=None,
            task_type=None,
            confidence=0.9,
            observed_at=NOW + timedelta(minutes=2),
            canonical_order=3,
        ),
    )
    repository = _HistoryRepository((_profile_version(1),), events)

    result = retrieve_memory(
        repository,
        _query(subjects=(), task_types=(), limit=2),
    )

    assert [summary.observation.id for summary in result] == ["first-id", "later-id"]
    assert all(summary.relevance_reason is MemoryRelevanceReason.GENERAL_CATEGORY_MATCH for summary in result)


def test_retrieve_memory_excludes_revoked_and_superseded_facts() -> None:
    assertion = _event("old", profile_version=1)
    replacement = _event(
        "current",
        profile_version=2,
        action=ProfilePatchAction.SUPERSEDE,
        value_text="secure",
        target_event_id="old",
    )
    repository = _HistoryRepository(
        (_profile_version(1), _profile_version(2)),
        (assertion, replacement),
    )

    result = retrieve_memory(repository, _query())

    assert [summary.observation.id for summary in result] == ["current"]


def test_profile_snapshot_contract_keeps_each_exact_version_projection() -> None:
    assertion = _event("old", profile_version=1)
    replacement = _event(
        "current",
        profile_version=2,
        action=ProfilePatchAction.SUPERSEDE,
        value_text="secure",
        target_event_id=assertion.id,
    )
    versions = (_profile_version(1), _profile_version(2))

    snapshot_v1 = ProfileSnapshot(
        profile_version=1,
        active_observations=project_profile(
            (assertion,),
            versions[:1],
            versions[0].committed_at,
        ),
    )
    snapshot_v2 = ProfileSnapshot(
        profile_version=2,
        active_observations=project_profile(
            (assertion, replacement),
            versions,
            versions[-1].committed_at,
        ),
    )

    assert snapshot_v1.active_observations == (assertion,)
    assert snapshot_v2.active_observations == (replacement,)
