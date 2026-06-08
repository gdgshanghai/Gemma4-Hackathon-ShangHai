"""GemmaClient 文本+tools 的 chat_handler 切换（多模态单实例下走原生 FunctionGemma formatter）。

根因（QP e2e 发现）：mmproj 多模态 handler 的 CHAT_FORMAT 不渲染工具声明 → 带 tools 的文本请求
模型看不到工具（auto 不调、forced 靠 grammar 兜）。修复：text+tools 请求临时换 GGUF 原生
FunctionGemma formatter（渲染 tools）；音频/无 tools 仍走多模态 handler。LLMService 的 _lock
串行化所有 client 调用，故 chat_handler 临时换/还原无竞态。

本文件用 fake _llm（绕过 __init__ 不加载模型）验「哪个 handler 在调用期间活跃 + 调用后还原」。
真模型端到端验证见 test_qp_smoke.py（@smoke）。
"""
from __future__ import annotations

import pytest

from backend.llm.client import GemmaClient


class _RecordingLlm:
    """记录每次 create_chat_completion 调用期间活跃的 chat_handler。"""

    def __init__(self) -> None:
        self.chat_handler = "MULTIMODAL"
        self.active: list[object] = []

    def create_chat_completion(self, messages, **kwargs):  # noqa: ANN001, ANN003
        self.active.append(self.chat_handler)
        return {"choices": [{"message": {"content": "ok"}}]}


class _FakeMmHandler:
    def __init__(self) -> None:
        self.audio_sets: list[object] = []

    def set_pending_audio(self, audio) -> None:  # noqa: ANN001
        self.audio_sets.append(audio)


def _client(*, text_tool_handler: object, handler: object | None = None) -> GemmaClient:
    """绕过 __init__（不加载模型），手装 _llm / _handler / _text_tool_handler。"""
    c = GemmaClient.__new__(GemmaClient)
    c._llm = _RecordingLlm()  # type: ignore[attr-defined]
    c._handler = handler if handler is not None else _FakeMmHandler()  # type: ignore[attr-defined]
    c._text_tool_handler = text_tool_handler  # type: ignore[attr-defined]
    return c


def test_text_with_tools_swaps_to_native_then_restores() -> None:
    c = _client(text_tool_handler="NATIVE")
    c.create_chat_completion(
        messages=[{"role": "user", "content": "x"}], tools=[{"function": {"name": "t"}}], tool_choice="auto"
    )
    assert c._llm.active == ["NATIVE"]  # 调用期间用原生 formatter（渲染 tools）
    assert c._llm.chat_handler == "MULTIMODAL"  # 调用后还原多模态 handler


def test_text_without_tools_keeps_multimodal() -> None:
    c = _client(text_tool_handler="NATIVE")
    c.create_chat_completion(messages=[{"role": "user", "content": "x"}])
    assert c._llm.active == ["MULTIMODAL"]
    assert c._llm.chat_handler == "MULTIMODAL"


def test_audio_path_keeps_multimodal_and_stashes_audio() -> None:
    fake_h = _FakeMmHandler()
    c = _client(text_tool_handler="NATIVE", handler=fake_h)
    # 音频 + tools（voice NP forced）：走音频分支，用多模态 handler（音频要它，grammar 兜工具），不切原生。
    c.create_chat_completion(
        messages=[{"role": "user", "content": "x"}], tools=[{"function": {"name": "t"}}], audio=b"wav"
    )
    assert c._llm.active == ["MULTIMODAL"]
    assert fake_h.audio_sets == [b"wav", None]  # 设音频 + 推理后复位


def test_no_native_handler_no_swap() -> None:
    # 纯文本 client（无 mmproj）或 _build_native_tool_handler 兜底返 None → 不切，用原 handler。
    c = _client(text_tool_handler=None)
    c.create_chat_completion(
        messages=[{"role": "user", "content": "x"}], tools=[{"function": {"name": "t"}}]
    )
    assert c._llm.active == ["MULTIMODAL"]
    assert c._llm.chat_handler == "MULTIMODAL"


