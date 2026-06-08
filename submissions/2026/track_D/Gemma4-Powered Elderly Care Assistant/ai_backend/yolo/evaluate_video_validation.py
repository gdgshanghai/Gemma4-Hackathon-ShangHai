import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ultralytics import YOLO

from detection import run_video_detection


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = BASE_DIR / "video_validation" / "urfall_manifest.csv"
DEFAULT_WEIGHTS = BASE_DIR / "weights" / "best.pt"
DEFAULT_OUTPUT_DIR = BASE_DIR / "outputs" / "video_validation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate video validation clips with temporal fall confirmation."
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.45)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--confirm-frames", type=int, default=5)
    parser.add_argument("--min-fall-ratio", type=float, default=0.35)
    parser.add_argument("--frame-stride", type=int, default=1)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument(
        "--save-visual",
        action="store_true",
        help="Save annotated videos for each validation clip.",
    )
    return parser.parse_args()


def read_manifest(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def resolve_source(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else BASE_DIR / path


def classify_video(video_summary: Dict[str, Any], min_fall_ratio: float) -> str:
    if (
        video_summary.get("fall_alert")
        and float(video_summary.get("fall_frame_ratio") or 0.0) >= min_fall_ratio
    ):
        return "fall"
    return "no_fall"


def confusion_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    for row in rows:
        expected = row["expected_label"]
        predicted = row["predicted_label"]
        if expected == "fall" and predicted == "fall":
            counts["tp"] += 1
        elif expected == "no_fall" and predicted == "no_fall":
            counts["tn"] += 1
        elif expected == "no_fall" and predicted == "fall":
            counts["fp"] += 1
        elif expected == "fall" and predicted == "no_fall":
            counts["fn"] += 1
    return counts


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    weights_path = Path(args.weights).resolve()
    output_dir = Path(args.output_dir).resolve()
    run_root = output_dir / datetime.now().strftime("eval_%Y%m%d_%H%M%S")
    run_root.mkdir(parents=True, exist_ok=True)

    rows = read_manifest(manifest_path)
    model = YOLO(str(weights_path))
    results: List[Dict[str, Any]] = []

    for row in rows:
        source = resolve_source(row["source_path"]).resolve()
        clip_run_dir = run_root / row["id"]
        json_path = clip_run_dir / "predictions.json"
        payload = run_video_detection(
            model=model,
            source=str(source),
            weights=weights_path,
            run_dir=clip_run_dir,
            json_path=json_path,
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            save_visual=args.save_visual,
            max_frames=args.max_frames,
            frame_stride=args.frame_stride,
            show=False,
            confirm_frames=args.confirm_frames,
        )
        video_summary = payload["video_summary"]
        predicted_label = classify_video(video_summary, args.min_fall_ratio)
        results.append(
            {
                "id": row["id"],
                "expected_label": row["label"],
                "predicted_label": predicted_label,
                "correct": row["label"] == predicted_label,
                "fall_frames": video_summary["fall_frames"],
                "total_frames": video_summary["total_frames"],
                "fall_frame_ratio": video_summary["fall_frame_ratio"],
                "max_consecutive_fall_frames": video_summary[
                    "max_consecutive_fall_frames"
                ],
                "fall_alert": video_summary["fall_alert"],
                "json_path": str(json_path),
                "output_video": payload.get("output_video"),
            }
        )

    counts = confusion_counts(results)
    total = len(results)
    correct = sum(1 for row in results if row["correct"])
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "manifest": str(manifest_path),
        "weights": str(weights_path),
        "confirm_frames": args.confirm_frames,
        "min_fall_ratio": args.min_fall_ratio,
        "items": total,
        "correct": correct,
        "accuracy": round(correct / total, 6) if total else 0.0,
        **counts,
    }

    results_path = run_root / "results.csv"
    with results_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    summary_path = run_root / "summary.json"
    summary_path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"run_dir: {run_root}")
    print(f"results_csv: {results_path}")
    print(f"summary_json: {summary_path}")
    print(f"summary: {summary}")


if __name__ == "__main__":
    main()
