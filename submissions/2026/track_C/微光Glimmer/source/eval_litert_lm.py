from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import click
import numpy as np

from asd_ds_dataset import load_asd_ds
from run_train import (
    DEFAULT_DATA_ROOT,
    DEFAULT_MODEL_DIR,
    DEFAULT_PROMPT_LANG,
    FEATURE_IDS,
    compute_multilabel_metrics,
    find_tool,
    invalid_failure_label_vector,
    load_prompt_bundle,
    load_video_frames,
    parse_generated_label_code,
    requested_frame_count,
    run_command,
    sanitize_cache_name,
    save_f1_figure,
    stable_hash,
)


DEFAULT_LITERTLM_FILE = (
    "outputs/gemma4-asd-lora-r32-remix010-zh-v2-litert-w4-audio/model.litertlm"
)
DEFAULT_OUTPUT_DIR = (
    "outputs/gemma4-asd-lora-r32-remix010-zh-v2-litert-w4-audio/generated_metrics"
)
DEFAULT_MEDIA_CACHE_DIR = (
    "outputs/gemma4-asd-lora-r32-remix010-zh-v2-litert-w4-audio/media_cache"
)


@click.command()
@click.option("--litertlm-file", default=DEFAULT_LITERTLM_FILE, show_default=True, type=click.Path(path_type=Path))
@click.option("--data-root", default=DEFAULT_DATA_ROOT, show_default=True, type=click.Path(path_type=Path))
@click.option(
    "--model-dir",
    default=DEFAULT_MODEL_DIR,
    show_default=True,
    type=click.Path(path_type=Path),
    help="Kept for parity metadata with HF evaluation; LiteRT-LM loads --litertlm-file.",
)
@click.option("--split", default="test", show_default=True, type=click.Choice(["train", "validation", "test"]))
@click.option("--prompt-lang", default="zh", show_default=True, type=click.Choice(["en", "zh"]))
@click.option("--output-dir", default=DEFAULT_OUTPUT_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option("--media-cache-dir", default=DEFAULT_MEDIA_CACHE_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option("--frame-fps", default=1.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--max-frames", default=16, show_default=True, type=click.IntRange(min=1))
@click.option("--max-audio-seconds", default=30.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--image-width", default=512, show_default=True, type=click.IntRange(min=64))
@click.option("--max-samples", default=None, type=click.IntRange(min=1))
@click.option("--start-index", default=0, show_default=True, type=click.IntRange(min=0))
@click.option("--backend", default="gpu", show_default=True, type=click.Choice(["gpu", "cpu"]))
@click.option("--vision-backend", default="gpu", show_default=True, type=click.Choice(["gpu", "cpu"]))
@click.option("--audio-backend", default="cpu", show_default=True, type=click.Choice(["gpu", "cpu"]))
@click.option("--audio/--no-audio", "use_audio", default=True, show_default=True)
@click.option("--cache-dir", default=None, type=click.Path(path_type=Path), help="LiteRT-LM compiled artifact cache dir.")
@click.option("--temperature", default=0.0, show_default=True, type=click.FloatRange(min=0.0))
@click.option("--top-p", default=1.0, show_default=True, type=click.FloatRange(min=0.0, max=1.0))
@click.option("--top-k", default=1, show_default=True, type=click.IntRange(min=1))
@click.option(
    "--max-output-tokens",
    default=None,
    type=click.IntRange(min=1),
    help="Maximum generated tokens per response. Uses LiteRT-LM session config for conversation eval.",
)
@click.option("--workers", default=1, show_default=True, type=click.IntRange(min=1))
@click.option("--rebuild-media-cache/--reuse-media-cache", default=False, show_default=True)
def main(
    *,
    litertlm_file: Path,
    data_root: Path,
    model_dir: Path,
    split: str,
    prompt_lang: str,
    output_dir: Path,
    media_cache_dir: Path,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    max_samples: int | None,
    start_index: int,
    backend: str,
    vision_backend: str,
    audio_backend: str,
    use_audio: bool,
    cache_dir: Path | None,
    temperature: float,
    top_p: float,
    top_k: int,
    max_output_tokens: int | None,
    workers: int,
    rebuild_media_cache: bool,
) -> None:
    """Evaluate exported LiteRT-LM model on ASD-DS with project metrics."""
    litertlm_file = litertlm_file.expanduser()
    if not litertlm_file.is_file():
        raise click.ClickException(f"--litertlm-file does not exist: {litertlm_file}")

    prompts = load_prompt_bundle(prompt_lang)
    dataset = load_asd_ds(data_root)[split]
    if workers > 1:
        run_parallel_eval(
            litertlm_file=litertlm_file,
            data_root=data_root,
            model_dir=model_dir,
            split=split,
            prompt_lang=prompt_lang,
            output_dir=output_dir,
            media_cache_dir=media_cache_dir,
            frame_fps=frame_fps,
            max_frames=max_frames,
            max_audio_seconds=max_audio_seconds,
            image_width=image_width,
            max_samples=max_samples,
            start_index=start_index,
            backend=backend,
            vision_backend=vision_backend,
            audio_backend=audio_backend,
            use_audio=use_audio,
            cache_dir=cache_dir,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            workers=workers,
            rebuild_media_cache=rebuild_media_cache,
            prompts=prompts,
            full_dataset_len=len(dataset),
        )
        hard_exit_success()

    import litert_lm

    if start_index:
        dataset = dataset.skip(start_index)
    if max_samples is not None:
        dataset = dataset.select(range(min(max_samples, len(dataset))))

    output_dir.mkdir(parents=True, exist_ok=True)
    media_cache_dir.mkdir(parents=True, exist_ok=True)
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_tool("ffmpeg")
    run_id = make_run_id(
        split=split,
        prompt_lang=prompt_lang,
        start_index=start_index,
        max_samples=max_samples,
        use_audio=use_audio,
    )
    predictions_path = output_dir / f"{run_id}_predictions.jsonl"
    metrics_path = output_dir / f"{run_id}_metrics.json"
    figure_path = output_dir / f"{run_id}_f1.png"

    click.echo("== LiteRT-LM eval setup ==")
    click.echo(f"litertlm_file: {litertlm_file}")
    click.echo(f"data_root: {data_root}")
    click.echo(f"model_dir: {model_dir}")
    click.echo(f"split: {split}")
    click.echo(f"samples: {len(dataset)}")
    click.echo(f"prompt_lang: {prompt_lang}")
    click.echo(f"output_dir: {output_dir}")
    click.echo(f"media_cache_dir: {media_cache_dir}")
    click.echo(f"backend: {backend}")
    click.echo(f"vision_backend: {vision_backend}")
    click.echo(f"audio_backend: {audio_backend}")
    click.echo(f"use_audio: {use_audio}")

    litert_lm.set_min_log_severity(litert_lm.LogSeverity.ERROR)
    sampler_config = litert_lm.SamplerConfig(top_k=top_k, top_p=top_p, temperature=temperature, seed=42)

    y_true: list[list[int]] = []
    y_pred: list[list[int]] = []
    records: list[dict[str, Any]] = []
    start = time.perf_counter()

    with litert_lm.Engine(
        str(litertlm_file),
        backend=make_backend(litert_lm, backend),
        vision_backend=make_backend(litert_lm, vision_backend),
        audio_backend=make_backend(litert_lm, audio_backend) if use_audio else None,
        cache_dir=str(cache_dir) if cache_dir else "",
    ) as engine:
        with predictions_path.open("w", encoding="utf-8") as handle:
            for index, row in enumerate(dataset):
                if index and index % 10 == 0:
                    elapsed = time.perf_counter() - start
                    click.echo(f"[litert-metrics] {run_id}: {index}/{len(dataset)} elapsed={elapsed:.1f}s")

                media = prepare_media(
                    ffmpeg=ffmpeg,
                    row=row,
                    sample_index=start_index + index,
                    media_cache_dir=media_cache_dir,
                    frame_fps=frame_fps,
                    max_frames=max_frames,
                    max_audio_seconds=max_audio_seconds,
                    image_width=image_width,
                    use_audio=use_audio,
                    rebuild=rebuild_media_cache,
                )
                response_text = generate_one(
                    litert_lm=litert_lm,
                    engine=engine,
                    system_prompt=prompts.system,
                    user_prompt=prompts.user,
                    frame_paths=media["frame_paths"],
                    audio_path=media["audio_path"],
                    use_audio=use_audio,
                    sampler_config=sampler_config,
                    max_output_tokens=max_output_tokens,
                )
                parsed = parse_generated_label_code(response_text)
                truth = [int(value) for value in row["label_vector"]]
                y_true.append(truth)
                y_pred.append(
                    parsed["label_vector"]
                    if parsed["parse_ok"]
                    else invalid_failure_label_vector(truth)
                )

                record = {
                    "split": split,
                    "run_id": run_id,
                    "index": start_index + index,
                    "video_id": row["video_id"],
                    "target_label_code": row["target_code"],
                    "predicted_label_code": parsed["label_code"],
                    "target_label_vector": truth,
                    "predicted_label_vector": parsed["label_vector"],
                    "target_json": row["target_json"],
                    "predicted_json": parsed["report_json"],
                    "raw_prediction": response_text,
                    "parse_ok": parsed["parse_ok"],
                    "parse_error": parsed["parse_error"],
                    "frame_paths": [str(path) for path in media["frame_paths"]],
                    "audio_path": str(media["audio_path"]) if media["audio_path"] is not None else None,
                }
                records.append(record)
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()

    elapsed = time.perf_counter() - start
    metrics = compute_multilabel_metrics(
        y_true=np.asarray(y_true, dtype=np.int64),
        y_pred=np.asarray(y_pred, dtype=np.int64),
        parse_ok=[bool(record["parse_ok"]) for record in records],
        split_name=run_id,
        step=0,
        epoch=None,
    )
    metrics["runtime"] = {
        "elapsed_seconds": elapsed,
        "seconds_per_sample": elapsed / len(records) if records else None,
    }
    metrics["config"] = {
        "litertlm_file": str(litertlm_file),
        "data_root": str(data_root),
        "model_dir": str(model_dir),
        "split": split,
        "prompt_lang": prompt_lang,
        "prompt_files": {
            "system": str(prompts.system_path),
            "user": str(prompts.user_path),
        },
        "frame_fps": frame_fps,
        "max_frames": max_frames,
        "max_audio_seconds": max_audio_seconds,
        "image_width": image_width,
        "backend": backend,
        "vision_backend": vision_backend,
        "audio_backend": audio_backend,
        "use_audio": use_audio,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "max_output_tokens": max_output_tokens,
    }
    metrics["artifacts"] = {
        "predictions_jsonl": str(predictions_path),
        "metrics_json": str(metrics_path),
        "f1_png": str(figure_path),
    }
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    save_f1_figure(metrics=metrics, path=figure_path)

    click.echo(
        "[litert-metrics] "
        f"{run_id}: micro_f1={metrics['micro']['f1']:.4f} "
        f"macro_f1={metrics['macro']['f1']:.4f} "
        f"exact_match={metrics['exact_match']:.4f} "
        f"parse_rate={metrics['parse_rate']:.4f} "
        f"elapsed={elapsed:.1f}s"
    )
    click.echo(f"[litert-metrics] saved: {metrics_path}")
    hard_exit_success()


def run_parallel_eval(
    *,
    litertlm_file: Path,
    data_root: Path,
    model_dir: Path,
    split: str,
    prompt_lang: str,
    output_dir: Path,
    media_cache_dir: Path,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    max_samples: int | None,
    start_index: int,
    backend: str,
    vision_backend: str,
    audio_backend: str,
    use_audio: bool,
    cache_dir: Path | None,
    temperature: float,
    top_p: float,
    top_k: int,
    max_output_tokens: int | None,
    workers: int,
    rebuild_media_cache: bool,
    prompts: Any,
    full_dataset_len: int,
) -> None:
    total = max(0, full_dataset_len - start_index)
    if max_samples is not None:
        total = min(total, max_samples)
    if total <= 0:
        raise click.ClickException("No samples selected for evaluation.")

    workers = min(workers, total)
    run_id = make_run_id(
        split=split,
        prompt_lang=prompt_lang,
        start_index=start_index,
        max_samples=max_samples,
        use_audio=use_audio,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    media_cache_dir.mkdir(parents=True, exist_ok=True)
    shard_root = output_dir / "_parallel_shards" / run_id
    if shard_root.exists():
        shutil.rmtree(shard_root)
    shard_root.mkdir(parents=True)

    cache_base = cache_dir or (litertlm_file.parent / "litert_cache_parallel")
    cache_base = cache_base / run_id
    cache_base.mkdir(parents=True, exist_ok=True)

    click.echo("== Parallel LiteRT-LM eval setup ==")
    click.echo(f"litertlm_file: {litertlm_file}")
    click.echo(f"split: {split}")
    click.echo(f"samples: {total}")
    click.echo(f"workers: {workers}")
    click.echo(f"output_dir: {output_dir}")
    click.echo(f"shard_root: {shard_root}")
    click.echo(f"media_cache_dir: {media_cache_dir}")
    click.echo(f"cache_base: {cache_base}")

    shards = make_shards(total=total, start_index=start_index, workers=workers)
    processes = []
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    for worker_index, (shard_start, shard_count) in enumerate(shards):
        shard_output_dir = shard_root / f"worker_{worker_index:02d}"
        shard_cache_dir = cache_base / f"worker_{worker_index:02d}"
        shard_log = shard_root / f"worker_{worker_index:02d}.log"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--litertlm-file",
            str(litertlm_file),
            "--data-root",
            str(data_root),
            "--model-dir",
            str(model_dir),
            "--split",
            split,
            "--prompt-lang",
            prompt_lang,
            "--output-dir",
            str(shard_output_dir),
            "--media-cache-dir",
            str(media_cache_dir),
            "--frame-fps",
            str(frame_fps),
            "--max-frames",
            str(max_frames),
            "--max-audio-seconds",
            str(max_audio_seconds),
            "--image-width",
            str(image_width),
            "--start-index",
            str(shard_start),
            "--max-samples",
            str(shard_count),
            "--backend",
            backend,
            "--vision-backend",
            vision_backend,
            "--audio-backend",
            audio_backend,
            "--audio" if use_audio else "--no-audio",
            "--cache-dir",
            str(shard_cache_dir),
            "--temperature",
            str(temperature),
            "--top-p",
            str(top_p),
            "--top-k",
            str(top_k),
            *(["--max-output-tokens", str(max_output_tokens)] if max_output_tokens is not None else []),
            "--workers",
            "1",
        ]
        if rebuild_media_cache:
            command.append("--rebuild-media-cache")
        log_handle = shard_log.open("w", encoding="utf-8")
        process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT, env=env)
        processes.append(
            {
                "worker_index": worker_index,
                "start": shard_start,
                "count": shard_count,
                "process": process,
                "log_handle": log_handle,
                "log_path": shard_log,
                "output_dir": shard_output_dir,
            }
        )
        click.echo(
            f"[parallel] worker={worker_index} pid={process.pid} "
            f"start={shard_start} count={shard_count} log={shard_log}"
        )

    started = time.perf_counter()
    while True:
        running = [entry for entry in processes if entry["process"].poll() is None]
        finished = len(processes) - len(running)
        elapsed = time.perf_counter() - started
        progress_parts = []
        for entry in processes:
            prediction_count = count_shard_predictions(
                output_dir=entry["output_dir"],
                split=split,
                prompt_lang=prompt_lang,
                start=entry["start"],
                count=entry["count"],
                use_audio=use_audio,
            )
            progress_parts.append(f"w{entry['worker_index']}={prediction_count}/{entry['count']}")
        click.echo(f"[parallel] finished={finished}/{len(processes)} elapsed={elapsed:.1f}s {' '.join(progress_parts)}")
        if not running:
            break
        time.sleep(30)

    for entry in processes:
        entry["log_handle"].close()

    failed = [entry for entry in processes if entry["process"].returncode != 0]
    if failed:
        for entry in failed:
            click.echo(f"== worker {entry['worker_index']} failed log tail ==")
            click.echo(tail_text(entry["log_path"], lines=80))
        raise click.ClickException(
            "Parallel LiteRT-LM eval failed for worker(s): "
            + ", ".join(str(entry["worker_index"]) for entry in failed)
        )

    records = []
    for entry in processes:
        child_run_id = make_run_id(
            split=split,
            prompt_lang=prompt_lang,
            start_index=entry["start"],
            max_samples=entry["count"],
            use_audio=use_audio,
        )
        predictions_path = entry["output_dir"] / f"{child_run_id}_predictions.jsonl"
        if not predictions_path.is_file():
            raise click.ClickException(f"Missing shard predictions: {predictions_path}")
        with predictions_path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))

    records.sort(key=lambda record: int(record["index"]))
    if len(records) != total:
        raise click.ClickException(f"Expected {total} merged predictions, got {len(records)}")

    predictions_path = output_dir / f"{run_id}_predictions.jsonl"
    metrics_path = output_dir / f"{run_id}_metrics.json"
    figure_path = output_dir / f"{run_id}_f1.png"
    with predictions_path.open("w", encoding="utf-8") as handle:
        for record in records:
            record["merged_run_id"] = run_id
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    y_true = np.asarray([record["target_label_vector"] for record in records], dtype=np.int64)
    y_pred = np.asarray(
        [
            record["predicted_label_vector"]
            if record["parse_ok"]
            else invalid_failure_label_vector(record["target_label_vector"])
            for record in records
        ],
        dtype=np.int64,
    )
    metrics = compute_multilabel_metrics(
        y_true=y_true,
        y_pred=y_pred,
        parse_ok=[bool(record["parse_ok"]) for record in records],
        split_name=run_id,
        step=0,
        epoch=None,
    )
    elapsed = time.perf_counter() - started
    metrics["runtime"] = {
        "elapsed_seconds": elapsed,
        "seconds_per_sample": elapsed / len(records) if records else None,
        "workers": workers,
    }
    metrics["config"] = {
        "litertlm_file": str(litertlm_file),
        "data_root": str(data_root),
        "model_dir": str(model_dir),
        "split": split,
        "prompt_lang": prompt_lang,
        "prompt_files": {
            "system": str(prompts.system_path),
            "user": str(prompts.user_path),
        },
        "frame_fps": frame_fps,
        "max_frames": max_frames,
        "max_audio_seconds": max_audio_seconds,
        "image_width": image_width,
        "backend": backend,
        "vision_backend": vision_backend,
        "audio_backend": audio_backend,
        "use_audio": use_audio,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "max_output_tokens": max_output_tokens,
        "workers": workers,
        "shards": [
            {"worker_index": entry["worker_index"], "start": entry["start"], "count": entry["count"]}
            for entry in processes
        ],
    }
    metrics["artifacts"] = {
        "predictions_jsonl": str(predictions_path),
        "metrics_json": str(metrics_path),
        "f1_png": str(figure_path),
        "shard_root": str(shard_root),
    }
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    save_f1_figure(metrics=metrics, path=figure_path)
    click.echo(
        "[litert-metrics] "
        f"{run_id}: micro_f1={metrics['micro']['f1']:.4f} "
        f"macro_f1={metrics['macro']['f1']:.4f} "
        f"exact_match={metrics['exact_match']:.4f} "
        f"parse_rate={metrics['parse_rate']:.4f} "
        f"elapsed={elapsed:.1f}s workers={workers}"
    )
    click.echo(f"[litert-metrics] saved: {metrics_path}")


def make_shards(*, total: int, start_index: int, workers: int) -> list[tuple[int, int]]:
    base = total // workers
    remainder = total % workers
    shards = []
    cursor = start_index
    for worker_index in range(workers):
        count = base + (1 if worker_index < remainder else 0)
        if count <= 0:
            continue
        shards.append((cursor, count))
        cursor += count
    return shards


def count_shard_predictions(
    *,
    output_dir: Path,
    split: str,
    prompt_lang: str,
    start: int,
    count: int,
    use_audio: bool,
) -> int:
    run_id = make_run_id(
        split=split,
        prompt_lang=prompt_lang,
        start_index=start,
        max_samples=count,
        use_audio=use_audio,
    )
    path = output_dir / f"{run_id}_predictions.jsonl"
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def tail_text(path: Path, *, lines: int) -> str:
    if not path.is_file():
        return f"<missing log: {path}>"
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def hard_exit_success() -> None:
    sys.stdout.flush()
    sys.stderr.flush()
    # The current LiteRT-LM native library can crash during interpreter
    # shutdown after successful GPU inference. Files and metrics are already
    # written at this point, so exit directly to keep automation reliable.
    os._exit(0)


def make_backend(litert_lm: Any, name: str) -> Any:
    if name == "gpu":
        return litert_lm.Backend.GPU()
    if name == "cpu":
        return litert_lm.Backend.CPU()
    raise ValueError(f"Unsupported backend: {name}")


def make_run_id(
    *,
    split: str,
    prompt_lang: str,
    start_index: int,
    max_samples: int | None,
    use_audio: bool,
) -> str:
    modality = "audio" if use_audio else "noaudio"
    if max_samples is None and start_index == 0:
        return f"{split}_litert_{modality}_{prompt_lang}"
    return f"{split}_litert_{modality}_{prompt_lang}_start_{start_index:04d}_n_{max_samples or 'all'}"


def prepare_media(
    *,
    ffmpeg: str,
    row: dict,
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


def generate_one(
    *,
    litert_lm: Any,
    engine: Any,
    system_prompt: str,
    user_prompt: str,
    frame_paths: list[Path],
    audio_path: Path | None,
    use_audio: bool,
    sampler_config: Any,
    max_output_tokens: int | None,
) -> str:
    contents = [
        *[litert_lm.Content.ImageFile(absolute_path=str(path.resolve())) for path in frame_paths],
    ]
    if use_audio:
        if audio_path is None:
            raise click.ClickException("Internal error: audio eval requested but audio_path is missing.")
        contents.append(litert_lm.Content.AudioFile(absolute_path=str(audio_path.resolve())))
    contents.append(litert_lm.Content.Text(user_prompt))
    messages = [litert_lm.Message.system(system_prompt)]
    with create_eval_conversation(
        litert_lm=litert_lm,
        engine=engine,
        messages=messages,
        sampler_config=sampler_config,
        max_output_tokens=max_output_tokens,
    ) as conversation:
        response = conversation.send_message(litert_lm.Message.user(litert_lm.Contents.of(contents)))
    return extract_response_text(response).strip()


def create_eval_conversation(
    *,
    litert_lm: Any,
    engine: Any,
    messages: list[Any],
    sampler_config: Any,
    max_output_tokens: int | None,
) -> Any:
    if max_output_tokens is None:
        return engine.create_conversation(messages=messages, sampler_config=sampler_config)

    import ctypes
    from litert_lm.conversation import Conversation
    from litert_lm.utils import _sampler_config_to_params

    lib = engine._lib
    session_config = lib.litert_lm_session_config_create()
    if not session_config:
        raise RuntimeError("Failed to create LiteRT-LM session config")
    try:
        params = _sampler_config_to_params(sampler_config)
        lib.litert_lm_session_config_set_sampler_params(session_config, ctypes.byref(params))
        lib.litert_lm_session_config_set_max_output_tokens(session_config, int(max_output_tokens))

        conv_config = lib.litert_lm_conversation_config_create()
        if not conv_config:
            raise RuntimeError("Failed to create LiteRT-LM conversation config")
        try:
            lib.litert_lm_conversation_config_set_session_config(conv_config, session_config)
            if messages:
                serialized_messages = [message.to_json() if hasattr(message, "to_json") else message for message in messages]
                lib.litert_lm_conversation_config_set_messages(conv_config, json.dumps(serialized_messages))
            conv_ptr = lib.litert_lm_conversation_create(engine._engine_ptr, conv_config)
        finally:
            lib.litert_lm_conversation_config_delete(conv_config)
    finally:
        lib.litert_lm_session_config_delete(session_config)

    if not conv_ptr:
        raise RuntimeError("Failed to create LiteRT-LM conversation")

    return Conversation(
        lib,
        conv_ptr,
        engine=engine,
        messages=messages or [],
        sampler_config=sampler_config,
    )


def extract_response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if not isinstance(response, dict):
        return str(response)
    pieces = []
    content = response.get("content", [])
    if isinstance(content, dict):
        content = [content]
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            pieces.append(str(item.get("text", "")))
        elif isinstance(item, str):
            pieces.append(item)
    if pieces:
        return "".join(pieces)
    return json.dumps(response, ensure_ascii=False)


if __name__ == "__main__":
    main()
