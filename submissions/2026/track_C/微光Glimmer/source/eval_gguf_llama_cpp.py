from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import click
import numpy as np

from asd_eval_common import (
    DEFAULT_DATA_ROOT,
    DEFAULT_MODEL_DIR,
    compute_multilabel_metrics,
    find_tool,
    invalid_failure_label_vector,
    load_prompt_bundle,
    parse_generated_label_code,
    prepare_media,
    save_f1_figure,
)
from asd_ds_dataset import load_asd_ds


DEFAULT_EXPERIMENT_DIR = Path("outputs/gguf_experiments/gemma4-asd-code9-waudio-step420")
DEFAULT_LLAMA_SERVER_BIN = "outputs/llama.cpp/build/bin/llama-server"
DEFAULT_MODEL_FILE = DEFAULT_EXPERIMENT_DIR / "model-Q4_K_M.gguf"
DEFAULT_MMPROJ_FILE = DEFAULT_EXPERIMENT_DIR / "mmproj-bf16.gguf"
DEFAULT_OUTPUT_DIR = DEFAULT_EXPERIMENT_DIR / "generated_metrics"
DEFAULT_MEDIA_CACHE_DIR = DEFAULT_EXPERIMENT_DIR / "media_cache"
DEFAULT_MEDIA_MARKER = "<__media__>"

CODE9_GRAMMAR = r'''
root ::= bit bit bit bit bit bit bit bit bit
bit ::= "0" | "1"
'''.strip()


