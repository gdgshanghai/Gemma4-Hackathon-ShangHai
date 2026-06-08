import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_WEIGHTS = BASE_DIR / "weights" / "best.pt"
DEFAULT_SOURCE = BASE_DIR / "inputs" / "test.jpg"
DEFAULT_OUTPUT_DIR = BASE_DIR / "outputs" / "detection"

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fall detection inference with annotated outputs and JSON results."
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Image, image folder, video file, or webcam index. Default: inputs/test.jpg",
    )
    parser.add_argument(
        "--weights",
        default=str(DEFAULT_WEIGHTS),
        help="YOLO weight path. Default: weights/best.pt",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Base output directory. Default: outputs/detection",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Run name under output-dir. Default: run_YYYYmmdd_HHMMSS",
    )
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size.")
    parser.add_argument("--conf", type=float, default=0.45, help="Confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IoU threshold.")
    parser.add_argument(
        "--json",
        default=None,
        help="JSON output path. Default: output-dir/name/predictions.json",
    )
    parser.add_argument(
        "--no-save-visual",
        action="store_true",
        help="Do not save annotated images/video.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Video/webcam frame limit. 0 means process the full video.",
    )
    parser.add_argument(
        "--frame-stride",
        type=int,
        default=1,
        help="Video frame stride. 1 means process every frame.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show video/webcam preview window while processing.",
    )
    parser.add_argument(
        "--confirm-frames",
        type=int,
        default=5,
        help="Video fall alert threshold. A fall is confirmed after N consecutive fall frames.",
    )
    return parser.parse_args()


