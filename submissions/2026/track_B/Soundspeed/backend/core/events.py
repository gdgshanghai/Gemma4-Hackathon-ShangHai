"""事件类型常量与 payload dataclass（contract C1 + C3）。

集中定义所有 WS topic 的事件类型常量与 payload。多数是 Orchestrator 内部事件
（contract C1）；少数是传输层事件（如 viewer.count，由 ConnectionManager 直接广播、
不经 orchestrator）。事件类型字符串值与 WS topic 命名完全一致。
Payload 使用 frozen=True 的 dataclass，防止 handler 间互相篡改。
"""
from __future__ import annotations

from dataclasses import dataclass

# ── 事件类型常量 ──────────────────────────────────────────────────────────────

# ASR 事件（contract C1）
ASR_PARTIAL_CH1 = "asr.partial.ch1"
ASR_PARTIAL_CH2 = "asr.partial.ch2"
ASR_FINAL_CH1 = "asr.final.ch1"
ASR_FINAL_CH2 = "asr.final.ch2"

# Take 事件（contract C3：FastAPI 调用 publish）
TAKE_START = "take.start"
TAKE_END = "take.end"
TAKE_CHANGED = "take.changed"

# LLM 状态事件（1.J-1.L：驱动前端 LLM chip 黄点 Loading）
LLM_STATUS = "llm.status"

# Diarization 回填完成（通知前端刷新 segments 的说话人标签）
TAKE_SEGMENTS_UPDATED = "take.segments.updated"

# take.end 后处理进度（前端 Live 框状态条：分离说话人 / 生成摘要 / 完成 / 出错）
TAKE_PROCESSING = "take.processing"

# 其他事件（本 ticket 只定义常量，不注册 handler）
MANUAL_MARK = "manual.mark"
QUERY_REQUEST = "query.request"
SCRIPT_UPLOAD = "script.upload"

# 2.C 新增事件
TAKE_DELETED = "take.deleted"
SCENE_CHANGED = "scene.changed"

# 音频设备 warning（设备拔走时通知前端）
DEVICE_WARNING = "device.warning"

# 实时 RMS 电平（采集线程每 chunk 推，驱动前端电平条）
AUDIO_LEVEL = "audio.level"

# 在线观看数（WS 连接建立 / 断开时 ConnectionManager 广播，驱动前端 header 眼睛计数）
VIEWER_COUNT = "viewer.count"

# QP 查询管线（QP route 直接调 cm.broadcast，不经 orchestrator.publish；topic 带动态 conn_id）
QP_ANSWER = "qp.answer"  # 实际广播 topic 为 f"{QP_ANSWER}.{conn_id}"，客户端按前缀过滤


# ── Payload dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AsrPartialPayload:
    """asr.partial.ch1 / asr.partial.ch2 的 payload。

    start_frame / end_frame 单位为毫秒（秒 × 1000 取整），字段名沿用历史命名。
    """

    text: str
    start_frame: int
    end_frame: int
    speaker: str | None
    take_id: int | None
    is_partial: bool


@dataclass(frozen=True)
class AsrFinalPayload:
    """asr.final.ch1 / asr.final.ch2 的 payload。

    start_frame / end_frame 单位为毫秒（秒 × 1000 取整），字段名沿用历史命名。
    """

    text: str
    start_frame: int
    end_frame: int
    speaker: str | None
    take_id: int | None
    is_partial: bool


@dataclass(frozen=True)
class TakeStartPayload:
    """take.start 的 payload（contract C3）。

    speaker_ids：本 take 在场的已注册演员 id 列表（diarization 回填只在这些演员里匹配；
    空 → 全部出匿名说话人N）。
    """

    scene_id: int
    shot: str | None
    start_ts: float
    speaker_ids: tuple[int, ...] = ()
    # 待录 take 的显式号（用户在底部 Take 弹窗手动指定）。None → 后端按 (scene,shot) 自动 MAX+1。
    take_number: int | None = None


@dataclass(frozen=True)
class TakeEndPayload:
    """take.end 的 payload。"""

    end_ts: float


@dataclass(frozen=True)
class ManualMarkPayload:
    """manual.mark 的 payload。"""

    mark_type: str
    note: str | None
    ts: float


