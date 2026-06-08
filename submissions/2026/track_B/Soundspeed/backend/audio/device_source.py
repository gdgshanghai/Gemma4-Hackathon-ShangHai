"""DeviceSource：实时采集设备作为 AudioSource。"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

import numpy as np
import sounddevice as sd

from backend.audio.source import AudioConfig, AudioSource

logger = logging.getLogger(__name__)


class DeviceError(RuntimeError):
    """采集设备无法打开、或采集中途失败时抛出。"""


def _open_input_stream(
    device: int | str, config: AudioConfig
) -> tuple[sd.InputStream, int, int]:
    """打开设备 InputStream 并 start，返回 (stream, rate, channels)。

    失败时抛 DeviceError（query 失败或 PortAudioError）。
    调用方负责 stop/close 流。
    """
    try:
        info = sd.query_devices(device, "input")
    except (ValueError, sd.PortAudioError) as exc:
        available = "\n".join(
            f"  [{i}] {d['name']}"
            for i, d in enumerate(sd.query_devices())
            if d["max_input_channels"] > 0
        )
        raise DeviceError(
            f"找不到输入设备 {device!r}。可用输入设备：\n{available}"
        ) from exc
    rate = int(info["default_samplerate"])
    channels = int(info["max_input_channels"])
    try:
        stream = sd.InputStream(
            device=device, samplerate=rate,
            channels=channels, dtype="float32",
        )
        stream.start()
    except sd.PortAudioError as exc:
        raise DeviceError(f"打开设备 {device!r} 失败：{exc}") from exc
    return stream, rate, channels


class DeviceSource(AudioSource):
    """从声卡 / 虚拟声卡 / USB 接口 / 录音机 line-out 实时采集。

    用 sounddevice 阻塞式 read —— 阻塞本身就是实时节奏与拉取语义，
    无后台线程、无队列。
    """

    def __init__(self, device: str | int, config: AudioConfig) -> None:
        super().__init__(config)
        self._device = device
        self._stream: sd.InputStream | None = None
        self._block_frames = 0
        self._overflow_count = 0

    def _open(self) -> tuple[int, int]:
        stream, rate, channels = _open_input_stream(self._device, self._config)
        self._stream = stream
        self._block_frames = rate * self._config.chunk_ms // 1000
        return rate, channels

    def _read_raw_block(self) -> np.ndarray:
        assert self._stream is not None
        try:
            data, overflowed = self._stream.read(self._block_frames)
        except sd.PortAudioError as exc:
            raise DeviceError(f"设备采集中断：{exc}") from exc
        if overflowed:
            self._overflow_count += 1
            logger.warning(
                "设备输入缓冲溢出（第 %d 次），消费速度跟不上实时",
                self._overflow_count,
            )
        return data

    def _close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


def _default_probe(device: int | str, config: AudioConfig) -> None:
    """默认探测函数：短暂打开并立即关闭 InputStream，确认设备可用。

    成功则静默返回；失败则抛 DeviceError。
    open_device_with_fallback 用此函数探测候选设备，不保留已打开的流。
    """
    stream, _rate, _channels = _open_input_stream(device, config)
    stream.stop()
    stream.close()


def open_device_with_fallback(
    candidates: Sequence[int | str | None],
    config: AudioConfig,
    _probe: Callable[[int | str, AudioConfig], None] | None = None,
) -> int | str:
    """按候选顺序探测设备，返回首个可成功打开的 index/name；全部失败则抛 DeviceError。

    参数：
      candidates: 要尝试的设备 index/name 列表（优先级从高到低）。None 值跳过。
        重复的 index/name 只探测一次（去重保序）。
      config: 探测时传给 _probe 的配置。
      _probe: 可注入的探测函数（默认 _default_probe）。
        签名：(device, config) -> None；无法打开则抛 DeviceError。
        测试注入假 probe 避免真 PortAudio。

    返回值：首个成功的 index/name（int | str），调用方再用此值构造 DeviceSource。
    全部失败则抛 DeviceError，消息包含所有已尝试的候选列表。
    """
    probe = _probe if _probe is not None else _default_probe
    unique = list(dict.fromkeys(c for c in candidates if c is not None))
    last_exc: DeviceError | None = None

    for candidate in unique:
        try:
            probe(candidate, config)
            return candidate
        except DeviceError as exc:
            logger.warning("设备 %r 打开失败，尝试下一个候选：%s", candidate, exc)
            last_exc = exc

    raise DeviceError(
        f"全部候选设备均无法打开（已尝试：{unique}）"
    ) from last_exc
