"""StreamDriver 测试：AudioChunk 流 → 每声道 VAD → whisper_runner → publish asr.final.chN。

用假 source（直接构造 AudioChunk）+ 假探测器（幅度）+ 假 runner + 捕获 publish，
端到端验证驱动逻辑，无需真模型 / 真音频文件。
"""
import numpy as np

from backend.audio.source import AudioChunk
from backend.core.events import ASR_FINAL_CH1, ASR_FINAL_CH2, AsrFinalPayload
from backend.vad.models import VadConfig
from backend.asr.stream_driver import StreamDriver


# ── 假件 ──────────────────────────────────────────────────────────────────────


class _FakeSource:
    """上下文管理器 + AudioChunk 迭代器，喂预置 chunk。"""

    def __init__(self, chunks: list[AudioChunk]) -> None:
        self._chunks = chunks

    def __enter__(self) -> "_FakeSource":
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def __iter__(self):
        return iter(self._chunks)


class _AmplitudeVad:
    def __init__(self, amp: float = 1000.0) -> None:
        self._amp = amp

    def speech_prob(self, frame: np.ndarray) -> float:
        return 1.0 if float(np.sqrt(np.mean(frame.astype(np.float64) ** 2))) > self._amp else 0.0

    def reset(self) -> None:
        pass


class _FakeRunner:
    def __init__(self, text: str = "转录文本") -> None:
        self._text = text
        self.seen: list[np.ndarray] = []

    def transcribe_pcm(self, pcm: np.ndarray) -> str:
        self.seen.append(pcm)
        return self._text


def _silence(n: int) -> np.ndarray:
    return np.zeros(n, dtype=np.int16)


def _speech(n: int, amp: int = 8000) -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.integers(-amp, amp, size=n, endpoint=True).astype(np.int16)


def _vad_cfg(**kw) -> VadConfig:
    from dataclasses import replace
    base = VadConfig(frame_samples=512, threshold=0.5, min_silence_ms=300,
                     min_speech_ms=250, pre_roll_ms=200, post_roll_ms=200, max_segment_ms=30000)
    return replace(base, **kw)


def _chunk(seq: int, start_frame: int, channels: list[np.ndarray]) -> AudioChunk:
    return AudioChunk(seq=seq, channels=channels, n_frames=len(channels[0]), start_frame=start_frame)


def _drive(chunks, runner=None, detector_factory=None, vad_config=None, process_channels=None):
    runner = runner or _FakeRunner()
    published: list[tuple[str, object]] = []
    driver = StreamDriver(
        runner=runner,
        publish=lambda topic, payload: published.append((topic, payload)),
        vad_config=vad_config or _vad_cfg(),
        detector_factory=detector_factory or (lambda: _AmplitudeVad()),
        process_channels=process_channels,
    )
    driver.run(_FakeSource(chunks))
    return published, runner


# ── 测试 ──────────────────────────────────────────────────────────────────────


def _asr_events(published: list[tuple[str, object]]) -> list[tuple[str, object]]:
    """过滤出 ASR 相关事件（排除 audio.level）。"""
    return [(t, p) for t, p in published if t.startswith("asr.")]


def test_ch1_segment_publishes_asr_final_ch1():
    audio = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])
    published, _ = _drive([_chunk(0, 0, [audio])])
    asr = _asr_events(published)
    assert len(asr) == 1
    topic, payload = asr[0]
    assert topic == ASR_FINAL_CH1
    assert isinstance(payload, AsrFinalPayload)
    assert payload.text == "转录文本"
    assert payload.speaker is None
    assert payload.is_partial is False
    assert payload.take_id is None


def test_ch2_segment_publishes_asr_final_ch2():
    silent = _silence(20000)
    voice = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])
    published, _ = _drive([_chunk(0, 0, [silent, voice])])
    topics = [t for t, _ in published]
    assert ASR_FINAL_CH2 in topics
    assert ASR_FINAL_CH1 not in topics  # ch1 全静音，无段