@dataclass(frozen=True)
class QueryRequestPayload:
    """query.request 的 payload。"""

    connection_id: str
    query: str


@dataclass(frozen=True)
class ScriptUploadPayload:
    """script.upload 的 payload。"""

    scene_id: int
    raw_text: str


@dataclass(frozen=True)
class TakeChangedPayload:
    """take.changed 的 payload（1.H L2 pipeline 完成后 publish）。

    status 取值与 takes.status 一致：'pass' | 'ng' | 'keep' | 'tbd'。
    script_diff=None 表示 L2 未完成或失败（降级状态）。
    """

    take_id: int
    scene_id: int
    take_number: int
    status: str
    script_diff: dict | None


@dataclass(frozen=True)
class TakeSegmentsUpdatedPayload:
    """take.segments.updated 的 payload。

    diarization 回填完成后 publish，通知前端 refetch GET /takes/{take_id}。
    """

    take_id: int
    scene_id: int


@dataclass(frozen=True)
class TakeProcessingPayload:
    """take.processing 的 payload（take.end 后处理进度，驱动前端 Live 框状态条）。

    phase 取值：
      'diarizing'    正在分离说话人（pyannote 跑批，较慢）
      'summarizing'  正在生成场记摘要（Gemma L2）
      'done'         后处理完成（前端清除状态条）
      'error'        出错，detail 含原因
    detail：错误信息或附加说明（非 error 时通常 None）。
    """

    take_id: int
    scene_id: int
    phase: str
    detail: str | None = None


@dataclass(frozen=True)
class LlmStatusPayload:
    """llm.status 的 payload（1.J-1.L：驱动前端 LLM chip 状态）。

    state 取值：
      'idle'        空闲（L2 任务完成后）
      'downloading' 模型文件不在本地，正在通过 huggingface_hub 下载（可能数分钟）
      'loading'     模型文件存在，首次加载权重到内存/Metal（数秒）
      'running'     模型已加载，正在推理中
    task_type / take_id 在 idle 时可为 None。
    """

    state: str          # "idle" | "downloading" | "loading" | "running"
    task_type: str | None
    take_id: int | None

# Note 事件（4.x NP Pipeline）
NOTE_PROCESSED = "note.processed"


@dataclass(frozen=True)
class NoteProcessedPayload:
    """note.processed 的 payload：NP Pipeline 归置完成后发布。"""

    event_id: int
    take_id: int
    category: str
    content: str
    ts: float
    # 前端乐观 pending 的去重键：原样回传，content 被 LLM 改写、ts 不同源也能精确移除对应 pending。
    client_id: str | None = None


# Note 失败兜底（4.I）
NOTE_FAILED = "note.failed"


@dataclass(frozen=True)
class NoteFailedPayload:
    """note.failed 的 payload：NP Pipeline 失败时发布，让前端把对应 pending 转失败态而非永久卡死。

    reason 只列机制上可检测的失败：
      - take_not_found    —— LLM 返回的 take_id 不存在（insert_note 撞 FK）。
      - parse_error       —— LLM 输出非合法 JSON / 字段缺失（NPParseError）。
      - timeout           —— infer 排队 + 推理超时（asyncio.TimeoutError）。
      - model_unavailable —— 多模态模型不可用（mmproj 缺失/下载失败退纯文本，或 mtmd 自检失败）。
    asr_unclear（音频没听清）需模型自报机制，非后端可直接判定，MVP 不发。
    upload_failed 由前端网络/上传层失败时自行置位，不经后端。
    """

    reason: str
    ts: float
    # 前端乐观 pending 的去重键：定位要标失败的那条 pending；缺失时前端不误标，仅记日志。
    client_id: str | None = None


@dataclass(frozen=True)
class TakeDeletedPayload:
    """take.deleted 的 payload（2.C）。"""

    take_id: int
    scene_id: int


@dataclass(frozen=True)
class SceneChangedPayload:
    """scene.changed 的 payload（2.C）。"""

    scene_id: int
    scene_code: str
    is_active: bool


@dataclass(frozen=True)
class DeviceWarningPayload:
    """device.warning 的 payload（设备拔走 fallback 通知前端）。

    message: 人类可读描述。
    device_name: 保存的设备名（已不在场）。
    """

    message: str
    device_name: str


