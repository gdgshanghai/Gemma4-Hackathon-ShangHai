"""Read-only Hugging Face DatasetDict adapter for the ASD-DS raw dataset."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Iterable

from datasets import Dataset, DatasetDict, Features, Sequence, Value


DEFAULT_ROOT = Path("data/raw/ASD-DS")
SCHEMA_VERSION = "1.0"

SPLIT_FILES = {
    "train": "train.csv",
    "validation": "val.csv",
    "test": "test.csv",
}

FEATURE_SPECS = (
    {
        "id": "B01",
        "column": "Absence or Avoidance of Eye Contact",
        "slug": "absence_or_avoidance_of_eye_contact",
    },
    {
        "id": "B02",
        "column": "Aggressive Behavior",
        "slug": "aggressive_behavior",
    },
    {
        "id": "B03",
        "column": "Hyper- or Hyporeactivity to Sensory Input",
        "slug": "hyper_or_hyporeactivity_to_sensory_input",
    },
    {
        "id": "B04",
        "column": "Non-Responsiveness to Verbal Interaction",
        "slug": "non_responsiveness_to_verbal_interaction",
    },
    {
        "id": "B05",
        "column": "Non-Typical Language",
        "slug": "non_typical_language",
    },
    {
        "id": "B06",
        "column": "Object Lining-Up",
        "slug": "object_lining_up",
    },
    {
        "id": "B07",
        "column": "Self-Hitting or Self-Injurious Behavior",
        "slug": "self_hitting_or_self_injurious_behavior",
    },
    {
        "id": "B08",
        "column": "Self-Spinning or Spinning Objects",
        "slug": "self_spinning_or_spinning_objects",
    },
    {
        "id": "B09",
        "column": "Upper Limb Stereotypies",
        "slug": "upper_limb_stereotypies",
    },
    {
        "id": "B10",
        "column": "Background",
        "slug": "background",
    },
)

FEATURE_IDS = tuple(spec["id"] for spec in FEATURE_SPECS)
LABEL_COLUMNS = tuple(spec["column"] for spec in FEATURE_SPECS)
FEATURE_ID_TO_COLUMN = {spec["id"]: spec["column"] for spec in FEATURE_SPECS}
FEATURE_ID_TO_SLUG = {spec["id"]: spec["slug"] for spec in FEATURE_SPECS}
BACKGROUND_FEATURE_ID = "B10"
BEHAVIOR_FEATURE_IDS = FEATURE_IDS[:-1]
LABEL_CODE_RE = re.compile(r"^[01]{9}$")


HF_FEATURES = Features(
    {
        "split": Value("string"),
        "row_idx": Value("int64"),
        "video_id": Value("string"),
        "source_id": Value("string"),
        "start_sec": Value("int64"),
        "end_sec": Value("int64"),
        "duration_sec": Value("int64"),
        "video_path": Value("string"),
        "audio_path": Value("string"),
        "label_vector": Sequence(Value("int64"), length=len(FEATURE_IDS)),
        "labels": {feature_id: Value("bool") for feature_id in FEATURE_IDS},
        "positive_feature_ids": Sequence(Value("string")),
        "positive_label_names": Sequence(Value("string")),
        "target_code": Value("string"),
        "target_json": Value("string"),
    }
)


def get_feature_specs() -> tuple[dict[str, str], ...]:
    """Return the canonical feature schema used by this adapter."""
    return tuple(dict(spec) for spec in FEATURE_SPECS)


def parse_video_id(video_id: str) -> tuple[str, int, int]:
    """Parse '<source_id>_<start_sec>_<end_sec>' IDs without assuming source shape."""
    try:
        source_id, start_raw, end_raw = video_id.rsplit("_", 2)
        start_sec = int(start_raw)
        end_sec = int(end_raw)
    except ValueError as exc:
        raise ValueError(f"Invalid Video_ID format: {video_id!r}") from exc

    if end_sec <= start_sec:
        raise ValueError(f"Invalid Video_ID time range: {video_id!r}")
    return source_id, start_sec, end_sec


def build_target_json(labels: dict[str, bool]) -> str:
    """Build the final app-report reference JSON for one sample."""
    overall = "background" if labels[BACKGROUND_FEATURE_ID] else "behavior_features_observed"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "features": {feature_id: bool(labels[feature_id]) for feature_id in FEATURE_IDS},
        "overall": overall,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def build_target_code(labels: dict[str, bool]) -> str:
    """Build the supervised assistant target code for B01 through B09."""
    return "".join("1" if labels[feature_id] else "0" for feature_id in BEHAVIOR_FEATURE_IDS)


def build_report_from_code(code: str) -> dict:
    """Build the final report JSON object from a strict 9-bit B01-B09 code."""
    if LABEL_CODE_RE.fullmatch(code) is None:
        raise ValueError(f"Invalid label code: {code!r}")

    behavior_values = [char == "1" for char in code]
    background = not any(behavior_values)
    features = {
        feature_id: value
        for feature_id, value in zip(BEHAVIOR_FEATURE_IDS, behavior_values, strict=True)
    }
    features[BACKGROUND_FEATURE_ID] = background
    return {
        "schema_version": SCHEMA_VERSION,
        "features": features,
        "overall": "background" if background else "behavior_features_observed",
    }


def load_asd_ds(
    root: str | Path = DEFAULT_ROOT,
    *,
    validate: bool = True,
    splits: Iterable[str] = ("train", "validation", "test"),
) -> DatasetDict:
    """Load ASD-DS as an in-memory Hugging Face DatasetDict.

    This function does not decode media and does not write to the raw dataset.
    Returned rows carry file paths, parsed clip timing, canonical labels, the
    deterministic 9-bit assistant target code, and final JSON report reference.
    """
    root = Path(root)
    split_names = tuple(splits)
    unknown_splits = sorted(set(split_names) - set(SPLIT_FILES))
    if unknown_splits:
        raise ValueError(f"Unknown splits: {unknown_splits}. Valid splits: {sorted(SPLIT_FILES)}")

    if validate:
        _validate_root(root, split_names)

    dataset_dict = DatasetDict()
    for split in split_names:
        records = _load_split_records(root, split, validate=validate)
        dataset_dict[split] = Dataset.from_list(records, features=HF_FEATURES)

    if validate:
        _validate_no_source_overlap(dataset_dict)

    return dataset_dict


def _load_split_records(root: Path, split: str, *, validate: bool) -> list[dict]:
    csv_path = root / "csvs" / SPLIT_FILES[split]
    records = []
    seen_ids = set()

    with csv_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_columns(csv_path, reader.fieldnames)

        for row_idx, row in enumerate(reader):
            video_id = row["Video_ID"]
            if validate and video_id in seen_ids:
                raise ValueError(f"Duplicate Video_ID in {csv_path}: {video_id}")
            seen_ids.add(video_id)

            source_id, start_sec, end_sec = parse_video_id(video_id)
            video_path = root / "clips_video" / f"{video_id}.mp4"
            audio_path = root / "clips_audio" / f"{video_id}.wav"

            if validate:
                if not video_path.is_file():
                    raise FileNotFoundError(f"Missing video file for {video_id}: {video_path}")
                if not audio_path.is_file():
                    raise FileNotFoundError(f"Missing audio file for {video_id}: {audio_path}")

            label_vector = []
            labels = {}
            for feature_id, column in zip(FEATURE_IDS, LABEL_COLUMNS, strict=True):
                value = row[column]
                if validate and value not in {"0", "1"}:
                    raise ValueError(
                        f"Non-binary label in {csv_path}, row {row_idx + 2}, "
                        f"column {column!r}: {value!r}"
                    )
                label_int = int(value)
                label_vector.append(label_int)
                labels[feature_id] = bool(label_int)

            behavior_sum = sum(label_vector[:-1])
            expected_background = behavior_sum == 0
            if validate and labels[BACKGROUND_FEATURE_ID] != expected_background:
                raise ValueError(f"Background is not derived correctly for {video_id}")

            positive_feature_ids = [
                feature_id for feature_id, label_int in zip(FEATURE_IDS, label_vector, strict=True) if label_int
            ]
            positive_label_names = [FEATURE_ID_TO_COLUMN[feature_id] for feature_id in positive_feature_ids]
            target_code = build_target_code(labels)

            records.append(
                {
                    "split": split,
                    "row_idx": row_idx,
                    "video_id": video_id,
                    "source_id": source_id,
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                    "duration_sec": end_sec - start_sec,
                    "video_path": str(video_path),
                    "audio_path": str(audio_path),
                    "label_vector": label_vector,
                    "labels": labels,
                    "positive_feature_ids": positive_feature_ids,
                    "positive_label_names": positive_label_names,
                    "target_code": target_code,
                    "target_json": build_target_json(labels),
                }
            )

    return records


def _validate_root(root: Path, split_names: Iterable[str]) -> None:
    if not root.is_dir():
        raise FileNotFoundError(f"ASD-DS root does not exist: {root}")

    required_dirs = (root / "csvs", root / "clips_video", root / "clips_audio")
    for directory in required_dirs:
        if not directory.is_dir():
            raise FileNotFoundError(f"Missing ASD-DS directory: {directory}")

    for split in split_names:
        csv_path = root / "csvs" / SPLIT_FILES[split]
        if not csv_path.is_file():
            raise FileNotFoundError(f"Missing split CSV: {csv_path}")


def _validate_columns(csv_path: Path, fieldnames: list[str] | None) -> None:
    expected = ("Video_ID", *LABEL_COLUMNS)
    actual = tuple(fieldnames or ())
    if actual != expected:
        raise ValueError(
            f"Unexpected columns in {csv_path}.\n"
            f"Expected: {expected}\n"
            f"Actual:   {actual}"
        )


def _validate_no_source_overlap(dataset_dict: DatasetDict) -> None:
    sources_by_split = {
        split: set(dataset["source_id"])
        for split, dataset in dataset_dict.items()
        if split in {"train", "validation", "test"}
    }
    split_names = tuple(sources_by_split)
    for idx, left in enumerate(split_names):
        for right in split_names[idx + 1 :]:
            overlap = sources_by_split[left] & sources_by_split[right]
            if overlap:
                sample = sorted(overlap)[:10]
                raise ValueError(f"Source-level overlap between {left} and {right}: {sample}")


def summarize(dataset_dict: DatasetDict) -> dict:
    """Return a small summary useful for sanity checks and logs."""
    summary = {}
    for split, dataset in dataset_dict.items():
        label_counts = {feature_id: 0 for feature_id in FEATURE_IDS}
        durations = list(dataset["duration_sec"])
        for labels in dataset["labels"]:
            for feature_id in FEATURE_IDS:
                label_counts[feature_id] += int(labels[feature_id])

        summary[split] = {
            "rows": len(dataset),
            "sources": len(set(dataset["source_id"])),
            "duration_min_sec": min(durations) if durations else None,
            "duration_max_sec": max(durations) if durations else None,
            "duration_mean_sec": sum(durations) / len(durations) if durations else None,
            "label_counts": label_counts,
        }
    return summary


if __name__ == "__main__":
    ds = load_asd_ds()
    print(json.dumps(summarize(ds), indent=2, sort_keys=True))