def ensure_path(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")


def is_webcam_source(source: str) -> bool:
    return source.isdigit()


def source_type(source: str) -> str:
    if is_webcam_source(source):
        return "video"

    path = Path(source)
    if path.is_dir():
        return "image"

    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in VIDEO_SUFFIXES:
        return "video"

    raise ValueError(f"Unsupported source type: {source}")


def box_to_detection(box: Any, names: Dict[int, str]) -> Dict[str, Any]:
    class_id = int(box.cls[0])
    class_name = str(names.get(class_id, class_id))
    return {
        "class_id": class_id,
        "class_name": class_name,
        "confidence": round(float(box.conf[0]), 6),
        "bbox_xyxy": [round(float(v), 3) for v in box.xyxy[0].tolist()],
        "bbox_xywh": [round(float(v), 3) for v in box.xywh[0].tolist()],
    }


def result_to_record(result: Any, visual_dir: Optional[Path]) -> Dict[str, Any]:
    source_path = Path(str(result.path))
    names = result.names or {}
    detections = [box_to_detection(box, names) for box in result.boxes]
    max_confidence = max((item["confidence"] for item in detections), default=0.0)

    visual_path = None
    if visual_dir is not None:
        candidate = visual_dir / source_path.name
        visual_path = str(candidate) if candidate.exists() else None

    return {
        "source": str(source_path),
        "output_image": visual_path,
        "image_shape": list(result.orig_shape) if result.orig_shape else None,
        "fall_detected": bool(detections),
        "detection_count": len(detections),
        "max_confidence": max_confidence,
        "detections": detections,
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_payload(
    *,
    mode: str,
    source: str,
    weights: Path,
    run_dir: Path,
    json_path: Path,
    results: List[Dict[str, Any]],
    output_video: Optional[Path] = None,
) -> Dict[str, Any]:
    fall_count = sum(1 for item in results if item.get("fall_detected"))
    return {
        "task": "fall_detection",
        "mode": mode,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "weights": str(weights),
        "run_dir": str(run_dir),
        "json_path": str(json_path),
        "output_video": str(output_video) if output_video else None,
        "summary": {
            "items": len(results),
            "fall_detected_items": fall_count,
            "no_fall_items": len(results) - fall_count,
        },
        "results": results,
    }


def summarize_video_records(
    records: List[Dict[str, Any]], confirm_frames: int
) -> Dict[str, Any]:
    fall_frame_count = sum(1 for item in records if item.get("fall_detected"))
    confirmed_frame_count = sum(1 for item in records if item.get("confirmed_fall"))
    max_consecutive = 0
    current = 0

    for item in records:
        if item.get("fall_detected"):
            current += 1
            max_consecutive = max(max_consecutive, current)
        else:
            current = 0

    total = len(records)
    return {
        "confirm_frames": max(1, confirm_frames),
        "fall_alert": max_consecutive >= max(1, confirm_frames),
        "fall_frames": fall_frame_count,
        "confirmed_fall_frames": confirmed_frame_count,
        "total_frames": total,
        "fall_frame_ratio": round(fall_frame_count / total, 6) if total else 0.0,
        "max_consecutive_fall_frames": max_consecutive,
    }


def run_image_detection(
    model: YOLO,
    source: str,
    weights: Path,
    run_dir: Path,
    json_path: Path,
    imgsz: int,
    conf: float,
    iou: float,
    save_visual: bool,
) -> Dict[str, Any]:
    visual_dir = run_dir / "visualizations" if save_visual else None
    results = model.predict(
        source=source,
        imgsz=imgsz,
        conf=conf,
        iou=iou,
        save=save_visual,
        project=str(run_dir),
        name="visualizations",
        exist_ok=True,
        verbose=False,
    )

    records = [result_to_record(result, visual_dir) for result in results]
    payload = build_payload(
        mode="image",
        source=source,
        weights=weights,
        run_dir=run_dir,
        json_path=json_path,
        results=records,
    )
    write_json(json_path, payload)
    return payload


def open_video_source(source: str) -> cv2.VideoCapture:
    if is_webcam_source(source):
        return cv2.VideoCapture(int(source))
    return cv2.VideoCapture(source)


def run_video_detection(
    model: YOLO,
    source: str,
    weights: Path,
    run_dir: Path,
    json_path: Path,
    imgsz: int,
    conf: float,
    iou: float,
    save_visual: bool,
    max_frames: int,
    frame_stride: int,
    show: bool,
    confirm_frames: int = 5,
) -> Dict[str, Any]:
    cap = open_video_source(source)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video/webcam source: {source}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    frame_stride = max(1, frame_stride)

    output_video = None
    writer = None
    if save_visual:
        visual_dir = run_dir / "visualizations"
        visual_dir.mkdir(parents=True, exist_ok=True)
        output_video = visual_dir / "video_result.mp4"
        writer = cv2.VideoWriter(
            str(output_video),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )

    records: List[Dict[str, Any]] = []
    frame_index = 0
    processed = 0
    fall_streak = 0
    confirm_frames = max(1, confirm_frames)

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_index % frame_stride != 0:
            frame_index += 1
            continue

        result = model.predict(
            source=frame,
            imgsz=imgsz,
            conf=conf,
            iou=iou,
            verbose=False,
        )[0]
        names = result.names or {}
        detections = [box_to_detection(box, names) for box in result.boxes]
        has_fall = bool(detections)
        fall_streak = fall_streak + 1 if has_fall else 0
        confirmed_fall = fall_streak >= confirm_frames
        records.append(
            {
                "frame_index": frame_index,
                "timestamp_seconds": round(frame_index / fps, 3),
                "fall_detected": has_fall,
                "confirmed_fall": confirmed_fall,
                "fall_streak": fall_streak,
                "detection_count": len(detections),
                "max_confidence": max(
                    (item["confidence"] for item in detections), default=0.0
                ),
                "detections": detections,
            }
        )

        if writer is not None or show:
            annotated = result.plot()
            if writer is not None:
                writer.write(annotated)
            if show:
                cv2.imshow("Fall Detection", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        processed += 1
        frame_index += 1
        if max_frames > 0 and processed >= max_frames:
            break

    cap.release()
    if writer is not None:
        writer.release()
    if show:
        cv2.destroyAllWindows()

    payload = build_payload(
        mode="video",
        source=source,
        weights=weights,
        run_dir=run_dir,
        json_path=json_path,
        output_video=output_video,
        results=records,
    )
    payload["video_summary"] = summarize_video_records(records, confirm_frames)
    payload["summary"]["fall_alert"] = payload["video_summary"]["fall_alert"]
    payload["summary"]["confirmed_fall_frames"] = payload["video_summary"][
        "confirmed_fall_frames"
    ]
    payload["summary"]["max_consecutive_fall_frames"] = payload["video_summary"][
        "max_consecutive_fall_frames"
    ]
    write_json(json_path, payload)
    return payload


def main() -> None:
    args = parse_args()

    weights = Path(args.weights).resolve()
    ensure_path(weights, "weights")

    source = args.source
    if not is_webcam_source(source):
        ensure_path(Path(source), "source")

    run_name = args.name or datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_dir = Path(args.output_dir).resolve() / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = Path(args.json).resolve() if args.json else run_dir / "predictions.json"

    mode = source_type(source)
    model = YOLO(str(weights))
    save_visual = not args.no_save_visual

    if mode == "image":
        payload = run_image_detection(
            model=model,
            source=source,
            weights=weights,
            run_dir=run_dir,
            json_path=json_path,
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            save_visual=save_visual,
        )
    else:
        payload = run_video_detection(
            model=model,
            source=source,
            weights=weights,
            run_dir=run_dir,
            json_path=json_path,
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            save_visual=save_visual,
            max_frames=args.max_frames,
            frame_stride=args.frame_stride,
            show=args.show,
            confirm_frames=args.confirm_frames,
        )

    print(f"mode: {payload['mode']}")
    print(f"weights: {payload['weights']}")
    print(f"run_dir: {payload['run_dir']}")
    print(f"json_path: {payload['json_path']}")
    print(f"summary: {payload['summary']}")
    if payload.get("output_video"):
        print(f"output_video: {payload['output_video']}")


if __name__ == "__main__":
    main()
