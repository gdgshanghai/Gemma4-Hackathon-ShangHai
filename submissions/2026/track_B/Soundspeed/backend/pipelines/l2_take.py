"""L2 Pipeline：台词 diff 检测（ticket 1.G）。

根据 ch1 转录记录与剧本台词，调用 LLM 生成逐行对比结果（script_diff）。

公共 API：
  L2Input       输入 dataclass（frozen）
  L2Output      输出 dataclass（frozen）
  LineMatch     逐行比对结果（frozen）
  L2ParseError  LLM 输出解析失败异常
  run_l2_take   纯异步函数，执行一次 L2 Pipeline

设计依据：
  docs/specs/2026-05-27-l2-pipeline.md §3-§7
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from backend.llm.config import TASK_CONFIG
from backend.pipelines.l2_constants import _VALID_DIFF_TYPES  # noqa: F401  # re-exported

if TYPE_CHECKING:
    from backend.llm.service import LLMService


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class L2ParseError(Exception):
    """LLM 输出解析失败。

    cause 串联原始异常（json.JSONDecodeError / KeyError 等），
    调用方可通过 e.cause 取原始异常细节。
    """

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


# ---------------------------------------------------------------------------
# 数据类型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineMatch:
    """单行台词比对结果。

    diff_type 取值：match / missing / substitution / insertion。
    insertion 类型 line_no 固定为 -1（无对应剧本行）。
    seg_idx：本行对应的转录段下标（truncate 后列表，0-indexed），用于把"实际说的"
        原文逐字 join 进并置文档（_build_juxtaposition）。漏说 → 空 tuple。
    """

    line_no: int
    diff_type: str
    detail: str | None
    seg_idx: tuple[int, ...] = ()


@dataclass(frozen=True)
class JuxtaLine:
    """并置文档的一行：剧本台词 ‖ 实际说的（缺口③ 的核心交付）。

    以剧本行为骨架逐行排列，把对齐到的转录原文贴到右侧；剧本有而没说 →
    spoken_text=None；实际多说（剧本无此行）→ line_no=-1、script_text=None。
    diff_type 是 line_matches 的副产物（前端这版不展示），无对应匹配时为 None。
    """

    line_no: int                # 剧本行号；-1 = insertion（剧本无此行）
    character: str | None       # 角色（剧本侧）；insertion 为 None
    script_text: str | None     # 剧本台词；insertion 为 None
    spoken_text: str | None     # 实际说的（转录原文，逐字）；漏说为 None
    speaker: str | None         # 谁说的（转录 speaker=角色名/说话人N）；漏说为 None
    diff_type: str | None       # 副产物，前端可忽略；无对应 line_match 为 None
    # 本行对齐到的真实转录段 segment_id（稳定 DB 主键，非位置下标）。前端据此把"实录侧"
    # 重接到最新可编辑的转录段——说话人纠正后即时同步，绕开 seg_idx 的截断/排序不稳定问题。
    # 漏说行为空 tuple；老库/无 segment_id 的输入也为空（前端按行回退到 spoken_text/speaker）。
    segment_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class L2Input:
    """L2 Pipeline 输入（caller 组装后传入）。

    transcript_segments 总字符数上限 2500 字符（§3 决策），
    超限时 pipeline 截断保留末尾段落。

    script_lines 总字符数上限 1000 字符，由 caller（1.H）在组装时截断，
    pipeline 不处理 script_lines 截断。
    """

    take_id: int
    scene_id: int
    take_number: int
    transcript_segments: list[dict]
    script_lines: list[dict]
    previous_notes: list[str]


@dataclass(frozen=True)
class CorrectedSegment:
    """单个转录片段的错别字修正结果（v0.2 新增）。

    idx 指向 L2Input.transcript_segments 截断后列表的下标（从 0 开始）。
    只对真正有修改的 segment 输出；未改动的 segment 不出现。
    """

    idx: int
    original: str
    corrected: str


@dataclass(frozen=True)
class L2Output:
    """L2 Pipeline 输出。

    script_diff_summary → takes.script_diff（JSON 顶层字段，由 caller 写库）。
    line_matches → take_line_matches 表（由 caller 1.H 写库）。
    corrected_segments → takes.script_diff（JSON 字段，由 caller 写库）。
    insertion 类型 line_no=-1 时，caller 跳过写 take_line_matches（§4 决策）。
    """

    script_diff_summary: str | None
    line_matches: list[LineMatch]
    corrected_segments: list[CorrectedSegment]
    # 并置文档（缺口③）：剧本行骨架 + 对齐的实际台词。由 run_l2_take 在解析后组装
    # （需要 script_lines + 截断后 segments），_validate_data_dict 不填，默认空列表。
    juxtaposition: list[JuxtaLine] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 内部常量
# ---------------------------------------------------------------------------

_TRANSCRIPT_CHAR_LIMIT = 2500
# _VALID_DIFF_TYPES 从 l2_constants 导入（module 顶部 import 语句），此处不重复定义。
# 测试文件 `from backend.pipelines.l2_take import _VALID_DIFF_TYPES` 仍然有效（re-export）。


# ---------------------------------------------------------------------------
# Prompt 构建（§5）
# ---------------------------------------------------------------------------


def _build_script_lines_block(script_lines: list[dict]) -> str:
    """格式化剧本行为 [行N] 角色：台词 文本。"""
    if not script_lines:
        return "（无剧本，跳过偏差检测）"
    lines = []
    for item in script_lines:
        character = item.get("character")
        char_label = character if character is not None else "（舞台指示）"
        lines.append(f"[行{item['line_no']}] {char_label}：{item['text']}")
    return "\n".join(lines)


def _build_transcript_block(segments: list[dict], truncated: bool) -> str:
    """格式化 transcript_segments 为 [idx][speaker] text 文本。

    truncated=True 时在头部加截断警告。
    idx 从 0 开始，与 corrected_segments.idx 对应。
    """
    if not segments:
        return "（无转录片段）"
    lines = []
    if truncated:
        lines.append("[WARNING: transcript truncated to 2500 chars, earliest segments dropped]")
    for idx, seg in enumerate(segments):
        speaker = seg.get("speaker")
        label = speaker if speaker is not None else "未知说话人"
        lines.append(f"[{idx}][{label}] {seg['text']}")
    return "\n".join(lines)


def _truncate_segments(segments: list[dict]) -> tuple[list[dict], bool]:
    """截断 transcript_segments 使总字符数不超过 _TRANSCRIPT_CHAR_LIMIT。

    保留末尾段落（take 末尾更可能包含关键台词，§3 决策）。
    返回 (截断后的 segments, 是否发生了截断)。
    """
    total_chars = sum(len(s["text"]) for s in segments)
    if total_chars <= _TRANSCRIPT_CHAR_LIMIT:
        return segments, False

    # 从末尾开始累加，直到达到上限
    result: list[dict] = []
    accumulated = 0
    for seg in reversed(segments):
        text_len = len(seg["text"])
        if accumulated + text_len > _TRANSCRIPT_CHAR_LIMIT:
            # P2 #4：如果第一段（result 为空）就超长，保留 tail 而非跳过
            if not result:
                tail_text = seg["text"][-_TRANSCRIPT_CHAR_LIMIT:]
                tail_seg = {**seg, "text": tail_text}
                result.insert(0, tail_seg)
            break
        result.insert(0, seg)
        accumulated += text_len

    return result, True


def _build_user_message(
    input_data: L2Input, truncated_segments: list[dict], was_truncated: bool
) -> str:
    """组装 user message（§5 模板）。

    script_lines 为空时走无剧本路径：不含剧本块、不含 insertion/比对任务，
    只含转录记录和纯纠错任务。

    truncated_segments / was_truncated 由 caller（run_l2_take）截断一次后传入，
    与并置文档复用同一份截断结果——避免重复截断，且保证 seg_idx 下标基准一致。
    """
    transcript_block = _build_transcript_block(truncated_segments, was_truncated)

    if not input_data.script_lines:
        # 无剧本路径：只含转录记录 + 纯纠错任务
        return (
            f"## Take {input_data.take_number} 转录记录（含下标索引）\n\n"
            f"{transcript_block}\n\n"
            "任务：识别转录文本中的 ASR 错别字（同音字、形近字误识别），输出到 corrected_segments。"
        )

    # 有剧本路径（原有逻辑，不变）
    script_block = _build_script_lines_block(input_data.script_lines)

    previous_section = ""
    if input_data.previous_notes:
        n = len(input_data.previous_notes)
        notes_text = "\n".join(input_data.previous_notes)
        previous_section = f"\n## 历史偏差参考（最近 {n} 条）\n\n{notes_text}\n"

    return (
        f"## 剧本台词（场次 {input_data.scene_id}）\n\n"
        f"{script_block}\n\n"
        f"## Take {input_data.take_number} 转录记录（含下标索引）\n\n"
        f"{transcript_block}\n"
        f"{previous_section}\n"
        "任务：①找出转录中剧本完全没有对应的内容标为 insertion（line_no=-1），"
        "②逐行比对剧本标 match/substitution/missing，"
        "③识别 ASR 错别字放入 corrected_segments。\n"
        "直接输出 JSON。"
    )


# ---------------------------------------------------------------------------
# 输出解析（§6）
# ---------------------------------------------------------------------------


def _strip_markdown_fence(text: str) -> str:
    """剥除 ```json ... ``` 或 ``` ... ``` 包裹，只剥一层。"""
    stripped = text.strip()
    if stripped.startswith("```"):
        # 找第一行结束和最后一个 ``` 开始的位置
        first_newline = stripped.find("\n")
        if first_newline == -1:
            return stripped
        content_start = first_newline + 1
        # 从末尾找最后一个 ```
        last_fence = stripped.rfind("```")
        if last_fence > content_start:
            return stripped[content_start:last_fence].strip()
    return stripped


def _validate_data_dict(data: dict, *, strict: bool = True) -> L2Output:
    """校验已解析的 dict，构造并返回 L2Output。

    接受来自 json.loads 的 dict（无论是 FC 路径还是旧文本路径），
    执行字段存在性校验、枚举值校验、类型校验，最终构造 L2Output。

    strict=True（有剧本路径）：script_diff_summary / line_matches 必须存在，
        缺失时抛 L2ParseError（保留原有严格校验）。
    strict=False（无剧本路径）：script_diff_summary / line_matches 缺失时给默认值
        （None / []），corrected_segments 仍要求必须存在。

    两条路径均执行：
    - original==corrected 的 corrected_segments 条目被过滤丢弃
    - line_matches 中 detail 为字符串 "null"/"none"/"" 时归一化为 Python None

    Raises:
        L2ParseError: 字段缺失（strict 模式）/ 枚举值非法 / 类型错误。
    """
    if not isinstance(data, dict):
        raise L2ParseError("LLM response JSON is not a dict object")

    # 字段存在性检查
    if strict:
        if "script_diff_summary" not in data:
            raise L2ParseError("LLM response missing required field: 'script_diff_summary'")
        if "line_matches" not in data:
            raise L2ParseError("LLM response missing required field: 'line_matches'")
        if "corrected_segments" not in data:
            raise L2ParseError("LLM response missing required field: 'corrected_segments'")
        script_diff_summary: str | None = data["script_diff_summary"]
        raw_matches = data["line_matches"]
        raw_corrections = data["corrected_segments"]
    else:
        # 宽松模式：缺失字段给默认值
        script_diff_summary = data.get("script_diff_summary")  # 缺失 → None
        raw_matches = data.get("line_matches", [])              # 缺失 → []
        raw_corrections = data.get("corrected_segments")        # 仍要求必须存在
        if raw_corrections is None:
            raise L2ParseError("LLM response missing required field: 'corrected_segments'")

    if not isinstance(raw_matches, list):
        raise L2ParseError("LLM response 'line_matches' is not a list")
    if not isinstance(raw_corrections, list):
        raise L2ParseError("LLM response 'corrected_segments' is not a list")

    line_matches: list[LineMatch] = []
    for i, item in enumerate(raw_matches):
        if not isinstance(item, dict):
            raise L2ParseError(f"line_matches[{i}] is not a dict")

        # line_no 类型校验
        line_no = item.get("line_no")
        if not isinstance(line_no, int):
            raise L2ParseError(
                f"line_matches[{i}].line_no is not an integer: {line_no!r}"
            )

        # diff_type 枚举校验
        diff_type = item.get("diff_type")
        if diff_type not in _VALID_DIFF_TYPES:
            raise L2ParseError(
                f"line_matches[{i}].diff_type invalid: {diff_type!r}, "
                f"must be one of {sorted(_VALID_DIFF_TYPES)}"
            )

        # detail 归一化：字符串 "null"/"none"/"" → Python None
        raw_detail = item.get("detail")
        if isinstance(raw_detail, str):
            stripped = raw_detail.strip().lower()
            detail: str | None = None if stripped in ("null", "none", "") else raw_detail
        else:
            detail = raw_detail  # None 直接保留

        # seg_idx 容错解析（best-effort，不抛错）：只保留合法非负整数，过滤 bool。
        raw_seg = item.get("seg_idx")
        seg_idx: tuple[int, ...] = ()
        if isinstance(raw_seg, list):
            seg_idx = tuple(
                x for x in raw_seg
                if isinstance(x, int) and not isinstance(x, bool) and x >= 0
            )

        line_matches.append(
            LineMatch(line_no=line_no, diff_type=diff_type, detail=detail, seg_idx=seg_idx)
        )

    corrected_segments: list[CorrectedSegment] = []
    for j, cs_item in enumerate(raw_corrections):
        if not isinstance(cs_item, dict):
            raise L2ParseError(f"corrected_segments[{j}] is not a dict")

        idx = cs_item.get("idx")
        if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0:
            raise L2ParseError(
                f"corrected_segments[{j}].idx is not a non-negative integer: {idx!r}"
            )

        original = cs_item.get("original")
        if not isinstance(original, str):
            raise L2ParseError(
                f"corrected_segments[{j}].original is not a string: {original!r}"
            )

        corrected = cs_item.get("corrected")
        if not isinstance(corrected, str):
            raise L2ParseError(
                f"corrected_segments[{j}].corrected is not a string: {corrected!r}"
            )

        # 过滤无效纠错段（original == corrected）
        if original == corrected:
            continue

        corrected_segments.append(CorrectedSegment(idx=idx, original=original, corrected=corrected))

    return L2Output(
        script_diff_summary=script_diff_summary,
        line_matches=line_matches,
        corrected_segments=corrected_segments,
    )


def _parse_llm_output(raw_text: str) -> L2Output:
    """解析 LLM 输出文本为 L2Output（旧文本路径，保留供回退/测试）。

    解析流程：strip_markdown_fence → json.loads → _validate_data_dict → L2Output。

    Raises:
        L2ParseError: 空响应 / JSON 解析失败 / 字段缺失 / 枚举值非法 / line_no 非整数。
    """
    if not raw_text or not raw_text.strip():
        raise L2ParseError("LLM returned empty response")

    cleaned = _strip_markdown_fence(raw_text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise L2ParseError("LLM response is not valid JSON", cause=exc) from exc

    return _validate_data_dict(data)


# ---------------------------------------------------------------------------
# 并置文档组装（缺口③）
# ---------------------------------------------------------------------------


def _resolve_spoken(
    segments: list[dict], seg_idx: tuple[int, ...]
) -> tuple[str | None, str | None, tuple[int, ...]]:
    """按 seg_idx 从（截断后）转录段取真实原文 + speaker + 真实 segment_id 列表。

    多段按下标顺序拼接（中文无空格，直接相连）；speaker 取首个非空段的 speaker；
    segment_ids 收集所有命中段的真实 segment_id（供前端把"实录侧"重接到可编辑的最新段）。
    无有效下标 → (None, None, ())，对应"漏说该行"。越界下标静默跳过（LLM best-effort）。
    输入段缺 segment_id（老库/直接构造的测试输入）时该段不计入 segment_ids。
    """
    parts: list[str] = []
    speaker: str | None = None
    seg_ids: list[int] = []
    for i in seg_idx:
        if 0 <= i < len(segments):
            seg = segments[i]
            parts.append(seg.get("text", ""))
            if speaker is None:
                speaker = seg.get("speaker")
            sid = seg.get("segment_id")
            if isinstance(sid, int) and not isinstance(sid, bool):
                seg_ids.append(sid)
    if not parts:
        return None, None, ()
    return "".join(parts), speaker, tuple(seg_ids)


def _build_juxtaposition(
    script_lines: list[dict],
    segments: list[dict],
    line_matches: list[LineMatch],
) -> list[JuxtaLine]:
    """组装并置文档：剧本行为骨架，逐行贴上对齐的实际台词，末尾追加 insertion。

    - 骨架用 script_lines（保证整段剧本都呈现，不依赖 LLM 是否给齐 line_matches）；
    - 每行的实际台词来自该行 line_match 的 seg_idx → 转录原文（漏说 → None）；
    - insertion（line_no=-1）实际多说的内容追加在末尾，剧本侧留空；seg_idx 缺失时
      退回用 detail 文本兜底。
    """
    match_by_no: dict[int, LineMatch] = {}
    insertions: list[LineMatch] = []
    for m in line_matches:
        if m.line_no == -1:
            insertions.append(m)
        elif m.line_no not in match_by_no:
            match_by_no[m.line_no] = m  # 同行号重复时取首条

    rows: list[JuxtaLine] = []
    for line in script_lines:
        line_no = line["line_no"]
        m = match_by_no.get(line_no)
        spoken_text, speaker, seg_ids = _resolve_spoken(segments, m.seg_idx if m else ())
        rows.append(
            JuxtaLine(
                line_no=line_no,
                character=line.get("character"),
                script_text=line.get("text"),
                spoken_text=spoken_text,
                speaker=speaker,
                diff_type=m.diff_type if m else None,
                segment_ids=seg_ids,
            )
        )

    for m in insertions:
        spoken_text, speaker, seg_ids = _resolve_spoken(segments, m.seg_idx)
        if spoken_text is None and m.detail:  # seg_idx 缺失 → detail 兜底
            spoken_text = m.detail
        rows.append(
            JuxtaLine(
                line_no=-1,
                character=None,
                script_text=None,
                spoken_text=spoken_text,
                speaker=speaker,
                diff_type="insertion",
                segment_ids=seg_ids,
            )
        )

    return rows


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------


async def run_l2_take(
    input_data: L2Input,
    llm_service: "LLMService",
    timeout: float | None = None,
) -> L2Output:
    """执行一次 L2 Pipeline：台词 diff 检测。

    Args:
        input_data: L2 输入，含转录记录、剧本行、历史偏差。
        llm_service: 注入的 LLMService 实例（不调 get_service()）。
        timeout: 最大等待时间（含排队 + 首次模型加载 + 推理）。None → 取
            SOUNDSPEED_L2_TIMEOUT（默认 300s）。L2 是 take 后台批处理、不在用户等待路径，
            CPU 上首条 take 含 Gemma 懒加载（GPU 失败回落 CPU 再载）+ CPU 推理，
            60s 不够（实测 TimeoutError，详见 soundspeed_diarization_runtime）。

    Returns:
        L2Output，含 script_diff_summary 和 line_matches。

    Raises:
        L2ParseError: LLM 输出非合法 JSON / 字段缺失 / 枚举值非法 / 响应为空。
        asyncio.TimeoutError: 排队 + 推理总耗时超 timeout（由 LLMService 抛出，不吞）。
    """
    if timeout is None:
        timeout = float(os.environ.get("SOUNDSPEED_L2_TIMEOUT", "300"))
    no_script = not input_data.script_lines
    task_type = "l2_take_no_script" if no_script else "l2_take"

    # 截断一次：user message 渲染与并置文档组装复用同一份（seg_idx 下标基准必须一致）。
    truncated_segments, was_truncated = _truncate_segments(input_data.transcript_segments)

    system_prompt = TASK_CONFIG[task_type]["system"]
    user_message = _build_user_message(input_data, truncated_segments, was_truncated)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    # FC 路径：调 infer_tool，取 tool_calls[0]，解析 arguments JSON
    # asyncio.TimeoutError 从 infer_tool 传出，pipeline 不捕获（让 caller 感知）
    try:
        tool_call: dict = await llm_service.infer_tool(
            messages,
            task_type=task_type,
            priority=2,
            timeout=timeout,
        )
    except LookupError as exc:
        raise L2ParseError("tool_calls 缺失或为空，模型未走 function calling 路径", cause=exc) from exc

    try:
        args_json: str = tool_call["function"]["arguments"]
        data = json.loads(args_json)
    except (KeyError, json.JSONDecodeError) as exc:
        raise L2ParseError("tool_call arguments 解析失败", cause=exc) from exc

    # 有剧本路径用 strict=True（原有严格校验），无剧本路径用 strict=False（宽松）
    output = _validate_data_dict(data, strict=not no_script)

    # 并置文档（缺口③）：仅有剧本路径组装。复用上方截断好的 truncated_segments
    # （seg_idx 引用的就是这份截断后转录段），不再二次截断。
    if no_script:
        return output
    juxtaposition = _build_juxtaposition(
        input_data.script_lines, truncated_segments, output.line_matches
    )
    return replace(output, juxtaposition=juxtaposition)