def test_frames_converted_to_ms():
    # start_frame(16k 帧) → payload.start_frame(ms) = round(frame/16)
    audio = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])
    published, _ = _drive([_chunk(0, 32000, [audio])])
    asr = _asr_events(published)
    assert len(asr) == 1
    _, payload = asr[0]
    assert isinstance(payload, AsrFinalPayload)
    # 段起点绝对帧 ≥ 32000，转 ms 应 ≈ frame/16
    assert payload.end_frame > payload.start_frame
    assert payload.start_frame >= 32000 // 16


def test_empty_transcription_skipped():
    audio = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])
    published, _ = _drive([_chunk(0, 0, [audio])], runner=_FakeRunner(text="  "))
    # 空文本不推 ASR 事件（audio.level 仍会推，不计入此断言）
    assert _asr_events(published) == []


def test_two_channels_independent_topics():
    ch1 = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])
    ch2 = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])
    published, _ = _drive([_chunk(0, 0, [ch1, ch2])])
    asr_topics = sorted(t for t, _ in _asr_events(published))
    assert asr_topics == sorted([ASR_FINAL_CH1, ASR_FINAL_CH2])


def test_process_channels_ch1_only_skips_ch2():
    # 双声道同源（设备复制），process_channels=(0,) → 只出 ch1，不重复 ch2
    ch1 = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])
    ch2 = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])
    published, _ = _drive([_chunk(0, 0, [ch1, ch2])], process_channels=(0,))
    asr_topics = [t for t, _ in _asr_events(published)]
    assert asr_topics == [ASR_FINAL_CH1]
    assert ASR_FINAL_CH2 not in asr_topics


def test_stop_breaks_loop_before_next_chunk():
    # 第一个 chunk 后置 stop；第二个 chunk 不应被处理（模拟 take.end 停采集）
    runner = _FakeRunner()
    published: list[tuple[str, object]] = []
    driver = StreamDriver(
        runner=runner,
        publish=lambda topic, payload: published.append((topic, payload)),
        vad_config=_vad_cfg(),
        detector_factory=lambda: _AmplitudeVad(),
    )
    seg_audio = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])

    def _gen():
        yield _chunk(0, 0, [seg_audio])
        driver.stop()
        yield _chunk(1, 32000, [_speech(8000)])  # stop 后，不应处理

    class _Src:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def __iter__(self):
            return _gen()

    driver.run(_Src())
    # 第一个 chunk 出 1 条 ASR + 1 条 audio.level；第二个 chunk 被 stop 截断，不处理
    assert len(_asr_events(published)) == 1


def test_flush_emits_trailing_segment_across_chunks():
    # 语音延续到流末（无收尾静音），分两个 chunk 喂，flush 补出段
    c0 = _chunk(0, 0, [np.concatenate([_silence(4000), _speech(4000)])])
    c1 = _chunk(1, 8000, [_speech(4000)])
    published, _ = _drive([c0, c1])
    asr = _asr_events(published)
    assert len(asr) == 1
    assert asr[0][0] == ASR_FINAL_CH1


# ── AUDIO_LEVEL 测试 ───────────────────────────────────────────────────────────


def test_audio_level_published_per_chunk():
    """每个 chunk 对 ch1 算 RMS 并 publish AUDIO_LEVEL。"""
    from backend.core.events import AUDIO_LEVEL, AudioLevelPayload  # noqa: PLC0415

    chunk = _chunk(0, 0, [_speech(3200, amp=8000)])
    published, _ = _drive([chunk])
    level_events = [(t, p) for t, p in published if t == AUDIO_LEVEL]
    assert len(level_events) == 1
    _, payload = level_events[0]
    assert isinstance(payload, AudioLevelPayload)
    assert 0.0 <= payload.rms <= 1.0


