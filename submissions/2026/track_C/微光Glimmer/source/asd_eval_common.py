from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from asd_ds_dataset import FEATURE_ID_TO_COLUMN, FEATURE_IDS, LABEL_CODE_RE, build_report_from_code


DEFAULT_DATA_ROOT = "data/raw/ASD-DS"
DEFAULT_MODEL_DIR = "/home/huzi/Downloads/gemma-4-E4B-it"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_PROMPT_LANG = "en"
PROMPT_LANGS = ("en", "zh")
BREW_BIN = Path("/home/linuxbrew/.linuxbrew/bin")


@dataclass(frozen=True)
class PromptBundle:
    lang: str
    system: str
    user: str
    system_path: Path
    user_path: Path


def load_prompt_bundle(prompt_lang: str) -> PromptBundle:
    lang = prompt_lang.strip().lower()
    prompt_dir = PROMPTS_DIR / lang
    system_path = prompt_dir / "system.md"
    user_path = prompt_dir / "user.md"
    missing = [str(path) for path in (system_path, user_path) if not path.is_file()]
    if missing:
        raise click.ClickException(f"Missing prompt file(s) for --prompt-lang {lang}: {', '.join(missing)}")

    system_prompt = system_path.read_text(encoding="utf-8").strip()
    user_prompt = user_path.read_text(encoding="utf-8").strip()
    if not system_prompt:
        raise click.ClickException(f"Prompt file is empty: {system_path}")
    if not user_prompt:
        raise click.ClickException(f"Prompt file is empty: {user_path}")

    return PromptBundle(
        lang=lang,
        system=system_prompt,
        user=user_prompt,
        system_path=system_path,
        user_path=user_path,
    )


