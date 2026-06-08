"""EnrollRecorder 线程生命周期 + 守卫测试（注入假源，不碰 PortAudio）。"""
from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from backend.audio.source import AudioChunk
from backend.diarization.enroll_recorder import (
    CaptureActiveError,
    EnrollBusyError,
    EnrollRecorder,
)


class _FiniteSource:
    """吐 n_chunks 个固定 chunk（每块 chunk_frames 个样本）后耗尽。"""

    def __init__(self, n_chunks: int, value: int = 1000, chunk_frames: int = 1600):
        self._n = n_chunks
        self._value = value
        self._chunk_frames = chunk_frames
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *exc):
        self.exited = True

    def __iter__(self):
        for sf in range(self._n):
            yield AudioChunk(
                seq=sf,
                channels=[np.full(self._chunk_frames, self._value, dtype=np.int16)],
                n_frames=self._chunk_frames,
                start_frame=sf * self._chunk_frames,
            )


class _InfiniteSource:
    """无限吐 chunk，模拟实时设备流；首次迭代置 started 事件。"""

    def __init__(self, value: int = 1000, chunk_frames: int = 1600):
        self._value = value
        self._chunk_frames = chunk_frames
        self.started = threading.Event()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def __iter__(self):
        sf = 0
        while True:
            self.started.set()
            yield AudioChunk(
                seq=sf,
                channels=[np.full(self._chunk_frames, self._value, dtype=np.int16)],
                n_frames=self._chunk_frames,
                start_frame=sf * self._chunk_frames,
            )
            sf += 1
            time.sleep(0.001)


def test_start_stop_accumulates_channel0():
    src = _FiniteSource(n_chunks=3, value=1000, chunk_frames=1600)
    rec = EnrollRecorder(make_source=lambda: src)
    rec.start()
    # 有限源会自行耗尽。等线程跑完再 stop —— 否则 stop 可能在消费完前就置停止标志，
    # 导致循环提前 break、buffer 不全（之前的 sleep 只是侥幸掩盖了这个竞态）。
    for _ in range(200):
        if not rec.running:
            break
        time.sleep(0.01)
    assert not rec.running
    pcm = rec.stop()
    assert pcm.dtype == np.int16
    assert len(pcm) == 3 * 1600
    assert int(pcm[0]) == 1000
    assert src.entered and src.exited  # 上下文管理器正确进出


def test_stop_without_start_returns_empty():
    rec = EnrollRecorder(make_source=lambda: _FiniteSource(0))
    pcm = rec.stop()
    assert pcm.dtype == np.int16
    assert len(pcm) == 0


def test_running_flag_and_stop_joins():
    src = _InfiniteSource()
    rec = EnrollRecorder(make_source=lambda: src)
    assert not rec.running
    rec.start()
    assert src.started.wait(timeout=2.0)
    assert rec.running
    pcm = rec.stop()
    assert not rec.running
    assert len(pcm) > 0


def test_max_seconds_caps_buffer():
    # max_seconds=0.5s @16k = 8000 帧；每块 1600 → 第 5 块越界，截断到 ~8000
    src = _InfiniteSource(chunk_frames=1600)
    rec = EnrollRecorder(make_source=lambda: src, max_seconds=0.5, sample_rate=16000)
    rec.start()
    # 等线程自行触顶停止
    for _ in range(200):
        if not rec.running:
            break
        time.sleep(0.01)
    assert not rec.running  # cap 后线程自停
    pcm = rec.stop()
    assert 8000 <= len(pcm) <= 8000 + 1600  # 触顶那块算进来
    assert rec.capped is True


def test_start_rejected_while_capture_active():
    rec = EnrollRecorder(make_source=lambda: _FiniteSource(1), is_capture_active=lambda: True)
    with pytest.raises(CaptureActiveError):
        rec.start()


def test_double_start_rejected():
    src = _InfiniteSource()
    rec = EnrollRecorder(make_source=lambda: src)
    rec.start()
    assert src.started.wait(timeout=2.0)
    with pytest.raises(EnrollBusyError):
        rec.start()
    rec.stop()


def test_abort_discards_buffer_and_releases():
    src = _InfiniteSource()
    rec = EnrollRecorder(make_source=lambda: src)
    rec.start()
    assert src.started.wait(timeout=2.0)
    rec.abort()
    assert not rec.running
    # abort 后再 stop 返回空（buffer 已弃）
    assert len(rec.stop()) == 0


def test_start_does_not_block_on_slow_make_source():
    """make_source（真实设备探测/开流可能慢甚至卡）必须在录音线程里调用，不能阻塞
    start() 的调用方 —— enroll_start 端点在 asyncio 事件循环上同步调 start()，一旦
    被设备打开阻塞，整个后端事件循环就冻住，前端卡在「正在启动现场麦」。
    """
    gate = threading.Event()

    def slow_source():
        gate.wait(timeout=2.0)  # 模拟慢/卡的设备打开
        return _InfiniteSource()

    rec = EnrollRecorder(make_source=slow_source)
    t0 = time.monotonic()
    try:
        rec.start()  # 不应被 make_source 阻塞
        elapsed = time.monotonic() - t0
        assert elapsed < 0.5, f"start() 被 make_source 阻塞了 {elapsed:.2f}s（设备打开没移到录音线程）"
    finally:
        gate.set()  # 放行线程，让 stop 能收束
        rec.stop()
