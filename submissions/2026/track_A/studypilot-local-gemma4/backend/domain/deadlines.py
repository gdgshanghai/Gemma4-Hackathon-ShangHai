"""Deterministic resolution of school deadline wording."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


_WEEKDAYS = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}


@dataclass(frozen=True, slots=True)
class DeadlineResolution:
    due_at: datetime | None
    latest_safe_evening: date | None
    planned_evening_date: date | None
    must_do_tonight: bool
    display_label: str


def resolve_deadline(
    deadline_text: str | None,
    planning_date: date,
    timezone: str,
) -> DeadlineResolution:
    """Resolve supported relative wording without asking the model to calculate dates."""
    text = (deadline_text or "").strip()
    due_date = _resolve_due_date(text, planning_date)
    if due_date is None:
        return DeadlineResolution(
            due_at=None,
            latest_safe_evening=None,
            planned_evening_date=None,
            must_do_tonight=True,
            display_label="截止未说明，按今晚必做",
        )

    latest_safe = due_date - timedelta(days=1)
    must_do = latest_safe <= planning_date
    planned = None
    if not must_do:
        first_future = planning_date + timedelta(days=1)
        safety_date = latest_safe - timedelta(days=1)
        planned = max(first_future, safety_date)
    return DeadlineResolution(
        due_at=datetime.combine(due_date, time(8), tzinfo=ZoneInfo(timezone)),
        latest_safe_evening=latest_safe,
        planned_evening_date=planned,
        must_do_tonight=must_do,
        display_label=text,
    )


def _resolve_due_date(text: str, planning_date: date) -> date | None:
    if any(token in text for token in ("今晚", "今天", "当晚")):
        return planning_date
    if any(token in text for token in ("明早", "明天", "次日")):
        return planning_date + timedelta(days=1)

    iso_match = re.search(r"(?P<year>20\d{2})[-/.年](?P<month>\d{1,2})[-/.月](?P<day>\d{1,2})", text)
    if iso_match:
        return date(
            int(iso_match.group("year")),
            int(iso_match.group("month")),
            int(iso_match.group("day")),
        )

    month_day_match = re.search(r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日?", text)
    if month_day_match:
        candidate = date(
            planning_date.year,
            int(month_day_match.group("month")),
            int(month_day_match.group("day")),
        )
        if candidate < planning_date:
            candidate = candidate.replace(year=candidate.year + 1)
        return candidate

    weekday_match = re.search(
        r"(?P<next>下)?(?:周|星期)(?P<weekday>[一二三四五六日天])",
        text,
    )
    if weekday_match:
        target = _WEEKDAYS[weekday_match.group("weekday")]
        if weekday_match.group("next"):
            next_monday = planning_date + timedelta(days=7 - planning_date.weekday())
            return next_monday + timedelta(days=target)
        return planning_date + timedelta(days=(target - planning_date.weekday()) % 7)
    return None
