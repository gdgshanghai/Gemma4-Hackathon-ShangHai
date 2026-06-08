from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import hashlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from transformers.trainer_callback import TrainerCallback

from asd_ds_dataset import FEATURE_ID_TO_COLUMN, FEATURE_IDS, LABEL_CODE_RE, build_report_from_code, load_asd_ds


DEFAULT_DATA_ROOT = "data/raw/ASD-DS"
DEFAULT_MODEL_DIR = "/home/huzi/Downloads/gemma-4-E4B-it"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_PROMPT_LANG = "en"
PROMPT_LANGS = ("en", "zh")
BREW_BIN = Path("/home/linuxbrew/.linuxbrew/bin")
DEFAULT_OUTPUT_DIR = "outputs/gemma4-asd-lora-r32"
DEFAULT_CACHE_DIR = "outputs/asd_ds_processor_cache"
DEFAULT_WANDB_PROJECT = "gemma4-asd-ft"
DEFAULT_RUN_NAME = "gemma4-asd-lora-r32"
DEFAULT_LITERT_TEMPLATE_OVERRIDE = "litert-community/gemma-4-E4B-it-litert-lm"
DEFAULT_LITERT_QUANTIZATION_RECIPE = "dynamic_wi4_afp32"
DEFAULT_LITERT_VISION_QUANTIZATION_RECIPE = "dynamic_wi8_afp32"
DEFAULT_OFFICIAL_LITERT_REPO = "litert-community/gemma-4-E4B-it-litert-lm"
DEFAULT_OFFICIAL_LITERT_FILENAME = "gemma-4-E4B-it.litertlm"
DEFAULT_OFFICIAL_LITERT_DIR = Path("outputs/gemma4-official-litert")
REQUIRED_TEXT_VISION_LITERT_MODEL_TYPES = (
    "tf_lite_embedder",
    "tf_lite_per_layer_embedder",
    "tf_lite_vision_encoder",
    "tf_lite_vision_adapter",
    "tf_lite_prefill_decode",
)
REQUIRED_AUDIO_LITERT_MODEL_TYPES = (
    "tf_lite_audio_encoder_hw",
    "tf_lite_audio_adapter",
    "tf_lite_end_of_audio",
)
REQUIRED_FINAL_LITERT_MODEL_TYPES = REQUIRED_TEXT_VISION_LITERT_MODEL_TYPES + REQUIRED_AUDIO_LITERT_MODEL_TYPES
CACHE_VERSION = "gemma4_asd_ds_processor_cache_v2_code9"
CACHE_KINDS = ("supervised", "prompt")
LANGUAGE_LORA_REGEX = (
    r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$"
)
_CACHE_WORKER_STATE: dict[str, Any] = {}


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
        raise click.ClickException(
            f"Missing prompt file(s) for --prompt-lang {lang}: {', '.join(missing)}"
        )

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


@click.group()
def cli() -> None:
    """Training utilities for Gemma 4 ASD-DS fine-tuning."""


