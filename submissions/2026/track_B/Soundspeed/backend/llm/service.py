"""LLMService：单例 + asyncio.PriorityQueue + asyncio.Lock + worker task。

设计依据：
  llm-service-design v1.1 §决策 1-3
  1.F 实施 spec §3-§4
  1.J-1.L-frontend-integration v0.3：模型缺失时自动下载 + downloading 状态

公共 API：
  resolve_model_path(download) -> str | None   模型路径解析器（模块级函数）
  get_service() -> LLMService                  工厂函数，返回模块级单例
  _reset_service() -> None                     仅供测试使用，清空单例
  LLMService.infer(...)                        统一推理入口
  LLMService.aclose()                          关闭 worker，释放资源
  LLMService.ensure_model_ready()              异步解析+下载模型路径（在 worker thread）
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from backend.llm.config import TASK_CONFIG

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.llm.client import LLMClient

logger = logging.getLogger(__name__)

# gen_kwargs 中过滤掉的元字段（不传给 client）
_META_KEYS = frozenset({"priority", "_reserved", "system"})

# HF 模型坐标（与 client.py 的默认路径对应）
_HF_REPO_ID = "unsloth/gemma-4-E4B-it-GGUF"
_HF_FILENAME = "gemma-4-E4B-it-Q4_K_M.gguf"
# 多模态投影器（vision gemma4v + audio gemma4a，同仓），4.J 单实例多模态用
_HF_MMPROJ_FILENAME = "mmproj-F16.gguf"


def _text_only() -> bool:
    """SOUNDSPEED_LLM_TEXT_ONLY=1 → 只加载纯文本 Gemma，跳过 mmproj（不解析/不下载/不占显存）。

    用于「只做文本」的运行档（剧本解析/L2/NP 文本/导入档）：8GB 卡上 base+mmproj+KV 易撑爆，
    且省掉对 mmproj 的联网校验/下载。视觉（照片 OCR）路径需要 mmproj，勿设此开关。
    """
    return os.environ.get("SOUNDSPEED_LLM_TEXT_ONLY") == "1"


def _resolve_hf_path(env_var: str, filename: str, download: bool) -> str | None:
    """解析 HF 仓库内某文件的本地路径，优先级：本地 env > HF cache > 下载 > None。

    1. `env_var` 指向的文件存在 → 直接返回，不调用任何 HF 函数。
    2. `try_to_load_from_cache` 命中（返回 str）→ 返回缓存路径。
       注意：返回值可能是哨兵对象（truthy 非 str），用 isinstance(result, str) 判。
    3. download=True → `hf_hub_download` 触发下载并返回路径。
    4. 否则 → None（不可用，调用方应发 downloading 再 await ensure_model_ready）。

    同步函数，在 worker thread 内调用（asyncio.to_thread），不阻塞 event loop。
    base gguf 与 mmproj 同仓（_HF_REPO_ID），仅 env_var / filename 不同。
    """
    env_path = os.environ.get(env_var)
    if env_path and Path(env_path).exists():
        return env_path

    import huggingface_hub  # noqa: PLC0415

    cache_result = huggingface_hub.try_to_load_from_cache(repo_id=_HF_REPO_ID, filename=filename)
    if isinstance(cache_result, str):
        return cache_result  # 缓存命中

    if download:
        return huggingface_hub.hf_hub_download(repo_id=_HF_REPO_ID, filename=filename)

    return None


def resolve_model_path(download: bool) -> str | None:
    """解析 base gguf 路径（env GEMMA_MODEL_PATH > HF cache > 下载）。"""
    return _resolve_hf_path("GEMMA_MODEL_PATH", _HF_FILENAME, download)


def resolve_mmproj_path(download: bool) -> str | None:
    """解析多模态投影器 mmproj-F16.gguf 路径（env GEMMA_MMPROJ_PATH > HF cache > 下载）。"""
    return _resolve_hf_path("GEMMA_MMPROJ_PATH", _HF_MMPROJ_FILENAME, download)


@dataclass
class _InferPayload:
    """worker 内部处理的推理负载。"""

    messages: list[dict]
    task_type: str
    gen_kwargs: dict
    # function calling（main #25）：True 时 worker 取 tool_calls[0] 而非 content。
    want_tool_call: bool = False
    # 语音 NP（4.J）：非 None 时随 messages 一并喂多模态 client；文本/tool 路径恒为 None。
    audio: bytes | None = None


class LLMService:
    """LLM 推理单例。

    不直接实例化，通过 get_service() 获取。

    内部结构：
    - _queue: asyncio.PriorityQueue，元素 (priority, counter, fut, payload)
    - _lock: asyncio.Lock，串行化 client 调用
    - _worker_task: 长运行 asyncio.Task，从队列取任务逐个推理
    - _client: LLMClient 实例，首次 infer 时 lazy 初始化
    - _model_path: 已解析的模型路径（ensure_model_ready 后填充）
    - _counter: itertools.count()，保证相同 priority 下 FIFO
    """

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue[
            tuple[int, int, asyncio.Future, _InferPayload]
        ] = asyncio.PriorityQueue()
        self._lock: asyncio.Lock = asyncio.Lock()
        self._worker_task: asyncio.Task[None] | None = None
        self._client: LLMClient | None = None
        self._model_path: str | None = None
        self._mmproj_path: str | None = None
        self._counter = itertools.count()
        self._tool_call_tap: Callable[[str, dict, dict, dict], None] | None = None

    def set_tool_call_tap(self, callback: Callable[[str, dict, dict, dict], None] | None) -> None:
        """注册（或清除）tool-call tap 回调。

        callback(task_type, tool_call_dict, gen_kwargs, result_dict) 在每次
        want_tool_call=True 推理成功 set_result 之后立即调用。
        - task_type：_InferPayload.task_type
        - tool_call_dict：tool_calls[0]（完整 dict，含 id/type/function）
        - gen_kwargs：_InferPayload.gen_kwargs（含 tools/tool_choice 等）
        - result_dict：llama-cpp 返回的完整 dict（含 choices/usage/model 等）
        tap 异常不影响推理主流程（被 try/except 保护）。传 None 清除已注册的 tap。
        """
        self._tool_call_tap = callback

    @property
    def model_loaded(self) -> bool:
        """首次 infer 前（_ensure_client 未调用）为 False，加载后为 True。

        供 Orchestrator 区分 loading（首次权重加载）vs running（后续推理）。
        """
        return self._client is not None

    @property
    def model_present(self) -> bool:
        """模型是否可用（本地或 HF cache 存在），同步检查，不触发下载。

        - _client 已加载 → True（已就绪）。
        - resolve_model_path(download=False) 非 None → True（文件存在，下次加载不需下载）。
        - 否则 → False（需要先 await ensure_model_ready() 再推理）。
        """
        if self._client is not None:
            return True
        return resolve_model_path(download=False) is not None

    async def ensure_model_ready(self) -> None:
        """在 worker thread 内解析（或下载）模型路径，存入 _model_path。

        download=True：缓存未命中时触发 hf_hub_download，阻塞直到下载完成。
        不触发模型加载（加载在 _ensure_client/_worker 内完成）。

        方案 A：单实例升多模态，mmproj 与 base 一并就绪。mmproj 下载失败（离线/缺文件）
        不阻塞启动——退回纯文本（音频/图像不可用，L2/文本 NP 照常）。
        """
        self._model_path = await asyncio.to_thread(resolve_model_path, True)
        if _text_only():
            self._mmproj_path = None  # 纯文本档：不解析/不下载 mmproj
            return
        try:
            self._mmproj_path = await asyncio.to_thread(resolve_mmproj_path, True)
        except Exception:  # noqa: BLE001  下载失败容错：退纯文本，不崩启动
            self._mmproj_path = None

    def _ensure_worker(self) -> None:
        """Lazy 启动 worker task，只启动一次。

        asyncio 事件循环单线程语义保证此处无竞态：
        同一 event loop 中 infer 协程是顺序执行的，不会出现两个协程
        同时通过 self._worker_task is None 判断的情况。
        """
        if self._worker_task is None:
            self._worker_task = asyncio.get_running_loop().create_task(self._worker())

    def _ensure_client(self) -> LLMClient:
        """Lazy 初始化 client（首次推理时加载模型）。

        model_path 优先用 _model_path（ensure_model_ready 已填充），
        回退 resolve_model_path(False)（本地/cache），最后 None（GemmaClient 自行解析）。
        """
        if self._client is None:
            from backend.llm.client import GemmaClient  # noqa: PLC0415

            path = self._model_path or resolve_model_path(download=False)
            # 多模态单实例（方案 A，spec §5.1）：mmproj 优先用已就绪路径 / cache；未缓存则
            # **运行时自动下载**（在 worker thread 内，阻塞可接受）——修部署态缺口：base 已缓存而
            # mmproj 未缓存的现存安装（升级路径），首条音频前自动补 mmproj 升多模态，而非静默退纯文本
            # 致语音永久失败。下载失败（离线）→ 退纯文本，音频路径随后由 note.failed(model_unavailable) 兜底。
            mmproj = self._mmproj_path
            if mmproj is None and not _text_only():
                # resolve_mmproj_path(download=True) 内部先查 env/cache，未命中才真下载，
                # 故无需先单独探一次 download=False（会多一次 HF cache 查询）。
                try:
                    mmproj = resolve_mmproj_path(download=True)
                except Exception:  # noqa: BLE001  下载失败容错：退纯文本，不崩
                    logger.warning("mmproj 自动下载失败，退纯文本（音频/图像暂不可用）", exc_info=True)
                    mmproj = None
                self._mmproj_path = mmproj
            self._client = GemmaClient(model_path=path, mmproj_path=mmproj)
        return self._client

    async def _submit(
        self,
        messages: list[dict],
        task_type: str,
        priority: int | None,
        timeout: float | None,
        want_tool_call: bool,
        audio: bytes | None = None,
        tool_choice: str | dict | None = None,
    ) -> asyncio.Future:
        """infer / infer_tool / infer_voice 共享：校验入参、组装 payload、入队、启动 worker。

        返回尚未 await 的 Future；调用方负责 asyncio.wait_for(fut, timeout)。
        三条路径校验完全相同，区别仅在 payload.want_tool_call（取 content vs tool_calls）
        与 payload.audio（语音 NP 随 messages 一并喂多模态 client，文本/tool 恒为 None）。

        Raises:
            ValueError: task_type 不在 TASK_CONFIG，或 priority/timeout 非法。
            NotImplementedError: task_type 标 _reserved=True。
        """
        if task_type not in TASK_CONFIG:
            raise ValueError(f"未知的 task_type: {task_type!r}，合法值: {list(TASK_CONFIG)}")
        cfg = TASK_CONFIG[task_type]
        if cfg.get("_reserved"):
            raise NotImplementedError(
                f"task_type={task_type!r} 标记为 _reserved=True，MVP 阶段不可用"
            )
        # priority 为 None 时从 TASK_CONFIG 取默认值
        if priority is None:
            priority = cfg["priority"]
        if priority not in (1, 2, 3):
            raise ValueError(f"priority 必须为 1/2/3，收到: {priority!r}")
        if timeout is not None and timeout <= 0:
            raise ValueError(f"timeout 必须为正数或 None，收到: {timeout!r}")

        # 从 TASK_CONFIG 提取 gen_kwargs，过滤掉元字段
        gen_kwargs = {k: v for k, v in cfg.items() if k not in _META_KEYS}

        # 按调用覆盖 tool_choice（QP forced 跳动态强制某工具名，spec §5.4）。
        # None = 不覆盖，沿用 TASK_CONFIG 的静态 tool_choice（默认行为不变）。
        if tool_choice is not None:
            gen_kwargs["tool_choice"] = tool_choice

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        payload = _InferPayload(
            messages=messages,
            task_type=task_type,
            gen_kwargs=gen_kwargs,
            want_tool_call=want_tool_call,
            audio=audio,
        )
        counter = next(self._counter)
        await self._queue.put((priority, counter, fut, payload))

        # 确保 worker 已启动（lazy）
        self._ensure_worker()
        return fut

    async def infer(
        self,
        messages: list[dict],
        task_type: str,
        priority: int | None = None,
        timeout: float | None = 30.0,
        tool_choice: str | dict | None = None,
    ) -> str:
        """统一推理入口。

        Args:
            messages: 标准 chat 消息列表，每个元素有 "role" 和 "content" 键。
            task_type: TASK_CONFIG 中的合法 key。
            priority: 1=用户态, 2=普通, 3=批处理。None 时从 TASK_CONFIG[task_type]["priority"] 取默认值。
                      超出范围抛 ValueError。
            timeout: 最大等待时间（含排队 + 推理）秒数，None 表示不超时。
                     传 0 或负数抛 ValueError。
            tool_choice: 可选，按调用覆盖 TASK_CONFIG 的 tool_choice；None 沿用配置。

        Returns:
            LLM 生成的文本字符串（choices[0]["message"]["content"]）。

        Raises:
            ValueError: task_type 不在 TASK_CONFIG，或 priority/timeout 非法。
            NotImplementedError: task_type 标 _reserved=True（当前为 agent_init）。
            asyncio.TimeoutError: 排队 + 推理总耗时超 timeout。
            RuntimeError: client.create_chat_completion 内部崩溃时通过 Future 回传。
            LookupError: client 返回 dict 缺少 choices[0]["message"]["content"]。
        """
        fut = await self._submit(
            messages, task_type, priority, timeout, want_tool_call=False, audio=None,
            tool_choice=tool_choice,
        )
        # 等待结果，支持超时。
        # 不用 shield：超时后 wait_for 自动 cancel(fut)，
        # worker 下一轮取出时 fut.cancelled() 为 True，直接跳过，节省推理资源。
        return await asyncio.wait_for(fut, timeout=timeout)

    async def infer_voice(
        self,
        messages: list[dict],
        audio: bytes,
        task_type: str,
        priority: int | None = None,
        timeout: float | None = 60.0,
    ) -> str:
        """音频推理入口（语音 NP，4.J）。

        与 infer 共用 _client + _lock + priority 队列、同一调度（不开第二实例），仅多透 audio：
        字节随 payload 喂多模态 client，由 handler 从音频哨兵取回；messages 内须含音频哨兵
        content（np_note 组装，§5.3）。音频编码 + 推理略慢，默认 timeout 放宽到 60s。

        Raises 与 infer 一致；另若 client 非多模态（未挂 handler）会在推理时抛 ModelUnavailableError
        （经 Future 回传）。

        tool_choice 固定来自 TASK_CONFIG（note_struct 静态 forced），
        不参与 QP 动态循环、不支持按调用覆盖。
        """
        fut = await self._submit(
            messages, task_type, priority, timeout, want_tool_call=False, audio=audio
        )
        return await asyncio.wait_for(fut, timeout=timeout)

    async def infer_tool(
        self,
        messages: list[dict],
        task_type: str,
        priority: int | None = None,
        timeout: float | None = 30.0,
        tool_choice: str | dict | None = None,
    ) -> dict:
        """tool-call 推理入口。

        走与 infer 相同的 PriorityQueue / Lock / worker，区别在于：
        - payload.want_tool_call=True，worker 取 tool_calls[0] 而非 content
        - 返回 tool_calls[0] 字典，包含 type/function/id 字段

        Args:
            messages: 标准 chat 消息列表。
            task_type: TASK_CONFIG 中的合法 key（须含 tools/tool_choice 字段）。
            priority: 同 infer，None 时从 TASK_CONFIG 取默认值。
            timeout: 最大等待时间（含排队 + 推理）秒数。
            tool_choice: 可选，按调用覆盖 TASK_CONFIG 的 tool_choice；None 沿用配置。

        Returns:
            tool_calls[0] 字典，含 type、function（name + arguments JSON 字符串）。

        Raises:
            ValueError: task_type 不在 TASK_CONFIG，或 priority/timeout 非法。
            NotImplementedError: task_type 标 _reserved=True。
            asyncio.TimeoutError: 超时。
            LookupError: client 返回的 tool_calls 缺失或为空。
        """
        fut = await self._submit(
            messages, task_type, priority, timeout, want_tool_call=True,
            tool_choice=tool_choice,
        )
        return await asyncio.wait_for(fut, timeout=timeout)

    async def infer_voice_tool(
        self,
        messages: list[dict],
        audio: bytes,
        task_type: str,
        priority: int | None = None,
        timeout: float | None = 60.0,
        tool_choice: dict | str | None = None,
    ) -> dict:
        """音频 + tool-call 推理入口（语音 forced tool-call，hop B）。

        = infer_voice（透 audio）∩ infer_tool（取 tool_calls[0]）：_submit 同时带 audio +
        want_tool_call=True（两者正交）。多模态 handler 在 __call__ 里先把音频 eval 进 KV，
        再按 forced tool_choice 的 schema grammar 约束生成（输入/输出两阶段不冲突，源码实证）。
        messages 须含音频哨兵（run_np_voice 组装）。返回 tool_calls[0] dict。

        Args:
            messages: 标准 chat 消息列表，须含 AUDIO_SENTINEL content part。
            audio: 原始音频字节（wav/pcm），随 messages 一并喂多模态 client。
            task_type: TASK_CONFIG 中的合法 key（须含 tools/tool_choice 字段）。
            priority: 1=用户态, 2=普通, 3=批处理。None 时从 TASK_CONFIG 取默认值。
            timeout: 最大等待时间（含排队 + 推理）秒数，None 表示不超时。
            tool_choice: 可选，按调用覆盖 TASK_CONFIG 的 tool_choice；None 沿用配置。
                         hop B forced 取参时传入具体工具名，镜像 infer_tool 行为。
        """
        fut = await self._submit(
            messages,
            task_type=task_type,
            priority=priority,
            timeout=timeout,
            want_tool_call=True,
            audio=audio,
            tool_choice=tool_choice,
        )
        return await asyncio.wait_for(fut, timeout=timeout)

    async def aclose(self) -> None:
        """关闭 worker task，清空队列中未处理的 Future。

        若 worker 从未启动（lazy init 且 infer 从未被调用），直接返回（no-op）。
        FastAPI lifespan 负责在应用关闭时调用此方法。
        """
        if self._worker_task is None:
            return

        self._worker_task.cancel()
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass

        # 清空队列中未处理的 Future
        while not self._queue.empty():
            try:
                _, _, fut, _ = self._queue.get_nowait()
                if not fut.done():
                    fut.set_exception(asyncio.CancelledError())
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break

        self._worker_task = None

    async def _worker(self) -> None:
        """长运行 worker：串行从队列取任务，逐个推理。

        单线程 asyncio 语义保证无竞态；只启动一次（见 _ensure_worker）。
        _ensure_client 改为 await asyncio.to_thread 调用，首次加载模型权重在 worker thread
        内进行，不阻塞 event loop（1.F advisor 标记的 loop-freeze 修复）。
        worker 异常处理：捕获所有异常并通过 fut.set_exception 回传，
        worker 本身不退出。只有 asyncio.CancelledError 允许穿透（触发 task 退出）。
        """
        while True:
            priority, counter, fut, payload = await self._queue.get()
            # 超时后 fut 被 cancel，跳过此任务
            if fut.cancelled():
                self._queue.task_done()
                continue
            try:
                # to_thread：_ensure_client 内的 GemmaClient() 会加载权重（同步阻塞），
                # 放进 worker thread 避免首次加载冻结 event loop。
                client = await asyncio.to_thread(self._ensure_client)
                # 音频仅语音路径携带；文本路径不传 audio kwarg（保持文本调用形状不变）。
                audio_kwarg = {"audio": payload.audio} if payload.audio is not None else {}
                async with self._lock:
                    result_dict = await asyncio.to_thread(
                        client.create_chat_completion,
                        messages=payload.messages,
                        **audio_kwarg,
                        **payload.gen_kwargs,
                    )
                if payload.want_tool_call:
                    # tool_call 路径：取 choices[0]["message"]["tool_calls"][0]
                    # 显式 raise 的 LookupError 不被下面 (KeyError, IndexError, TypeError)
                    # 捕获（它们都是 LookupError 子类，反向不成立），直接穿透到 set_exception。
                    try:
                        tool_calls = result_dict["choices"][0]["message"].get("tool_calls")
                    except (KeyError, IndexError, TypeError) as e:
                        raise LookupError(
                            f"client 返回 dict 格式异常，缺少 tool_calls: {e}"
                        ) from e
                    if not tool_calls:
                        raise LookupError(
                            "client 返回 dict 缺少 tool_calls 或 tool_calls 为空列表"
                        )
                    if not fut.done():
                        fut.set_result(tool_calls[0])
                        if self._tool_call_tap is not None:
                            try:
                                self._tool_call_tap(
                                    payload.task_type,
                                    tool_calls[0],
                                    payload.gen_kwargs,
                                    result_dict,
                                )
                            except Exception:
                                logger.warning(
                                    "tool_call_tap 异常（不影响推理主流程）",
                                    exc_info=True,
                                )
                else:
                    # content 路径
                    try:
                        choice = result_dict["choices"][0]
                        # content 可能为 None（如下方护栏处理的 forced tool_choice 误用）。
                        text: str | None = choice["message"]["content"]
                    except (KeyError, IndexError, TypeError) as e:
                        raise LookupError(
                            f"client 返回 dict 格式异常，缺少 choices[0]['message']['content']: {e}"
                        ) from e
                    # 护栏：对配了强制 tool_choice 的 task 误走 infer（content 路径）时，
                    # content=None 且 finish_reason="tool_calls"，旧逻辑会静默 set_result(None)
                    # 让下游静默失败。这里明确报错，引导改用 infer_tool 取 tool_calls。
                    if text is None and choice.get("finish_reason") == "tool_calls":
                        raise LookupError(
                            "content 为 None 且 finish_reason='tool_calls'：该 task 配置了"
                            "强制 tool_choice，应调用 infer_tool 而非 infer"
                        )
                    if not fut.done():
                        fut.set_result(text)
            except asyncio.CancelledError:
                # worker 被取消，清理后退出
                if not fut.done():
                    fut.set_exception(asyncio.CancelledError())
                raise
            except Exception as exc:
                if not fut.done():
                    fut.set_exception(exc)
            finally:
                self._queue.task_done()


# 模块级单例
_service: LLMService | None = None


def get_service() -> LLMService:
    """返回 LLMService 单例，首次调用时创建实例。

    不触发模型加载（lazy init，首次 infer 时才初始化 client 和 worker）。
    """
    global _service
    if _service is None:
        _service = LLMService()
    return _service


def _reset_service() -> None:
    """仅供测试使用，清空模块级单例，避免测试间单例污染。

    生产代码不调用此函数。
    """
    global _service
    _service = None
