"""4.J-2 多模态 handler 单测：音频哨兵路由（脱离真模型）。

MultimodalGemma4Handler.__init__（继承 Llava15ChatHandler）只存 clip_model_path +
os.path.exists 检查，不加载 mtmd 上下文（那是 _init_mtmd_context 懒加载），故构造只需
一个存在的 mmproj 文件占位，无需真模型——音频哨兵分支不碰模型，可单测。
"""

from __future__ import annotations

import pytest


def _make_handler(tmp_path):
    from backend.llm.multimodal import MultimodalGemma4Handler  # noqa: PLC0415

    mmproj = tmp_path / "mmproj-F16.gguf"
    mmproj.write_bytes(b"fake")  # __init__ 仅检查存在
    return MultimodalGemma4Handler(clip_model_path=str(mmproj), verbose=False)


def test_load_image_audio_sentinel_returns_pending_audio(tmp_path) -> None:
    """音频哨兵命中 → 返回当前请求 set_pending_audio 的 WAV 字节（不走父类图像加载）。"""
    from backend.llm.multimodal import AUDIO_SENTINEL  # noqa: PLC0415

    h = _make_handler(tmp_path)
    h.set_pending_audio(b"RIFF....WAVfake")
    assert h.load_image(AUDIO_SENTINEL) == b"RIFF....WAVfake"


def test_load_image_audio_sentinel_without_pending_raises(tmp_path) -> None:
    """哨兵命中但未 set_pending_audio → 明确报错（而非静默走父类把哨兵当图片 URL 加载）。"""
    from backend.llm.multimodal import AUDIO_SENTINEL  # noqa: PLC0415

    h = _make_handler(tmp_path)
    with pytest.raises(ValueError):
        h.load_image(AUDIO_SENTINEL)


def test_set_pending_audio_none_clears(tmp_path) -> None:
    """set_pending_audio(None) 清空（每次推理后复位，避免串号）→ 再命中哨兵报错。"""
    from backend.llm.multimodal import AUDIO_SENTINEL  # noqa: PLC0415

    h = _make_handler(tmp_path)
    h.set_pending_audio(b"x")
    h.set_pending_audio(None)
    with pytest.raises(ValueError):
        h.load_image(AUDIO_SENTINEL)


def test_non_sentinel_url_delegates_to_super(tmp_path) -> None:
    """非哨兵 URL → 委托父类 load_image（图像路径，3.x vision 复用），不被音频分支拦截。"""
    h = _make_handler(tmp_path)
    h.set_pending_audio(b"audio")
    # 父类 load_image 对非法图片 URL 会自行处理/报错；我们只断言「没把它当哨兵返回音频字节」。
    try:
        result = h.load_image("https://example.com/not-a-sentinel.png")
    except Exception:
        result = None
    assert result != b"audio", "非哨兵 URL 不应返回 pending 音频字节"


def test_image_token_budget_is_ocr_tier() -> None:
    """vision-ready：image token 档位常量 = 1120（gemma4 OCR 档），供 _init_mtmd_context 用。"""
    from backend.llm.multimodal import MultimodalGemma4Handler  # noqa: PLC0415

    assert MultimodalGemma4Handler.IMAGE_TOKENS == 1120
