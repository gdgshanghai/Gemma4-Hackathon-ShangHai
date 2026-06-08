"""WhisperRunner 测试：int16 16k PCM → 文字。

用假转录器（_FakeModel）测封装逻辑（int16→float32 转换、语言透传、文本拼接），
真实 pywhispercpp 模型留 smoke / [手动测试]，不在此覆盖。
"""
import numpy as np

from backend.asr.config import ASRConfig
from backend.asr.whisper_runner import WhisperRunner


class _FakeSeg:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModel:
    """记录 transcribe 调用，返回预置 segment。"""

    def __init__(self, segs: list[str] | None = None) -> None:
        self.calls: list[tuple[np.ndarray, str]] = []
        self._segs = segs if segs is not None else ["你好", "世界"]

    def transcribe(self, audio: np.ndarray, language: str = "", **kw: object) -> list[_FakeSeg]:
        self.calls.append((audio, language))
        return [_FakeSeg(t) for t in self._segs]


def _pcm(n: int = 16000, amp: int = 1000) -> np.ndarray:
    return (np.ones(n) * amp).astype(np.int16)


def test_transcribe_pcm_joins_segments():
    runner = WhisperRunner(ASRConfig(language="zh"), model=_FakeModel(["你好", "世界"]))
    assert runner.transcribe_pcm(_pcm()) == "你好世界"


def test_int16_converted_to_float32_in_range():
    model = _FakeModel()
    runner = WhisperRunner(ASRConfig(), model=model)
    # 极值 int16，验证转换后落在 [-1, 1] 且为 float32
    pcm = np.array([32767, -32768, 0], dtype=np.int16)
    runner.transcribe_pcm(pcm)
    seen = model.calls[0][0]
    assert seen.dtype == np.float32
    assert seen.max() <= 1.0
    assert seen.min() >= -1.0


def test_language_passed_from_config():
    model = _FakeModel()
    runner = WhisperRunner(ASRConfig(language="zh"), model=model)
    runner.transcribe_pcm(_pcm())
    assert model.calls[0][1] == "zh"


def test_empty_segments_returns_empty_string():
    runner = WhisperRunner(ASRConfig(), model=_FakeModel([]))
    assert runner.transcribe_pcm(_pcm()) == ""


def test_outer_whitespace_stripped():
    runner = WhisperRunner(ASRConfig(), model=_FakeModel([" 你好世界 "]))
    assert runner.transcribe_pcm(_pcm()) == "你好世界"


def test_set_language_overrides_config():
    model = _FakeModel()
    runner = WhisperRunner(ASRConfig(language="zh"), model=model)
    runner.set_language("en")
    assert runner.language == "en"
    runner.transcribe_pcm(_pcm())
    assert model.calls[0][1] == "en"  # 用切换后的语言转录


def test_model_size_property():
    runner = WhisperRunner(ASRConfig(model_size="medium"), model=_FakeModel())
    assert runner.model_size == "medium"


def test_injected_model_reused_not_rebuilt():
    model = _FakeModel()
    runner = WhisperRunner(ASRConfig(), model=model)
    runner.transcribe_pcm(_pcm())
    runner.transcribe_pcm(_pcm())
    assert len(model.calls) == 2  # 同一注入实例被复用
