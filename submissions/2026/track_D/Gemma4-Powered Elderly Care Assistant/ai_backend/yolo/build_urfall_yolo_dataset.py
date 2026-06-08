import argparse
import csv
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List

import cv2
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = BASE_DIR / "video_validation" / "urfall_full_manifest.csv"
DEFAULT_OUTPUT_DIR = BASE_DIR / "dataset_urfall_frames"
DEFAULT_WEIGHTS = BASE_DIR / "weights" / "best.pt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a YOLO frame dataset from UR Fall validation videos."
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    parser.add_argument("--frame-stride", type=int, default=15)
    parser.add_argument("--pseudo-conf", type=float, default=0.55)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--jpg-quality", type=int, default=92)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def read_manifest(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def split_for_id(item_id: str, val_ratio: float) -> str:
    digest = hashlib.md5(item_id.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return "val" if value < val_ratio else "train"


def ensure_dataset_dirs(output_dir: Path) -> None:
    for split in ("train", "val"):
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)


def write_data_yaml(output_dir: Path) -> None:
    text = "\n".join(
        [
            f"path: {str(output_dir).replace(chr(92), '/')}",
            "train: images/train",
            "val: images/val",
            "names:",
            "  0: fall",
            "",
        ]
    )
    (output_dir / "data.yaml").write_text(text, encoding="utf-8")


def yolo_label_from_box(box: Any, width: int, height: int) -> str:
    x_center, y_center, box_width, box_height = [
        float(value) for value in box.xywh[0].tolist()
    ]
    return "0 {:.6f} {:.6f} {:.6f} {:.6f}".format(
        x_center / width,
        y_center / height,
        box_width / width,
        box_height / height,
    )


def pseudo_labels(
    model: YOLO,
    frame: Any,
    width: int,
    height: int,
    imgsz: int,
    conf: float,
) -> List[str]:
    result = model.predict(source=frame, imgsz=imgsz, conf=conf, verbose=False)[0]
    return [yolo_label_from_box(box, width, height) for box in result.boxes]


def sampled_frame_indices(total_frames: int, stride: int) -> Iterable[int]:
    stride = max(1, stride)
    return range(0, max(0, total_frames), stride)


def process_video(
    row: Dict[str, str],
    output_dir: Path,
    model: YOLO,
    frame_stride: int,
    pseudo_conf: float,
    imgsz: int,
    val_ratio: float,
    jpg_quality: int,
    force: bool,
) -> List[Dict[str, Any]]:
    source = BASE_DIR / row["source_path"]
    split = split_for_id(row["id"], val_ratio)
    label = row["label"]
    records: List[Dict[str, Any]] = []

    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        return [
            {
                "source_id": row["id"],
                "source_path": str(source),
                "status": "open_failed",
            }
        ]

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        for frame_index in sampled_frame_indices(total_frames, frame_stride):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            stem = f"{row['id']}_f{frame_index:05d}"
            image_path = output_dir / "images" / split / f"{stem}.jpg"
            label_path = output_dir / "labels" / split / f"{stem}.txt"
            if image_path.exists() and label_path.exists() and not force:
                records.append(
                    {
                        "source_id": row["id"],
                        "frame_index": frame_index,
                        "split": split,
                        "label": label,
                        "image_path": str(image_path),
                        "label_path": str(label_path),
                        "box_count": len(label_path.read_text(encoding="utf-8").splitlines()),
                        "status": "skipped",
                    }
                )
                continue

            if label == "fall":
                lines = pseudo_labels(model, frame, width, height, imgsz, pseudo_conf)
                if not lines:
                    records.append(
                        {
                            "source_id": row["id"],
                            "frame_index": frame_index,
                            "split": split,
                            "label": label,
                            "image_path": "",
                            "label_path": "",
                            "box_count": 0,
                            "status": "needs_review",
                        }
                    )
                    continue
            else:
                lines = []

            cv2.imwrite(
                str(image_path),
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), jpg_quality],
            )
            label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            records.append(
                {
                    "source_id": row["id"],
                    "frame_index": frame_index,
                    "split": split,
                    "label": label,
                    "image_path": str(image_path),
                    "label_path": str(label_path),
                    "box_count": len(lines),
                    "status": "written",
                }
            )
    finally:
        cap.release()

    return records


def write_build_report(output_dir: Path, records: List[Dict[str, Any]]) -> None:
    report_path = output_dir / "build_report.csv"
    fieldnames = [
        "source_id",
        "frame_index",
        "split",
        "label",
        "image_path",
        "label_path",
        "box_count",
        "status",
    ]
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    summary = {
        "total_records": len(records),
        "written": sum(1 for item in records if item.get("status") == "written"),
        "skipped": sum(1 for item in records if item.get("status") == "skipped"),
        "needs_review": sum(
            1 for item in records if item.get("status") == "needs_review"
        ),
        "fall_images": sum(
            1
            for item in records
            if item.get("status") in {"written", "skipped"}
            and item.get("label") == "fall"
        ),
        "no_fall_images": sum(
            1
            for item in records
            if item.get("status") in {"written", "skipped"}
            and item.get("label") == "no_fall"
        ),
    }
    (output_dir / "build_summary.json").write_text(
        __import__("json").dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"report: {report_path}")
    print(f"summary: {summary}")


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    output_dir = Path(args.output_dir).resolve()
    ensure_dataset_dirs(output_dir)
    write_data_yaml(output_dir)

    rows = read_manifest(manifest_path)
    model = YOLO(str(Path(args.weights).resolve()))
    all_records: List[Dict[str, Any]] = []

    for index, row in enumerate(rows, start=1):
        print(f"[{index:03d}/{len(rows)}] {row['id']}")
        all_records.extend(
            process_video(
                row,
                output_dir,
                model,
                args.frame_stride,
                args.pseudo_conf,
                args.imgsz,
                args.val_ratio,
                args.jpg_quality,
                args.force,
            )
        )

    write_build_report(output_dir, all_records)


if __name__ == "__main__":
    main()