@dataclass(frozen=True)
class AudioLevelPayload:
    """audio.level 的 payload（采集线程每 chunk 推，驱动前端电平条）。

    rms: ch1 当前 chunk 的 RMS 电平，归一化到 [0, 1]。
         计算式：clamp(sqrt(mean((x/32768)^2)), 0, 1)，可乘小增益便于观察。
    """

    rms: float


@dataclass(frozen=True)
class ViewerCountPayload:
    """viewer.count 的 payload（在线观看数）。

    count: 当前连着 /ws 的客户端总数（含场记自己这台）。WS 连接建立 / 断开后由
           ConnectionManager 广播，前端 header 眼睛据此显示。
    """

    count: int


@dataclass(frozen=True)
class QpAnswerPayload:
    """qp.answer.{conn_id} 的 payload（QP 完成后广播，客户端按 conn_id 认领）。

    client_id：发起这条 query 的前端乐观去重键。文本 query 由 /notes 调度分支透传（队列模型
    据此把答案落到对应那条 qaItem）；语音 query 由 voice dispatch 透传（精确撤掉对应语音 pending）。
    直连 /api/v1/query demo 不带，默认 None。与 voice-qp 共享同一字段契约。
    """

    connection_id: str
    answer_text: str
    client_id: str | None = None


def broadcast_qp_answer(cm, conn_id: str, answer_text: str, *, client_id: str | None = None) -> None:
    """广播 qp.answer.{conn_id}（topic + payload 的单一来源）。cm 鸭子类型，避免 events.py 反向依赖连接层。"""
    cm.broadcast(f"{QP_ANSWER}.{conn_id}", QpAnswerPayload(connection_id=conn_id, answer_text=answer_text, client_id=client_id))


# Gemma tool-call 轨迹实时推送（#51 tool.call）
TOOL_CALL = "tool.call"


@dataclass(frozen=True)
class ToolCallPayload:
    """tool.call 的 payload v2：Gemma agent 每次 function-calling 请求侧事件 + 元数据。

    只含请求侧（工具名+参数）与推理元数据，不含工具执行返回结果，不含 messages/memory。

    tool_id：tool_calls[0]["id"]（llama-cpp 可能缺失，给 None）。
    tool_type：tool_calls[0]["type"]，通常 "function"（可能缺失，给 None）。
    tool_name：tool_calls[0]["function"]["name"]。
    arguments：tool_calls[0]["function"]["arguments"]，原样透传 JSON 字符串，前端负责美化。
    finish_reason：result_dict["choices"][0].get("finish_reason")（可能缺失，给 None）。
    model：result_dict.get("model")（llama-cpp 不保证带，给 None）。
    prompt_tokens：result_dict["usage"]["prompt_tokens"]（usage 整块可能缺失，给 None）。
    completion_tokens：result_dict["usage"]["completion_tokens"]（同上）。
    total_tokens：result_dict["usage"]["total_tokens"]（同上）。
    available_tools：本次推理可调工具名列表，从 gen_kwargs["tools"] 抽 function.name；缺失给 []。
    tool_choice：gen_kwargs["tool_choice"] 规整后的字符串：dict {function:{name}} → 那个 name；
                 "auto"/"none"/"required" 原样；缺失给 None。
    ts：time.time() epoch 秒（float）。
    """

    task_type: str
    tool_name: str
    arguments: str
    ts: float
    tool_id: str | None = None
    tool_type: str | None = None
    finish_reason: str | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    available_tools: tuple[str, ...] = ()
    tool_choice: str | None = None


def broadcast_tool_call(
    cm,
    task_type: str,
    tool_name: str,
    arguments: str,
    *,
    ts: float,
    tool_id: str | None = None,
    tool_type: str | None = None,
    finish_reason: str | None = None,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    available_tools: tuple[str, ...] = (),
    tool_choice: str | None = None,
) -> None:
    """广播 tool.call（全局，不带 conn_id）。cm 鸭子类型，避免 events.py 反向依赖连接层。"""
    cm.broadcast(
        TOOL_CALL,
        ToolCallPayload(
            task_type=task_type,
            tool_name=tool_name,
            arguments=arguments,
            ts=ts,
            tool_id=tool_id,
            tool_type=tool_type,
            finish_reason=finish_reason,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            available_tools=available_tools,
            tool_choice=tool_choice,
        ),
    )
