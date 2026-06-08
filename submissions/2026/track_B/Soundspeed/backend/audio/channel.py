"""每声道处理单元：流式重采样到 16kHz，转 int16。"""
from __future__ import annotations

import numpy as np
import soxr

from backend.audio.constants import OUTPUT_SAMPLE_RATE


class ChannelProcessor:
    """有状态的单声道处理器，每声道一个实例。

    持有一个 soxr 流式重采样器 —— 必须每声道独立，因为重采样器在块
    之间携带滤波状态。输入恒为 float32 单声道（归一化到 [-1, 1]），
    输出 16kHz int16。
    """

    def __init__(self, in_rate: int) -> None:
        self._resampler = soxr.ResampleStream(
            in_rate, OUTPUT_SAMPLE_RATE, 1, dtype="float32"
        )

    @staticmethod
    def _to_int16(resampled: np.ndarray) -> np.ndarray:
        scaled = np.round(resampled * 32767.0)
        return np.clip(scaled, -32768.0, 32767.0).astype(np.int16)

    def process(self, mono_block: np.ndarray) -> np.ndarray:
        """重采样一块 float32 单声道到 16kHz，返回 int16 一维数组。"""
        resampled = self._resampler.resample_chunk(
            np.ascontiguousarray(mono_block, dtype=np.float32)
        )
        return self._to_int16(resampled)

    def flush(self) -> np.ndarray:
        """排出重采样器尾部缓冲的滤波延迟样本，返回 int16。流结束时调用一次。"""
        resampled = self._resampler.resample_chunk(
            np.zeros(0, dtype=np.float32), last=True
        )
        return self._to_int16(resampled)
