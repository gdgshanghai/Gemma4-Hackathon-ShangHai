import argparse
import csv
import hashlib
from pathlib import Path
from typing import Dict, List


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = BASE_DIR / "video_validation" / "urfall_full_manifest.csv"
DEFAULT_TRAIN = BASE_DIR / "video_validation" / "urfall_train_manifest.csv"
DEFAULT_HOLDOUT = BASE_DIR / "video_validation" / "urfall_holdout_manifest.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split UR Fall videos into train and holdout manifests."
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--train-output", default=str(DEFAULT_TRAIN))
    parser.add_argument("--holdout-output", default=str(DEFAULT_HOLDOUT))
    parser.add_argument("--holdout-ratio", type=float, default=0.2)
    return parser.parse_args()


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def stable_value(text: str) -> float:
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def write_rows(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    rows = read_rows(Path(args.manifest).resolve())
    fieldnames = list(rows[0].keys())
    holdout_ratio = max(0.0, min(1.0, args.holdout_ratio))

    train_rows: List[Dict[str, str]] = []
    holdout_rows: List[Dict[str, str]] = []
    labels = sorted({row["label"] for row in rows})
    for label in labels:
        label_rows = [row for row in rows if row["label"] == label]
        label_rows.sort(key=lambda row: stable_value(row["id"]))
        holdout_count = max(1, round(len(label_rows) * holdout_ratio))
        holdout_rows.extend(label_rows[:holdout_count])
        train_rows.extend(label_rows[holdout_count:])

    train_rows.sort(key=lambda row: row["id"])
    holdout_rows.sort(key=lambda row: row["id"])

    write_rows(Path(args.train_output).resolve(), train_rows, fieldnames)
    write_rows(Path(args.holdout_output).resolve(), holdout_rows, fieldnames)

    print(
        {
            "total": len(rows),
            "train": len(train_rows),
            "holdout": len(holdout_rows),
            "train_fall": sum(1 for row in train_rows if row["label"] == "fall"),
            "train_no_fall": sum(1 for row in train_rows if row["label"] == "no_fall"),
            "holdout_fall": sum(1 for row in holdout_rows if row["label"] == "fall"),
            "holdout_no_fall": sum(1 for row in holdout_rows if row["label"] == "no_fall"),
        }
    )


if __name__ == "__main__":
    main()