def test_exception_in_llm_still_restores_handler() -> None:
    # 核心不变量：text+tools 切原生后，即便 create_chat_completion 抛异常，finally 也还原多模态 handler。
    class _BrokenLlm(_RecordingLlm):
        def create_chat_completion(self, messages, **kwargs):  # noqa: ANN001, ANN003
            raise RuntimeError("model crash")

    c = _client(text_tool_handler="NATIVE")
    c._llm = _BrokenLlm()  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError):
        c.create_chat_completion(
            messages=[{"role": "user", "content": "x"}], tools=[{"function": {"name": "t"}}]
        )
    assert c._llm.chat_handler == "MULTIMODAL"  # 异常路径也还原


# ---------------------------------------------------------------------------
# GPU→CPU 加载回落（_load_with_cpu_fallback）：GPU 优先、显存装不下回落 CPU
# ---------------------------------------------------------------------------


def test_load_fallback_retries_cpu_on_gpu_oom():
    """想上 GPU 但 OOM（Failed to load model）→ 自动用 n_gpu_layers=0 重试。"""
    calls: list = []

    def fake_llama(model_path, **params):
        calls.append(params.get("n_gpu_layers"))
        if params.get("n_gpu_layers") != 0:
            raise RuntimeError("Failed to load model from file: x.gguf (CUBLAS_ALLOC_FAILED)")
        return "cpu_llm"

    out = GemmaClient._load_with_cpu_fallback(fake_llama, "x.gguf", {"n_gpu_layers": -1})
    assert out == "cpu_llm"
    assert calls == [-1, 0]  # 先 GPU(-1) 失败，回落 CPU(0)


def test_load_fallback_keeps_gpu_when_it_fits():
    """GPU 加载成功（大显存设备）→ 不触发回落，留在 GPU。"""
    calls: list = []

    def fake_llama(model_path, **params):
        calls.append(params.get("n_gpu_layers"))
        return "gpu_llm"

    out = GemmaClient._load_with_cpu_fallback(fake_llama, "x.gguf", {"n_gpu_layers": -1})
    assert out == "gpu_llm"
    assert calls == [-1]  # 一次成功，无回落


def test_load_fallback_cpu_failure_reraises():
    """本就纯 CPU(0) 还失败 → 非显存问题，照抛不吞。"""
    def fake_llama(model_path, **params):
        raise RuntimeError("disk gone")

    with pytest.raises(RuntimeError, match="disk gone"):
        GemmaClient._load_with_cpu_fallback(fake_llama, "x.gguf", {"n_gpu_layers": 0})


# ---------------------------------------------------------------------------
# 显存预判（_resolve_gpu_layers）：占满走 CPU、够用留 GPU（Windows 主动判定）
# ---------------------------------------------------------------------------


def test_resolve_gpu_layers_cpu_when_vram_full(monkeypatch, tmp_path):
    """可用显存 < 需求 → 退 CPU(0)。"""
    import torch

    f = tmp_path / "m.gguf"
    f.write_bytes(b"x" * (1 << 20))  # 1MB
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "mem_get_info", lambda: (1 << 29, 8 << 30))  # 0.5GB free
    assert GemmaClient._resolve_gpu_layers(-1, str(f)) == 0


def test_resolve_gpu_layers_gpu_when_vram_free(monkeypatch, tmp_path):
    """可用显存充足 → 保持 GPU(-1)。"""
    import torch

    f = tmp_path / "m.gguf"
    f.write_bytes(b"x" * (1 << 20))
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "mem_get_info", lambda: (8 << 30, 8 << 30))  # 8GB free
    assert GemmaClient._resolve_gpu_layers(-1, str(f)) == -1


def test_resolve_gpu_layers_zero_passthrough(tmp_path):
    """已是 CPU(0) → 不查显存，直接 0。"""
    f = tmp_path / "m.gguf"
    f.write_bytes(b"x")
    assert GemmaClient._resolve_gpu_layers(0, str(f)) == 0


def test_resolve_gpu_layers_no_cuda_keeps_wanted(monkeypatch, tmp_path):
    """无 CUDA → 保持原意图（不强制改）。"""
    import torch

    f = tmp_path / "m.gguf"
    f.write_bytes(b"x")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert GemmaClient._resolve_gpu_layers(-1, str(f)) == -1
