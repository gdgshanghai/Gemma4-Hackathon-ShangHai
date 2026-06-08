# Baseline Results

Model:

```text
weights/best.pt
```

Command pattern:

```powershell
python detection.py --source <video> --weights weights\best.pt --name <run_name> --max-frames 0
```

## Smoke Tests

| Clip | Label | Frames | Fall-detected frames | Output |
| --- | --- | ---: | ---: | --- |
| `inputs/urfall_fall_01_cam0.mp4` | fall | 160 | 75 | `outputs/detection/urfall_fall_01_full` |
| `inputs/urfall_adl_01_cam0.mp4` | no_fall | 150 | 38 | `outputs/detection/urfall_adl_01_full` |

## 10-Clip Validation Subset Result

Command:

```powershell
python evaluate_video_validation.py --manifest video_validation\urfall_manifest.csv --weights weights\best.pt --output-dir outputs\video_validation --confirm-frames 5 --min-fall-ratio 0.35
```

Run:

```text
outputs/video_validation/eval_20260601_095838
```

Summary:

| Items | Accuracy | TP | TN | FP | FN |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.90 | 5 | 4 | 1 | 0 |

Remaining failure:

- `urfall_adl_03` is still a false positive with `fall_frame_ratio=0.372222`.

## Interpretation

- The video pipeline can read real dataset videos and generate JSON plus annotated MP4 outputs.
- The fall clip is useful: fall detections appear in the later part of the clip, so short first-frame smoke tests are not enough.
- The ADL/no-fall clip currently produces false positives. This is useful validation pressure for the model and temporal confirmation logic.

Next validation pass should review `urfall_adl_03` visually and tune the model or temporal threshold before using this as a product-level metric.

## 100-Video Full Validation Result

Command:

```powershell
python evaluate_video_validation.py --manifest video_validation\urfall_full_manifest.csv --weights weights\best.pt --output-dir outputs\video_validation_full --confirm-frames 5 --min-fall-ratio 0.35
```

Run:

```text
outputs/video_validation_full/eval_20260601_102834
```

Summary:

| Items | Accuracy | TP | TN | FP | FN |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 0.86 | 53 | 33 | 7 | 7 |

Interpretation:

- The current YOLO model is still a frame detector, not a video-sequence model.
- Temporal confirmation improves stability, but the full validation set still shows both false positives and false negatives.
- Next model improvement should use this video set to extract hard frames for labeling or add a separate temporal/action recognition layer.

## Fine-Tuned Model Result

Dataset build:

```powershell
python build_urfall_yolo_dataset.py --manifest video_validation\urfall_full_manifest.csv --weights weights\best.pt --frame-stride 15 --pseudo-conf 0.55
```

Generated data:

```text
written images: 885
fall pseudo-labeled images: 278
no-fall empty-label images: 607
fall frames needing review: 152
```

Training:

```powershell
conda run -n yolov8 python train_urfall_finetune.py --data dataset_urfall_frames\data.yaml --weights weights\best.pt --epochs 20 --imgsz 640 --batch 8 --device 0 --name train_urfall_gpu_20e --copy-best
```

Output:

```text
weights/best_urfall_finetuned.pt
```

Full video validation with fine-tuned weights:

```powershell
conda run -n yolov8 python evaluate_video_validation.py --manifest video_validation\urfall_full_manifest.csv --weights weights\best_urfall_finetuned.pt --output-dir outputs\video_validation_finetuned --confirm-frames 5 --min-fall-ratio 0.35
```

Summary:

| Items | Accuracy | TP | TN | FP | FN |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 1.00 | 60 | 40 | 0 | 0 |

Caveat:

- This is not an independent generalization score because the fine-tuning frames came from the same UR Fall videos used for validation.
- It is still useful for proving the training pipeline and reducing errors on the current video module test set.

## Independent Holdout Fine-Tune Result

Split:

```powershell
python split_urfall_manifest.py --manifest video_validation\urfall_full_manifest.csv --train-manifest video_validation\urfall_train_manifest.csv --holdout-manifest video_validation\urfall_holdout_manifest.csv
```

Dataset build:

```powershell
python build_urfall_yolo_dataset.py --manifest video_validation\urfall_train_manifest.csv --output-dir dataset_urfall_train_frames --weights weights\best.pt --frame-stride 15 --pseudo-conf 0.55 --force
```

Generated training data:

```text
train videos: 80
holdout videos: 20
written images: 724
fall pseudo-labeled images: 231
no-fall empty-label images: 493
fall frames needing review: 122
```

Training:

```powershell
$env:KMP_DUPLICATE_LIB_OK='TRUE'
conda run -n yolov8 python train_urfall_finetune.py --data dataset_urfall_train_frames\data.yaml --weights weights\best.pt --epochs 50 --imgsz 640 --batch 8 --device 0 --name train_urfall_holdout_gpu_50e --copy-best
```

Output:

```text
outputs/runs/train_urfall_holdout_gpu_50e/weights/best.pt
weights/best_urfall_finetuned.pt
```

Ultralytics validation metrics from the frame dataset:

| Precision | Recall | mAP50 | mAP50-95 |
| ---: | ---: | ---: | ---: |
| 0.983 | 1.000 | 0.995 | 0.878 |

Do not over-read this frame metric because the generated YOLO validation split is very small.

Holdout video validation with the 50-epoch fine-tuned weights:

```powershell
conda run -n yolov8 python evaluate_video_validation.py --manifest video_validation\urfall_holdout_manifest.csv --weights weights\best_urfall_finetuned.pt --output-dir outputs\video_validation_holdout_50e --confirm-frames 5 --min-fall-ratio 0.35
```

Run:

```text
outputs/video_validation_holdout_50e/eval_20260601_133051
```

Summary:

| Items | Accuracy | TP | TN | FP | FN |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | 1.00 | 12 | 8 | 0 | 0 |

Original model on the same holdout:

```powershell
conda run -n yolov8 python evaluate_video_validation.py --manifest video_validation\urfall_holdout_manifest.csv --weights weights\best.pt --output-dir outputs\video_validation_holdout_original --confirm-frames 5 --min-fall-ratio 0.35
```

Run:

```text
outputs/video_validation_holdout_original/eval_20260601_133132
```

Summary:

| Weights | Items | Accuracy | TP | TN | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `weights/best.pt` | 20 | 0.95 | 11 | 8 | 0 | 1 |
| `weights/best_urfall_finetuned.pt` | 20 | 1.00 | 12 | 8 | 0 | 0 |

Interpretation:

- The holdout videos were not used for training-frame extraction, so this is more meaningful than the 100-video backtest.
- Training labels are still pseudo-labels generated by the original model, not hand-reviewed annotations.
- The next quality step is to review the `needs_review` fall frames and manually correct hard fall/no-fall cases before treating the score as product-level evidence.
