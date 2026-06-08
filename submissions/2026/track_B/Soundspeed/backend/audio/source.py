"""Audio Input Layer：源抽象与输出数据结构。"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from backend.audio.channel import ChannelProcessor
from backend.audio.constants import OUTPUT_SAMPLE_RATE

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioConfig:
    """源无关的行为配置，所有 AudioSource 子类共用一份。"""

    chunk_ms: int = 200
    max_channels: int = 2


@dataclass(frozen=True)
class AudioChunk:
    """一个时间切片，横跨所有已处理声道。

    channels[i] 是第 i 路独立的单声道 16kHz int16 数组。各声道不交织、
    不混音 —— 它们是分开的信号，打包在一起只为共享 seq / start_frame
    供下游做时间对齐。
    """

    seq: int
    channels: list[np.ndarray]
    n_frames: int
    start_frame: int
    sample_rate: int = OUTPUT_SAMPLE_RATE


class AudioSource(ABC):
    """拉取式音频源：上下文管理器 + AudioChunk 迭代器。

    子类只实现三个钩子：_open / _read_raw_block / _close。通用机制
    （声道截断、顺序逐声道处理、组装 chunk、seq/start_frame 记账）在
    本基类，对每个源完全一致。
    """

    def __init__(self, config: AudioConfig) -> None:
        self._config = config
        self._seq = 0
        self._start_frame = 0
        self._n_channels = 0
        self._processors: list[ChannelProcessor] = []
        self._flushed = False

    # ---- 子类钩子 ----
    @abstractmethod
    def _open(self) -> tuple[int, int]:
        """打开源。返回 (原生采样率, 源声道总数)。"""

    @abstractmethod
    def _read_raw_block(self) -> np.ndarray | None:
        """读一块原始音频，二维 float32 数组 (帧, 源声道数)。
        源耗尽时返回 None。"""

    @abstractmethod
    def _close(self) -> None:
        """释放底层设备流 / 文件句柄。"""

    # ---- 通用机制 ----
    def __enter__(self) -> "AudioSource":
        native_rate, source_channels = self._open()
        try:
            self._n_channels = min(source_channels, self._config.max_channels)
            if source_channels > self._n_channels:
                logger.info(
                    "输入 %d 声道，处理前 %d 路，丢弃 %d 路",
                    source_channels, self._n_channels,
                    source_channels - self._n_channels,
                )
            self._processors = [
                ChannelProcessor(native_rate) for _ in range(self._n_channels)
            ]
        except Exception:
            self._close()
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        self._close()

    def __iter__(self) -> "AudioSource":
        return self

    def __next__(self) -> AudioChunk:
        raw = self._read_raw_block()
        if raw is None:
            return self._drain()
        out_channels = [
            self._processors[i].process(raw[:, i])
            for i in range(self._n_channels)
        ]
        return self._emit(out_channels)

    def _drain(self) -> AudioChunk:
        """源耗尽：排出每声道重采样器尾部，作为最后一个 chunk 吐出。"""
        if self._flushed:
            raise StopIteration
        self._flushed = True
        out_channels = [proc.flush() for proc in self._processors]
        if not out_channels or len(out_channels[0]) == 0:
            raise StopIteration
        return self._emit(out_channels)

    def _emit(self, out_channels: list[np.ndarray]) -> AudioChunk:
        n_frames = len(out_channels[0])
        chunk = AudioChunk(
            seq=self._seq,
            channels=out_channels,
            n_frames=n_frames,
            start_frame=self._start_frame,
        )
        self._seq += 1
        self._start_frame += n_frames
        return chunk
