"""统一多模态 chat handler（4.J，方案 A）。

单模型实例（一份 `Llama`）挂这一个 handler，由它按 content 类型分三个入口——
text / audio / image——全走同一份 `CHAT_FORMAT`（继承 0.3.25 内置 `Gemma4ChatHandler`
的官方 gemma 模板，system 合并进首个 user turn）。spec：voice-note-and-np-refinement v0.5 §5.1/§5.2。

设计要点：
- **音频入口**：WAV 字节从 `image_url` content 通道走（mtmd 的 media_marker 对音频/图像通用，
  tokenize/eval 不区分）。调用方在 LLMService 的 `_lock` 串行下 `set_pending_audio(wav)` 再发起
  推理，handler 的 `load_image(AUDIO_SENTINEL)` 取回该次字节；`_lock` 保证同一时刻只有一个请求，
  故单一 `_pending_audio` 槽位无竞态。
- **图像入口（vision-ready，3.x 收敛）**：`_init_mtmd_context` 设 `image_min/max_tokens=1120`
  （gemma4 vision OCR 高分辨率档；默认 280 档读不清密集小字）。`n_batch=n_ubatch=2048` 由
  `GemmaClient` 在构造 `Llama` 时给（gemma4 vision non-causal 要 1120 image token 落单 ubatch）。
  这两项 audio/text 用不上但无害，现在就位以便 3.x vision 合并时只接调用、不动实例构造。
- **启动自检**：`_init_mtmd_context` 断言 mmproj 同时支持 audio + vision（mmproj-F16 两投影器都在），
  不匹配 fail-fast。

收敛：3.x 的 vision 探针（`scripts/sp_vision_probe.py`，0.3.23 手搓 `Llava15ChatHandler` 子类）
合并到 0.3.25 一侧时切到本 handler，三入口共用同一实现。
"""

from __future__ import annotations

import llama_cpp
from llama_cpp._utils import suppress_stdout_stderr
from llama_cpp.llama_chat_format import Gemma4ChatHandler

from backend.llm.errors import ModelUnavailableError

# 音频哨兵：WAV 字节不进 messages（messages 只放此 URL 占位），由 load_image 在推理时取回。
# 取一个不会与真实图片 URL 撞的 scheme。
AUDIO_SENTINEL = "soundspeed://audio/current.wav"


class MultimodalGemma4Handler(Gemma4ChatHandler):
    """text / audio / image 三入口统一的 gemma4 多模态 handler。

    继承 0.3.25 内置 `Gemma4ChatHandler` 拿官方 `CHAT_FORMAT`（system 折进首个 user turn），
    两处 override：`load_image`（音频哨兵 → 当前请求 WAV 字节）、`_init_mtmd_context`
    （image token 档 1120 + audio/vision 自检）。
    """

    # gemma4 vision OCR 档（默认 280；档位 70/140/280/560/1120）。vision-ready，audio/text 不依赖。
    IMAGE_TOKENS = 1120

    def __init__(self, clip_model_path: str, verbose: bool = False) -> None:
        super().__init__(clip_model_path=clip_model_path, verbose=verbose)
        # 当前请求的 WAV 字节（_lock 串行下 set，load_image 取，推理后复位 None）。
        self._pending_audio: bytes | None = None

    def set_pending_audio(self, audio: bytes | None) -> None:
        """在发起音频推理前（_lock 持有下）设置该次请求的 WAV 字节；推理后传 None 复位。"""
        self._pending_audio = audio

    def load_image(self, image_url: str) -> bytes:
        """音频哨兵 → 返回当前 pending WAV 字节；其余 URL 委托父类（图像路径，3.x vision 复用）。"""
        if image_url == AUDIO_SENTINEL:
            if self._pending_audio is None:
                raise ValueError(
                    "音频哨兵命中但无 pending 音频字节（set_pending_audio 未在 _lock 下设置）"
                )
            return self._pending_audio
        return super().load_image(image_url)

    def _init_mtmd_context(self, llama_model: llama_cpp.Llama) -> None:
        """复刻 0.3.25 父类逻辑，额外：① 设 image token 档 1120（OCR）；② 断言 audio + vision 双支持。"""
        if self.mtmd_ctx is not None:
            return
        with suppress_stdout_stderr(disable=self.verbose):
            ctx_params = self._mtmd_cpp.mtmd_context_params_default()
            ctx_params.use_gpu = True
            ctx_params.print_timings = self.verbose
            ctx_params.n_threads = llama_model.n_threads
            ctx_params.flash_attn_type = (
                llama_cpp.LLAMA_FLASH_ATTN_TYPE_ENABLED
                if (
                    llama_model.context_params.flash_attn_type
                    == llama_cpp.LLAMA_FLASH_ATTN_TYPE_ENABLED
                )
                else llama_cpp.LLAMA_FLASH_ATTN_TYPE_DISABLED
            )
            # vision-ready：OCR 高分辨率档（密集中文小字默认 280 档读不清）。
            ctx_params.image_min_tokens = self.IMAGE_TOKENS
            ctx_params.image_max_tokens = self.IMAGE_TOKENS

            self.mtmd_ctx = self._mtmd_cpp.mtmd_init_from_file(
                self.clip_model_path.encode(), llama_model.model, ctx_params
            )
            if self.mtmd_ctx is None:
                raise ModelUnavailableError(f"mtmd 上下文加载失败：{self.clip_model_path}")

            # 启动自检（spec §5.2）：单实例多模态必须 audio + vision 双支持（mmproj-F16 两投影器）。
            if not self._mtmd_cpp.mtmd_support_audio(self.mtmd_ctx):
                raise ModelUnavailableError("mmproj 不支持音频（缺 gemma4a 音频投影器）")
            if not self._mtmd_cpp.mtmd_support_vision(self.mtmd_ctx):
                raise ModelUnavailableError("mmproj 不支持视觉（缺 gemma4v 视觉投影器）")

            def mtmd_free() -> None:
                with suppress_stdout_stderr(disable=self.verbose):
                    if self.mtmd_ctx is not None:
                        self._mtmd_cpp.mtmd_free(self.mtmd_ctx)
                        self.mtmd_ctx = None

            self._exit_stack.callback(mtmd_free)
