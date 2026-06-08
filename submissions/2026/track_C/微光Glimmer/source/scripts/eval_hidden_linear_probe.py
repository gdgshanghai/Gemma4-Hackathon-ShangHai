#!/usr/bin/env python3
"""Train 9 binary linear probes on Gemma hidden activations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
from transformers import AutoProcessor, Gemma4ForConditionalGeneration

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from asd_ds_dataset import FEATURE_IDS, load_asd_ds
from run_train import (
    ProcessorCache,
    build_cache_config,
    build_prompt_inputs,
    compute_multilabel_metrics,
    infer_model_input_device,
    load_prompt_bundle,
    move_tensor_dict,
)


DEFAULT_MODEL_DIR = Path("outputs/gemma4-asd-lora-r32-code9-zh-examples-noaudio-v1-merged")
DEFAULT_PROCESSOR_DIR = Path("/home/huzi/Downloads/gemma-4-E4B-it")
DEFAULT_DATA_ROOT = Path("data/raw/ASD-DS")
DEFAULT_CACHE_DIR = Path("outputs/asd_ds_processor_cache_code9_examples_noaudio")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--processor-dir", type=Path, default=DEFAULT_PROCESSOR_DIR)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--cache-mode", choices=("off", "read-write", "require"), default="require")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/hidden_linear_probe/r32_3epoch_noaudio_zh"))
    parser.add_argument("--prompt-lang", default="zh")
    parser.add_argument("--frame-fps", type=float, default=1.0)
    parser.add_argument("--max-frames", type=int, default=16)
    parser.add_argument("--max-audio-seconds", type=float, default=30.0)
    parser.add_argument("--image-width", type=int, default=512)
    parser.add_argument("--ffmpeg", default=os.environ.get("FFMPEG", "/home/linuxbrew/.linuxbrew/bin/ffmpeg"))
    parser.add_argument("--audio", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--force-features", action="store_true")
    parser.add_argument("--probe-epochs", type=int, default=1500)
    parser.add_argument("--probe-lr", type=float, default=1e-2)
    parser.add_argument("--probe-weight-decay", type=float, default=1e-3)
    parser.add_argument("--max-pos-weight", type=float, default=20.0)
    parser.add_argument("--threshold-grid-size", type=int, default=101)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    prompts = load_prompt_bundle(args.prompt_lang)
    processor = AutoProcessor.from_pretrained(args.processor_dir, local_files_only=True)
    cache_store = None
    if args.cache_mode != "off":
        cache_store = ProcessorCache(
            cache_dir=args.cache_dir,
            config=build_cache_config(
                model_dir=args.processor_dir,
                frame_fps=args.frame_fps,
                max_frames=args.max_frames,
                max_audio_seconds=args.max_audio_seconds,
                image_width=args.image_width,
                prompts=prompts,
                use_audio=args.audio,
            ),
            mode=args.cache_mode,
        )

    print("== Hidden linear probe setup ==")
    print(f"model_dir: {args.model_dir}")
    print(f"processor_dir: {args.processor_dir}")
    print(f"data_root: {args.data_root}")
    print(f"cache_dir: {args.cache_dir}")
    print(f"cache_mode: {args.cache_mode}")
    print(f"cache_root: {cache_store.root if cache_store else None}")
    print(f"prompt_lang: {args.prompt_lang}")
    print(f"use_audio: {args.audio}")
    print(f"output_dir: {args.output_dir}")

    dataset = load_asd_ds(args.data_root, splits=("train", "validation"))
    feature_path = args.output_dir / "hidden_features.pt"
    if feature_path.is_file() and not args.force_features:
        print(f"Loading cached hidden features: {feature_path}")
        feature_payload = torch.load(feature_path, map_location="cpu", weights_only=False)
    else:
        feature_payload = extract_features(args=args, dataset=dataset, processor=processor, prompts=prompts, cache_store=cache_store)
        torch.save(feature_payload, feature_path)
        print(f"Saved hidden features: {feature_path}")

    metrics_payload = train_and_evaluate(args=args, feature_payload=feature_payload)
    metrics_path = args.output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics_payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Saved metrics: {metrics_path}")
    print_summary(metrics_payload)


def extract_features(
    *,
    args: argparse.Namespace,
    dataset: Any,
    processor: Any,
    prompts: Any,
    cache_store: ProcessorCache | None,
) -> dict[str, Any]:
    print("Loading HF model...")
    model = Gemma4ForConditionalGeneration.from_pretrained(
        args.model_dir,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        local_files_only=True,
    )
    model.eval()
    input_device = infer_model_input_device(model)

    payload: dict[str, Any] = {
        "config": {
            "model_dir": str(args.model_dir),
            "processor_dir": str(args.processor_dir),
            "data_root": str(args.data_root),
            "prompt_lang": args.prompt_lang,
            "frame_fps": args.frame_fps,
            "max_frames": args.max_frames,
            "max_audio_seconds": args.max_audio_seconds,
            "image_width": args.image_width,
            "use_audio": args.audio,
        },
        "splits": {},
    }

    with torch.inference_mode():
        for split_name in ("train", "validation"):
            split = dataset[split_name]
            features = []
            y10 = []
            rows = []
            print(f"Extracting {split_name}: {len(split)} samples")
            for index, row in enumerate(split):
                if index and index % 25 == 0:
                    print(f"[extract] {split_name}: {index}/{len(split)}")

                builder = lambda row=row: build_prompt_inputs(
                    processor=processor,
                    ffmpeg=args.ffmpeg,
                    row=row,
                    frame_fps=args.frame_fps,
                    max_frames=args.max_frames,
                    max_audio_seconds=args.max_audio_seconds,
                    image_width=args.image_width,
                    prompts=prompts,
                    use_audio=args.audio,
                )
                prompt_inputs = (
                    builder()
                    if cache_store is None
                    else cache_store.load_or_build(kind="prompt", row=row, builder=builder)
                )
                model_inputs = move_tensor_dict(prompt_inputs, device=input_device)
                outputs = model(
                    **model_inputs,
                    output_hidden_states=True,
                    return_dict=True,
                    logits_to_keep=1,
                )
                hidden = outputs.hidden_states[-1]
                attention_mask = model_inputs["attention_mask"]
                last_idx = int(attention_mask[0].sum().item()) - 1
                features.append(hidden[0, last_idx].detach().float().cpu())
                y10.append([int(value) for value in row["label_vector"]])
                rows.append(
                    {
                        "split": row["split"],
                        "row_idx": int(row["row_idx"]),
                        "video_id": row["video_id"],
                        "target_code": row["target_code"],
                        "label_vector": [int(value) for value in row["label_vector"]],
                    }
                )

            payload["splits"][split_name] = {
                "x": torch.stack(features, dim=0),
                "y10": torch.tensor(y10, dtype=torch.float32),
                "rows": rows,
            }
            print(f"[extract] {split_name}: x={tuple(payload['splits'][split_name]['x'].shape)}")

    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return payload


def train_and_evaluate(*, args: argparse.Namespace, feature_payload: dict[str, Any]) -> dict[str, Any]:
    x_train = feature_payload["splits"]["train"]["x"].float()
    y_train10 = feature_payload["splits"]["train"]["y10"].float()
    x_val = feature_payload["splits"]["validation"]["x"].float()
    y_val10 = feature_payload["splits"]["validation"]["y10"].float()

    y_train9 = y_train10[:, :9]
    y_val9 = y_val10[:, :9]

    mean = x_train.mean(dim=0, keepdim=True)
    std = x_train.std(dim=0, keepdim=True).clamp_min(1e-6)
    x_train = (x_train - mean) / std
    x_val = (x_val - mean) / std

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    x_train = x_train.to(device)
    y_train9 = y_train9.to(device)
    x_val = x_val.to(device)

    model = torch.nn.Linear(x_train.shape[1], 9).to(device)
    pos = y_train9.sum(dim=0)
    neg = y_train9.shape[0] - pos
    pos_weight = torch.where(pos > 0, neg / pos.clamp_min(1.0), torch.ones_like(pos))
    pos_weight = pos_weight.clamp(max=args.max_pos_weight)
    criterion = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.probe_lr, weight_decay=args.probe_weight_decay)

    print("Training linear probes...")
    for epoch in range(1, args.probe_epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        logits = model(x_train)
        loss = criterion(logits, y_train9)
        loss.backward()
        optimizer.step()
        if epoch == 1 or epoch % 250 == 0 or epoch == args.probe_epochs:
            print(f"[probe] epoch={epoch} loss={loss.item():.6f}")

    model.eval()
    with torch.inference_mode():
        train_probs = torch.sigmoid(model(x_train)).cpu().numpy()
        val_probs = torch.sigmoid(model(x_val)).cpu().numpy()

    y_train9_np = y_train10[:, :9].numpy().astype(np.int64)
    y_val10_np = y_val10.numpy().astype(np.int64)
    y_val9_np = y_val10_np[:, :9]

    fixed_thresholds = np.full(9, 0.5, dtype=np.float32)
    tuned_thresholds = tune_thresholds(
        probs=train_probs,
        truth=y_train9_np,
        grid_size=args.threshold_grid_size,
    )

    fixed_pred9 = (val_probs >= fixed_thresholds[None, :]).astype(np.int64)
    tuned_pred9 = (val_probs >= tuned_thresholds[None, :]).astype(np.int64)

    fixed_pred10 = append_background(fixed_pred9)
    tuned_pred10 = append_background(tuned_pred9)

    fixed_metrics = compute_multilabel_metrics(
        y_true=y_val10_np,
        y_pred=fixed_pred10,
        parse_ok=[True] * y_val10_np.shape[0],
        split_name="validation_hidden_probe_threshold_0_5",
        step=0,
        epoch=None,
    )
    tuned_metrics = compute_multilabel_metrics(
        y_true=y_val10_np,
        y_pred=tuned_pred10,
        parse_ok=[True] * y_val10_np.shape[0],
        split_name="validation_hidden_probe_train_tuned_threshold",
        step=0,
        epoch=None,
    )

    rows = feature_payload["splits"]["validation"]["rows"]
    predictions_path = args.output_dir / "validation_predictions.jsonl"
    with predictions_path.open("w") as handle:
        for row, truth, probs, fixed9, tuned9 in zip(rows, y_val10_np, val_probs, fixed_pred9, tuned_pred9, strict=True):
            record = {
                "row_idx": row["row_idx"],
                "video_id": row["video_id"],
                "target_code": row["target_code"],
                "target_label_vector": truth.tolist(),
                "probabilities_b01_b09": [float(value) for value in probs],
                "predicted_code_threshold_0_5": "".join(str(int(value)) for value in fixed9),
                "predicted_label_vector_threshold_0_5": append_background(fixed9[None, :])[0].tolist(),
                "predicted_code_train_tuned": "".join(str(int(value)) for value in tuned9),
                "predicted_label_vector_train_tuned": append_background(tuned9[None, :])[0].tolist(),
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "config": feature_payload["config"],
        "probe": {
            "epochs": args.probe_epochs,
            "lr": args.probe_lr,
            "weight_decay": args.probe_weight_decay,
            "pos_weight": [float(value) for value in pos_weight.detach().cpu().tolist()],
            "thresholds_fixed": [float(value) for value in fixed_thresholds.tolist()],
            "thresholds_train_tuned": [float(value) for value in tuned_thresholds.tolist()],
        },
        "features": {
            "train_shape": list(feature_payload["splits"]["train"]["x"].shape),
            "validation_shape": list(feature_payload["splits"]["validation"]["x"].shape),
        },
        "validation_threshold_0_5": fixed_metrics,
        "validation_train_tuned_threshold": tuned_metrics,
        "predictions_path": str(predictions_path),
    }


def tune_thresholds(*, probs: np.ndarray, truth: np.ndarray, grid_size: int) -> np.ndarray:
    grid = np.linspace(0.0, 1.0, grid_size, dtype=np.float32)
    thresholds = np.full(probs.shape[1], 0.5, dtype=np.float32)
    for label_idx in range(probs.shape[1]):
        best_f1 = -1.0
        best_threshold = 0.5
        y = truth[:, label_idx]
        for threshold in grid:
            pred = (probs[:, label_idx] >= threshold).astype(np.int64)
            tp = int(((pred == 1) & (y == 1)).sum())
            fp = int(((pred == 1) & (y == 0)).sum())
            fn = int(((pred == 0) & (y == 1)).sum())
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = float(threshold)
        thresholds[label_idx] = best_threshold
    return thresholds


def append_background(pred9: np.ndarray) -> np.ndarray:
    background = (pred9.sum(axis=1, keepdims=True) == 0).astype(np.int64)
    return np.concatenate([pred9.astype(np.int64), background], axis=1)


def print_summary(metrics_payload: dict[str, Any]) -> None:
    print("== Validation summary ==")
    for key in ("validation_threshold_0_5", "validation_train_tuned_threshold"):
        metrics = metrics_payload[key]
        print(
            f"{key}: "
            f"micro_f1={metrics['micro']['f1']:.4f} "
            f"macro_f1={metrics['macro']['f1']:.4f} "
            f"exact_match={metrics['exact_match']:.4f} "
            f"hamming={metrics['hamming_accuracy']:.4f}"
        )
    tuned = metrics_payload["validation_train_tuned_threshold"]
    print("per-label F1, train-tuned threshold:")
    for feature_id in FEATURE_IDS:
        values = tuned["per_label"][feature_id]
        print(
            f"  {feature_id}: f1={values['f1']:.4f} "
            f"p={values['precision']:.4f} r={values['recall']:.4f} support={values['support']}"
        )


if __name__ == "__main__":
    main()