def find_tool(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path

    venv_path = Path(__file__).parent / ".venv" / "bin" / name
    if venv_path.is_file():
        return str(venv_path)

    brew_path = BREW_BIN / name
    if brew_path.is_file():
        return str(brew_path)

    raise click.ClickException(f"Could not find {name}. Install it or add it to PATH.")


def run_command(
    command: list[str],
    *,
    capture_stdout: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE if capture_stdout else None,
            stderr=subprocess.PIPE,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise click.ClickException(f"Command failed: {' '.join(command)}\n{stderr}") from exc


def stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sanitize_cache_name(value: str) -> str:
    sanitized = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return sanitized[:90] or "sample"


def requested_frame_count(*, duration_sec: float, fps: float, max_frames: int) -> int:
    if duration_sec <= 0:
        return 1
    return max(1, min(max_frames, int(np.ceil(duration_sec * fps))))


def sampled_frame_fps(frame_count: int, duration_sec: float) -> float:
    if duration_sec <= 0:
        return float(frame_count)
    return frame_count / duration_sec


def load_video_frames(
    *,
    ffmpeg: str,
    video_path: Path,
    fps: float,
    max_frames: int,
    image_width: int,
    duration_sec: float,
) -> list[Image.Image]:
    frame_count = requested_frame_count(duration_sec=duration_sec, fps=fps, max_frames=max_frames)
    ffmpeg_fps = sampled_frame_fps(frame_count, duration_sec)

    with tempfile.TemporaryDirectory(prefix="asd_ds_frames_") as tmpdir:
        out_pattern = Path(tmpdir) / "frame_%04d.jpg"
        command = [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vf",
            f"fps={ffmpeg_fps:.8f},scale={image_width}:-2",
            "-frames:v",
            str(frame_count),
            str(out_pattern),
        ]
        run_command(command)
        frame_paths = sorted(Path(tmpdir).glob("frame_*.jpg"))
        if not frame_paths:
            raise click.ClickException(f"ffmpeg produced no frames for {video_path}")
        return [Image.open(path).convert("RGB").copy() for path in frame_paths]


def prepare_media(
    *,
    ffmpeg: str,
    row: dict[str, Any],
    sample_index: int,
    media_cache_dir: Path,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    use_audio: bool,
    rebuild: bool,
) -> dict[str, Any]:
    duration_sec = float(row["duration_sec"])
    frame_count = requested_frame_count(duration_sec=duration_sec, fps=frame_fps, max_frames=max_frames)
    config = {
        "version": "litert_eval_media_v1",
        "video_path": str(row["video_path"]),
        "audio_path": str(row["audio_path"]),
        "duration_sec": duration_sec,
        "frame_fps": frame_fps,
        "max_frames": max_frames,
        "max_audio_seconds": max_audio_seconds,
        "image_width": image_width,
        "frame_count": frame_count,
        "use_audio": use_audio,
    }
    if use_audio:
        config.update(
            {
                "audio_codec": "pcm_s16le",
                "audio_sample_rate": 16000,
                "audio_channels": 1,
            }
        )
    digest = stable_hash(config)[:12]
    sample_dir = media_cache_dir / f"{sample_index:04d}_{sanitize_cache_name(str(row['video_id']))}_{digest}"
    manifest_path = sample_dir / "manifest.json"
    if not rebuild and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        frame_paths = [Path(path) for path in manifest["frame_paths"]]
        audio_path = Path(manifest["audio_path"]) if manifest.get("audio_path") else None
        audio_ready = audio_path is None or audio_path.is_file()
        if audio_ready and all(path.is_file() for path in frame_paths):
            return {"frame_paths": frame_paths, "audio_path": audio_path}

    if sample_dir.exists():
        shutil.rmtree(sample_dir)
    sample_dir.mkdir(parents=True, exist_ok=True)

    frames = load_video_frames(
        ffmpeg=ffmpeg,
        video_path=Path(row["video_path"]),
        fps=frame_fps,
        max_frames=max_frames,
        image_width=image_width,
        duration_sec=duration_sec,
    )
    frame_paths = []
    for frame_index, frame in enumerate(frames):
        frame_path = sample_dir / f"frame_{frame_index:04d}.jpg"
        frame.save(frame_path, format="JPEG", quality=95)
        frame_paths.append(frame_path.resolve())

    audio_path = None
    if use_audio:
        audio_path = (sample_dir / "audio_16k_mono.wav").resolve()
        run_command(
            [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(row["audio_path"]),
                "-t",
                f"{min(duration_sec, max_audio_seconds):.3f}",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(audio_path),
            ]
        )
        if not audio_path.is_file():
            raise click.ClickException(f"ffmpeg did not create audio file: {audio_path}")

    manifest = {
        "config": config,
        "frame_paths": [str(path) for path in frame_paths],
        "audio_path": str(audio_path) if audio_path is not None else None,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"frame_paths": frame_paths, "audio_path": audio_path}


def parse_generated_label_code(text: str) -> dict[str, Any]:
    code = text.strip()
    if LABEL_CODE_RE.fullmatch(code) is None:
        return {
            "parse_ok": False,
            "parse_error": f"Output does not match ^[01]{{9}}$: {text!r}",
            "label_code": None,
            "label_vector": None,
            "report_json": None,
        }

    report = build_report_from_code(code)
    label_vector = [int(bool(report["features"][feature_id])) for feature_id in FEATURE_IDS]
    return {
        "parse_ok": True,
        "parse_error": None,
        "label_code": code,
        "label_vector": label_vector,
        "report_json": report,
    }


def invalid_failure_label_vector(truth: list[int]) -> list[int]:
    return [0 if int(value) else 1 for value in truth]


def compute_multilabel_metrics(
    *,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    parse_ok: list[bool],
    split_name: str,
    step: int,
    epoch: float | None,
) -> dict[str, Any]:
    if y_true.shape != y_pred.shape:
        raise ValueError(f"Prediction shape mismatch: {y_true.shape} != {y_pred.shape}")
    if y_true.ndim != 2 or y_true.shape[1] != len(FEATURE_IDS):
        raise ValueError(f"Expected label matrix with {len(FEATURE_IDS)} columns, got {y_true.shape}")
    if len(parse_ok) != int(y_true.shape[0]):
        raise ValueError(f"parse_ok length mismatch: {len(parse_ok)} != {y_true.shape[0]}")

    parse_mask = np.asarray(parse_ok, dtype=bool)
    valid_y_true = y_true[parse_mask]
    valid_y_pred = y_pred[parse_mask]
    if valid_y_true.shape[0]:
        tp = ((valid_y_true == 1) & (valid_y_pred == 1)).sum(axis=0)
        fp = ((valid_y_true == 0) & (valid_y_pred == 1)).sum(axis=0)
        fn = ((valid_y_true == 1) & (valid_y_pred == 0)).sum(axis=0)
        tn = ((valid_y_true == 0) & (valid_y_pred == 0)).sum(axis=0)
        support = valid_y_true.sum(axis=0)
    else:
        tp = np.zeros(len(FEATURE_IDS), dtype=np.int64)
        fp = np.zeros(len(FEATURE_IDS), dtype=np.int64)
        fn = np.zeros(len(FEATURE_IDS), dtype=np.int64)
        tn = np.zeros(len(FEATURE_IDS), dtype=np.int64)
        support = np.zeros(len(FEATURE_IDS), dtype=np.int64)

    per_label = {}
    for index, feature_id in enumerate(FEATURE_IDS):
        precision = safe_divide(tp[index], tp[index] + fp[index])
        recall = safe_divide(tp[index], tp[index] + fn[index])
        f1 = f1_from_precision_recall(precision, recall)
        per_label[feature_id] = {
            "name": FEATURE_ID_TO_COLUMN[feature_id],
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(support[index]),
            "tp": int(tp[index]),
            "fp": int(fp[index]),
            "fn": int(fn[index]),
            "tn": int(tn[index]),
        }

    micro_precision = safe_divide(tp.sum(), tp.sum() + fp.sum())
    micro_recall = safe_divide(tp.sum(), tp.sum() + fn.sum())
    macro_precision = float(np.mean([values["precision"] for values in per_label.values()]))
    macro_recall = float(np.mean([values["recall"] for values in per_label.values()]))
    macro_f1 = float(np.mean([values["f1"] for values in per_label.values()]))
    valid_row_matches = np.all(y_true == y_pred, axis=1) & parse_mask if y_true.shape[0] else np.asarray([])
    valid_label_matches = (y_true == y_pred) & parse_mask[:, None] if y_true.shape[0] else np.asarray([])

    return {
        "split": split_name,
        "step": step,
        "epoch": epoch,
        "num_samples": int(y_true.shape[0]),
        "num_valid": int(parse_mask.sum()),
        "num_invalid": int((~parse_mask).sum()),
        "num_labels": len(FEATURE_IDS),
        "parse_rate": float(np.mean(parse_mask.astype(np.float32))) if parse_ok else 0.0,
        "exact_match": float(np.mean(valid_row_matches)) if y_true.shape[0] else 0.0,
        "hamming_accuracy": float(valid_label_matches.sum() / y_true.size) if y_true.size else 0.0,
        "micro": {
            "precision": micro_precision,
            "recall": micro_recall,
            "f1": f1_from_precision_recall(micro_precision, micro_recall),
        },
        "macro": {
            "precision": macro_precision,
            "recall": macro_recall,
            "f1": macro_f1,
        },
        "per_label": per_label,
    }


def safe_divide(numerator: Any, denominator: Any) -> float:
    denominator = float(denominator)
    if denominator == 0.0:
        return 0.0
    return float(numerator) / denominator


def f1_from_precision_recall(precision: float, recall: float) -> float:
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def save_f1_figure(*, metrics: dict[str, Any], path: Path) -> None:
    width = 1400
    row_height = 58
    top = 130
    bottom = 50
    height = top + row_height * len(FEATURE_IDS) + bottom
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    title = (
        f"{metrics['split']} step={metrics['step']} "
        f"micro-F1={metrics['micro']['f1']:.3f} "
        f"macro-F1={metrics['macro']['f1']:.3f} "
        f"exact={metrics['exact_match']:.3f}"
    )
    draw.text((40, 32), "ASD-DS Generated Label F1 by Behavior Dimension", fill=(20, 20, 20), font=font)
    draw.text((40, 62), title, fill=(60, 60, 60), font=font)
    draw.text((40, 92), f"parse_rate={metrics['parse_rate']:.3f} samples={metrics['num_samples']}", fill=(60, 60, 60), font=font)

    label_x = 40
    bar_x = 470
    bar_width = 620
    value_x = bar_x + bar_width + 28
    for index, feature_id in enumerate(FEATURE_IDS):
        values = metrics["per_label"][feature_id]
        y = top + index * row_height
        f1 = float(values["f1"])
        bar_fill = (43, 113, 181) if f1 >= 0.5 else (190, 72, 72)
        label = f"{feature_id} {values['name']}"
        summary = (
            f"F1 {f1:.3f}  P {values['precision']:.3f}  "
            f"R {values['recall']:.3f}  support {values['support']}"
        )
        draw.text((label_x, y + 8), label, fill=(30, 30, 30), font=font)
        draw.rectangle((bar_x, y + 4, bar_x + bar_width, y + 30), outline=(170, 170, 170), width=1)
        draw.rectangle((bar_x, y + 4, bar_x + int(bar_width * f1), y + 30), fill=bar_fill)
        draw.text((value_x, y + 8), summary, fill=(30, 30, 30), font=font)
        draw.line((bar_x, y + 42, value_x + 260, y + 42), fill=(235, 235, 235), width=1)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
