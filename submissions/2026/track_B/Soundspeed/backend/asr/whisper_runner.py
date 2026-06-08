"""WhisperRunner：一段 16kHz int16 PCM → 文字（whisper.cpp via pywhispercpp）。

模型懒加载；可注入 transcriber（测试用假实例，生产用 pywhispercpp Model）。
段级用法：上游 VAD 收尾一个 SpeechSegment → 调一次 transcribe_pcm → 出一条文字。
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from backend.asr.config import ASRConfig

logger = logging.getLogger(__name__)

_INT16_FULL_SCALE = 32768.0


class WhisperRunner:
    """封装 pywhispercpp，对外只暴露 transcribe_pcm(int16 16k) -> str。"""

    def __init__(self, config: ASRConfig, *, model: Any = None) -> None:
        self._config = config
        self._model = model  # None 时首次 transcribe 懒加载真实模型
        self._language = config.language  # 可运行时切换（set_language）

    @property
    def language(self) -> str:
        return self._language

    @property
    def model_size(self) -> str:
        return self._config.model_size

    def set_language(self, language: str) -> None:
        """运行时切换转录语言（zh/en/auto/…）。下一段转录生效，无需重载模型。"""
        self._language = language

    def _ensure_model(self) -> Any:
        if self._model is None:
            from pywhispercpp.model import Model  # 延迟导入，避免无 pywhispercpp 环境 import 失败

            logger.info(
                "加载 whisper.cpp 模型 size=%s models_dir=%s",
                self._config.model_size,
                self._config.models_dir or "(pywhispercpp 默认)",
            )
            self._model = Model(
                self._config.model_size,
                models_dir=self._config.models_dir,
                n_threads=self._config.n_threads,
                print_realtime=False,
                print_progress=False,
            )
        return self._model

    def warmup(self) -> None:
        """启动时预加载模型（首次含下载，缓存后秒级）。"""
        self._ensure_model()

    def transcribe_pcm(self, pcm_int16: np.ndarray) -> str:
        """16kHz 单声道 int16 → 文字。whisper.cpp 吃 float32 [-1,1]。"""
        model = self._ensure_model()
        audio_f32 = np.ascontiguousarray(pcm_int16, dtype=np.int16).astype(np.float32) / _INT16_FULL_SCALE
        segments = model.transcribe(audio_f32, language=self._language)
        return "".join(seg.text for seg in segments).strip()
