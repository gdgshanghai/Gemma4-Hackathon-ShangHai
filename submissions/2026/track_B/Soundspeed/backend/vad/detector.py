"""VAD 探测器抽象 + silero-vad onnx 封装（spec v0.1 §4 §7）。

切段状态机（segmenter.py）只依赖 VadDetector 协议；真实模型封装在此，
import 全部延迟，使无 silero / onnx 环境下本模块仍可导入（测试用假探测器）。

运行环境 Python 3.12，silero-vad + onnxruntime wheel 齐全（已在 backend/requirements.txt）。
EnergyVad 作为零依赖 fallback 保留（用于无模型环境 / 首轮端到端跑通）。
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class VadDetector(Protocol):
    """逐帧语音概率探测器。帧长由 VadConfig.frame_samples 决定（silero 须 512）。"""

    def speech_prob(self, frame: np.ndarray) -> float:
        """输入一个 frame_samples 长的 16kHz int16 帧，返回语音概率 [0,1]。"""
        ...

    def reset(self) -> None:
        """重置内部状态（一段流开始/结束时调用）。"""
        ...


class EnergyVad:
    """零依赖能量门限 VAD（fallback）。帧 RMS 超阈值即判语音。

    粗糙、对底噪敏感，但无需 torch/silero，适合首轮端到端跑通。
    质量要求高时换 SileroVad（需 torch venv）。
    """

    def __init__(self, rms_threshold: float = 500.0) -> None:
        self._threshold = rms_threshold

    def speech_prob(self, frame: np.ndarray) -> float:
        rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
        return 1.0 if rms > self._threshold else 0.0

    def reset(self) -> None:
        pass


class SileroVad:
    """silero-vad onnx 封装。帧长须为 512（@16k，silero v5 硬要求）。

    薄封装，留 smoke / [手动测试]；状态机逻辑不依赖它。
    """

    def __init__(self) -> None:
        from silero_vad import load_silero_vad  # 延迟导入

        self._model = load_silero_vad(onnx=True)
        self._sr = 16000

    def speech_prob(self, frame: np.ndarray) -> float:
        import torch

        # int16 → float32 [-1, 1]
        f = frame.astype(np.float32) / 32768.0
        with torch.no_grad():
            prob = self._model(torch.from_numpy(f), self._sr)
        return float(prob.item())

    def reset(self) -> None:
        reset_states = getattr(self._model, "reset_states", None)
        if callable(reset_states):
            reset_states()
