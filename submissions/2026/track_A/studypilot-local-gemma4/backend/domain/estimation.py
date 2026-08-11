"""Conservative task-duration estimation."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from backend.contracts.models import TaskItem


_SUBJECT_ALIASES = {
    "math": "mathematics",
    "maths": "mathematics",
    "mathematics": "mathematics",
    "数学": "mathematics",
    "chinese": "chinese",
    "mandarin": "chinese",
    "语文": "chinese",
    "english": "english",
    "英语": "english",
    "道德与法治": "civics",
    "道法": "civics",
    "civics": "civics",
    "历史": "history",
    "history": "history",
    "地理": "geography",
    "geography": "geography",
    "生物": "biology",
    "生物学": "biology",
    "biology": "biology",
}
_TASK_TYPE_ALIASES = {
    "written": "written",
    "writing": "written",
    "written work": "written",
    "书面": "written",
    "练习": "written",
    "recitation": "recitation",
    "memorization": "recitation",
    "memorisation": "recitation",
    "背诵": "recitation",
    "默写": "recitation",
    "correction": "correction",
    "corrections": "correction",
    "error correction": "correction",
    "订正": "correction",
    "reading": "reading",
    "阅读": "reading",
    "preparation": "preparation",
    "prep": "preparation",
    "preview": "preparation",
    "预习": "preparation",
    "准备材料": "preparation",
    "map reading": "map_reading",
    "map_reading": "map_reading",
    "读图": "map_reading",
}
_TYPE_DEFAULTS = {
    "recitation": 15,
    "correction": 10,
    "reading": 20,
    "preparation": 10,
    "map_reading": 15,
}
_WRITTEN_DEFAULTS = {
    "mathematics": 30,
    "chinese": 25,
    "english": 20,
}
_FALLBACK_MINUTES = 20
_MINIMUM_MINUTES = 5


@dataclass(frozen=True, slots=True)
class EstimateEvidence:
    history_minutes: tuple[int, ...]
    parent_high_minutes: int | None


@dataclass(frozen=True, slots=True)
class EstimateResult:
    minutes: int
    source: str
    confidence: str
    sample_count: int


def estimation_key(
    subject: str | None,
    task_type: str | None,
    *,
    title: str | None = None,
) -> tuple[str | None, str | None]:
    normalized_subject = _normalize(subject)
    normalized_type = _normalize(task_type)
    canonical_type = _TASK_TYPE_ALIASES.get(normalized_type or "")
    if canonical_type is None and title:
        canonical_type = _infer_task_type(title)
    return (
        _SUBJECT_ALIASES.get(normalized_subject or "", normalized_subject),
        canonical_type,
    )


def conservative_estimate(
    task: TaskItem,
    evidence: EstimateEvidence,
    adaptation_mode: bool,
) -> EstimateResult:
    if task.remaining_percent == 0:
        return EstimateResult(
            minutes=0,
            source="domain_default",
            confidence="low",
            sample_count=0,
        )
    history = sorted(
        value
        for value in evidence.history_minutes
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
    )
    sample_count = len(history)
    selected_is_remaining = False

    if sample_count >= 3:
        rank = ceil(sample_count * 0.8)
        minutes = history[rank - 1]
        source = "history_p80"
        confidence = "high" if sample_count >= 6 else "medium"
    else:
        if evidence.parent_high_minutes is not None:
            minutes = evidence.parent_high_minutes
            source = "parent_range"
            confidence = "medium"
        elif task.child_estimate_minutes is not None:
            minutes = task.child_estimate_minutes
            source = "child_adjusted"
            confidence = "low"
            selected_is_remaining = True
        else:
            minutes = _domain_default(task.subject, task.task_type, task.title)
            source = "domain_default"
            confidence = "low"

        history_floor = history[-1] if history else None
        if history_floor is not None and task.remaining_percent < 100:
            history_floor = _scale_remaining(history_floor, task.remaining_percent)
        if history_floor is not None and history_floor > minutes:
            minutes = history_floor
            source = "history_p80"
            confidence = "low"
            selected_is_remaining = True

    if not selected_is_remaining and task.remaining_percent < 100:
        minutes = _scale_remaining(minutes, task.remaining_percent)

    return EstimateResult(
        minutes=max(_MINIMUM_MINUTES, minutes),
        source=source,
        confidence=confidence,
        sample_count=sample_count,
    )


def _ceil_ratio(value: int, *, numerator: int, denominator: int) -> int:
    return (value * numerator + denominator - 1) // denominator


def _scale_remaining(minutes: int, remaining_percent: int) -> int:
    scaled = _ceil_ratio(minutes, numerator=remaining_percent, denominator=100)
    return ((scaled + 4) // 5) * 5


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.strip().casefold().replace("_", " ").replace("-", " ").split())


def _domain_default(
    subject: str | None,
    task_type: str | None,
    title: str | None = None,
) -> int:
    normalized_subject, normalized_type = estimation_key(subject, task_type)
    normalized_title = _normalize(title) or ""
    if normalized_type == "written" and "提纲" in normalized_title:
        return 15
    if normalized_type == "written" and "练习册" in normalized_title:
        return 20
    if normalized_type == "written" and "结构图" in normalized_title:
        return 10
    if normalized_type == "recitation" and "课文" in normalized_title:
        return 10
    if normalized_type in _TYPE_DEFAULTS:
        return _TYPE_DEFAULTS[normalized_type]
    if normalized_type == "written" and normalized_subject in _WRITTEN_DEFAULTS:
        return _WRITTEN_DEFAULTS[normalized_subject]
    return _FALLBACK_MINUTES


def _infer_task_type(title: str) -> str | None:
    normalized = _normalize(title) or ""
    rules = (
        ("map_reading", ("读图", "经纬网", "map reading")),
        ("correction", ("订正", "错题", "correction")),
        ("recitation", ("背诵", "默写", "词汇", "recitation", "vocabulary")),
        ("preparation", ("预习", "准备材料", "preview")),
        ("reading", ("阅读", "摘录", "reading")),
        (
            "written",
            (
                "练习",
                "运算",
                "作文",
                "提纲",
                "练习册",
                "结构图",
                "时间轴",
                "笔记",
                "worksheet",
                "written",
            ),
        ),
    )
    for task_type, keywords in rules:
        if any(keyword in normalized for keyword in keywords):
            return task_type
    return None
