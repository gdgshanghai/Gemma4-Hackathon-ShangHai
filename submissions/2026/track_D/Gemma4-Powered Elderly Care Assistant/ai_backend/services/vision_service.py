import base64
import os
import time
from pathlib import Path
from typing import Any


class VisionService:
    """OpenCV + YOLO adapter for fall detection."""

    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parents[1]
        self.weights_dir = self.base_dir / "yolo"
        self.fall_model_path = self._select_fall_model_path()
        self.person_model_path = self.weights_dir / "person.pt"
        self.fall_model: Any | None = None
        self.person_model: Any | None = None
        self.model_error: str | None = None
        self.names: dict[int, str] = {}

    def _select_fall_model_path(self) -> Path:
        candidates = [
            self.weights_dir / "best_urfall_finetuned.pt",
            self.weights_dir / "weights" / "best.pt",
            self.weights_dir / "best.pt",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def _load_model(self, model_path: Path):
        if self.model_error is not None:
            raise RuntimeError(self.model_error)
        if not model_path.exists():
            self.model_error = f"YOLO weights not found: {model_path}"
            raise RuntimeError(self.model_error)

        try:
            os.environ.setdefault("YOLO_CONFIG_DIR", str(self.base_dir / ".ultralytics"))
            from ultralytics import YOLO

            model = YOLO(str(model_path))
            self.names = dict(getattr(model, "names", {}) or {})
            return model
        except Exception as exc:
            self.model_error = f"Failed to load YOLO model: {exc}"
            raise RuntimeError(self.model_error)

    def _load_fall_model(self):
        if self.fall_model is None:
            self.fall_model = self._load_model(self.fall_model_path)
        return self.fall_model

    def _load_person_model(self):
        if self.person_model_path.exists():
            if self.person_model is None:
                self.person_model = self._load_model(self.person_model_path)
            return self.person_model
        return None

    def _fallback_demo_detection(self, source: str = "demo_camera") -> dict:
        simulated_fall = int(time.time()) % 18 >= 9
        confidence = 0.9 if simulated_fall else 0.18
        return {
            "fall_detected": simulated_fall,
            "confidence": confidence,
            "label": "fall" if simulated_fall else "person",
            "fps": 28,
            "detections": [
                {
                    "id": "elderly-person-1",
                    "label": "fall" if simulated_fall else "person",
                    "confidence": confidence,
                    "fall_detected": simulated_fall,
                    "x": 0.28 if simulated_fall else 0.42,
                    "y": 0.58 if simulated_fall else 0.20,
                    "width": 0.42 if simulated_fall else 0.18,
                    "height": 0.18 if simulated_fall else 0.52,
                }
            ],
            "source": source,
            "model": "demo-fallback",
            "model_ready": False,
        }

    def health(self) -> dict:
        try:
            self._load_fall_model()
            person_ready = self._load_person_model() is not None
            return {
                "model_ready": True,
                "fall_model_path": str(self.fall_model_path),
                "person_model_path": str(self.person_model_path) if person_ready else None,
                "classes": self.names,
                "error": None,
            }
        except Exception as exc:
            return {
                "model_ready": False,
                "fall_model_path": str(self.fall_model_path),
                "person_model_path": str(self.person_model_path) if self.person_model_path.exists() else None,
                "classes": {},
                "error": str(exc),
            }

    def detect_fall(self, frame_path: str | None = None) -> dict:
        if not frame_path:
            return self._fallback_demo_detection()

        try:
            return self._predict_source(frame_path, source_label=frame_path)
        except Exception as exc:
            result = self._fallback_demo_detection(frame_path)
            result["error"] = str(exc)
            return result

    def detect_frame_data_url(self, frame_data_url: str) -> dict:
        try:
            import cv2
            import numpy as np
        except Exception as exc:
            raise RuntimeError(f"OpenCV/Numpy dependency missing: {exc}") from exc

        if "," in frame_data_url:
            frame_data_url = frame_data_url.split(",", 1)[1]

        raw = base64.b64decode(frame_data_url)
        image_array = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError("Could not decode uploaded frame.")

        return self._predict_source(frame, source_label="browser-camera-frame")

    def analyze_video(self, video_path: str, max_frames: int = 80, frame_stride: int = 5) -> dict:
        try:
            import cv2
        except Exception as exc:
            raise RuntimeError(f"OpenCV dependency missing: {exc}") from exc

        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        fps = capture.get(cv2.CAP_PROP_FPS) or 25
        frame_index = 0
        processed = 0
        fall_frames = 0
        best_result: dict | None = None

        try:
            while processed < max_frames:
                ok, frame = capture.read()
                if not ok:
                    break
                if frame_index % max(1, frame_stride) != 0:
                    frame_index += 1
                    continue

                result = self._predict_source(frame, source_label=f"video-frame-{frame_index}")
                result["frame_index"] = frame_index
                result["timestamp_seconds"] = round(frame_index / fps, 3)
                if result["fall_detected"]:
                    fall_frames += 1

                if best_result is None or result["confidence"] > best_result.get("confidence", 0):
                    best_result = result

                processed += 1
                frame_index += 1
        finally:
            capture.release()

        best_result = best_result or {
            "fall_detected": False,
            "confidence": 0,
            "label": "person",
            "fps": 0,
            "detections": [],
            "source": video_path,
            "model": str(self.fall_model_path),
            "person_model": str(self.person_model_path) if self.person_model_path.exists() else None,
            "model_ready": True,
        }
        fall_ratio = fall_frames / processed if processed else 0
        best_result["fall_detected"] = best_result["fall_detected"] or fall_ratio >= 0.25
        best_result["frames_processed"] = processed
        best_result["fall_frames"] = fall_frames
        best_result["fall_frame_ratio"] = round(fall_ratio, 4)
        best_result["duration"] = round(frame_index / fps, 2) if fps else 0
        return best_result

    def _predict_source(self, source: Any, source_label: str) -> dict:
        started = time.perf_counter()
        fall_model = self._load_fall_model()
        person_model = self._load_person_model()
        fall_result = fall_model.predict(source=source, imgsz=640, conf=0.35, iou=0.45, verbose=False)[0]
        person_result = (
            person_model.predict(source=source, imgsz=640, conf=0.35, iou=0.45, verbose=False)[0]
            if person_model is not None
            else None
        )
        elapsed = max(time.perf_counter() - started, 0.001)
        image_height, image_width = fall_result.orig_shape
        detections = []

        for index, box in enumerate(person_result.boxes if person_result is not None else []):
            confidence = float(box.conf[0])
            class_id = int(box.cls[0])
            label = str(person_result.names.get(class_id, "person"))
            if label.lower() not in {"0", "person"}:
                continue
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            detections.append(
                {
                    "id": f"person-{index + 1}",
                    "class_id": class_id,
                    "label": "person" if label.lower() in {"0", "person"} else label,
                    "confidence": round(confidence, 4),
                    "fall_detected": False,
                    "x": round(max(0.0, x1 / image_width), 6),
                    "y": round(max(0.0, y1 / image_height), 6),
                    "width": round(max(0.0, (x2 - x1) / image_width), 6),
                    "height": round(max(0.0, (y2 - y1) / image_height), 6),
                }
            )

        fall_detections = []
        for index, box in enumerate(fall_result.boxes):
            confidence = float(box.conf[0])
            class_id = int(box.cls[0])
            label = str(fall_result.names.get(class_id, "fall"))
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            fall_box = {
                "id": f"fall-{index + 1}",
                "class_id": class_id,
                "label": "fall",
                "confidence": round(confidence, 4),
                "fall_detected": True,
                "x": round(max(0.0, x1 / image_width), 6),
                "y": round(max(0.0, y1 / image_height), 6),
                "width": round(max(0.0, (x2 - x1) / image_width), 6),
                "height": round(max(0.0, (y2 - y1) / image_height), 6),
            }
            fall_detections.append(fall_box)
            detections.append(fall_box)

        posture_fall = None
        if not fall_detections:
            posture_fall = self._detect_fall_posture(detections)
            if posture_fall is not None:
                fall_detections.append(posture_fall)

        max_detection = max(detections, key=lambda item: item["confidence"], default=None)
        max_fall = max(fall_detections, key=lambda item: item["confidence"], default=None)

        return {
            "fall_detected": bool(max_fall),
            "confidence": float((max_fall or max_detection or {}).get("confidence", 0)),
            "label": (max_fall or max_detection or {}).get("label", "person"),
            "fps": round(1 / elapsed),
            "detections": detections,
            "source": source_label,
            "model": str(self.fall_model_path),
            "person_model": str(self.person_model_path) if person_model is not None else None,
            "model_ready": True,
        }

    def _detect_fall_posture(self, detections: list[dict]) -> dict | None:
        """Infer a suspected fall from a horizontal person box when fall YOLO misses."""
        person_boxes = [item for item in detections if item.get("label") == "person"]
        if not person_boxes:
            return None

        best_candidate = None
        best_score = 0.0
        for box in person_boxes:
            width = float(box.get("width") or 0)
            height = float(box.get("height") or 0)
            y = float(box.get("y") or 0)
            confidence = float(box.get("confidence") or 0)
            if width <= 0 or height <= 0:
                continue

            aspect_ratio = width / height
            bottom = y + height
            is_horizontal = aspect_ratio >= 1.55 and height <= 0.42
            is_low_floor = bottom >= 0.66 and height <= 0.46
            is_compact_low = aspect_ratio >= 1.25 and height <= 0.32 and bottom >= 0.58
            if not (is_horizontal or (is_horizontal and is_low_floor) or is_compact_low):
                continue

            horizontal_score = min(1.0, max(0.0, (aspect_ratio - 1.45) / 1.35))
            low_height_score = min(1.0, max(0.0, (0.46 - height) / 0.28))
            floor_score = min(1.0, max(0.0, (bottom - 0.6) / 0.28))
            score = confidence * (
                0.5 * horizontal_score
                + 0.3 * low_height_score
                + 0.2 * floor_score
            )

            if score > best_score:
                best_score = score
                best_candidate = box

        if best_candidate is None or best_score < 0.18:
            return None

        best_candidate["fall_detected"] = True
        best_candidate["label"] = "suspected_fall"
        best_candidate["posture_fall"] = True
        best_candidate["confidence"] = round(min(0.68, 0.36 + best_score), 4)
        return best_candidate