@cli.command("smoke-test")
@click.option("--data-root", default=DEFAULT_DATA_ROOT, show_default=True, type=click.Path(path_type=Path))
@click.option("--model-dir", default=DEFAULT_MODEL_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option("--split", default="train", show_default=True, type=click.Choice(["train", "validation", "test"]))
@click.option("--index", "row_index", default=0, show_default=True, type=click.IntRange(min=0))
@click.option("--frame-fps", default=1.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--max-frames", default=8, show_default=True, type=click.IntRange(min=1))
@click.option("--max-audio-seconds", default=30.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--image-width", default=512, show_default=True, type=click.IntRange(min=64))
@click.option("--prompt-lang", default=DEFAULT_PROMPT_LANG, show_default=True, type=click.Choice(PROMPT_LANGS))
@click.option("--audio/--no-audio", "use_audio", default=True, show_default=True)
def smoke_test(
    data_root: Path,
    model_dir: Path,
    split: str,
    row_index: int,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    prompt_lang: str,
    use_audio: bool,
) -> None:
    """Load one sample, preprocess media, and build masked training labels."""
    from transformers import AutoProcessor
    from transformers.video_utils import VideoMetadata

    ffmpeg = find_tool("ffmpeg")
    click.echo("== Smoke test: Gemma 4 multimodal training sample ==")
    click.echo(f"data_root: {data_root}")
    click.echo(f"model_dir:  {model_dir}")
    click.echo(f"ffmpeg:     {ffmpeg}")
    prompts = load_prompt_bundle(prompt_lang)
    click.echo(f"prompt_lang: {prompts.lang}")
    click.echo(f"use_audio: {use_audio}")

    dataset = load_asd_ds(data_root, splits=(split,))[split]
    if row_index >= len(dataset):
        raise click.ClickException(f"--index {row_index} is out of range for {split} with {len(dataset)} rows")

    row = dataset[row_index]
    print_sample_summary(row, split, row_index)

    frames = load_video_frames(
        ffmpeg=ffmpeg,
        video_path=Path(row["video_path"]),
        fps=frame_fps,
        max_frames=max_frames,
        image_width=image_width,
        duration_sec=float(row["duration_sec"]),
    )
    click.echo("\n== Media preprocessing ==")
    click.echo(f"frames: {len(frames)}")
    click.echo(f"first_frame_size: {frames[0].size[0]}x{frames[0].size[1]}")
    audio = None
    if use_audio:
        audio = load_audio_mono_16k(
            ffmpeg=ffmpeg,
            audio_path=Path(row["audio_path"]),
            max_seconds=min(float(row["duration_sec"]), max_audio_seconds),
        )
        click.echo(f"audio_samples: {audio.shape[0]}")
        click.echo(f"audio_seconds_at_16k: {audio.shape[0] / 16000:.3f}")
        click.echo(f"audio_min_max: {audio.min():.4f}, {audio.max():.4f}")
    else:
        click.echo("audio: disabled")

    processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
    prompt_text = build_chat_text(processor, row, prompts=prompts, include_answer=False, use_audio=use_audio)
    full_text = build_chat_text(processor, row, prompts=prompts, include_answer=True, use_audio=use_audio)
    metadata = VideoMetadata(
        total_num_frames=len(frames),
        fps=frame_fps,
        duration=len(frames) / frame_fps,
        frames_indices=list(range(len(frames))),
    )

    prompt_inputs = processor(
        text=[prompt_text],
        videos=[frames],
        return_tensors="pt",
        return_mm_token_type_ids=True,
        videos_kwargs={"video_metadata": [metadata], "do_sample_frames": False},
        **processor_audio_kwargs(audio=audio),
    )
    full_inputs = processor(
        text=[full_text],
        videos=[frames],
        return_tensors="pt",
        return_mm_token_type_ids=True,
        videos_kwargs={"video_metadata": [metadata], "do_sample_frames": False},
        **processor_audio_kwargs(audio=audio),
    )
    labels = build_masked_labels(full_inputs, prompt_len=prompt_inputs["input_ids"].shape[-1])

    click.echo("\n== Chat text ==")
    click.echo(f"prompt_text_chars: {len(prompt_text)}")
    click.echo(f"full_text_chars:   {len(full_text)}")
    click.echo("prompt_text_preview:")
    click.echo(indent_preview(prompt_text))
    click.echo("target_code:")
    click.echo(row["target_code"])
    click.echo("target_json:")
    click.echo(row["target_json"])

    click.echo("\n== Processor outputs ==")
    print_tensor_summary("prompt", prompt_inputs)
    print_tensor_summary("full", full_inputs)
    click.echo(f"prompt_token_len: {prompt_inputs['input_ids'].shape[-1]}")
    click.echo(f"full_token_len:   {full_inputs['input_ids'].shape[-1]}")
    click.echo(f"label_token_count: {(labels != -100).sum().item()}")

    decoded_label_text = processor.tokenizer.decode(
        full_inputs["input_ids"][0][labels[0] != -100],
        skip_special_tokens=False,
    )
    click.echo("\n== Decoded supervised label text ==")
    click.echo(decoded_label_text)

    assert_label_code(row)
    assert_label_payload(row["target_json"])
    click.echo("\nSMOKE TEST PASSED")


@cli.command("build-cache")
@click.option("--data-root", default=DEFAULT_DATA_ROOT, show_default=True, type=click.Path(path_type=Path))
@click.option("--model-dir", default=DEFAULT_MODEL_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option("--cache-dir", default=DEFAULT_CACHE_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option(
    "--split",
    "splits",
    multiple=True,
    default=("train", "validation", "test"),
    show_default=True,
    type=click.Choice(["train", "validation", "test"]),
)
@click.option(
    "--cache-kind",
    "cache_kinds",
    multiple=True,
    default=CACHE_KINDS,
    show_default=True,
    type=click.Choice(CACHE_KINDS),
)
@click.option("--max-samples", default=None, type=click.IntRange(min=1))
@click.option("--frame-fps", default=1.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--max-frames", default=16, show_default=True, type=click.IntRange(min=1))
@click.option("--max-audio-seconds", default=30.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--image-width", default=512, show_default=True, type=click.IntRange(min=64))
@click.option("--overwrite/--no-overwrite", default=False, show_default=True)
@click.option("--prompt-lang", default=DEFAULT_PROMPT_LANG, show_default=True, type=click.Choice(PROMPT_LANGS))
@click.option("--audio/--no-audio", "use_audio", default=True, show_default=True)
@click.option(
    "--workers",
    default=1,
    show_default=True,
    type=click.IntRange(min=1),
    help="Parallel CPU worker processes for processor-cache building.",
)
def build_cache(
    data_root: Path,
    model_dir: Path,
    cache_dir: Path,
    splits: tuple[str, ...],
    cache_kinds: tuple[str, ...],
    max_samples: int | None,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    overwrite: bool,
    prompt_lang: str,
    use_audio: bool,
    workers: int,
) -> None:
    """Precompute processor batches so training does not run ffmpeg/processor per step."""
    from transformers import AutoProcessor

    ffmpeg = find_tool("ffmpeg")
    prompts = load_prompt_bundle(prompt_lang)
    cache_store = ProcessorCache(
        cache_dir=cache_dir,
        config=build_cache_config(
            model_dir=model_dir,
            frame_fps=frame_fps,
            max_frames=max_frames,
            max_audio_seconds=max_audio_seconds,
            image_width=image_width,
            prompts=prompts,
            use_audio=use_audio,
        ),
        mode="read-write",
    )
    cache_store.write_config()

    click.echo("== Building processor cache ==")
    click.echo(f"data_root: {data_root}")
    click.echo(f"model_dir: {model_dir}")
    click.echo(f"cache_root: {cache_store.root}")
    click.echo(f"ffmpeg: {ffmpeg}")
    click.echo(f"prompt_lang: {prompts.lang}")
    click.echo(f"use_audio: {use_audio}")
    click.echo(f"workers: {workers}")
    click.echo(f"splits: {', '.join(splits)}")
    click.echo(f"kinds: {', '.join(cache_kinds)}")

    dataset = load_asd_ds(data_root, splits=splits)
    rows: list[dict] = []
    total_written = 0
    total_existing = 0
    for split in splits:
        split_dataset = dataset[split]
        if max_samples is not None:
            split_dataset = split_dataset.select(range(min(max_samples, len(split_dataset))))

        click.echo(f"== {split}: {len(split_dataset)} samples ==")
        rows.extend(dict(row) for row in split_dataset)

    if workers == 1:
        processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
        for index, row in enumerate(rows, start=1):
            if index > 1 and (index - 1) % 25 == 0:
                click.echo(
                    f"[cache] rows: {index - 1}/{len(rows)} "
                    f"written={total_written} existing={total_existing}"
                )

            counts = build_cache_row(
                cache_store=cache_store,
                processor=processor,
                ffmpeg=ffmpeg,
                row=row,
                cache_kinds=cache_kinds,
                overwrite=overwrite,
                frame_fps=frame_fps,
                max_frames=max_frames,
                max_audio_seconds=max_audio_seconds,
                image_width=image_width,
                prompts=prompts,
                use_audio=use_audio,
            )
            total_written += counts["written"]
            total_existing += counts["existing"]
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=init_cache_worker,
            initargs=(
                str(model_dir),
                str(cache_dir),
                cache_store.config,
                ffmpeg,
                tuple(cache_kinds),
                frame_fps,
                max_frames,
                max_audio_seconds,
                image_width,
                prompts,
                use_audio,
            ),
        ) as executor:
            futures = [executor.submit(build_cache_row_worker, row, overwrite) for row in rows]
            for index, future in enumerate(as_completed(futures), start=1):
                counts = future.result()
                total_written += counts["written"]
                total_existing += counts["existing"]
                if index % 25 == 0 or index == len(rows):
                    click.echo(
                        f"[cache] rows: {index}/{len(rows)} "
                        f"written={total_written} existing={total_existing}"
                    )

    click.echo(
        "CACHE BUILD DONE "
        f"written={total_written} existing={total_existing} cache_root={cache_store.root}"
    )


@cli.command("train")
@click.option("--cuda-devices", default="1,2,3", show_default=True, help="Physical CUDA device IDs.")
@click.option("--data-root", default=DEFAULT_DATA_ROOT, show_default=True, type=click.Path(path_type=Path))
@click.option("--model-dir", default=DEFAULT_MODEL_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option("--output-dir", default=DEFAULT_OUTPUT_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option("--cache-dir", default=DEFAULT_CACHE_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option(
    "--cache-mode",
    default="read-write",
    show_default=True,
    type=click.Choice(["off", "read-write", "require"]),
    help="'require' fails on missing cache; 'read-write' builds missing entries lazily.",
)
@click.option("--prompt-lang", default=DEFAULT_PROMPT_LANG, show_default=True, type=click.Choice(PROMPT_LANGS))
@click.option("--run-name", default=DEFAULT_RUN_NAME, show_default=True)
@click.option("--wandb-project", default=DEFAULT_WANDB_PROJECT, show_default=True)
@click.option("--wandb-entity", default="chenghuzi")
@click.option("--env-file", default=".env", show_default=True, type=click.Path(path_type=Path))
@click.option("--wandb/--no-wandb", default=True, show_default=True)
@click.option("--num-train-epochs", default=1.0, show_default=True, type=click.FloatRange(min=0))
@click.option("--max-steps", default=-1, show_default=True, type=int)
@click.option("--max-train-samples", default=None, type=click.IntRange(min=1))
@click.option("--max-eval-samples", default=None, type=click.IntRange(min=1))
@click.option("--max-test-samples", default=None, type=click.IntRange(min=1))
@click.option("--remix-train-validation/--no-remix-train-validation", default=False, show_default=True)
@click.option(
    "--remix-validation-ratio",
    default=0.10,
    show_default=True,
    type=click.FloatRange(min=0.0, max=1.0, min_open=True, max_open=True),
)
@click.option("--remix-seed", default=42, show_default=True, type=int)
@click.option("--learning-rate", default=1e-4, show_default=True, type=float)
@click.option("--warmup-ratio", default=0.03, show_default=True, type=click.FloatRange(min=0, max=1))
@click.option("--weight-decay", default=0.0, show_default=True, type=click.FloatRange(min=0))
@click.option("--per-device-train-batch-size", default=1, show_default=True, type=click.IntRange(min=1))
@click.option("--per-device-eval-batch-size", default=1, show_default=True, type=click.IntRange(min=1))
@click.option("--gradient-accumulation-steps", default=8, show_default=True, type=click.IntRange(min=1))
@click.option("--logging-steps", default=5, show_default=True, type=click.IntRange(min=1))
@click.option("--eval-steps", default=50, show_default=True, type=click.IntRange(min=1))
@click.option("--save-steps", default=50, show_default=True, type=click.IntRange(min=1))
@click.option("--save-total-limit", default=3, show_default=True, type=click.IntRange(min=1))
@click.option("--frame-fps", default=1.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--max-frames", default=16, show_default=True, type=click.IntRange(min=1))
@click.option("--max-audio-seconds", default=30.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--image-width", default=512, show_default=True, type=click.IntRange(min=64))
@click.option("--audio/--no-audio", "use_audio", default=True, show_default=True)
@click.option("--lora-r", default=32, show_default=True, type=click.IntRange(min=1))
@click.option("--lora-alpha", default=64, show_default=True, type=click.IntRange(min=1))
@click.option("--lora-dropout", default=0.05, show_default=True, type=click.FloatRange(min=0, max=1))
@click.option(
    "--target-modules",
    default="language",
    show_default=True,
    help="'language', 'all-linear', or comma-separated PEFT target module names/regex.",
)
@click.option("--max-memory-per-gpu", default="22GiB", show_default=True)
@click.option("--prediction-max-new-tokens", default=16, show_default=True, type=click.IntRange(min=1))
@click.option("--generated-metrics/--no-generated-metrics", default=True, show_default=True)
@click.option(
    "--generated-early-stopping-metric",
    default="none",
    show_default=True,
    type=click.Choice(["none", "micro_f1", "macro_f1", "exact_match", "hamming_accuracy", "parse_rate"]),
    help="Stop training from generated validation metrics. Disabled by default.",
)
@click.option(
    "--generated-early-stopping-patience",
    default=0,
    show_default=True,
    type=click.IntRange(min=0),
    help="Number of generated validation evaluations without improvement before stopping.",
)
@click.option(
    "--generated-early-stopping-min-delta",
    default=0.0,
    show_default=True,
    type=click.FloatRange(min=0.0),
    help="Minimum improvement required for generated early stopping.",
)
@click.option("--bf16/--no-bf16", default=True, show_default=True)
@click.option("--gradient-checkpointing/--no-gradient-checkpointing", default=True, show_default=True)
@click.option("--qlora-4bit/--no-qlora-4bit", default=False, show_default=True)
@click.option("--loftq/--no-loftq", default=False, show_default=True)
@click.option("--loftq-bits", default=4, show_default=True, type=click.IntRange(min=2, max=8))
@click.option("--loftq-iter", default=1, show_default=True, type=click.IntRange(min=1))
@click.option("--resume-from-checkpoint", default=None, type=click.Path(path_type=Path))
def train(
    cuda_devices: str,
    data_root: Path,
    model_dir: Path,
    output_dir: Path,
    cache_dir: Path,
    cache_mode: str,
    prompt_lang: str,
    run_name: str,
    wandb_project: str,
    wandb_entity: str | None,
    env_file: Path,
    wandb: bool,
    num_train_epochs: float,
    max_steps: int,
    max_train_samples: int | None,
    max_eval_samples: int | None,
    max_test_samples: int | None,
    remix_train_validation: bool,
    remix_validation_ratio: float,
    remix_seed: int,
    learning_rate: float,
    warmup_ratio: float,
    weight_decay: float,
    per_device_train_batch_size: int,
    per_device_eval_batch_size: int,
    gradient_accumulation_steps: int,
    logging_steps: int,
    eval_steps: int,
    save_steps: int,
    save_total_limit: int,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    use_audio: bool,
    lora_r: int,
    lora_alpha: int,
    lora_dropout: float,
    target_modules: str,
    max_memory_per_gpu: str,
    prediction_max_new_tokens: int,
    generated_metrics: bool,
    generated_early_stopping_metric: str,
    generated_early_stopping_patience: int,
    generated_early_stopping_min_delta: float,
    bf16: bool,
    gradient_checkpointing: bool,
    qlora_4bit: bool,
    loftq: bool,
    loftq_bits: int,
    loftq_iter: int,
    resume_from_checkpoint: Path | None,
) -> None:
    """Fine-tune Gemma 4 E4B with BF16 LoRA on ASD-DS."""
    if per_device_train_batch_size != 1 or per_device_eval_batch_size != 1:
        raise click.ClickException("This first training collator supports batch size 1 only.")

    prompts = load_prompt_bundle(prompt_lang)
    configure_runtime(cuda_devices)

    import torch
    import wandb as wandb_lib
    from peft import LoftQConfig, LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoProcessor, BitsAndBytesConfig, Gemma4ForConditionalGeneration, Trainer, TrainingArguments

    ffmpeg = find_tool("ffmpeg")
    load_env_file(env_file)
    setup_wandb(
        enabled=wandb,
        wandb_lib=wandb_lib,
        project=wandb_project,
        entity=wandb_entity,
        run_name=run_name,
    )

    click.echo("== Training setup ==")
    click.echo(f"CUDA_VISIBLE_DEVICES: {os.environ['CUDA_VISIBLE_DEVICES']}")
    click.echo(f"visible_cuda_count: {torch.cuda.device_count()}")
    for idx in range(torch.cuda.device_count()):
        click.echo(f"cuda:{idx}: {torch.cuda.get_device_name(idx)}")
    click.echo(f"data_root: {data_root}")
    click.echo(f"model_dir: {model_dir}")
    click.echo(f"output_dir: {output_dir}")
    click.echo(f"cache_dir: {cache_dir}")
    click.echo(f"cache_mode: {cache_mode}")
    click.echo(f"prompt_lang: {prompts.lang}")
    click.echo(f"use_audio: {use_audio}")
    click.echo(f"qlora_4bit: {qlora_4bit}")
    click.echo(f"loftq: {loftq}")
    if generated_early_stopping_metric != "none" and generated_early_stopping_patience > 0:
        click.echo(
            "generated_early_stopping: "
            f"metric={generated_early_stopping_metric} "
            f"patience={generated_early_stopping_patience} "
            f"min_delta={generated_early_stopping_min_delta}"
        )
    if loftq:
        click.echo(f"loftq_bits: {loftq_bits}")
        click.echo(f"loftq_iter: {loftq_iter}")
    click.echo(f"ffmpeg: {ffmpeg}")

    dataset = load_asd_ds(data_root)
    train_dataset = dataset["train"]
    eval_dataset = dataset["validation"]
    test_dataset = dataset["test"]
    if remix_train_validation:
        train_dataset, eval_dataset = remix_train_validation_split(
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            validation_ratio=remix_validation_ratio,
            seed=remix_seed,
        )
        click.echo("== Remixed train/validation split ==")
        click.echo(f"remix_validation_ratio: {remix_validation_ratio}")
        click.echo(f"remix_seed: {remix_seed}")
        click.echo(f"train_samples: {len(train_dataset)} origin={dataset_origin_counts(train_dataset)}")
        click.echo(f"validation_samples: {len(eval_dataset)} origin={dataset_origin_counts(eval_dataset)}")
        click.echo(f"test_samples_unchanged: {len(test_dataset)}")

    if max_train_samples is not None:
        train_dataset = train_dataset.select(range(min(max_train_samples, len(train_dataset))))
    if max_eval_samples is not None:
        eval_dataset = eval_dataset.select(range(min(max_eval_samples, len(eval_dataset))))
    if max_test_samples is not None:
        test_dataset = test_dataset.select(range(min(max_test_samples, len(test_dataset))))

    processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
    cache_store = None
    if cache_mode != "off":
        cache_store = ProcessorCache(
            cache_dir=cache_dir,
            config=build_cache_config(
                model_dir=model_dir,
                frame_fps=frame_fps,
                max_frames=max_frames,
                max_audio_seconds=max_audio_seconds,
                image_width=image_width,
                prompts=prompts,
                use_audio=use_audio,
            ),
            mode=cache_mode,
        )
        cache_store.write_config()
        click.echo(f"processor_cache_root: {cache_store.root}")

    collator = Gemma4ASDDSCollator(
        processor=processor,
        ffmpeg=ffmpeg,
        frame_fps=frame_fps,
        max_frames=max_frames,
        max_audio_seconds=max_audio_seconds,
        image_width=image_width,
        prompts=prompts,
        use_audio=use_audio,
        cache_store=cache_store,
    )

    max_memory = {idx: max_memory_per_gpu for idx in range(torch.cuda.device_count())}
    quantization_config = None
    if qlora_4bit and not loftq:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16 if bf16 else torch.float16,
            bnb_4bit_use_double_quant=True,
        )

    model = Gemma4ForConditionalGeneration.from_pretrained(
        model_dir,
        dtype=torch.bfloat16 if bf16 else torch.float16,
        device_map="auto",
        max_memory=max_memory,
        quantization_config=quantization_config,
        local_files_only=True,
    )
    model.config.use_cache = False

    if gradient_checkpointing:
        enable_gradient_checkpointing(model)

    if qlora_4bit and not loftq:
        model = prepare_model_for_kbit_training(
            model,
            use_gradient_checkpointing=gradient_checkpointing,
        )

    lora_init: bool | str = True
    loftq_config = None
    if loftq:
        lora_init = "loftq"
        loftq_config = LoftQConfig(loftq_bits=loftq_bits, loftq_iter=loftq_iter)

    lora_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=parse_target_modules(target_modules),
        init_lora_weights=lora_init,
        loftq_config=loftq_config,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        run_name=run_name,
        report_to=["wandb"] if wandb else [],
        num_train_epochs=num_train_epochs,
        max_steps=max_steps,
        per_device_train_batch_size=per_device_train_batch_size,
        per_device_eval_batch_size=per_device_eval_batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        weight_decay=weight_decay,
        bf16=bf16,
        logging_steps=logging_steps,
        eval_strategy="steps",
        eval_steps=eval_steps,
        save_strategy="steps",
        save_steps=save_steps,
        save_total_limit=save_total_limit,
        remove_unused_columns=False,
        dataloader_num_workers=0,
        dataloader_pin_memory=False,
        gradient_checkpointing=gradient_checkpointing,
        optim="adamw_torch",
    )

    metrics_evaluator = None
    callbacks = []
    if generated_metrics:
        metrics_evaluator = GeneratedMetricsEvaluator(
            processor=processor,
            ffmpeg=ffmpeg,
            frame_fps=frame_fps,
            max_frames=max_frames,
            max_audio_seconds=max_audio_seconds,
            image_width=image_width,
            prompts=prompts,
            use_audio=use_audio,
            output_dir=output_dir / "generated_metrics",
            max_new_tokens=prediction_max_new_tokens,
            wandb_enabled=wandb,
            cache_store=cache_store,
        )
        callbacks.append(
            GeneratedMetricsCallback(
                evaluator=metrics_evaluator,
                eval_dataset=eval_dataset,
                early_stopping_metric=generated_early_stopping_metric,
                early_stopping_patience=generated_early_stopping_patience,
                early_stopping_min_delta=generated_early_stopping_min_delta,
            )
        )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=collator,
        processing_class=processor,
        callbacks=callbacks,
    )

    click.echo("== Starting training ==")
    trainer.train(resume_from_checkpoint=str(resume_from_checkpoint) if resume_from_checkpoint else None)
    click.echo("== Saving adapter and processor ==")
    trainer.save_model(str(output_dir))
    processor.save_pretrained(output_dir)
    click.echo(f"Saved training artifacts to {output_dir}")

    if metrics_evaluator is not None:
        click.echo("== Running final generated validation metrics ==")
        metrics_evaluator.evaluate(
            model=trainer.model,
            dataset=eval_dataset,
            split_name="validation_final",
            step=int(trainer.state.global_step),
            epoch=trainer.state.epoch,
        )
        click.echo("== Running final generated test metrics ==")
        metrics_evaluator.evaluate(
            model=trainer.model,
            dataset=test_dataset,
            split_name="test_final",
            step=int(trainer.state.global_step),
            epoch=trainer.state.epoch,
        )


@cli.command("eval-hf")
@click.option("--cuda-devices", default="1,2,3", show_default=True, help="Physical CUDA device IDs.")
@click.option("--data-root", default=DEFAULT_DATA_ROOT, show_default=True, type=click.Path(path_type=Path))
@click.option("--model-dir", required=True, type=click.Path(path_type=Path), help="Merged HF model directory to evaluate.")
@click.option(
    "--processor-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Processor directory used for preprocessing/cache identity. Defaults to --model-dir.",
)
@click.option("--output-dir", required=True, type=click.Path(path_type=Path))
@click.option("--cache-dir", default=DEFAULT_CACHE_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option(
    "--cache-mode",
    default="require",
    show_default=True,
    type=click.Choice(["off", "read-write", "require"]),
)
@click.option("--split", default="test", show_default=True, type=click.Choice(["validation", "test"]))
@click.option("--prompt-lang", default=DEFAULT_PROMPT_LANG, show_default=True, type=click.Choice(PROMPT_LANGS))
@click.option("--max-samples", default=None, type=click.IntRange(min=1))
@click.option("--frame-fps", default=1.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--max-frames", default=16, show_default=True, type=click.IntRange(min=1))
@click.option("--max-audio-seconds", default=30.0, show_default=True, type=click.FloatRange(min=0.1))
@click.option("--image-width", default=512, show_default=True, type=click.IntRange(min=64))
@click.option("--audio/--no-audio", "use_audio", default=True, show_default=True)
@click.option("--prediction-max-new-tokens", default=16, show_default=True, type=click.IntRange(min=1))
@click.option("--max-memory-per-gpu", default="22GiB", show_default=True)
@click.option("--bf16/--no-bf16", default=True, show_default=True)
def eval_hf(
    cuda_devices: str,
    data_root: Path,
    model_dir: Path,
    processor_dir: Path | None,
    output_dir: Path,
    cache_dir: Path,
    cache_mode: str,
    split: str,
    prompt_lang: str,
    max_samples: int | None,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    use_audio: bool,
    prediction_max_new_tokens: int,
    max_memory_per_gpu: str,
    bf16: bool,
) -> None:
    """Run generated metrics for a merged Hugging Face model."""
    configure_runtime(cuda_devices)

    import torch
    from transformers import AutoProcessor, Gemma4ForConditionalGeneration

    model_dir = model_dir.expanduser()
    processor_dir = (processor_dir or model_dir).expanduser()
    prompts = load_prompt_bundle(prompt_lang)
    ffmpeg = find_tool("ffmpeg")

    dataset = load_asd_ds(data_root)[split]
    if max_samples is not None:
        dataset = dataset.select(range(min(max_samples, len(dataset))))

    click.echo("== HF generated eval setup ==")
    click.echo(f"model_dir: {model_dir}")
    click.echo(f"processor_dir: {processor_dir}")
    click.echo(f"data_root: {data_root}")
    click.echo(f"split: {split}")
    click.echo(f"samples: {len(dataset)}")
    click.echo(f"output_dir: {output_dir}")
    click.echo(f"cache_dir: {cache_dir}")
    click.echo(f"cache_mode: {cache_mode}")
    click.echo(f"prompt_lang: {prompts.lang}")
    click.echo(f"use_audio: {use_audio}")

    processor = AutoProcessor.from_pretrained(processor_dir, local_files_only=True)
    cache_store = None
    if cache_mode != "off":
        cache_store = ProcessorCache(
            cache_dir=cache_dir,
            config=build_cache_config(
                model_dir=processor_dir,
                frame_fps=frame_fps,
                max_frames=max_frames,
                max_audio_seconds=max_audio_seconds,
                image_width=image_width,
                prompts=prompts,
                use_audio=use_audio,
            ),
            mode=cache_mode,
        )
        cache_store.write_config()
        click.echo(f"processor_cache_root: {cache_store.root}")

    max_memory = {idx: max_memory_per_gpu for idx in range(torch.cuda.device_count())}
    model_kwargs: dict[str, Any] = {
        "dtype": torch.bfloat16 if bf16 else torch.float16,
        "device_map": "auto",
        "local_files_only": True,
    }
    if torch.cuda.is_available():
        model_kwargs["max_memory"] = max_memory
    model = Gemma4ForConditionalGeneration.from_pretrained(model_dir, **model_kwargs)

    evaluator = GeneratedMetricsEvaluator(
        processor=processor,
        ffmpeg=ffmpeg,
        frame_fps=frame_fps,
        max_frames=max_frames,
        max_audio_seconds=max_audio_seconds,
        image_width=image_width,
        prompts=prompts,
        use_audio=use_audio,
        output_dir=output_dir,
        max_new_tokens=prediction_max_new_tokens,
        wandb_enabled=False,
        cache_store=cache_store,
    )
    evaluator.evaluate(
        model=model,
        dataset=dataset,
        split_name=f"{split}_hf",
        step=0,
        epoch=None,
    )


@cli.command("merge")
@click.option("--cuda-devices", default="1,2,3", show_default=True, help="Physical CUDA device IDs for merging.")
@click.option("--model-dir", default=DEFAULT_MODEL_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option("--adapter-dir", required=True, type=click.Path(path_type=Path))
@click.option("--merged-model-dir", required=True, type=click.Path(path_type=Path))
@click.option("--max-memory-per-gpu", default="22GiB", show_default=True)
@click.option("--bf16/--no-bf16", default=True, show_default=True)
@click.option("--overwrite/--no-overwrite", default=False, show_default=True)
def merge_model(
    cuda_devices: str,
    model_dir: Path,
    adapter_dir: Path,
    merged_model_dir: Path,
    max_memory_per_gpu: str,
    bf16: bool,
    overwrite: bool,
) -> None:
    """Merge a LoRA adapter into a Hugging Face model directory."""
    configure_runtime(cuda_devices)
    adapter_dir = adapter_dir.expanduser()
    merged_model_dir = merged_model_dir.expanduser()

    validate_existing_adapter_dir(adapter_dir)
    should_merge = prepare_merged_output_dir(merged_model_dir, overwrite=overwrite)

    click.echo("== Merge setup ==")
    click.echo(f"model_dir: {model_dir}")
    click.echo(f"adapter_dir: {adapter_dir}")
    click.echo(f"merged_model_dir: {merged_model_dir}")

    if should_merge:
        merge_lora_adapter(
            model_dir=model_dir,
            adapter_dir=adapter_dir,
            merged_model_dir=merged_model_dir,
            max_memory_per_gpu=max_memory_per_gpu,
            bf16=bf16,
        )
    else:
        click.echo(f"Reusing existing merged HF model at {merged_model_dir}")

    click.echo("MERGE DONE")
    click.echo(f"merged_model_dir: {merged_model_dir}")


@cli.command("export")
@click.option("--cuda-devices", default="1,2,3", show_default=True, help="Physical CUDA device IDs for merging.")
@click.option("--model-dir", default=DEFAULT_MODEL_DIR, show_default=True, type=click.Path(path_type=Path))
@click.option("--adapter-dir", required=True, type=click.Path(path_type=Path))
@click.option("--merged-model-dir", default=None, type=click.Path(path_type=Path))
@click.option("--litert-out-dir", default=None, type=click.Path(path_type=Path))
@click.option(
    "--official-litertlm-file",
    default=None,
    type=click.Path(path_type=Path),
    help=(
        "Official base Gemma 4 LiteRT-LM package used as the audio-section source. "
        "Defaults to outputs/gemma4-official-litert/gemma-4-E4B-it.litertlm, "
        "downloading it from Hugging Face if missing."
    ),
)
@click.option("--max-memory-per-gpu", default="22GiB", show_default=True)
@click.option("--bf16/--no-bf16", default=True, show_default=True)
@click.option("--overwrite/--no-overwrite", default=False, show_default=True)
@click.option("--inspect/--no-inspect", default=True, show_default=True)
@click.option("--smoke-test/--no-smoke-test", default=False, show_default=True)
@click.option("--smoke-backend", default="gpu", show_default=True, type=click.Choice(["gpu", "cpu"]))
@click.option("--audio/--no-audio", "use_audio", default=True, show_default=True)
@click.option(
    "--quantization-recipe",
    default=DEFAULT_LITERT_QUANTIZATION_RECIPE,
    show_default=True,
    help="LiteRT text decoder quantization recipe. Use 'none' to export without quantization.",
)
@click.option(
    "--vision-encoder-quantization-recipe",
    default=DEFAULT_LITERT_VISION_QUANTIZATION_RECIPE,
    show_default=True,
    help="LiteRT vision encoder quantization recipe. Use 'none' to export without quantization.",
)
@click.option(
    "--cache-length",
    default=4096,
    show_default=True,
    type=click.IntRange(min=1),
    help="LiteRT KV cache length. Increase when multimodal prompts exceed the default 4096-token limit.",
)
def export_model(
    cuda_devices: str,
    model_dir: Path,
    adapter_dir: Path,
    merged_model_dir: Path | None,
    litert_out_dir: Path | None,
    official_litertlm_file: Path | None,
    max_memory_per_gpu: str,
    bf16: bool,
    overwrite: bool,
    inspect: bool,
    smoke_test: bool,
    smoke_backend: str,
    use_audio: bool,
    quantization_recipe: str,
    vision_encoder_quantization_recipe: str,
    cache_length: int,
) -> None:
    """Merge a LoRA adapter and export a LiteRT-LM package."""
    configure_runtime(cuda_devices)
    adapter_dir = adapter_dir.expanduser()
    merged_model_dir = (merged_model_dir or default_export_dir(adapter_dir, "merged")).expanduser()
    quantization_recipe_value = normalize_optional_recipe(quantization_recipe)
    vision_quantization_recipe_value = normalize_optional_recipe(vision_encoder_quantization_recipe)
    litert_suffix = default_litert_suffix(
        use_audio=use_audio,
        quantization_recipe=quantization_recipe_value,
    )
    litert_out_dir = (litert_out_dir or default_export_dir(adapter_dir, litert_suffix)).expanduser()

    validate_existing_adapter_dir(adapter_dir)
    should_merge = prepare_merged_output_dir(merged_model_dir, overwrite=overwrite)
    prepare_litert_output_dir(litert_out_dir, overwrite=overwrite)
    if use_audio:
        official_litertlm_file = ensure_official_litertlm_file(official_litertlm_file)
    else:
        official_litertlm_file = None

    click.echo("== Export setup ==")
    click.echo(f"model_dir: {model_dir}")
    click.echo(f"adapter_dir: {adapter_dir}")
    click.echo(f"merged_model_dir: {merged_model_dir}")
    click.echo(f"litert_out_dir: {litert_out_dir}")
    click.echo(f"use_audio: {use_audio}")
    click.echo(f"official_litertlm_file: {official_litertlm_file}")
    click.echo(f"quantization_recipe: {quantization_recipe_value}")
    click.echo(f"vision_encoder_quantization_recipe: {vision_quantization_recipe_value}")
    click.echo(f"cache_length: {cache_length}")

    if should_merge:
        merge_lora_adapter(
            model_dir=model_dir,
            adapter_dir=adapter_dir,
            merged_model_dir=merged_model_dir,
            max_memory_per_gpu=max_memory_per_gpu,
            bf16=bf16,
        )
    else:
        click.echo(f"Reusing existing merged HF model at {merged_model_dir}")

    litert_out_dir.mkdir(parents=True, exist_ok=True)
    if use_audio:
        if official_litertlm_file is None:
            raise click.ClickException("Internal error: audio export requires an official LiteRT-LM source package.")
        text_vision_out_dir = litert_out_dir / "_text_vision_export"
        if text_vision_out_dir.exists():
            shutil.rmtree(text_vision_out_dir)

        text_vision_litertlm_file = export_text_vision_litert_lm(
            merged_model_dir=merged_model_dir,
            litert_out_dir=text_vision_out_dir,
            quantization_recipe=quantization_recipe_value,
            vision_encoder_quantization_recipe=vision_quantization_recipe_value,
            cache_length=cache_length,
        )
        litertlm_file = build_audio_capable_litert_lm(
            text_vision_litertlm_file=text_vision_litertlm_file,
            official_litertlm_file=official_litertlm_file,
            litert_out_dir=litert_out_dir,
            quantization_recipe=quantization_recipe_value,
            vision_encoder_quantization_recipe=vision_quantization_recipe_value,
            cache_length=cache_length,
        )
        shutil.rmtree(text_vision_out_dir, ignore_errors=True)
    else:
        litertlm_file = export_text_vision_litert_lm(
            merged_model_dir=merged_model_dir,
            litert_out_dir=litert_out_dir,
            quantization_recipe=quantization_recipe_value,
            vision_encoder_quantization_recipe=vision_quantization_recipe_value,
            cache_length=cache_length,
        )
        write_text_vision_export_manifest(
            manifest_path=litert_out_dir / "export_manifest.json",
            final_litertlm_file=litertlm_file,
            quantization_recipe=quantization_recipe_value,
            vision_encoder_quantization_recipe=vision_quantization_recipe_value,
            cache_length=cache_length,
        )

    if inspect:
        inspect_litert_lm(litertlm_file, use_audio=use_audio)
    validate_litert_lm_sections(litertlm_file, use_audio=use_audio)
    if smoke_test:
        smoke_test_litert_lm(litertlm_file, backend=smoke_backend)

    click.echo("EXPORT DONE")
    click.echo(f"litertlm_file: {litertlm_file}")


def default_export_dir(adapter_dir: Path, suffix: str) -> Path:
    adapter_dir = adapter_dir.expanduser()
    return adapter_dir.parent / f"{adapter_dir.name}-{suffix}"


def default_litert_suffix(*, use_audio: bool, quantization_recipe: str | None) -> str:
    quant_label = "w4" if quantization_recipe else "fp"
    audio_label = "audio" if use_audio else "noaudio"
    return f"litert-{quant_label}-{audio_label}"


def normalize_optional_recipe(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() in {"none", "null", "off", "false"}:
        return None
    return normalized


def validate_existing_adapter_dir(adapter_dir: Path) -> None:
    if not adapter_dir.is_dir():
        raise click.ClickException(f"--adapter-dir does not exist or is not a directory: {adapter_dir}")

    required_files = ("adapter_config.json", "adapter_model.safetensors")
    missing = [name for name in required_files if not (adapter_dir / name).is_file()]
    if missing:
        raise click.ClickException(f"--adapter-dir is missing required file(s): {', '.join(missing)}")


def prepare_merged_output_dir(path: Path, *, overwrite: bool) -> bool:
    ensure_under_outputs(path)
    if not path.exists():
        return True
    if not path.is_dir():
        raise click.ClickException(f"Output path exists and is not a directory: {path}")
    if not any(path.iterdir()):
        return True
    if is_merged_model_dir(path) and not overwrite:
        return False
    if not overwrite:
        raise click.ClickException(f"Merged output directory already exists and is not reusable: {path}")
    shutil.rmtree(path)
    return True


def prepare_litert_output_dir(path: Path, *, overwrite: bool) -> None:
    ensure_under_outputs(path)
    litertlm_file = path / "model.litertlm"
    if not path.exists():
        return
    if not path.is_dir():
        raise click.ClickException(f"Output path exists and is not a directory: {path}")
    if not any(path.iterdir()):
        return
    if litertlm_file.is_file() and not overwrite:
        raise click.ClickException(f"LiteRT-LM package already exists: {litertlm_file}")
    if not litertlm_file.is_file():
        click.echo(f"Removing incomplete LiteRT output directory: {path}")
    shutil.rmtree(path)


def is_merged_model_dir(path: Path) -> bool:
    return (
        (path / "config.json").is_file()
        and (path / "model.safetensors").is_file()
        and (path / "tokenizer.json").is_file()
        and (path / "processor_config.json").is_file()
    )


def ensure_under_outputs(path: Path) -> None:
    root = Path("outputs").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise click.ClickException(f"Generated export artifacts must stay under outputs/: {path}") from exc


def merge_lora_adapter(
    *,
    model_dir: Path,
    adapter_dir: Path,
    merged_model_dir: Path,
    max_memory_per_gpu: str,
    bf16: bool,
) -> None:
    import torch
    from peft import PeftModel
    from transformers import AutoProcessor, Gemma4ForConditionalGeneration

    click.echo("== Merging LoRA adapter ==")
    processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
    model_kwargs: dict[str, Any] = {
        "dtype": torch.bfloat16 if bf16 else torch.float16,
        "device_map": "auto",
        "local_files_only": True,
    }
    if torch.cuda.is_available():
        model_kwargs["max_memory"] = {idx: max_memory_per_gpu for idx in range(torch.cuda.device_count())}

    base_model = Gemma4ForConditionalGeneration.from_pretrained(model_dir, **model_kwargs)
    model = PeftModel.from_pretrained(base_model, adapter_dir)
    model = model.merge_and_unload()
    model.save_pretrained(merged_model_dir, safe_serialization=True)
    processor.save_pretrained(merged_model_dir)
    del model
    del base_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    click.echo(f"Saved merged HF model to {merged_model_dir}")


def ensure_official_litertlm_file(official_litertlm_file: Path | None) -> Path:
    if official_litertlm_file is not None:
        path = official_litertlm_file.expanduser()
        if not path.is_file():
            raise click.ClickException(f"--official-litertlm-file does not exist: {path}")
        return path

    default_path = DEFAULT_OFFICIAL_LITERT_DIR / DEFAULT_OFFICIAL_LITERT_FILENAME
    if default_path.is_file():
        return default_path

    click.echo("== Downloading official Gemma 4 LiteRT-LM reference package ==")
    click.echo(f"repo: {DEFAULT_OFFICIAL_LITERT_REPO}")
    click.echo(f"filename: {DEFAULT_OFFICIAL_LITERT_FILENAME}")
    DEFAULT_OFFICIAL_LITERT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise click.ClickException(
            "huggingface_hub is required to download the official LiteRT-LM package."
        ) from exc

    saved_env = {name: os.environ.get(name) for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}
    try:
        for name in saved_env:
            os.environ.pop(name, None)
        downloaded = Path(
            hf_hub_download(
                repo_id=DEFAULT_OFFICIAL_LITERT_REPO,
                filename=DEFAULT_OFFICIAL_LITERT_FILENAME,
                repo_type="model",
                local_dir=DEFAULT_OFFICIAL_LITERT_DIR,
                local_files_only=False,
            )
        )
    except Exception as exc:
        raise click.ClickException(
            "Could not locate or download the official Gemma 4 LiteRT-LM package. "
            f"Expected {default_path}. You can provide it with --official-litertlm-file."
        ) from exc
    finally:
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    if downloaded != default_path:
        shutil.copy2(downloaded, default_path)
    if not default_path.is_file():
        raise click.ClickException(f"Official LiteRT-LM download did not create {default_path}")
    return default_path


def export_text_vision_litert_lm(
    *,
    merged_model_dir: Path,
    litert_out_dir: Path,
    quantization_recipe: str | None,
    vision_encoder_quantization_recipe: str | None,
    cache_length: int,
) -> Path:
    litert_torch = find_tool("litert-torch")
    command = [
        litert_torch,
        "export_hf",
        f"--model={merged_model_dir}",
        f"--output_dir={litert_out_dir}",
        "--externalize_embedder",
        "--task=image_text_to_text",
        "--export_vision_encoder",
        f"--jinja_chat_template_override={DEFAULT_LITERT_TEMPLATE_OVERRIDE}",
        f"--cache_length={cache_length}",
    ]
    command.append(
        "--quantization_recipe="
        + (quantization_recipe if quantization_recipe is not None else "False")
    )
    command.append(
        "--vision_encoder_quantization_recipe="
        + (
            vision_encoder_quantization_recipe
            if vision_encoder_quantization_recipe is not None
            else "False"
        )
    )

    click.echo("== Exporting text+vision LiteRT-LM package ==")
    click.echo(" ".join(command))
    run_command(command, env=litert_export_env())

    litertlm_file = litert_out_dir / "model.litertlm"
    if not litertlm_file.is_file():
        raise click.ClickException(f"LiteRT export finished but did not create expected file: {litertlm_file}")
    return litertlm_file


def build_audio_capable_litert_lm(
    *,
    text_vision_litertlm_file: Path,
    official_litertlm_file: Path,
    litert_out_dir: Path,
    quantization_recipe: str | None,
    vision_encoder_quantization_recipe: str | None,
    cache_length: int,
) -> Path:
    litert_lm_builder = find_tool("litert-lm-builder")
    final_litertlm_file = litert_out_dir / "model.litertlm"
    with tempfile.TemporaryDirectory(prefix="litert-packaging-", dir=litert_out_dir) as tmp:
        work_dir = Path(tmp)
        text_vision_dump_dir = work_dir / "text_vision_dump"
        official_dump_dir = work_dir / "official_dump"

        dump_litert_lm(text_vision_litertlm_file, text_vision_dump_dir)
        dump_litert_lm(official_litertlm_file, official_dump_dir)

        model_toml = work_dir / "model.toml"
        write_audio_hybrid_toml(
            model_toml=model_toml,
            text_vision_dump_dir=text_vision_dump_dir,
            official_dump_dir=official_dump_dir,
        )

        click.echo("== Building audio-capable W4 LiteRT-LM package ==")
        run_command(
            [
                litert_lm_builder,
                "toml",
                "--path",
                str(model_toml),
                "output",
                "--path",
                str(final_litertlm_file),
            ]
        )

    if not final_litertlm_file.is_file():
        raise click.ClickException(f"LiteRT-LM builder did not create expected file: {final_litertlm_file}")
    write_export_manifest(
        manifest_path=litert_out_dir / "export_manifest.json",
        text_vision_litertlm_file=text_vision_litertlm_file,
        official_litertlm_file=official_litertlm_file,
        final_litertlm_file=final_litertlm_file,
        quantization_recipe=quantization_recipe,
        vision_encoder_quantization_recipe=vision_encoder_quantization_recipe,
        cache_length=cache_length,
    )
    validate_litert_lm_sections(final_litertlm_file, use_audio=True)
    return final_litertlm_file


def dump_litert_lm(litertlm_file: Path, dump_dir: Path) -> None:
    litert_lm_peek = find_tool("litert-lm-peek")
    if dump_dir.exists():
        shutil.rmtree(dump_dir)
    dump_dir.mkdir(parents=True, exist_ok=True)
    completed = run_command(
        [
            litert_lm_peek,
            "--litertlm_file",
            str(litertlm_file),
            "--dump_files_dir",
            str(dump_dir),
        ],
        capture_stdout=True,
    )
    (dump_dir / "peek.txt").write_bytes(completed.stdout or b"")


def write_export_manifest(
    *,
    manifest_path: Path,
    text_vision_litertlm_file: Path,
    official_litertlm_file: Path,
    final_litertlm_file: Path,
    quantization_recipe: str | None,
    vision_encoder_quantization_recipe: str | None,
    cache_length: int,
) -> None:
    manifest = {
        "format": "gemma4_asd_litert_audio_export_v1",
        "final_litertlm_file": str(final_litertlm_file),
        "use_audio": True,
        "text_vision_source": {
            "temporary_litertlm_file": str(text_vision_litertlm_file),
            "removed_after_packaging": True,
            "quantization_recipe": quantization_recipe,
            "vision_encoder_quantization_recipe": vision_encoder_quantization_recipe,
            "cache_length": cache_length,
        },
        "audio_source": {
            "litertlm_file": str(official_litertlm_file),
            "repo": DEFAULT_OFFICIAL_LITERT_REPO,
            "filename": DEFAULT_OFFICIAL_LITERT_FILENAME,
        },
        "required_model_types": list(REQUIRED_FINAL_LITERT_MODEL_TYPES),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def write_text_vision_export_manifest(
    *,
    manifest_path: Path,
    final_litertlm_file: Path,
    quantization_recipe: str | None,
    vision_encoder_quantization_recipe: str | None,
    cache_length: int,
) -> None:
    manifest = {
        "format": "gemma4_asd_litert_text_vision_export_v1",
        "final_litertlm_file": str(final_litertlm_file),
        "use_audio": False,
        "text_vision_source": {
            "quantization_recipe": quantization_recipe,
            "vision_encoder_quantization_recipe": vision_encoder_quantization_recipe,
            "cache_length": cache_length,
        },
        "required_model_types": list(required_litert_model_types(use_audio=False)),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def write_audio_hybrid_toml(
    *,
    model_toml: Path,
    text_vision_dump_dir: Path,
    official_dump_dir: Path,
) -> None:
    text_vision_sections = {
        "llm_metadata": require_dump_file(text_vision_dump_dir, "LlmMetadataProto.pbtext"),
        "tokenizer": require_tokenizer_dump_file(text_vision_dump_dir),
        "embedder": require_tflite_dump_file(text_vision_dump_dir, "tf_lite_embedder"),
        "per_layer_embedder": require_tflite_dump_file(text_vision_dump_dir, "tf_lite_per_layer_embedder"),
        "vision_encoder": require_tflite_dump_file(text_vision_dump_dir, "tf_lite_vision_encoder"),
        "vision_adapter": require_tflite_dump_file(text_vision_dump_dir, "tf_lite_vision_adapter"),
        "prefill_decode": require_tflite_dump_file(text_vision_dump_dir, "tf_lite_prefill_decode"),
    }
    official_audio_sections = {
        "audio_encoder_hw": require_tflite_dump_file(official_dump_dir, "tf_lite_audio_encoder_hw"),
        "audio_adapter": require_tflite_dump_file(official_dump_dir, "tf_lite_audio_adapter"),
        "end_of_audio": require_tflite_dump_file(official_dump_dir, "tf_lite_end_of_audio"),
    }
    tokenizer_section_type = (
        "HF_Tokenizer" if text_vision_sections["tokenizer"].suffix == ".zlib" else "SP_Tokenizer"
    )

    lines = [
        "[system_metadata]",
        "entries = [",
        '  { key = "Authors", value_type = "String", value = "ODML" },',
        (
            '  { key = "hybrid_source", value_type = "String", '
            'value = "ASD LoRA W4 text/vision + official Gemma 4 E4B audio sections" },'
        ),
        "]",
        "",
        "[[section]]",
        'section_type = "LlmMetadata"',
        f'data_path = "{toml_path(text_vision_sections["llm_metadata"])}"',
        "",
        "[[section]]",
        f'section_type = "{tokenizer_section_type}"',
        f'data_path = "{toml_path(text_vision_sections["tokenizer"])}"',
        "",
    ]
    lines.extend(tflite_toml_section("embedder", text_vision_sections["embedder"]))
    lines.extend(tflite_toml_section("per_layer_embedder", text_vision_sections["per_layer_embedder"]))
    lines.extend(
        tflite_toml_section(
            "audio_encoder_hw",
            official_audio_sections["audio_encoder_hw"],
            backend_constraint="cpu",
        )
    )
    lines.extend(
        tflite_toml_section(
            "audio_adapter",
            official_audio_sections["audio_adapter"],
            backend_constraint="cpu",
        )
    )
    lines.extend(tflite_toml_section("end_of_audio", official_audio_sections["end_of_audio"]))
    lines.extend(tflite_toml_section("vision_encoder", text_vision_sections["vision_encoder"]))
    lines.extend(tflite_toml_section("vision_adapter", text_vision_sections["vision_adapter"]))
    lines.extend(tflite_toml_section("prefill_decode", text_vision_sections["prefill_decode"]))

    model_toml.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tflite_toml_section(
    model_type: str,
    path: Path,
    *,
    backend_constraint: str | None = None,
) -> list[str]:
    lines = [
        "[[section]]",
        f'model_type = "{model_type}"',
    ]
    if backend_constraint is not None:
        lines.append(f'backend_constraint = "{backend_constraint}"')
    lines.extend(
        [
            'section_type = "TFLiteModel"',
            f'data_path = "{toml_path(path)}"',
            "",
        ]
    )
    return lines


def toml_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace('"', '\\"')


def require_dump_file(dump_dir: Path, filename: str) -> Path:
    path = dump_dir / filename
    if not path.is_file():
        raise click.ClickException(f"Required LiteRT-LM dump file is missing: {path}")
    return path


def require_tokenizer_dump_file(dump_dir: Path) -> Path:
    matches = sorted(dump_dir.glob("*_Tokenizer*"))
    matches = [path for path in matches if path.suffix in {".zlib", ".spiece"}]
    if len(matches) != 1:
        raise click.ClickException(
            f"Expected exactly one tokenizer dump in {dump_dir}, found {len(matches)}"
        )
    return matches[0]


def require_tflite_dump_file(dump_dir: Path, model_type: str) -> Path:
    matches = sorted(dump_dir.glob(f"*_{model_type}.tflite"))
    if len(matches) != 1:
        raise click.ClickException(
            f"Expected exactly one {model_type} TFLite dump in {dump_dir}, found {len(matches)}"
        )
    return matches[0]


def inspect_litert_lm(litertlm_file: Path, *, use_audio: bool) -> None:
    litert_lm_peek = find_optional_tool("litert-lm-peek")
    if litert_lm_peek is None:
        click.echo("Skipping inspection: litert-lm-peek was not found.")
        return
    click.echo("== Inspecting LiteRT-LM package ==")
    completed = run_command([litert_lm_peek, "--litertlm_file", str(litertlm_file)], capture_stdout=True)
    peek_text = (completed.stdout or b"").decode("utf-8", errors="replace")
    peek_path = litertlm_file.parent / "peek.txt"
    peek_path.write_text(peek_text, encoding="utf-8")
    click.echo(f"peek_file: {peek_path}")
    for model_type in required_litert_model_types(use_audio=use_audio):
        status = "ok" if model_type in peek_text else "missing"
        click.echo(f"{model_type}: {status}")


def validate_litert_lm_sections(litertlm_file: Path, *, use_audio: bool) -> None:
    litert_lm_peek = find_tool("litert-lm-peek")
    completed = run_command([litert_lm_peek, "--litertlm_file", str(litertlm_file)], capture_stdout=True)
    peek_text = (completed.stdout or b"").decode("utf-8", errors="replace")
    missing = [model_type for model_type in required_litert_model_types(use_audio=use_audio) if model_type not in peek_text]
    if missing:
        raise click.ClickException(
            "LiteRT-LM package is missing required multimodal section(s): " + ", ".join(missing)
        )


def required_litert_model_types(*, use_audio: bool) -> tuple[str, ...]:
    if use_audio:
        return REQUIRED_FINAL_LITERT_MODEL_TYPES
    return REQUIRED_TEXT_VISION_LITERT_MODEL_TYPES


def smoke_test_litert_lm(litertlm_file: Path, *, backend: str) -> None:
    litert_lm = find_tool("litert-lm")
    click.echo("== LiteRT-LM text smoke test ==")
    run_command(
        [
            litert_lm,
            "run",
            str(litertlm_file),
            f"--backend={backend}",
            "--prompt=Return exactly 000000000 and nothing else.",
        ]
    )


def litert_export_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        env.pop(name, None)
    return env


def find_optional_tool(name: str) -> str | None:
    try:
        return find_tool(name)
    except click.ClickException:
        return None


def find_tool(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path

    venv_path = Path(os.environ.get("VIRTUAL_ENV", Path(__file__).parent / ".venv")) / "bin" / name
    if venv_path.is_file():
        return str(venv_path)

    brew_path = BREW_BIN / name
    if brew_path.is_file():
        return str(brew_path)

    raise click.ClickException(f"Could not find {name}. Install it or add it to PATH.")


class Gemma4ASDDSCollator:
    """Build one Gemma 4 multimodal SFT batch from one ASD-DS row."""

    def __init__(
        self,
        *,
        processor: Any,
        ffmpeg: str,
        frame_fps: float,
        max_frames: int,
        max_audio_seconds: float,
        image_width: int,
        prompts: PromptBundle,
        use_audio: bool,
        cache_store: "ProcessorCache | None" = None,
    ) -> None:
        self.processor = processor
        self.ffmpeg = ffmpeg
        self.frame_fps = frame_fps
        self.max_frames = max_frames
        self.max_audio_seconds = max_audio_seconds
        self.image_width = image_width
        self.prompts = prompts
        self.use_audio = use_audio
        self.cache_store = cache_store

    def __call__(self, examples: list[dict]) -> dict:
        if len(examples) != 1:
            raise ValueError("Gemma4ASDDSCollator currently supports batch size 1 only.")

        row = examples[0]
        builder = lambda: build_supervised_inputs(
            processor=self.processor,
            ffmpeg=self.ffmpeg,
            row=row,
            frame_fps=self.frame_fps,
            max_frames=self.max_frames,
            max_audio_seconds=self.max_audio_seconds,
            image_width=self.image_width,
            prompts=self.prompts,
            use_audio=self.use_audio,
        )
        if self.cache_store is None:
            return builder()
        return self.cache_store.load_or_build(kind="supervised", row=row, builder=builder)


class GeneratedMetricsCallback(TrainerCallback):
    """Run generation-based validation metrics after Trainer loss evaluation."""

    def __init__(
        self,
        *,
        evaluator: "GeneratedMetricsEvaluator",
        eval_dataset: Any,
        early_stopping_metric: str = "none",
        early_stopping_patience: int = 0,
        early_stopping_min_delta: float = 0.0,
    ) -> None:
        self.evaluator = evaluator
        self.eval_dataset = eval_dataset
        self._seen_steps: set[int] = set()
        self.early_stopping_metric = early_stopping_metric
        self.early_stopping_patience = early_stopping_patience
        self.early_stopping_min_delta = early_stopping_min_delta
        self._best_metric: float | None = None
        self._best_step: int | None = None
        self._bad_evals = 0

    def on_evaluate(self, args: Any, state: Any, control: Any, **kwargs: Any) -> Any:
        if not state.is_world_process_zero:
            return control

        step = int(state.global_step)
        if step in self._seen_steps:
            return control
        self._seen_steps.add(step)

        model = kwargs.get("model")
        if model is None:
            return control

        metrics = self.evaluator.evaluate(
            model=model,
            dataset=self.eval_dataset,
            split_name="validation",
            step=step,
            epoch=state.epoch,
        )
        self._update_early_stopping(metrics=metrics, step=step, control=control)
        return control

    def _update_early_stopping(self, *, metrics: dict[str, Any], step: int, control: Any) -> None:
        if self.early_stopping_metric == "none" or self.early_stopping_patience <= 0:
            return

        value = generated_metric_value(metrics, self.early_stopping_metric)
        improved = (
            self._best_metric is None
            or value > self._best_metric + self.early_stopping_min_delta
        )
        if improved:
            self._best_metric = value
            self._best_step = step
            self._bad_evals = 0
            click.echo(
                "[generated-early-stop] "
                f"new best {self.early_stopping_metric}={value:.4f} at step {step}"
            )
            return

        self._bad_evals += 1
        click.echo(
            "[generated-early-stop] "
            f"{self.early_stopping_metric}={value:.4f} did not improve "
            f"best={self._best_metric:.4f} at step {self._best_step}; "
            f"bad_evals={self._bad_evals}/{self.early_stopping_patience}"
        )
        if self._bad_evals >= self.early_stopping_patience:
            control.should_training_stop = True
            click.echo(
                "[generated-early-stop] "
                f"stopping training after {self._bad_evals} generated validation evals "
                f"without improvement on {self.early_stopping_metric}"
            )


def generated_metric_value(metrics: dict[str, Any], metric_name: str) -> float:
    if metric_name == "micro_f1":
        return float(metrics["micro"]["f1"])
    if metric_name == "macro_f1":
        return float(metrics["macro"]["f1"])
    if metric_name in {"exact_match", "hamming_accuracy", "parse_rate"}:
        return float(metrics[metric_name])
    raise ValueError(f"Unsupported generated early-stopping metric: {metric_name}")


class GeneratedMetricsEvaluator:
    """Generate label codes and save per-label F1 metrics, plots, and predictions."""

    def __init__(
        self,
        *,
        processor: Any,
        ffmpeg: str,
        frame_fps: float,
        max_frames: int,
        max_audio_seconds: float,
        image_width: int,
        prompts: PromptBundle,
        use_audio: bool,
        output_dir: Path,
        max_new_tokens: int,
        wandb_enabled: bool,
        cache_store: "ProcessorCache | None" = None,
    ) -> None:
        self.processor = processor
        self.ffmpeg = ffmpeg
        self.frame_fps = frame_fps
        self.max_frames = max_frames
        self.max_audio_seconds = max_audio_seconds
        self.image_width = image_width
        self.prompts = prompts
        self.use_audio = use_audio
        self.output_dir = output_dir
        self.max_new_tokens = max_new_tokens
        self.wandb_enabled = wandb_enabled
        self.cache_store = cache_store

    def evaluate(
        self,
        *,
        model: Any,
        dataset: Any,
        split_name: str,
        step: int,
        epoch: float | None,
    ) -> dict[str, Any]:
        import torch

        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_epoch = "none" if epoch is None else f"{epoch:.4f}".replace(".", "_")
        run_id = f"{split_name}_step_{step:06d}_epoch_{safe_epoch}"
        predictions_path = self.output_dir / f"{run_id}_predictions.jsonl"
        metrics_path = self.output_dir / f"{run_id}_metrics.json"
        figure_path = self.output_dir / f"{run_id}_f1.png"

        click.echo(f"[generated-metrics] {split_name}: {len(dataset)} samples at step {step}")
        was_training = model.training
        model.eval()
        device = infer_model_input_device(model)

        y_true: list[list[int]] = []
        y_pred: list[list[int]] = []
        records = []
        with torch.inference_mode(), predictions_path.open("w") as handle:
            for index, row in enumerate(dataset):
                if index and index % 10 == 0:
                    click.echo(f"[generated-metrics] {split_name}: {index}/{len(dataset)}")

                builder = lambda row=row: build_prompt_inputs(
                    processor=self.processor,
                    ffmpeg=self.ffmpeg,
                    row=row,
                    frame_fps=self.frame_fps,
                    max_frames=self.max_frames,
                    max_audio_seconds=self.max_audio_seconds,
                    image_width=self.image_width,
                    prompts=self.prompts,
                    use_audio=self.use_audio,
                )
                if self.cache_store is None:
                    prompt_inputs = builder()
                else:
                    prompt_inputs = self.cache_store.load_or_build(kind="prompt", row=row, builder=builder)
                model_inputs = move_tensor_dict(prompt_inputs, device=device)
                generated_ids = model.generate(
                    **model_inputs,
                    max_new_tokens=self.max_new_tokens,
                    do_sample=False,
                    pad_token_id=self.processor.tokenizer.eos_token_id,
                )
                prompt_len = int(prompt_inputs["input_ids"].shape[-1])
                generated_text = self.processor.tokenizer.decode(
                    generated_ids[0][prompt_len:],
                    skip_special_tokens=True,
                ).strip()
                parsed = parse_generated_label_code(generated_text)
                truth = [int(value) for value in row["label_vector"]]
                y_true.append(truth)
                y_pred.append(
                    parsed["label_vector"]
                    if parsed["parse_ok"]
                    else invalid_failure_label_vector(truth)
                )

                record = {
                    "split": split_name,
                    "step": step,
                    "epoch": epoch,
                    "index": index,
                    "video_id": row["video_id"],
                    "target_label_code": row["target_code"],
                    "predicted_label_code": parsed["label_code"],
                    "target_label_vector": truth,
                    "predicted_label_vector": parsed["label_vector"],
                    "target_json": row["target_json"],
                    "predicted_json": parsed["report_json"],
                    "raw_prediction": generated_text,
                    "parse_ok": parsed["parse_ok"],
                    "parse_error": parsed["parse_error"],
                }
                records.append(record)
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        if was_training:
            model.train()

        metrics = compute_multilabel_metrics(
            y_true=np.asarray(y_true, dtype=np.int64),
            y_pred=np.asarray(y_pred, dtype=np.int64),
            parse_ok=[bool(record["parse_ok"]) for record in records],
            split_name=split_name,
            step=step,
            epoch=epoch,
        )
        metrics["artifacts"] = {
            "predictions_jsonl": str(predictions_path),
            "metrics_json": str(metrics_path),
            "f1_png": str(figure_path),
        }
        metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")
        save_f1_figure(metrics=metrics, path=figure_path)
        self.log_to_wandb(metrics=metrics, figure_path=figure_path, split_name=split_name, step=step)
        click.echo(
            "[generated-metrics] "
            f"{split_name}: micro_f1={metrics['micro']['f1']:.4f} "
            f"macro_f1={metrics['macro']['f1']:.4f} "
            f"exact_match={metrics['exact_match']:.4f} "
            f"parse_rate={metrics['parse_rate']:.4f}"
        )
        click.echo(f"[generated-metrics] saved: {metrics_path}")
        return metrics

    def log_to_wandb(self, *, metrics: dict[str, Any], figure_path: Path, split_name: str, step: int) -> None:
        if not self.wandb_enabled:
            return

        try:
            import wandb
        except ImportError:
            return

        if wandb.run is None:
            return

        payload: dict[str, Any] = {
            f"generated/{split_name}/micro_f1": metrics["micro"]["f1"],
            f"generated/{split_name}/macro_f1": metrics["macro"]["f1"],
            f"generated/{split_name}/exact_match": metrics["exact_match"],
            f"generated/{split_name}/hamming_accuracy": metrics["hamming_accuracy"],
            f"generated/{split_name}/parse_rate": metrics["parse_rate"],
            f"generated/{split_name}/f1_plot": wandb.Image(str(figure_path)),
        }
        for feature_id, values in metrics["per_label"].items():
            payload[f"generated/{split_name}/f1/{feature_id}"] = values["f1"]
            payload[f"generated/{split_name}/precision/{feature_id}"] = values["precision"]
            payload[f"generated/{split_name}/recall/{feature_id}"] = values["recall"]
        wandb.log(payload, step=step)


class ProcessorCache:
    """Disk cache for CPU processor outputs keyed by preprocessing config and row."""

    def __init__(self, *, cache_dir: Path, config: dict[str, Any], mode: str) -> None:
        if mode not in {"off", "read-write", "require"}:
            raise ValueError(f"Unknown cache mode: {mode}")
        self.cache_dir = Path(cache_dir)
        self.config = config
        self.config_hash = stable_hash(config)[:16]
        self.root = self.cache_dir / self.config_hash
        self.mode = mode

    def write_config(self) -> None:
        if self.mode == "off":
            return
        self.root.mkdir(parents=True, exist_ok=True)
        config_path = self.root / "cache_config.json"
        config_path.write_text(json.dumps(self.config, indent=2, ensure_ascii=False) + "\n")

    def path_for(self, *, kind: str, row: dict) -> Path:
        if kind not in CACHE_KINDS:
            raise ValueError(f"Unknown cache kind: {kind}")
        split = str(row["split"])
        row_idx = int(row["row_idx"])
        video_id = sanitize_cache_name(str(row["video_id"]))
        row_hash = stable_hash(
            {
                "cache_version": CACHE_VERSION,
                "kind": kind,
                "split": split,
                "row_idx": row_idx,
                "video_id": row["video_id"],
                "target_code": row["target_code"] if kind == "supervised" else None,
            }
        )[:12]
        return self.root / split / kind / f"{row_idx:05d}_{video_id}_{row_hash}.pt"

    def load_or_build(self, *, kind: str, row: dict, builder: Any) -> dict[str, Any]:
        if self.mode == "off":
            return builder()

        path = self.path_for(kind=kind, row=row)
        if path.is_file():
            return self.load(path)

        if self.mode == "require":
            raise click.ClickException(
                f"Missing {kind} processor cache for {row['split']}/{row['row_idx']} "
                f"{row['video_id']}: {path}\n"
                "Run `run_train.py build-cache` with the same media and prompt-language parameters first."
            )

        batch = builder()
        self.save(path=path, kind=kind, row=row, batch=batch)
        return batch

    def build_or_refresh(self, *, kind: str, row: dict, overwrite: bool, builder: Any) -> bool:
        path = self.path_for(kind=kind, row=row)
        if path.is_file() and not overwrite:
            return False

        batch = builder()
        self.save(path=path, kind=kind, row=row, batch=batch)
        return True

    def load(self, path: Path) -> dict[str, Any]:
        import torch

        try:
            payload = torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:
            payload = torch.load(path, map_location="cpu")

        if payload.get("cache_version") != CACHE_VERSION:
            raise click.ClickException(f"Unsupported cache version in {path}")
        if payload.get("config_hash") != self.config_hash:
            raise click.ClickException(f"Cache config hash mismatch in {path}")
        batch = payload.get("batch")
        if not isinstance(batch, dict):
            raise click.ClickException(f"Invalid cache payload in {path}")
        return batch

    def save(self, *, path: Path, kind: str, row: dict, batch: dict[str, Any]) -> None:
        import torch

        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cache_version": CACHE_VERSION,
            "config_hash": self.config_hash,
            "kind": kind,
            "split": row["split"],
            "row_idx": int(row["row_idx"]),
            "video_id": row["video_id"],
            "batch": detach_tensor_dict_to_cpu(batch),
        }
        tmp_path = path.parent / f".{path.name}.{os.getpid()}.tmp"
        torch.save(payload, tmp_path)
        tmp_path.replace(path)


def build_cache_config(
    *,
    model_dir: Path,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    prompts: PromptBundle,
    use_audio: bool,
) -> dict[str, Any]:
    return {
        "cache_version": CACHE_VERSION,
        "model_dir": str(Path(model_dir).expanduser().resolve()),
        "frame_fps": float(frame_fps),
        "max_frames": int(max_frames),
        "max_audio_seconds": float(max_audio_seconds),
        "image_width": int(image_width),
        "use_audio": bool(use_audio),
        "target_format": "code9_b01_b09",
        "prompt_lang": prompts.lang,
        "system_prompt_sha256": hashlib.sha256(prompts.system.encode("utf-8")).hexdigest(),
        "user_prompt_sha256": hashlib.sha256(prompts.user.encode("utf-8")).hexdigest(),
    }


def build_cached_kind(
    *,
    kind: str,
    processor: Any,
    ffmpeg: str,
    row: dict,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    prompts: PromptBundle,
    use_audio: bool,
) -> dict[str, Any]:
    if kind == "supervised":
        return build_supervised_inputs(
            processor=processor,
            ffmpeg=ffmpeg,
            row=row,
            frame_fps=frame_fps,
            max_frames=max_frames,
            max_audio_seconds=max_audio_seconds,
            image_width=image_width,
            prompts=prompts,
            use_audio=use_audio,
        )
    if kind == "prompt":
        return build_prompt_inputs(
            processor=processor,
            ffmpeg=ffmpeg,
            row=row,
            frame_fps=frame_fps,
            max_frames=max_frames,
            max_audio_seconds=max_audio_seconds,
            image_width=image_width,
            prompts=prompts,
            use_audio=use_audio,
        )
    raise ValueError(f"Unknown cache kind: {kind}")


def init_cache_worker(
    model_dir: str,
    cache_dir: str,
    cache_config: dict[str, Any],
    ffmpeg: str,
    cache_kinds: tuple[str, ...],
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    prompts: PromptBundle,
    use_audio: bool,
) -> None:
    from transformers import AutoProcessor

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    _CACHE_WORKER_STATE.clear()
    _CACHE_WORKER_STATE.update(
        {
            "processor": AutoProcessor.from_pretrained(model_dir, local_files_only=True),
            "cache_store": ProcessorCache(
                cache_dir=Path(cache_dir),
                config=cache_config,
                mode="read-write",
            ),
            "ffmpeg": ffmpeg,
            "cache_kinds": cache_kinds,
            "frame_fps": frame_fps,
            "max_frames": max_frames,
            "max_audio_seconds": max_audio_seconds,
            "image_width": image_width,
            "prompts": prompts,
            "use_audio": use_audio,
        }
    )


def build_cache_row_worker(row: dict, overwrite: bool) -> dict[str, int]:
    if not _CACHE_WORKER_STATE:
        raise RuntimeError("Cache worker was not initialized")

    return build_cache_row(
        cache_store=_CACHE_WORKER_STATE["cache_store"],
        processor=_CACHE_WORKER_STATE["processor"],
        ffmpeg=_CACHE_WORKER_STATE["ffmpeg"],
        row=row,
        cache_kinds=_CACHE_WORKER_STATE["cache_kinds"],
        overwrite=overwrite,
        frame_fps=_CACHE_WORKER_STATE["frame_fps"],
        max_frames=_CACHE_WORKER_STATE["max_frames"],
        max_audio_seconds=_CACHE_WORKER_STATE["max_audio_seconds"],
        image_width=_CACHE_WORKER_STATE["image_width"],
        prompts=_CACHE_WORKER_STATE["prompts"],
        use_audio=_CACHE_WORKER_STATE["use_audio"],
    )


def build_cache_row(
    *,
    cache_store: ProcessorCache,
    processor: Any,
    ffmpeg: str,
    row: dict,
    cache_kinds: tuple[str, ...],
    overwrite: bool,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    prompts: PromptBundle,
    use_audio: bool,
) -> dict[str, int]:
    written = 0
    existing = 0
    for kind in cache_kinds:
        did_write = cache_store.build_or_refresh(
            kind=kind,
            row=row,
            overwrite=overwrite,
            builder=lambda kind=kind: build_cached_kind(
                kind=kind,
                processor=processor,
                ffmpeg=ffmpeg,
                row=row,
                frame_fps=frame_fps,
                max_frames=max_frames,
                max_audio_seconds=max_audio_seconds,
                image_width=image_width,
                prompts=prompts,
                use_audio=use_audio,
            ),
        )
        if did_write:
            written += 1
        else:
            existing += 1
    return {"written": written, "existing": existing}


def detach_tensor_dict_to_cpu(batch: dict[str, Any]) -> dict[str, Any]:
    import torch

    detached = {}
    for key, value in batch.items():
        if torch.is_tensor(value):
            detached[key] = value.detach().cpu()
        else:
            detached[key] = value
    return detached


def stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sanitize_cache_name(value: str) -> str:
    sanitized = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return sanitized[:90] or "sample"


def configure_runtime(cuda_devices: str) -> None:
    cuda_devices = ",".join(part.strip() for part in cuda_devices.split(",") if part.strip())
    if not cuda_devices:
        raise click.ClickException("--cuda-devices must not be empty")

    os.environ["CUDA_VISIBLE_DEVICES"] = cuda_devices
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def setup_wandb(
    *,
    enabled: bool,
    wandb_lib: Any,
    project: str,
    entity: str | None,
    run_name: str,
) -> None:
    if not enabled:
        os.environ["WANDB_MODE"] = "disabled"
        return

    api_key = os.environ.get("WANDB_API_KEY")
    if not api_key:
        raise click.ClickException("WANDB_API_KEY is missing. Put it in .env or disable with --no-wandb.")

    os.environ["WANDB_PROJECT"] = project
    os.environ["WANDB_RUN_GROUP"] = project
    os.environ.setdefault("WANDB_WATCH", "false")
    os.environ.setdefault("WANDB_LOG_MODEL", "false")
    if entity:
        os.environ["WANDB_ENTITY"] = entity
    wandb_lib.login(key=api_key, relogin=True)
    click.echo(f"wandb enabled: project={project} run={run_name}")


def remix_train_validation_split(
    *,
    train_dataset: Any,
    eval_dataset: Any,
    validation_ratio: float,
    seed: int,
) -> tuple[Any, Any]:
    from collections import defaultdict

    from datasets import concatenate_datasets

    combined = concatenate_datasets([train_dataset, eval_dataset])
    total = len(combined)
    if total < 2:
        raise click.ClickException("Need at least two samples to remix train/validation.")

    target_eval_count = int(round(total * validation_ratio))
    target_eval_count = min(max(1, target_eval_count), total - 1)

    rng = np.random.default_rng(seed)
    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(combined):
        groups[label_vector_key(row)].append(index)

    train_indices: list[int] = []
    eval_indices: list[int] = []
    for indices in groups.values():
        shuffled = list(indices)
        rng.shuffle(shuffled)
        if len(shuffled) == 1:
            train_indices.extend(shuffled)
            continue

        group_eval_count = int(round(len(shuffled) * validation_ratio))
        group_eval_count = min(max(1, group_eval_count), len(shuffled) - 1)
        eval_indices.extend(shuffled[:group_eval_count])
        train_indices.extend(shuffled[group_eval_count:])

    if len(eval_indices) > target_eval_count:
        rng.shuffle(eval_indices)
        train_indices.extend(eval_indices[target_eval_count:])
        eval_indices = eval_indices[:target_eval_count]
    elif len(eval_indices) < target_eval_count:
        rng.shuffle(train_indices)
        move_count = min(target_eval_count - len(eval_indices), len(train_indices) - 1)
        eval_indices.extend(train_indices[:move_count])
        train_indices = train_indices[move_count:]

    rng.shuffle(train_indices)
    rng.shuffle(eval_indices)
    return combined.select(train_indices), combined.select(eval_indices)


def label_vector_key(row: dict) -> str:
    return "".join(str(int(value)) for value in row["label_vector"])


def dataset_origin_counts(dataset: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in dataset:
        split = str(row["split"])
        counts[split] = counts.get(split, 0) + 1
    return dict(sorted(counts.items()))


def enable_gradient_checkpointing(model: Any) -> None:
    try:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    except TypeError:
        model.gradient_checkpointing_enable()
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()


def parse_target_modules(value: str) -> str | list[str]:
    value = value.strip()
    if value == "language":
        return LANGUAGE_LORA_REGEX
    if value == "all-linear":
        return "all-linear"
    modules = [part.strip() for part in value.split(",") if part.strip()]
    if not modules:
        raise click.ClickException("--target-modules must not be empty")
    if len(modules) == 1:
        return modules[0]
    return modules


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


def requested_frame_count(*, duration_sec: float, fps: float, max_frames: int) -> int:
    if duration_sec <= 0:
        return 1
    return max(1, min(max_frames, int(np.ceil(duration_sec * fps))))


def sampled_frame_fps(frame_count: int, duration_sec: float) -> float:
    if duration_sec <= 0:
        return float(frame_count)
    return frame_count / duration_sec


def load_audio_mono_16k(*, ffmpeg: str, audio_path: Path, max_seconds: float) -> np.ndarray:
    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(audio_path),
        "-t",
        f"{max_seconds:.3f}",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "f32le",
        "pipe:1",
    ]
    completed = run_command(command, capture_stdout=True)
    audio = np.frombuffer(completed.stdout, dtype=np.float32).copy()
    if audio.size == 0:
        raise click.ClickException(f"ffmpeg produced no audio for {audio_path}")
    return audio


def processor_audio_kwargs(*, audio: np.ndarray | None) -> dict[str, Any]:
    if audio is None:
        return {}
    return {
        "audio": [audio],
        "audio_kwargs": {"sampling_rate": 16000},
    }


def build_supervised_inputs(
    *,
    processor: Any,
    ffmpeg: str,
    row: dict,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    prompts: PromptBundle,
    use_audio: bool,
) -> dict[str, Any]:
    from transformers.video_utils import VideoMetadata

    assert_label_code(row)
    frames = load_video_frames(
        ffmpeg=ffmpeg,
        video_path=Path(row["video_path"]),
        fps=frame_fps,
        max_frames=max_frames,
        image_width=image_width,
        duration_sec=float(row["duration_sec"]),
    )
    audio = (
        load_audio_mono_16k(
            ffmpeg=ffmpeg,
            audio_path=Path(row["audio_path"]),
            max_seconds=min(float(row["duration_sec"]), max_audio_seconds),
        )
        if use_audio
        else None
    )
    metadata = VideoMetadata(
        total_num_frames=len(frames),
        fps=sampled_frame_fps(len(frames), float(row["duration_sec"])),
        duration=float(row["duration_sec"]),
        frames_indices=list(range(len(frames))),
    )
    prompt_text = build_chat_text(
        processor,
        row,
        prompts=prompts,
        include_answer=False,
        use_audio=use_audio,
    )
    full_text = build_chat_text(
        processor,
        row,
        prompts=prompts,
        include_answer=True,
        use_audio=use_audio,
    )
    prompt_inputs = processor(
        text=[prompt_text],
        videos=[frames],
        return_tensors="pt",
        return_mm_token_type_ids=True,
        videos_kwargs={"video_metadata": [metadata], "do_sample_frames": False},
        **processor_audio_kwargs(audio=audio),
    )
    full_inputs = processor(
        text=[full_text],
        videos=[frames],
        return_tensors="pt",
        return_mm_token_type_ids=True,
        videos_kwargs={"video_metadata": [metadata], "do_sample_frames": False},
        **processor_audio_kwargs(audio=audio),
    )
    full_inputs["labels"] = build_masked_labels(
        full_inputs,
        prompt_len=prompt_inputs["input_ids"].shape[-1],
    )
    return dict(full_inputs)


def build_prompt_inputs(
    *,
    processor: Any,
    ffmpeg: str,
    row: dict,
    frame_fps: float,
    max_frames: int,
    max_audio_seconds: float,
    image_width: int,
    prompts: PromptBundle,
    use_audio: bool,
) -> dict[str, Any]:
    from transformers.video_utils import VideoMetadata

    frames = load_video_frames(
        ffmpeg=ffmpeg,
        video_path=Path(row["video_path"]),
        fps=frame_fps,
        max_frames=max_frames,
        image_width=image_width,
        duration_sec=float(row["duration_sec"]),
    )
    audio = (
        load_audio_mono_16k(
            ffmpeg=ffmpeg,
            audio_path=Path(row["audio_path"]),
            max_seconds=min(float(row["duration_sec"]), max_audio_seconds),
        )
        if use_audio
        else None
    )
    metadata = VideoMetadata(
        total_num_frames=len(frames),
        fps=sampled_frame_fps(len(frames), float(row["duration_sec"])),
        duration=float(row["duration_sec"]),
        frames_indices=list(range(len(frames))),
    )
    prompt_text = build_chat_text(
        processor,
        row,
        prompts=prompts,
        include_answer=False,
        use_audio=use_audio,
    )
    return processor(
        text=[prompt_text],
        videos=[frames],
        return_tensors="pt",
        return_mm_token_type_ids=True,
        videos_kwargs={"video_metadata": [metadata], "do_sample_frames": False},
        **processor_audio_kwargs(audio=audio),
    )


def move_tensor_dict(batch: dict[str, Any], *, device: Any) -> dict[str, Any]:
    import torch

    moved = {}
    for key, value in batch.items():
        if torch.is_tensor(value):
            moved[key] = value.to(device)
        else:
            moved[key] = value
    return moved


def infer_model_input_device(model: Any) -> Any:
    import torch

    for candidate in (model, getattr(model, "base_model", None), getattr(getattr(model, "base_model", None), "model", None)):
        device_map = getattr(candidate, "hf_device_map", None)
        if not device_map:
            continue

        preferred_keys = (
            "",
            "base_model.model.language_model.model.embed_tokens",
            "language_model.model.embed_tokens",
            "model.embed_tokens",
        )
        for key in preferred_keys:
            if key in device_map:
                return normalize_torch_device(device_map[key])

        for value in device_map.values():
            device = normalize_torch_device(value)
            if device.type == "cuda":
                return device

    try:
        return next(model.parameters()).device
    except StopIteration:
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def normalize_torch_device(value: Any) -> Any:
    import torch

    if isinstance(value, torch.device):
        return value
    if isinstance(value, int):
        return torch.device(f"cuda:{value}")
    if isinstance(value, str):
        if value == "disk":
            return torch.device("cpu")
        return torch.device(value)
    return torch.device("cpu")


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


def parse_generated_label_vector(text: str) -> dict[str, Any]:
    """Backward-compatible wrapper for older eval callers."""
    return parse_generated_label_code(text)


def invalid_failure_label_vector(truth: list[int]) -> list[int]:
    """Return a metric-only vector that makes every label wrong for invalid output."""
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


def build_chat_text(
    processor,
    row: dict,
    *,
    prompts: PromptBundle,
    include_answer: bool,
    use_audio: bool,
) -> str:
    user_content = [{"type": "video"}]
    if use_audio:
        user_content.append({"type": "audio"})
    user_content.append({"type": "text", "text": prompts.user})
    messages = [
        {"role": "system", "content": prompts.system},
        {
            "role": "user",
            "content": user_content,
        },
    ]
    if include_answer:
        messages.append({"role": "assistant", "content": row["target_code"]})
        return processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)

    return processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def build_masked_labels(inputs: dict[str, torch.Tensor], *, prompt_len: int) -> torch.Tensor:
    labels = inputs["input_ids"].clone()
    labels[:, :prompt_len] = -100
    if "attention_mask" in inputs:
        labels[inputs["attention_mask"] == 0] = -100
    if (labels != -100).sum().item() == 0:
        raise click.ClickException("No supervised label tokens remain after masking.")
    return labels


def print_sample_summary(row: dict, split: str, row_index: int) -> None:
    click.echo("\n== Dataset sample ==")
    click.echo(f"split/index: {split}/{row_index}")
    click.echo(f"video_id: {row['video_id']}")
    click.echo(f"source_id: {row['source_id']}")
    click.echo(f"clip_seconds: {row['start_sec']} -> {row['end_sec']} ({row['duration_sec']}s)")
    click.echo(f"video_path: {row['video_path']}")
    click.echo(f"audio_path: {row['audio_path']}")
    click.echo(f"positive_feature_ids: {row['positive_feature_ids']}")
    click.echo(f"positive_label_names: {row['positive_label_names']}")
    click.echo(f"label_vector: {row['label_vector']}")


def print_tensor_summary(prefix: str, batch: dict[str, torch.Tensor]) -> None:
    for key, value in batch.items():
        if hasattr(value, "shape"):
            click.echo(f"{prefix}.{key}: shape={tuple(value.shape)} dtype={value.dtype}")
        else:
            click.echo(f"{prefix}.{key}: {type(value).__name__}")


def indent_preview(text: str, max_chars: int = 900) -> str:
    preview = text[:max_chars]
    if len(text) > max_chars:
        preview += "...[truncated]"
    return "\n".join(f"  {line}" for line in preview.splitlines())


def assert_label_payload(target_json: str) -> None:
    payload = json.loads(target_json)
    feature_keys = tuple(payload["features"].keys())
    if feature_keys != FEATURE_IDS:
        raise click.ClickException(f"Unexpected target_json feature order: {feature_keys}")
    if not all(isinstance(value, bool) for value in payload["features"].values()):
        raise click.ClickException("target_json features must all be booleans")


def assert_label_code(row: dict) -> None:
    code = str(row["target_code"])
    if LABEL_CODE_RE.fullmatch(code) is None:
        raise click.ClickException(f"Invalid target_code: {code!r}")

    truth = [int(value) for value in row["label_vector"]]
    expected = [int(char) for char in code]
    expected.append(1 if sum(expected) == 0 else 0)
    if truth != expected:
        raise click.ClickException(
            f"target_code does not match label_vector: code={code} expected={expected} truth={truth}"
        )


if __name__ == "__main__":
    cli()