@click.command()
@click.option("--llama-server-bin", default=DEFAULT_LLAMA_SERVER_BIN, show_default=True, type=click.Path(path_type=Path))
@click.option("--model-file", default=DEFAULT_MODEL_FILE, show_default=True, type=click.Path(path_type=Path))
@click.option("--mmproj-file", default=DEFAULT_MMPROJ_FILE, show_default=True, type=click.Path(path_type=Path))
@click.option("--data-root", default=DEFAULT_DATA_ROOT, show_default=True, type=click.Path(path_type=Path))
@click.option("--model-dir", default=DEFAULT_MODEL_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option("--split", default="test", show_default=True, type=click.Choice(["train", "validation", "test"]))
@click.option("--prompt-lang", default="zh", show_default=True, type=click.Choice(["en", "zh"]))
@click.option("--output-dir", default=DEFAULT_OUTPUT_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option("--media-cache-dir", default=DEFAULT_MEDIA_CACHE_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option("--frame-fps", default=1.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--max-frames", default=32, show_default=True, type=click.IntRange(min=1))
@click.option("--max-audio-seconds", default=30.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--image-width", default=512, show_default=True, type=click.IntRange(min=64))
@click.option("--audio/--no-audio", "use_audio", default=True, show_default=True)
@click.option("--max-samples", default=None, type=click.IntRange(min=1))
@click.option("--start-index", default=0, show_default=True, type=click.IntRange(min=0))
@click.option("--rebuild-media-cache/--reuse-media-cache", default=False, show_default=True)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=18080, show_default=True, type=click.IntRange(min=1, max=65535))
@click.option("--ctx-size", default=8192, show_default=True, type=click.IntRange(min=512))
@click.option("--threads", default=16, show_default=True, type=click.IntRange(min=1))
@click.option("--threads-batch", default=16, show_default=True, type=click.IntRange(min=1))
@click.option("--parallel", default=1, show_default=True, type=click.IntRange(min=1))
@click.option("--cuda-visible-devices", default=None, help="Optional CUDA_VISIBLE_DEVICES for llama-server.")
@click.option("--device", default=None, help="Optional llama.cpp --device value, for example CUDA0 or CUDA0,CUDA1.")
@click.option("--gpu-layers", default=None, help="Optional llama.cpp --n-gpu-layers value, for example all.")
@click.option("--mmproj-offload/--no-mmproj-offload", default=True, show_default=True)
@click.option("--max-tokens", default=16, show_default=True, type=click.IntRange(min=1))
@click.option("--temperature", default=0.0, show_default=True, type=click.FloatRange(min=0.0))
@click.option("--top-p", default=1.0, show_default=True, type=click.FloatRange(min=0.0, max=1.0))
@click.option("--top-k", default=1, show_default=True, type=click.IntRange(min=0))
@click.option("--constrain-code/--no-constrain-code", default=True, show_default=True)
@click.option(
    "--media-marker",
    default=DEFAULT_MEDIA_MARKER,
    show_default=True,
    help="Pin llama-server LLAMA_MEDIA_MARKER for reproducible mtmd prompts.",
)
@click.option("--server-start-timeout", default=900, show_default=True, type=click.IntRange(min=30))
@click.option("--request-timeout", default=900, show_default=True, type=click.IntRange(min=30))
@click.option("--keep-server/--stop-server", default=False, show_default=True)
def main(
    *,
    llama_server_bin: Path,
    model_file: Path,
    mmproj_file: Path,
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
    use_audio: bool,
    max_samples: int | None,
    start_index: int,
    rebuild_media_cache: bool,
    host: str,
    port: int,
    ctx_size: int,
    threads: int,
    threads_batch: int,
    parallel: int,
    cuda_visible_devices: str | None,
    device: str | None,
    gpu_layers: str | None,
    mmproj_offload: bool,
    max_tokens: int,
    temperature: float,
    top_p: float,
    top_k: int,
    constrain_code: bool,
    media_marker: str,
    server_start_timeout: int,
    request_timeout: int,
    keep_server: bool,
) -> None:
    llama_server_bin = llama_server_bin.expanduser()
    model_file = model_file.expanduser()
    mmproj_file = mmproj_file.expanduser()
    if not media_marker:
        raise click.ClickException("--media-marker must not be empty.")
    for path, label in (
        (llama_server_bin, "--llama-server-bin"),
        (model_file, "--model-file"),
        (mmproj_file, "--mmproj-file"),
    ):
        if not path.is_file():
            raise click.ClickException(f"{label} does not exist: {path}")

    prompts = load_prompt_bundle(prompt_lang)
    dataset = load_asd_ds(data_root)[split]
    if start_index:
        dataset = dataset.skip(start_index)
    if max_samples is not None:
        dataset = dataset.select(range(min(max_samples, len(dataset))))
    if len(dataset) <= 0:
        raise click.ClickException("No samples selected for evaluation.")

    output_dir.mkdir(parents=True, exist_ok=True)
    media_cache_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    server_log_path = log_dir / "llama_server.log"
    run_id = make_run_id(
        split=split,
        prompt_lang=prompt_lang,
        start_index=start_index,
        max_samples=max_samples,
        use_audio=use_audio,
        constrained=constrain_code,
    )
    predictions_path = output_dir / f"{run_id}_predictions.jsonl"
    metrics_path = output_dir / f"{run_id}_metrics.json"
    figure_path = output_dir / f"{run_id}_f1.png"

    click.echo("== GGUF llama.cpp eval setup ==")
    click.echo(f"model_file: {model_file}")
    click.echo(f"mmproj_file: {mmproj_file}")
    click.echo(f"split: {split}")
    click.echo(f"samples: {len(dataset)}")
    click.echo(f"prompt_lang: {prompt_lang}")
    click.echo(f"use_audio: {use_audio}")
    click.echo(f"max_frames: {max_frames}")
    click.echo(f"constrain_code: {constrain_code}")
    click.echo(f"media_marker: {media_marker}")
    click.echo(f"output_dir: {output_dir}")

    server_process: subprocess.Popen[str] | None = None
    server_log_handle = None
    if is_server_ready(host=host, port=port, timeout=1.0):
        click.echo(f"Using existing llama-server at http://{host}:{port}")
        validate_server_media_marker(host=host, port=port, expected_marker=media_marker)
    else:
        server_log_handle = server_log_path.open("w", encoding="utf-8")
        server_process = start_server(
            llama_server_bin=llama_server_bin,
            model_file=model_file,
            mmproj_file=mmproj_file,
            host=host,
            port=port,
            ctx_size=ctx_size,
            threads=threads,
            threads_batch=threads_batch,
            parallel=parallel,
            cuda_visible_devices=cuda_visible_devices,
            device=device,
            gpu_layers=gpu_layers,
            mmproj_offload=mmproj_offload,
            media_marker=media_marker,
            log_handle=server_log_handle,
        )
        wait_for_server(host=host, port=port, process=server_process, timeout=server_start_timeout, log_path=server_log_path)
        validate_server_media_marker(host=host, port=port, expected_marker=media_marker)

    ffmpeg = find_tool("ffmpeg")
    records: list[dict[str, Any]] = []
    y_true: list[list[int]] = []
    y_pred: list[list[int]] = []
    started = time.perf_counter()
    try:
        with predictions_path.open("w", encoding="utf-8") as handle:
            for offset, row in enumerate(dataset):
                index = start_index + offset
                if offset and offset % 10 == 0:
                    elapsed = time.perf_counter() - started
                    click.echo(f"[gguf-metrics] {run_id}: {offset}/{len(dataset)} elapsed={elapsed:.1f}s")

                media = prepare_media(
                    ffmpeg=ffmpeg,
                    row=row,
                    sample_index=index,
                    media_cache_dir=media_cache_dir,
                    frame_fps=frame_fps,
                    max_frames=max_frames,
                    max_audio_seconds=max_audio_seconds,
                    image_width=image_width,
                    use_audio=use_audio,
                    rebuild=rebuild_media_cache,
                )
                raw_prediction = send_chat_completion(
                    host=host,
                    port=port,
                    system_prompt=prompts.system,
                    user_prompt=prompts.user,
                    frame_paths=media["frame_paths"],
                    audio_path=media["audio_path"],
                    use_audio=use_audio,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    constrain_code=constrain_code,
                    timeout=request_timeout,
                ).strip()
                parsed = parse_generated_label_code(raw_prediction)
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
                    "index": index,
                    "video_id": row["video_id"],
                    "target_label_code": row["target_code"],
                    "predicted_label_code": parsed["label_code"],
                    "target_label_vector": truth,
                    "predicted_label_vector": parsed["label_vector"],
                    "target_json": row["target_json"],
                    "predicted_json": parsed["report_json"],
                    "raw_prediction": raw_prediction,
                    "parse_ok": parsed["parse_ok"],
                    "parse_error": parsed["parse_error"],
                    "frame_paths": [str(path) for path in media["frame_paths"]],
                    "audio_path": str(media["audio_path"]) if media["audio_path"] is not None else None,
                }
                records.append(record)
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()

        elapsed = time.perf_counter() - started
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
            "model_file": str(model_file),
            "mmproj_file": str(mmproj_file),
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
            "use_audio": use_audio,
            "ctx_size": ctx_size,
            "cuda_visible_devices": cuda_visible_devices,
            "device": device,
            "gpu_layers": gpu_layers,
            "mmproj_offload": mmproj_offload,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "constrain_code": constrain_code,
            "media_marker": media_marker,
            "grammar": CODE9_GRAMMAR if constrain_code else None,
        }
        metrics["artifacts"] = {
            "predictions_jsonl": str(predictions_path),
            "metrics_json": str(metrics_path),
            "f1_png": str(figure_path),
            "server_log": str(server_log_path),
        }
        metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        save_f1_figure(metrics=metrics, path=figure_path)
        click.echo(
            "[gguf-metrics] "
            f"{run_id}: micro_f1={metrics['micro']['f1']:.4f} "
            f"macro_f1={metrics['macro']['f1']:.4f} "
            f"exact_match={metrics['exact_match']:.4f} "
            f"parse_rate={metrics['parse_rate']:.4f} "
            f"elapsed={elapsed:.1f}s"
        )
        click.echo(f"[gguf-metrics] saved: {metrics_path}")
    finally:
        if server_process is not None and not keep_server:
            stop_process(server_process)
        if server_log_handle is not None:
            server_log_handle.close()


def make_run_id(
    *,
    split: str,
    prompt_lang: str,
    start_index: int,
    max_samples: int | None,
    use_audio: bool,
    constrained: bool,
) -> str:
    modality = "audio" if use_audio else "noaudio"
    constraint = "grammar" if constrained else "nogrammar"
    if max_samples is None and start_index == 0:
        return f"{split}_gguf_{modality}_{prompt_lang}_{constraint}"
    return f"{split}_gguf_{modality}_{prompt_lang}_{constraint}_start_{start_index:04d}_n_{max_samples or 'all'}"


def start_server(
    *,
    llama_server_bin: Path,
    model_file: Path,
    mmproj_file: Path,
    host: str,
    port: int,
    ctx_size: int,
    threads: int,
    threads_batch: int,
    parallel: int,
    cuda_visible_devices: str | None,
    device: str | None,
    gpu_layers: str | None,
    mmproj_offload: bool,
    media_marker: str,
    log_handle: Any,
) -> subprocess.Popen[str]:
    command = [
        str(llama_server_bin),
        "--model",
        str(model_file),
        "--mmproj",
        str(mmproj_file),
        "--host",
        host,
        "--port",
        str(port),
        "--ctx-size",
        str(ctx_size),
        "--threads",
        str(threads),
        "--threads-batch",
        str(threads_batch),
        "--parallel",
        str(parallel),
        "--cache-ram",
        "0",
        "--no-cache-prompt",
        "--no-ui",
        "--jinja",
        "--chat-template-kwargs",
        '{"enable_thinking":false}',
        "--reasoning",
        "off",
        "--reasoning-format",
        "none",
        "--offline",
        "--log-prefix",
        "--log-timestamps",
    ]
    if device:
        command.extend(["--device", device])
    if gpu_layers:
        command.extend(["--n-gpu-layers", gpu_layers])
    command.append("--mmproj-offload" if mmproj_offload else "--no-mmproj-offload")
    env = os.environ.copy()
    env["LLAMA_ARG_FLASH_ATTN"] = "off"
    env["LLAMA_MEDIA_MARKER"] = media_marker
    if cuda_visible_devices:
        env["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices
    process = subprocess.Popen(
        command,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        start_new_session=True,
    )
    click.echo(f"Started llama-server pid={process.pid} log={getattr(log_handle, 'name', '<log>')}")
    return process


def wait_for_server(*, host: str, port: int, process: subprocess.Popen[str], timeout: int, log_path: Path) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise click.ClickException(
                f"llama-server exited with code {process.returncode}. Log tail:\n{tail_text(log_path, lines=120)}"
            )
        if is_server_ready(host=host, port=port, timeout=2.0):
            click.echo(f"llama-server ready at http://{host}:{port}")
            return
        time.sleep(2)
    raise click.ClickException(f"Timed out waiting for llama-server. Log tail:\n{tail_text(log_path, lines=120)}")


def is_server_ready(*, host: str, port: int, timeout: float) -> bool:
    request = urllib.request.Request(f"http://{host}:{port}/health")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status) == 200
    except Exception:
        return False


def validate_server_media_marker(*, host: str, port: int, expected_marker: str) -> None:
    request = urllib.request.Request(f"http://{host}:{port}/props")
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
            props = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise click.ClickException(f"Failed to read llama-server /props for media marker validation: {exc}") from exc

    actual_marker = str(props.get("media_marker", ""))
    if actual_marker != expected_marker:
        raise click.ClickException(
            "Existing llama-server media marker mismatch: "
            f"expected {expected_marker!r}, got {actual_marker!r}. "
            "Restart the server or pass --media-marker to match it."
        )


def send_chat_completion(
    *,
    host: str,
    port: int,
    system_prompt: str,
    user_prompt: str,
    frame_paths: list[Path],
    audio_path: Path | None,
    use_audio: bool,
    max_tokens: int,
    temperature: float,
    top_p: float,
    top_k: int,
    constrain_code: bool,
    timeout: int,
) -> str:
    content: list[dict[str, Any]] = []
    for frame_path in frame_paths:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64," + base64.b64encode(frame_path.read_bytes()).decode("ascii")
                },
            }
        )
    if use_audio:
        if audio_path is None:
            raise click.ClickException("Internal error: audio eval requested but audio_path is missing.")
        content.append(
            {
                "type": "input_audio",
                "input_audio": {
                    "data": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
                    "format": "wav",
                },
            }
        )
    content.append({"type": "text", "text": user_prompt})

    payload = {
        "model": "asd-gguf",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": 0.0,
        "typical_p": 1.0,
        "repeat_penalty": 1.0,
        "seed": 42,
        "cache_prompt": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "reasoning_format": "none",
    }
    if constrain_code:
        payload["grammar"] = CODE9_GRAMMAR

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"http://{host}:{port}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer no-key"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise click.ClickException(f"llama-server request failed HTTP {exc.code}: {error_body}") from exc
    parsed = json.loads(response_body.decode("utf-8"))
    try:
        return str(parsed["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise click.ClickException(f"Unexpected llama-server response: {json.dumps(parsed, ensure_ascii=False)[:2000]}") from exc


def tail_text(path: Path, *, lines: int) -> str:
    if not path.is_file():
        return f"<missing log: {path}>"
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


if __name__ == "__main__":
    main()
