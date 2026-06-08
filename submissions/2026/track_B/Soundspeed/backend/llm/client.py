"""底层模型加载与 client 抽象。

LLMClient 协议：定义 service 层依赖的接口契约。
GemmaClient：llama-cpp-python 封装（生产用）。
StubClient：确定性 stub（测试用）。

设计参考：llm-service-design v1.1 §底层模型加载 + 1.F 实施 spec §6。
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from backend.llm.errors import ModelUnavailableError

if TYPE_CHECKING:
    from backend.llm.multimodal import MultimodalGemma4Handler

logger = logging.getLogger(__name__)

# 默认模型路径，由环境变量覆盖
_DEFAULT_MODEL_PATH = "models/gemma-4-E4B-it-Q4_K_M.gguf"

# Gemma 上 GPU 的显存需求估计（_resolve_gpu_layers 用，查可用显存决定 GPU/CPU）：
# 权重 = gguf 大小 × 膨胀系数；再加 KV/计算缓冲余量。经验值（8GB 实测），
# 随 n_ctx / 模型更换需复核——这是个 advisory 启发式，不是精确账。
_VRAM_WEIGHT_FACTOR = 1.15
_VRAM_RUNTIME_RESERVE_BYTES = 1 << 30  # 1GB：KV cache + 计算缓冲余量

# llama-cpp-python 加载参数（来自 0.C spike 选型，llm-backend-selection v0.4 §11.3）
# n_ctx=8192：从 v0.3 的 4096 升一倍，支持长 take 场景（剧本 100+ 行 / 5+ 分钟转录），
# Q4_K_M @ 8192 实测 RSS ~6.5 GB（M1 Max 16 GB 余量充足，见 llm-backend-selection §3.3）。
_LLAMA_DEFAULTS: dict[str, object] = {
    "n_ctx": 8192,
    "n_gpu_layers": -1,  # 全卸载到 Metal（macOS）
    "seed": 42,
    "verbose": False,
    # flash attention：关键提速 + 省显存。未开时 llama 对 Gemma 的 V cache 做
    # padding-to-1024（日志 "FA is not enabled - padding V cache"），KV 撑大、
    # 8GB 卡上与 whisper/pyannote 同跑会挤爆显存 → KV 溢出到内存 → 解析慢到 ~10tok/s。
    # 开 FA 后 KV 不再 padding、attention 走 FA kernel，显存与速度双改善。
    "flash_attn": True,
}


@runtime_checkable
class LLMClient(Protocol):
    """service 层依赖的 client 协议。

    约定：返回 OpenAI 风格 dict，choices[0]["message"]["content"] 为生成文本。
    """

    def create_chat_completion(
        self,
        messages: list[dict],
        **kwargs: object,
    ) -> dict:
        """同步执行 chat completion，返回 OpenAI 风格 dict。

        多模态音频路径用 audio kwarg（GemmaClient 显式声明该形参，经 **kwargs 兼容本协议）：
        非 None 时 messages 含音频哨兵、client 把字节喂给 handler；纯文本 client 收到 audio 报错。
        """
        ...


class GemmaClient:
    """llama-cpp-python 封装，实现 LLMClient 协议。

    加载参数来自 0.C spike 选型（llm-backend-selection v0.4 §11.3）：
      n_ctx=8192, n_gpu_layers=-1（全 Metal 卸载）, seed=42, verbose=False。
    model_path 从环境变量 GEMMA_MODEL_PATH 读取，
    默认 models/gemma-4-E4B-it-Q4_K_M.gguf。

    不暴露内部 Llama 对象，调用方只能通过 create_chat_completion 接口，
    保证后续替换为 Ollama / vLLM 时只改 client.py。

    ⚠️ 并发不安全：多模态实例下 create_chat_completion 对 text+tools 请求临时换/还原
    `self._llm.chat_handler`（换原生 FunctionGemma formatter），并发调用会串 handler。
    依赖外层串行——生产恒经 LLMService 的 `_lock`（service.py:_worker），勿绕过 service 并发直调。
    """

    def __init__(
        self,
        model_path: str | None = None,
        mmproj_path: str | None = None,
        **llama_kwargs: object,
    ) -> None:
        from llama_cpp import Llama  # type: ignore[import]

        resolved_path = model_path or os.environ.get("GEMMA_MODEL_PATH", _DEFAULT_MODEL_PATH)
        params = {**_LLAMA_DEFAULTS, **llama_kwargs}
        # 显存吃紧时用 SOUNDSPEED_LLM_GPU_LAYERS 覆盖：0=纯 CPU（释放显存给 whisper/pyannote，
        # L2 非实时可接受）；-1=全 GPU。8GB 卡上三模型同跑会 OOM，本机建议设 0。
        gpu_env = os.environ.get("SOUNDSPEED_LLM_GPU_LAYERS")
        if gpu_env is not None and "n_gpu_layers" not in llama_kwargs:
            try:
                params["n_gpu_layers"] = int(gpu_env)
            except ValueError:
                pass

        # GPU 优先、显存占满走 CPU（用户 2026-06-07：占满走 CPU、没占满走 GPU）。
        # 主动查可用显存决定，不能只靠加载期 OOM 异常——Windows WDDM 显存超额不抛 OOM，
        # 而是把显存页换到内存：Gemma "在 GPU" 但奇慢、L2 卡死超时（实测 take_id=7）。
        if "n_gpu_layers" not in llama_kwargs:
            params["n_gpu_layers"] = self._resolve_gpu_layers(
                params.get("n_gpu_layers", -1), resolved_path
            )

        # mmproj_path 给定 → 升级为多模态单实例（text/audio/image 三入口共用，方案 A，spec §5.1）。
        # 文本（L2 + 文本 NP）也借道这一份 handler，保证文本输入统一格式化。
        self._handler: MultimodalGemma4Handler | None = None
        if mmproj_path is not None:
            from backend.llm.multimodal import MultimodalGemma4Handler  # noqa: PLC0415

            self._handler = MultimodalGemma4Handler(
                clip_model_path=mmproj_path, verbose=bool(params.get("verbose"))
            )
            params["chat_handler"] = self._handler
            # vision-ready：gemma4 vision non-causal 要 1120 image token 落单 ubatch，
            # 故 n_batch=n_ubatch=2048。audio/text 用不上但无害（caller 显式传则尊重）。
            params.setdefault("n_batch", 2048)
            params.setdefault("n_ubatch", 2048)

        # self._llm 标 Any：llama_cpp 是底层封装边界，不让其精确返回类型（CreateChatCompletion
        # Response | Iterator）泄漏到本层（否则 result: dict 赋值处处需 cast/ignore）。
        # GPU 优先、显存装不下自动回落 CPU（用户 2026-06-07：GPU 优先、占满走 CPU 保底、先保证跑通）：
        # 8GB 卡上 whisper+pyannote 已占满时 Gemma 上 GPU 会 OOM（Failed to load model /
        # CUBLAS_ALLOC_FAILED）→ 捕获后用 n_gpu_layers=0 重试；大显存设备 GPU 加载成功则不触发。
        self._llm: Any = self._load_with_cpu_fallback(Llama, resolved_path, params)

        # 多模态 handler 的 CHAT_FORMAT（继承 Gemma4ChatHandler）**不渲染工具声明**（无 FunctionGemma
        # <|tool> 宏），带 tools 的请求模型看不到工具 → auto 路径不调工具、forced 路径靠 grammar 兜。
        # 为「文本 + tools」请求另建 GGUF 内嵌的原生 FunctionGemma Jinja formatter（会渲染 tools），
        # create_chat_completion 按需临时换上（_lock 串行下无竞态）。音频/图像仍走多模态 handler。
        # 纯文本 GemmaClient（无 mmproj）的 Llama 本就用内嵌模板渲染 tools，无需此 handler，留 None。
        self._text_tool_handler: Any = None
        if self._handler is not None:
            self._text_tool_handler = self._build_native_tool_handler()

    @staticmethod
    def _resolve_gpu_layers(wanted: int, model_path: str) -> int:
        """想上 GPU（wanted≠0）时按**可用显存**决定：占满（free < 需求）→ 退 0（CPU）。

        为何主动查而非靠加载期 OOM 异常：Windows WDDM 显存超额不抛 OOM，而是把显存页换到
        系统内存 → Gemma "在 GPU" 但页换抖动、奇慢甚至卡死超时（实测 take_id=7 L2 60s 超时，
        且无 OOM/回落日志）。故 take 时 whisper+pyannote 已占 GPU，主动判定让 Gemma 走 CPU。
        需求估计 = gguf 大小 × 1.15 + 1GB（KV/计算缓冲）。无 CUDA/torch/查不到 → 保持 wanted。
        大显存设备 free 足 → 保持 GPU。
        """
        if wanted == 0:
            return 0
        try:
            import torch  # noqa: PLC0415

            if not torch.cuda.is_available():
                return wanted
            free, _total = torch.cuda.mem_get_info()
            need = os.path.getsize(model_path) * _VRAM_WEIGHT_FACTOR + _VRAM_RUNTIME_RESERVE_BYTES
            if free < need:
                logger.warning(
                    "可用显存 %.1fGB < Gemma 估计需求 %.1fGB → 走 CPU（GPU 已被 whisper/pyannote 占）",
                    free / 1e9, need / 1e9,
                )
                return 0
            logger.info("可用显存 %.1fGB 足够 → Gemma 上 GPU", free / 1e9)
            return wanted
        except Exception:  # noqa: BLE001 查显存失败不阻断，保持原意图
            return wanted

    @staticmethod
    def _load_with_cpu_fallback(llama_cls: Any, model_path: str, params: dict) -> Any:
        """加载 Llama；想上 GPU 但显存装不下 → 自动回落纯 CPU 重试。

        record 模式下 whisper+pyannote 已占满 8GB，Gemma 上 GPU 会 OOM（llama_cpp 抛
        'Failed to load model from file' / CUBLAS_ALLOC_FAILED）。捕获后用 n_gpu_layers=0
        重试，保证 L2 跑通（慢点可接受）。已是纯 CPU(0) 还失败 → 真错误（不是显存），照抛。
        大显存设备上首次 GPU 加载成功则不触发回落。用户 2026-06-07 定调：GPU 优先、CPU 保底。
        """
        wanted = params.get("n_gpu_layers", -1)
        try:
            return llama_cls(model_path=model_path, **params)
        except Exception as exc:  # noqa: BLE001 — llama_cpp 加载失败抛裸 Exception/ValueError
            if wanted == 0:
                raise  # 本就纯 CPU 还失败 → 非显存问题，照抛
            logger.warning(
                "Gemma 上 GPU 加载失败（n_gpu_layers=%s，可能显存不足），回落 CPU 重试：%s",
                wanted, exc,
            )
            return llama_cls(model_path=model_path, **{**params, "n_gpu_layers": 0})

    def _build_native_tool_handler(self) -> Any:
        """从 GGUF 内嵌 chat_template 建原生 FunctionGemma Jinja formatter（渲染 tools 声明）。

        多模态 handler 装上后 Llama 用其 CHAT_FORMAT（不含工具宏），故文本 + tools 请求需换回此
        原生 formatter。无内嵌模板（理论不该发生）返回 None，create_chat_completion 退回原 handler。
        """
        from llama_cpp.llama_chat_format import Jinja2ChatFormatter  # noqa: PLC0415

        # 整体兜底：取不到内嵌模板 / token（如测试用 FakeLlama，或非 gemma 模型）→ 返回 None，
        # create_chat_completion 退回原 handler（多模态/默认），不因此构造失败。
        try:
            template = self._llm.metadata.get("tokenizer.chat_template")
            if not template:
                return None

            # bos/eos 取自模型自身 token。必须 special=True：默认 detokenize 剥特殊 token 会返回空串，
            # 导致 Jinja 模板不 prepend <bos> → prompt 坏 → 模型立即吐 EOS（空输出）。空则兜底字面量。
            def _tok_text(token_id: int) -> str:
                try:
                    return self._llm.detokenize([token_id], special=True).decode("utf-8", "ignore")
                except Exception:  # noqa: BLE001
                    return ""

            bos = _tok_text(self._llm.token_bos()) or "<bos>"
            eos = _tok_text(self._llm.token_eos()) or "<eos>"
            return Jinja2ChatFormatter(
                template=template, bos_token=bos, eos_token=eos
            ).to_chat_handler()
        except Exception:  # noqa: BLE001
            return None

    def create_chat_completion(
        self,
        messages: list[dict],
        **kwargs: object,
    ) -> dict:
        # 音频路径：audio 经 kwargs 传入（保持签名与 LLMClient 协议一致，不破坏 StubClient 等的结构匹配）。
        audio = kwargs.pop("audio", None)
        if audio is not None:
            if self._handler is None:
                raise ModelUnavailableError("纯文本 GemmaClient 不支持音频推理（未挂多模态 handler）")
            if not isinstance(audio, (bytes, bytearray)):
                raise TypeError(f"audio 必须是 bytes，收到 {type(audio).__name__}")
            # 音频必须走多模态 handler（mtmd 上下文）；其 CHAT_FORMAT 不渲染 tools 但 voice NP
            # 走 forced tool_choice，grammar 兜工具，无碍。_lock 串行下设音频，推理后必复位避免串号。
            self._handler.set_pending_audio(bytes(audio))
            try:
                result: dict = self._llm.create_chat_completion(messages=messages, **kwargs)
            finally:
                self._handler.set_pending_audio(None)
            return result
        # 文本 + tools：多模态 handler 不渲染工具声明 → 临时换 GGUF 原生 FunctionGemma formatter。
        # _lock（LLMService 层）串行化所有 client 调用，故 chat_handler 的临时换/还原无竞态。
        # ⚠️ 3.x vision：未来 image content + tools 的请求不带 audio= kwarg，会落进本分支换原生
        #   formatter——但原生 formatter 不处理图像嵌入，须在此判据补 content-type 守卫（届时）。
        if self._text_tool_handler is not None and kwargs.get("tools"):
            prev = self._llm.chat_handler
            self._llm.chat_handler = self._text_tool_handler
            try:
                return self._llm.create_chat_completion(messages=messages, **kwargs)
            finally:
                self._llm.chat_handler = prev
        return self._llm.create_chat_completion(messages=messages, **kwargs)


class StubClient:
    """确定性 stub，不加载模型，供单元测试 fixture 使用。

    delay > 0 时调用 time.sleep 模拟同步阻塞推理耗时，
    service 层通过 asyncio.to_thread 包裹使其不阻塞事件循环。
    """

    def __init__(self, response: str = "stub response", delay: float = 0.0) -> None:
        self._response = response
        self._delay = delay

    def create_chat_completion(
        self,
        messages: list[dict],
        **kwargs: object,
    ) -> dict:
        if self._delay:
            time.sleep(self._delay)
        return {"choices": [{"message": {"content": self._response}}]}