def test_audio_level_silence_chunk_rms_near_zero():
    """静音 chunk → rms 约为 0。"""
    from backend.core.events import AUDIO_LEVEL, AudioLevelPayload  # noqa: PLC0415

    chunk = _chunk(0, 0, [_silence(3200)])
    published, _ = _drive([chunk])
    level_events = [(t, p) for t, p in published if t == AUDIO_LEVEL]
    assert len(level_events) == 1
    _, payload = level_events[0]
    assert isinstance(payload, AudioLevelPayload)
    assert payload.rms == 0.0


def test_audio_level_loud_chunk_rms_positive():
    """响的 chunk → rms > 0。"""
    from backend.core.events import AUDIO_LEVEL, AudioLevelPayload  # noqa: PLC0415

    chunk = _chunk(0, 0, [_speech(3200, amp=16000)])
    published, _ = _drive([chunk])
    level_events = [(t, p) for t, p in published if t == AUDIO_LEVEL]
    assert len(level_events) == 1
    _, payload = level_events[0]
    assert isinstance(payload, AudioLevelPayload)
    assert payload.rms > 0.0


def test_audio_level_rms_clamped_to_one():
    """超大振幅（int16 满幅 32767）→ rms 不超过 1.0。"""
    from backend.core.events import AUDIO_LEVEL, AudioLevelPayload  # noqa: PLC0415

    # 全满幅正弦替代：直接填 32767
    loud = np.full(3200, 32767, dtype=np.int16)
    chunk = _chunk(0, 0, [loud])
    published, _ = _drive([chunk])
    level_events = [(t, p) for t, p in published if t == AUDIO_LEVEL]
    assert len(level_events) == 1
    _, payload = level_events[0]
    assert isinstance(payload, AudioLevelPayload)
    assert payload.rms <= 1.0


def test_audio_level_one_per_chunk_multiple_chunks():
    """多个 chunk → AUDIO_LEVEL 每 chunk 一条（数量与 chunk 数相同）。"""
    from backend.core.events import AUDIO_LEVEL  # noqa: PLC0415

    chunks = [_chunk(i, i * 3200, [_speech(3200)]) for i in range(3)]
    published, _ = _drive(chunks)
    level_events = [t for t, _ in published if t == AUDIO_LEVEL]
    assert len(level_events) == 3


# ── 繁简转换测试 ────────────────────────────────────────────────────────────────


def test_emit_normalizes_trad_to_simplified():
    """_emit 产出的 AsrFinalPayload.text 应已是简体（繁体输入被转换）。

    用「漢字測試」（繁体，4 字符，不在幻觉表，不被长度过滤）→ 应转为「汉字测试」。
    """
    audio = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])
    runner = _FakeRunner(text="漢字測試")
    published, _ = _drive([_chunk(0, 0, [audio])], runner=runner)
    asr = _asr_events(published)
    assert len(asr) == 1
    _, payload = asr[0]
    assert isinstance(payload, AsrFinalPayload)
    assert payload.text == "汉字测试"


def test_normalize_idempotent_on_simplified():
    """_normalize_to_simplified 对已是简体或英文文本幂等（输出 == 输入）。"""
    from backend.asr.stream_driver import _normalize_to_simplified  # noqa: PLC0415

    assert _normalize_to_simplified("汉字测试") == "汉字测试"
    assert _normalize_to_simplified("hello world") == "hello world"


def test_normalize_filters_trad_hallucination():
    """繁体幻觉「謝謝觀看」在转简后被 _is_hallucination 拦截，不推送 payload。

    选「謝謝觀看」（4 字符）：未转换时不在幻觉表（繁体），转换后得「谢谢观看」命中表。
    只要转换在过滤之前执行，就应无 ASR 事件输出。
    """
    audio = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])
    runner = _FakeRunner(text="謝謝觀看")
    published, _ = _drive([_chunk(0, 0, [audio])], runner=runner)
    assert _asr_events(published) == []
