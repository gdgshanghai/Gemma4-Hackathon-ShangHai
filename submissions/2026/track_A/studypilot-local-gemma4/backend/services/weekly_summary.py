"""Deterministic weekly parent summary projection."""

from __future__ import annotations

from datetime import date, timedelta

from backend.contracts.api import NoDataMetric, WeeklySummaryData
from backend.storage.family_context import FamilyContextRepository


NO_DATA_METRIC = NoDataMetric(
    value=None,
    numerator=0,
    denominator=0,
    status="no_data",
)


def build_weekly_summary(
    repository: FamilyContextRepository,
    week_start: date,
) -> WeeklySummaryData:
    """Project confirmed profile facts without inventing evening metrics."""
    _, events = repository.list_profile_history()
    return WeeklySummaryData(
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        profile_version=repository.get_current_profile_version(),
        latest_calibration=repository.get_latest_calibration_summary(),
        confirmed_observation_count=len(events),
        estimate_error=NO_DATA_METRIC,
        omissions=NO_DATA_METRIC,
        start_confidence=NO_DATA_METRIC,
        parent_interventions=NO_DATA_METRIC,
    )
