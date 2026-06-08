"""EnrollRecorder：录声纹时从后端现场麦采集（与 Capture 同设备同链路）。

LiveAsrSession 的轻量兄弟：后台 daemon 线程迭代一个 AudioSource，累积
chunk.channels[0]（已是 16kHz 单声道 int16）。纯采集，不跑 VAD/ASR、不提 embedding
（提取在路由的 _finalize_enrollment 里做）。

设备互斥：start() 在 capture 进行中拒绝（CaptureActiveError）；TAKE_START 反向由
entrypoint 的 take-start handler 先 abort 本录音（Capture 优先）。
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable

import numpy as np

from backend.audio.constants import OUTPUT_SAMPLE_RATE

logger = logging.getLogger(__name__)


class EnrollBusyError(RuntimeError):
    """已有一段录音在进行。"""


class CaptureActiveError(RuntimeError):
    """正在 Capture（take 录制中），不能同时用现场麦录声纹。"""


class EnrollRecorder:
    """单实例、线程化的现场麦声纹录音器。"""

    def __init__(
        self,
        make_source: Callable[[], object],
        is_capture_active: Callable[[], bool] = lambda: False,
        max_seconds: float = 60.0,
        sample_rate: int = OUTPUT_SAMPLE_RATE,
    ) -> None:
        self._make_source = make_source
        self._is_capture_active = is_capture_active
        self._max_seconds = max_seconds
        self._sample_rate = sample_rate
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._chunks: list[np.ndarray] = []
        self._capped = False

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def capped(self) -> bool:
        return self._capped

    def start(self) -> None:
        """起后台录音线程。capture 进行中 → CaptureActiveError；已在录 → EnrollBusyError。

        设备打开（make_source → 真实 PortAudio 探测/开流）在录音线程里做，不在 start()
        的调用方阻塞 —— enroll_start 端点在 asyncio 事件循环上同步调 start()，慢/卡的
        设备一旦在这里阻塞就会冻住整个事件循环。与 LiveAsrSession 一致（设备在采集线程开）。
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise EnrollBusyError("已有一段声纹录音在进行")
            if self._is_capture_active():
                raise CaptureActiveError("正在 Capture，无法同时用现场麦录声纹")
            self._stop_event.clear()
            self._chunks = []
            self._capped = False
            self._thread = threading.Thread(
                target=self._run, name="enroll-rec", daemon=True
            )
            self._thread.start()

    def _run(self) -> None:
        max_frames = int(self._max_seconds * self._sample_rate)
        total = 0
        try:
            source = self._make_source()  # 设备探测/开流在采集线程里做，不阻塞事件循环
            with source as s:  # type: ignore[attr-defined]
                for chunk in s:
                    if self._stop_event.is_set():
                        break
                    ch0 = chunk.channels[0]
                    self._chunks.append(ch0)
                    total += len(ch0)
                    if total >= max_frames:
                        self._capped = True
                        logger.info("enroll 录音触顶 %.0fs，自动停止", self._max_seconds)
                        break
        except Exception:
            logger.exception("enroll 录音线程异常退出")

    def stop(self, timeout: float = 5.0) -> np.ndarray:
        """停止并返回累积的 int16 buffer（未起 / 已 abort → 空数组）。"""
        thread = self._join_and_clear_thread(timeout)
        with self._lock:
            chunks, self._chunks = self._chunks, []
        if thread is None or not chunks:
            return np.zeros(0, dtype=np.int16)
        return np.concatenate(chunks)

    def abort(self, timeout: float = 5.0) -> None:
        """放弃录音、弃 buffer、释放设备。未运行时安全 no-op。"""
        self._join_and_clear_thread(timeout)
        with self._lock:
            self._chunks = []

    def _join_and_clear_thread(self, timeout: float) -> threading.Thread | None:
        with self._lock:
            thread = self._thread
            self._thread = None
            self._stop_event.set()
        if thread is not None:
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.warning("enroll 录音线程 %.1fs 内未收束", timeout)
        return thread
