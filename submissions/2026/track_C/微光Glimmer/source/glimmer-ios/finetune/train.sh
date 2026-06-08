#!/usr/bin/env bash
# LoRA 微调 Gemma 4 多模态（自闭症行为筛查）
# 依赖：mlx-vlm（见仓库根 README）。在装了 mlx-vlm 的 venv 里运行。
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
MODEL="${MODEL:-mlx-community/gemma-4-e4b-it-4bit}"   # 端侧基座；要更高质量改 gemma-4-e4b-it-bf16
DATA="${DATA:-$REPO/data/ft}"                          # 含 train.jsonl 的目录
OUT="${OUT:-$REPO/finetune/adapters}"

python -m mlx_vlm.lora \
  --model-path "$MODEL" \
  --dataset "$DATA" \
  --split train \
  --custom-prompt-format '[{"role":"user","content":[{"type":"image","image":"{image}"},{"type":"text","text":"{question}"}]},{"role":"assistant","content":[{"type":"text","text":"{answer}"}]}]' \
  --image-resize-shape 384 384 \
  --iters "${ITERS:-30}" --batch-size "${BATCH:-1}" \
  --lora-rank "${RANK:-8}" --learning-rate "${LR:-1e-4}" \
  --steps-per-report 5 --steps-per-eval 1000 --steps-per-save "${ITERS:-30}" \
  --max-seq-length 1024 \
  --output-path "$OUT"
  # 想同时微调视觉塔：加 --train-vision（更慢、更吃内存）

echo "✅ adapter -> $OUT/adapters.safetensors"
