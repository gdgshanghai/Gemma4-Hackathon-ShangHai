"""LiveAsrSession 线程生命周期测试。

用无限静音假源（模拟 DeviceSource 实时流）+ 假 runner，验证 start/stop/幂等/空停。
真实 DeviceSource + 浏览器上屏是 [手动测试]，不在此覆盖。
"""
import threading
import time

import numpy as np
from dataclasses import replace

from backend.audio.source import AudioChunk
from backend.vad.models import VadConfig
from backend.asr.live_session import LiveAsrSession


class _AmplitudeVad:
    def speech_prob(self, frame: np.ndarray) -> float:
        return 1.0 if float(np.sqrt(np.mean(frame.astype(np.float64) ** 2))) > 1000.0 else 0.0

    def reset(self) -> None:
        pass


class _FakeRunner:
    def transcribe_pcm(self, pcm: np.ndarray) -> str:
        return ""


class _InfiniteSilenceSource:
    """无限吐静音 chunk，模拟实时设备流；首次迭代置 started 事件。"""

    def __init__(self) -> None:
        self.started = threading.Event()

    def __enter__(self) -> "_InfiniteSilenceSource":
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def __iter__(self):
        sf = 0
        while True:
            self.started.set()
            yield AudioChunk(seq=sf, channels=[np.zeros(3200, dtype=np.int16)], n_frames=3200, start_frame=sf * 3200)
            sf += 1
            time.sleep(0.001)  # 模拟实时节奏，避免空转占满 CPU


def _vad_cfg() -> VadConfig:
    return replace(VadConfig(), frame_samples=512)


def _session(source) -> LiveAsrSession:
    return LiveAsrSession(
        runner=_FakeRunner(),
        publish=lambda topic, payload: None,
        source_factory=lambda device: source,
        vad_config=_vad_cfg(),
        detector_factory=lambda: _AmplitudeVad(),
    )


def test_set_device_passed_to_source_factory():
    seen: list[object] = []
    src = _InfiniteSilenceSource()
    session = LiveAsrSession(
        runner=_FakeRunner(),
        publish=lambda topic, payload: None,
        source_factory=lambda device: (seen.append(device), src)[1],
        vad_config=_vad_cfg(),
        detector_factory=lambda: _AmplitudeVad(),
        default_device=None,
    )
    session.set_device(3)
    assert session.device == 3
    session.start()
    assert src.started.wait(timeout=2.0)
    session.stop()
    assert seen == [3]  # source_factory 收到选中的设备


def test_start_runs_then_stop_joins():
    src = _InfiniteSilenceSource()
    session = _session(src)
    assert not session.running
    session.start()
    assert src.started.wait(timeout=2.0)  # 线程确实跑起来
    assert session.running
    session.stop()
    assert not session.running


def test_double_start_idempotent():
    src = _InfiniteSilenceSource()
    session = _session(src)
    session.start()
    assert src.started.wait(timeout=2.0)
    session.start()  # 第二次应被忽略，不崩
    assert session.running
    session.stop()
    assert not session.running


def test_stop_without_start_safe():
    session = _session(_InfiniteSilenceSource())
    session.stop()  # 未起线程，安全 no-op
    assert not session.running


def test_restart_after_stop():
    src = _InfiniteSilenceSource()
    session = _session(src)
    session.start()
    assert src.started.wait(timeout=2.0)
    session.stop()
    assert not session.running
    # 同一 session 再次 start（新 take）
    src.started.clear()
    session.start()
    assert src.started.wait(timeout=2.0)
    assert session.running
    session.stop()
    assert not session.running


def test_make_source_uses_current_device():
    seen: list[object] = []
    sentinel = _InfiniteSilenceSource()
    session = LiveAsrSession(
        runner=_FakeRunner(),
        publish=lambda topic, payload: None,
        source_factory=lambda device: (seen.append(device), sentinel)[1],
        vad_config=_vad_cfg(),
        detector_factory=lambda: _AmplitudeVad(),
        default_device="USB Mic",
    )
    src = session.make_source()
    assert src is sentinel
    assert seen == ["USB Mic"]
    # 跟随 set_device
    session.set_device(7)
    session.make_source()
    assert seen == ["USB Mic", 7]
