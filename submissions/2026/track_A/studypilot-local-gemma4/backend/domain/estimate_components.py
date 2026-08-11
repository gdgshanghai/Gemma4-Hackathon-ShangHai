"""Deterministic cold-start workload components for evening tasks."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from math import ceil
from backend.contracts.evening import IntakeDraftTask
from backend.contracts.models import EstimateBreakdownItem, TaskCompletionState
from backend.domain.estimation import estimation_key
from backend.domain.family_calibration import FamilyCalibration, calibrated_minutes


class WorkloadBand(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


EstimateComponent = EstimateBreakdownItem


@dataclass(frozen=True, slots=True)
class ComponentEstimateResult:
    minutes: int
    breakdown: tuple[EstimateComponent, ...]
    signature: str | None
    source: str
    confidence: str


def estimate_task_components(
    task: IntakeDraftTask,
    *,
    calibration: FamilyCalibration,
    history_minutes: tuple[int, ...] = (),
    legacy_parent_minutes: int | None = None,
) -> ComponentEstimateResult:
    breakdown = build_reference_components(task)
    return estimate_component_snapshot(
        subject=task.subject,
        breakdown=breakdown,
        calibration=calibration,
        history_minutes=history_minutes,
        legacy_parent_minutes=legacy_parent_minutes,
        child_floor_minutes=task.child_estimate_minutes,
    )


def estimate_component_snapshot(
    *,
    subject: str | None,
    breakdown: tuple[EstimateComponent, ...],
    calibration: FamilyCalibration,
    history_minutes: tuple[int, ...] = (),
    legacy_parent_minutes: int | None = None,
    child_floor_minutes: int | None = None,
) -> ComponentEstimateResult:
    if not breakdown:
        return ComponentEstimateResult(0, (), None, "domain_default", "low")

    calibrated: list[EstimateComponent] = []
    matched_samples = 0
    for component in breakdown:
        factor = calibration.factor_for(subject, component.task_type)
        sample_count = calibration.sample_count_for(subject, component.task_type)
        matched_samples = max(matched_samples, sample_count)
        reference_component = component.model_copy(
            update={
                "calibrated_minutes": component.reference_minutes,
                "source": "domain_default",
                "confidence": "low",
            }
        )
        if sample_count:
            calibrated.append(
                reference_component.model_copy(
                    update={
                        "calibrated_minutes": calibrated_minutes(
                            component.reference_minutes,
                            factor,
                        ),
                        "source": "parent_range",
                        "confidence": _sample_confidence(sample_count),
                    }
                )
            )
        else:
            calibrated.append(reference_component)

    result_breakdown = tuple(calibrated)
    source = "parent_range" if matched_samples else "domain_default"
    confidence = _sample_confidence(matched_samples) if matched_samples else "low"
    valid_history = tuple(
        sorted(
            value
            for value in history_minutes
            if isinstance(value, int) and not isinstance(value, bool) and value > 0
        )
    )
    if len(valid_history) >= 3:
        selected = valid_history[ceil(len(valid_history) * 0.8) - 1]
        result_breakdown = _rescale_components(
            result_breakdown,
            selected,
            source="history_p80",
            confidence="high" if len(valid_history) >= 6 else "medium",
        )
        source = "history_p80"
        confidence = "high" if len(valid_history) >= 6 else "medium"
    elif matched_samples == 0 and legacy_parent_minutes is not None:
        result_breakdown = _rescale_components(
            result_breakdown,
            legacy_parent_minutes,
            source="parent_range",
            confidence="medium",
        )
        source = "parent_range"
        confidence = "medium"

    total = sum(component.calibrated_minutes for component in result_breakdown)
    if child_floor_minutes is not None and child_floor_minutes > total:
        result_breakdown = _rescale_components(
            result_breakdown,
            child_floor_minutes,
            source="child_adjusted",
            confidence="low",
        )
        total = sum(component.calibrated_minutes for component in result_breakdown)
        source = "child_adjusted"
        confidence = "low"

    return ComponentEstimateResult(
        minutes=total,
        breakdown=result_breakdown,
        signature=component_signature(result_breakdown),
        source=source,
        confidence=confidence,
    )


_BAND_RATIOS = {
    WorkloadBand.SMALL: (3, 4),
    WorkloadBand.MEDIUM: (1, 1),
    WorkloadBand.LARGE: (3, 2),
}
_MEDIUM_REFERENCE = {
    ("mathematics", "written"): 20,
    ("chinese", "written"): 10,
    ("english", "written"): 10,
    ("history", "written"): 20,
    ("civics", "written"): 20,
    ("biology", "written"): 5,
    (None, "written"): 20,
    (None, "reading"): 20,
    (None, "recitation"): 20,
    (None, "correction"): 5,
    (None, "preparation"): 10,
    (None, "map_reading"): 25,
}


def reference_minutes(
    subject: str | None,
    task_type: str,
    band: WorkloadBand = WorkloadBand.MEDIUM,
) -> int:
    canonical_subject, canonical_type = estimation_key(subject, task_type)
    selected_type = canonical_type or task_type
    base = _MEDIUM_REFERENCE.get(
        (canonical_subject, selected_type),
        _MEDIUM_REFERENCE.get((None, selected_type), 20),
    )
    numerator, denominator = _BAND_RATIOS[band]
    return _round_five(ceil(base * numerator / denominator))


def build_reference_components(task: IntakeDraftTask) -> tuple[EstimateComponent, ...]:
    if task.completion_state in {
        TaskCompletionState.COMPLETED,
        TaskCompletionState.NO_TASK,
    }:
        return ()
    subject, _ = estimation_key(task.subject, None)
    text = _normalize(" ".join(value for value in (task.title, task.notes) if value))
    components: list[EstimateComponent] = []

    if subject == "chinese" and any(word in text for word in ("阅读", "摘录")):
        pages = _remaining_quantity(text, total_pattern=r"(\d+)\s*页", unit="页") or 10
        reading_minutes = _scaled_reference(15, pages, 10)
        excerpt_minutes = 5 if "摘录" in text else 0
        components.append(
            _component(
                "reading_excerpt",
                "阅读与摘录",
                "reading",
                reading_minutes + excerpt_minutes,
                pages,
                "页",
            )
        )
        if "提纲" in text:
            components.append(_component("outline", "作文提纲", "written", 10))
        return tuple(components)

    if subject == "mathematics":
        if any(word in text for word in ("运算", "练习", "题")):
            if task.total_units is not None and task.completed_units is not None:
                questions = task.total_units - task.completed_units
            else:
                questions = (
                    _remaining_quantity(
                        text,
                        total_pattern=r"(\d+)\s*题",
                        unit="题",
                    )
                    or 6
                )
            if questions > 0:
                components.append(
                    _component(
                        "written_questions",
                        "剩余数学题",
                        "written",
                        _scaled_reference(10, questions, 6),
                        questions,
                        "题",
                    )
                )
        if any(word in text for word in ("订正", "错题")):
            components.append(_component("correction", "订正错题", "correction", 5))
        if components:
            return tuple(components)

    if subject == "english":
        recitation_minutes = 0
        if any(word in text for word in ("词汇", "单词")):
            recitation_minutes += 10
        if any(word in text for word in ("背诵", "课文")):
            recitation_minutes += 10
        if recitation_minutes:
            components.append(
                _component(
                    "vocabulary_recitation",
                    "词汇与背诵",
                    "recitation",
                    recitation_minutes,
                )
            )
        if "练习册" in text:
            pages = _remaining_workbook_pages(text)
            components.append(
                _component(
                    "workbook",
                    "练习册",
                    "written",
                    _scaled_reference(10, pages, 1),
                    pages,
                    "页",
                )
            )
        if components:
            return tuple(components)

    if subject == "history" and "时间轴" in text:
        return (_component("timeline", "时间轴剩余部分", "written", 10),)

    if subject == "geography":
        if any(word in text for word in ("经纬网", "读图")):
            questions = _first_int(text, r"(\d+)\s*题") or 8
            components.append(
                _component(
                    "map_reading",
                    "经纬网与读图",
                    "map_reading",
                    _scaled_reference(20, questions, 8),
                    questions,
                    "题",
                )
            )
        if any(word in text for word in ("订正", "小测")):
            components.append(_component("correction", "订正小测", "correction", 5))
        if components:
            return tuple(components)

    if subject == "biology":
        if any(word in text for word in ("结构图", "标注")):
            components.append(_component("diagram", "结构图标注", "written", 5))
        if "预习" in text:
            components.append(_component("preparation", "预习", "preparation", 10))
        if components:
            return tuple(components)

    if subject == "civics" and any(word in text for word in ("笔记", "整理")):
        minutes = 10 if task.completion_state is TaskCompletionState.PARTIAL else 20
        return (_component("notes", "课堂笔记剩余部分", "written", minutes),)

    _, task_type = estimation_key(task.subject, None, title=task.title)
    selected_type = task_type or "written"
    minutes = reference_minutes(subject, selected_type)
    if task.completion_state is TaskCompletionState.PARTIAL:
        minutes = _round_five(ceil(minutes / 2))
    return (_component("general", task.title, selected_type, minutes),)


def component_signature(components: tuple[EstimateComponent, ...]) -> str:
    return "+".join(sorted(component.component for component in components))


def _component(
    kind: str,
    label: str,
    task_type: str,
    minutes: int,
    quantity: int | None = None,
    unit: str | None = None,
) -> EstimateComponent:
    rounded = _round_five(minutes) if minutes else 0
    return EstimateComponent(
        component=kind,
        label=label,
        task_type=task_type,
        remaining_quantity=quantity,
        unit=unit,
        reference_minutes=rounded,
        calibrated_minutes=rounded,
        source="domain_default",
        confidence="low",
    )


def _remaining_quantity(text: str, *, total_pattern: str, unit: str) -> int | None:
    remaining = _first_int(text, rf"还剩\s*(\d+)\s*{re.escape(unit)}")
    if remaining is not None:
        return remaining
    total = _first_int(text, total_pattern)
    completed = _first_int(text, rf"(?:已完成前|已完成|做完)\s*(\d+)\s*{re.escape(unit)}?")
    if total is not None and completed is not None:
        return max(total - completed, 0)
    return total


def _remaining_workbook_pages(text: str) -> int:
    total = _first_int(text, r"练习册\s*(\d+)\s*页") or 1
    completed = _first_int(text, r"(?:练习册)?做完\s*(\d+)\s*页") or 0
    return max(total - completed, 1)


def _first_int(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text)
    return int(match.group(1)) if match is not None else None


def _scaled_reference(minutes: int, quantity: int, reference_quantity: int) -> int:
    return _round_five(ceil(minutes * quantity / reference_quantity))


def _round_five(value: int) -> int:
    return max(5, ((value + 4) // 5) * 5)


def _sample_confidence(sample_count: int) -> str:
    if sample_count >= 5:
        return "high"
    if sample_count >= 2:
        return "medium"
    return "low"


def _rescale_components(
    components: tuple[EstimateComponent, ...],
    target_minutes: int,
    *,
    source: str,
    confidence: str,
) -> tuple[EstimateComponent, ...]:
    target = max(len(components) * 5, _round_five(target_minutes))
    available_units = target // 5 - len(components)
    weights = [max(component.calibrated_minutes, 1) for component in components]
    weight_total = sum(weights)
    raw_units = [available_units * weight / weight_total for weight in weights]
    allocated = [int(value) for value in raw_units]
    remaining = available_units - sum(allocated)
    order = sorted(
        range(len(components)),
        key=lambda index: (raw_units[index] - allocated[index], weights[index]),
        reverse=True,
    )
    for index in order[:remaining]:
        allocated[index] += 1
    return tuple(
        component.model_copy(
            update={
                "calibrated_minutes": (allocated[index] + 1) * 5,
                "source": source,
                "confidence": confidence,
            }
        )
        for index, component in enumerate(components)
    )


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()
