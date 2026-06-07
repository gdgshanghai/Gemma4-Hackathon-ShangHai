from __future__ import annotations

import asyncio
import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

from app.core.config import settings
from app.schemas.live import AsrSentence

logger = logging.getLogger(__name__)

# Shared thread pool for running blocking Recognition instances
_asr_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="asr")


class _AsrCallback(RecognitionCallback):
    """Bridges Alibaba ASR SDK callbacks → asyncio.Queue."""

    def __init__(self, loop: asyncio.AbstractEventLoop, result_queue: asyncio.Queue):
        self._loop = loop
        self._result_queue = result_queue

    def on_open(self) -> None:
        logger.info("ASR connection opened")

    def on_close(self) -> None:
        logger.info("ASR connection closed")

    def on_complete(self) -> None:
        logger.info("ASR recognition completed")
        self._loop.call_soon_threadsafe(self._result_queue.put_nowait, None)

    def on_error(self, message) -> None:
        logger.error("ASR error: %s", message.message)
        self._loop.call_soon_threadsafe(
            self._result_queue.put_nowait,
            AsrSentence(text="", is_sentence_end=False),
        )

    def on_event(self, result: RecognitionResult) -> None:
        sentence = result.get_sentence()
        if "text" not in sentence:
            return
        is_end = RecognitionResult.is_sentence_end(sentence)
        logger.info(
            "ASR event: text=%r is_sentence_end=%s begin_time=%s end_time=%s",
            sentence["text"],
            is_end,
            sentence.get("begin_time"),
            sentence.get("end_time"),
        )
        asr = AsrSentence(
            text=sentence["text"],
            is_sentence_end=is_end,
            begin_time=sentence.get("begin_time") or 0,
            end_time=sentence.get("end_time") or 0,
        )
        self._loop.call_soon_threadsafe(self._result_queue.put_nowait, asr)


def _run_recognition(
    api_key: str,
    model: str,
    format: str,
    sample_rate: int,
    semantic_punctuation_enabled: bool,
    audio_queue: queue.Queue,
    result_queue: asyncio.Queue,
    stop_event: threading.Event,
    main_loop: asyncio.AbstractEventLoop,
) -> None:
    """Runs in a background thread. Owns the Recognition instance."""
    dashscope.api_key = api_key
    dashscope.base_websocket_api_url = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"

    logger.info("ASR background thread starting (model=%s, format=%s, sample_rate=%d)", model, format, sample_rate)

    callback = _AsrCallback(main_loop, result_queue)

    recognition = Recognition(
        model=model,
        format=format,
        sample_rate=sample_rate,
        semantic_punctuation_enabled=semantic_punctuation_enabled,
        callback=callback,
    )

    try:
        recognition.start()
        logger.info("ASR recognition started (model=%s)", model)

        while not stop_event.is_set():
            try:
                chunk = audio_queue.get(timeout=0.5)
                if chunk == b"":  # Sentinel: stop
                    logger.info("ASR audio loop received stop sentinel")
                    break
                recognition.send_audio_frame(chunk)
            except queue.Empty:
                continue
            except Exception:
                logger.warning("Error in ASR audio loop", exc_info=True)
                break

    except Exception:
        logger.error("ASR recognition failed", exc_info=True)
    finally:
        recognition.stop()
        logger.info("ASR recognition stopped")
        try:
            recognition.get_duplex_api().close(1000, "bye")
        except Exception:
            pass


class AsrSession:
    """Manages a single ASR recognition session.

    Created per frontend WebSocket connection. Audio chunks flow in through
    ``feed_audio()``, and results come out through ``results()``.
    """

    def __init__(self) -> None:
        self._audio_queue: queue.Queue = queue.Queue()
        self._result_queue: asyncio.Queue = asyncio.Queue()
        self._stop_event = threading.Event()
        self._future = None

    def start(self) -> None:
        """Launch the ASR recognition in a background thread."""
        api_key = settings.dashscope_api_key
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is not set")

        main_loop = asyncio.get_running_loop()
        logger.info("AsrSession.start() submitting to thread pool (loop=%s)", id(main_loop))

        self._future = _asr_executor.submit(
            _run_recognition,
            api_key=api_key,
            model=settings.asr_model,
            format=settings.asr_format,
            sample_rate=settings.asr_sample_rate,
            semantic_punctuation_enabled=settings.asr_semantic_punctuation_enabled,
            audio_queue=self._audio_queue,
            result_queue=self._result_queue,
            stop_event=self._stop_event,
            main_loop=main_loop,
        )

    async def feed_audio(self, pcm_bytes: bytes) -> None:
        """Push PCM audio data to the ASR engine (non-blocking)."""
        await asyncio.to_thread(self._audio_queue.put, pcm_bytes)

    async def results(self):
        """Async generator yielding AsrSentence results."""
        while True:
            item = await self._result_queue.get()
            if item is None:
                return  # Recognition complete
            yield item

    def stop(self) -> None:
        """Signal the ASR engine to stop."""
        self._stop_event.set()
        # Push sentinel so get() returns immediately
        self._audio_queue.put(b"")
