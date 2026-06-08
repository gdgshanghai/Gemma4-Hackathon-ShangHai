"""4.J-2 多模态 GemmaClient 构造 + 音频路由单测（脱离真模型）。

GemmaClient.__init__ 内 `from llama_cpp import Llama` 在调用时解析 `llama_cpp.Llama`，
monkeypatch 该属性为 FakeLlama 即可不加载真模型验证构造参数与音频路由。
MultimodalGemma4Handler 构造只检查 mmproj 文件存在（不加载 mtmd），用 tmp 占位文件。
"""

from __future__ import annotations

import llama_cpp
import pytest


def _fake_model(tmp_path) -> str:
    p = tmp_path / "model.gguf"
    p.write_bytes(b"fake")
    return str(p)


def _fake_mmproj(tmp_path) -> str:
    p = tmp_path / "mmproj-F16.gguf"
    p.write_bytes(b"fake")
    return str(p)


def test_multimodal_construction_passes_vision_ready_params(tmp_path, monkeypatch) -> None:
    """传 mmproj_path → 多模态构造：Llama 挂 MultimodalGemma4Handler，n_batch=n_ubatch=2048（方案 A）。"""
    from backend.llm.client import GemmaClient  # noqa: PLC0415
    from backend.llm.multimodal import MultimodalGemma4Handler  # noqa: PLC0415

    captured: dict = {}

    class FakeLlama:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(llama_cpp, "Llama", FakeLlama)

    GemmaClient(model_path=_fake_model(tmp_path), mmproj_path=_fake_mmproj(tmp_path))

    assert isinstance(captured["chat_handler"], MultimodalGemma4Handler)
    assert captured["n_batch"] == 2048
    assert captured["n_ubatch"] == 2048


def test_text_only_construction_has_no_handler(tmp_path, monkeypatch) -> None:
    """不传 mmproj_path → 纯文本构造（向后兼容）：无 chat_handler。"""
    from backend.llm.client import GemmaClient  # noqa: PLC0415

    captured: dict = {}

    class FakeLlama:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(llama_cpp, "Llama", FakeLlama)

    GemmaClient(model_path=_fake_model(tmp_path))

    assert captured.get("chat_handler") is None


def test_create_chat_completion_audio_stashes_and_clears(tmp_path, monkeypatch) -> None:
    """音频路由：create_chat_completion(audio=...) → 推理时 handler 持 pending 字节，推理后复位 None。"""
    from backend.llm.client import GemmaClient  # noqa: PLC0415

    seen: dict = {}

    class FakeLlama:
        def __init__(self, **kwargs: object) -> None:
            self._handler = kwargs.get("chat_handler")

        def create_chat_completion(self, messages: object, **kwargs: object) -> dict:
            seen["pending_during_infer"] = getattr(self._handler, "_pending_audio", None)
            return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(llama_cpp, "Llama", FakeLlama)

    client = GemmaClient(model_path=_fake_model(tmp_path), mmproj_path=_fake_mmproj(tmp_path))
    out = client.create_chat_completion(
        messages=[{"role": "user", "content": "x"}], audio=b"WAVBYTES"
    )

    assert out["choices"][0]["message"]["content"] == "ok"
    assert seen["pending_during_infer"] == b"WAVBYTES"  # 推理时已 set
    assert client._handler is not None
    assert client._handler._pending_audio is None  # 推理后已清（避免串到下次请求）


def test_text_client_rejects_audio(tmp_path, monkeypatch) -> None:
    """纯文本 client（无 handler）收到 audio → ModelUnavailableError（不能跑音频推理）。"""
    from backend.llm.client import GemmaClient  # noqa: PLC0415
    from backend.llm.errors import ModelUnavailableError  # noqa: PLC0415

    class FakeLlama:
        def __init__(self, **kwargs: object) -> None:
            pass

        def create_chat_completion(self, messages: object, **kwargs: object) -> dict:
            return {"choices": [{"message": {"content": "x"}}]}

    monkeypatch.setattr(llama_cpp, "Llama", FakeLlama)

    client = GemmaClient(model_path=_fake_model(tmp_path))
    with pytest.raises(ModelUnavailableError):
        client.create_chat_completion(
            messages=[{"role": "user", "content": "x"}], audio=b"x"
        )
