"""ASR 配置（Phase 1：实时 whisper.cpp 转录）。"""
from __future__ import annotations

from dataclasses import dataclass

# 默认 ASR 模型：large-v3-turbo 的 q8_0 量化（~834MB）。turbo 是 large-v3 的蒸馏版，
# 解码层大幅精简（4 层 vs 32），GPU 上速度接近 medium 而精度更高。单一真相源——
# dataclass 默认与 entrypoint 的 env 兜底都引用它，避免「改一处漏一处」的默认值漂移。
# 切回量化 medium：SOUNDSPEED_ASR_MODEL=medium-q8_0；fp16 基线：medium。
DEFAULT_ASR_MODEL = "large-v3-turbo-q8_0"


@dataclass(frozen=True)
class ASRConfig:
    """whisper.cpp（pywhispercpp）运行参数。

    model_size: ggml 模型大小。默认 "large-v3-turbo-q8_0"（large-v3 蒸馏版量化，精度高
      且 GPU 上接近实时）；可切 "medium-q8_0" / "medium"（fp16 基线）/ "small"。
    language: 转录语言，中文固定 "zh"。
    n_threads: whisper.cpp CPU 线程数（GPU 推理时影响较小）。
    models_dir: 模型文件存放目录；None 时用 pywhispercpp 默认缓存路径。
    """

    model_size: str = DEFAULT_ASR_MODEL
    language: str = "zh"
    n_threads: int = 4
    models_dir: str | None = None
