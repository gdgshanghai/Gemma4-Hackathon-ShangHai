"""1.G L2 Pipeline 单元测试。

覆盖 docs/specs/2026-05-27-l2-pipeline.md §7 全部 14 个用例。
全部使用 AsyncMock 注入 llm_service.infer，不加载真实模型。
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.llm.service import LLMService
from backend.pipelines.l2_take import (
    CorrectedSegment,
    L2Input,
    L2Output,
    L2ParseError,
    LineMatch,
    run_l2_take,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_segments() -> list[dict]:
    """3 段 ch1 转录，含 2 个 speaker + 1 个 None speaker。"""
    return [
        {
            "speaker": "SPEAKER_00",
            "text": "我不想走，请别拦着我。",
            "start_frame": 0,
            "end_frame": 16000,
        },
        {
            "speaker": "SPEAKER_01",
            "text": "你必须留下来。",
            "start_frame": 16000,
            "end_frame": 32000,
        },
        {
            "speaker": None,
            "text": "（背景噪音片段）",
            "start_frame": 32000,
            "end_frame": 40000,
        },
    ]


@pytest.fixture
def stub_script_lines() -> list[dict]:
    """3 行剧本，含角色行 + 舞台指示行。"""
    return [
        {"line_no": 1, "character": "主角", "text": "我不想走，请别拦着我。"},
        {"line_no": 2, "character": "配角", "text": "你必须留下来，不然一切都完了。"},
        {"line_no": 3, "character": None, "text": "（配角伸手拦住主角）"},
    ]


@pytest.fixture
def l2_input(stub_segments: list[dict], stub_script_lines: list[dict]) -> L2Input:
    return L2Input(
        take_id=1,
        scene_id=1,
        take_number=3,
        transcript_segments=stub_segments,
        script_lines=stub_script_lines,
        previous_notes=[],
    )


def _make_tool_call(arguments_json: str) -> dict:
    """把 JSON 字符串包装成 tool_call dict（infer_tool 的返回格式）。"""
    return {
        "id": "call_stub_test",
        "type": "function",
        "function": {
            "name": "report_script_analysis",
            "arguments": arguments_json,
        },
    }


def _mock_llm(response: str) -> MagicMock:
    """创建注入 AsyncMock.infer_tool 的 LLMService mock。

    response: JSON 字符串（直接作为 tool_call.function.arguments）。
    """
    svc = MagicMock(spec=LLMService)
    svc.infer_tool = AsyncMock(return_value=_make_tool_call(response))
    return svc


def _normal_response() -> str:
    return json.dumps(
        {
            "script_diff_summary": "台词基本匹配，第2行配角漏说「不然一切都完了」。",
            "line_matches": [
                {"line_no": 1, "diff_type": "match", "detail": None},
                {"line_no": 2, "diff_type": "missing", "detail": "漏词：「不然一切都完了」"},
                {"line_no": 3, "diff_type": "match", "detail": None},
            ],
            "corrected_segments": [],
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l2_take_normal(l2_input: L2Input) -> None:
    """正常返回：合法 JSON，L2Output 字段正确，diff_type 全部合法枚举。"""
    svc = _mock_llm(_normal_response())
    result = await run_l2_take(l2_input, svc)

    assert isinstance(result, L2Output)
    assert result.script_diff_summary is not None
    assert len(result.line_matches) == 3
    valid_types = {"match", "missing", "substitution", "insertion"}
    for lm in result.line_matches:
        assert isinstance(lm, LineMatch)
        assert lm.diff_type in valid_types


@pytest.mark.asyncio
async def test_run_l2_take_empty_transcript(stub_script_lines: list[dict]) -> None:
    """transcript_segments 为空列表，pipeline 不抛错，line_matches 为空列表。"""
    inp = L2Input(
        take_id=2,
        scene_id=1,
        take_number=1,
        transcript_segments=[],
        script_lines=stub_script_lines,
        previous_notes=[],
    )
    empty_response = json.dumps(
        {"script_diff_summary": None, "line_matches": [], "corrected_segments": []},
        ensure_ascii=False,
    )
    svc = _mock_llm(empty_response)
    result = await run_l2_take(inp, svc)

    assert result.line_matches == []


@pytest.mark.asyncio
async def test_run_l2_take_empty_script_lines(stub_segments: list[dict]) -> None:
    """script_lines 为空列表，pipeline 不抛错，line_matches=[]，script_diff_summary=None。"""
    inp = L2Input(
        take_id=3,
        scene_id=1,
        take_number=1,
        transcript_segments=stub_segments,
        script_lines=[],
        previous_notes=[],
    )
    no_script_response = json.dumps(
        {"script_diff_summary": None, "line_matches": [], "corrected_segments": []},
        ensure_ascii=False,
    )
    svc = _mock_llm(no_script_response)
    result = await run_l2_take(inp, svc)

    assert result.line_matches == []
    assert result.script_diff_summary is None


@pytest.mark.asyncio
async def test_run_l2_take_invalid_json_raises(l2_input: L2Input) -> None:
    """LLM 返回非 JSON 字符串，抛 L2ParseError，e.cause 为 JSONDecodeError。"""
    svc = _mock_llm("这不是JSON内容，只是一段文本。")
    with pytest.raises(L2ParseError) as exc_info:
        await run_l2_take(l2_input, svc)

    import json as _json

    assert isinstance(exc_info.value.cause, _json.JSONDecodeError)


@pytest.mark.asyncio
async def test_run_l2_take_markdown_wrapped_json(l2_input: L2Input) -> None:
    """FC 路径：tool_call.arguments 是纯 JSON（grammar 保证无 markdown fence），pipeline 能成功解析。

    原旧路径测试「markdown fence → _strip → json.loads」，FC 路径 grammar 约束下不会产生 markdown 包裹，
    改为直接验证纯 JSON arguments 成功解析。
    """
    svc = _mock_llm(_normal_response())
    result = await run_l2_take(l2_input, svc)

    assert isinstance(result, L2Output)
    assert len(result.line_matches) == 3


@pytest.mark.asyncio
async def test_run_l2_take_missing_field_raises(l2_input: L2Input) -> None:
    """LLM 返回缺少 line_matches 字段的 JSON，抛 L2ParseError。"""
    bad_response = json.dumps({"script_diff_summary": "没有line_matches字段"})
    svc = _mock_llm(bad_response)
    with pytest.raises(L2ParseError):
        await run_l2_take(l2_input, svc)


@pytest.mark.asyncio
async def test_run_l2_take_invalid_diff_type_raises(l2_input: L2Input) -> None:
    """LLM 返回 diff_type="unknown" 的 JSON，抛 L2ParseError。"""
    bad_response = json.dumps(
        {
            "script_diff_summary": "有非法枚举",
            "line_matches": [
                {"line_no": 1, "diff_type": "unknown", "detail": None},
            ],
        }
    )
    svc = _mock_llm(bad_response)
    with pytest.raises(L2ParseError):
        await run_l2_take(l2_input, svc)


@pytest.mark.asyncio
async def test_run_l2_take_transcript_truncated(stub_script_lines: list[dict]) -> None:
    """transcript_segments 总字符数超 2500，pipeline 截断后仍能调 LLMService。

    验证：user message 中含 WARNING: transcript truncated 标注。
    """
    # 构造超过 2500 字符的 transcript_segments
    long_segments = [
        {
            "speaker": "SPEAKER_00",
            "text": "这是很长的台词文本，用于测试截断逻辑。" * 20,  # 约 400+ 字符
            "start_frame": i * 16000,
            "end_frame": (i + 1) * 16000,
        }
        for i in range(10)  # 10 段，总字符数远超 2500
    ]
    inp = L2Input(
        take_id=4,
        scene_id=1,
        take_number=1,
        transcript_segments=long_segments,
        script_lines=stub_script_lines,
        previous_notes=[],
    )
    svc = _mock_llm(_normal_response())
    result = await run_l2_take(inp, svc)

    assert isinstance(result, L2Output)
    # 验证 infer_tool 被调用，且 messages[1]["content"] 含截断警告
    assert svc.infer_tool.called
    call_args = svc.infer_tool.call_args
    messages = call_args[0][0]  # positional 第一个参数是 messages
    user_message = next(m["content"] for m in messages if m["role"] == "user")
    assert "WARNING: transcript truncated" in user_message


@pytest.mark.asyncio
async def test_run_l2_take_insertion_line_no_minus_one(l2_input: L2Input) -> None:
    """LLM 返回含 line_no=-1, diff_type="insertion" 的输出，pipeline 能正常解析为 LineMatch。"""
    response = json.dumps(
        {
            "script_diff_summary": "演员添加了剧本外台词。",
            "line_matches": [
                {"line_no": 1, "diff_type": "match", "detail": None},
                {"line_no": -1, "diff_type": "insertion", "detail": "额外台词：「等等，我还有话说。」"},
            ],
            "corrected_segments": [],
        },
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    result = await run_l2_take(l2_input, svc)

    insertion_matches = [lm for lm in result.line_matches if lm.diff_type == "insertion"]
    assert len(insertion_matches) == 1
    assert insertion_matches[0].line_no == -1


@pytest.mark.asyncio
async def test_run_l2_take_previous_notes_in_prompt(
    stub_segments: list[dict], stub_script_lines: list[dict]
) -> None:
    """previous_notes 非空时，user message 包含「历史偏差参考」节。"""
    inp = L2Input(
        take_id=5,
        scene_id=1,
        take_number=2,
        transcript_segments=stub_segments,
        script_lines=stub_script_lines,
        previous_notes=["take 1 偏差摘要：配角漏词明显。"],
    )
    svc = _mock_llm(_normal_response())
    await run_l2_take(inp, svc)

    call_args = svc.infer_tool.call_args
    messages = call_args[0][0]
    user_message = next(m["content"] for m in messages if m["role"] == "user")
    assert "历史偏差参考" in user_message


@pytest.mark.asyncio
async def test_run_l2_take_no_previous_notes_section_absent(
    stub_segments: list[dict], stub_script_lines: list[dict]
) -> None:
    """previous_notes 为空时，user message 不包含「历史偏差参考」节。"""
    inp = L2Input(
        take_id=6,
        scene_id=1,
        take_number=1,
        transcript_segments=stub_segments,
        script_lines=stub_script_lines,
        previous_notes=[],
    )
    svc = _mock_llm(_normal_response())
    await run_l2_take(inp, svc)

    call_args = svc.infer_tool.call_args
    messages = call_args[0][0]
    user_message = next(m["content"] for m in messages if m["role"] == "user")
    assert "历史偏差参考" not in user_message


@pytest.mark.asyncio
async def test_run_l2_take_empty_llm_response_raises(l2_input: L2Input) -> None:
    """LLM 返回空字符串，抛 L2ParseError。"""
    svc = _mock_llm("")
    with pytest.raises(L2ParseError):
        await run_l2_take(l2_input, svc)


@pytest.mark.asyncio
async def test_run_l2_take_timeout_propagated(l2_input: L2Input) -> None:
    """LLMService.infer_tool 抛 asyncio.TimeoutError，pipeline 不吞，让其穿透到 caller。"""
    svc = MagicMock(spec=LLMService)
    svc.infer_tool = AsyncMock(side_effect=asyncio.TimeoutError())
    with pytest.raises(asyncio.TimeoutError):
        await run_l2_take(l2_input, svc, timeout=0.1)


@pytest.mark.asyncio
async def test_run_l2_take_uses_priority_2(l2_input: L2Input) -> None:
    """run_l2_take 调用 llm_service.infer_tool 时 priority=2 且 task_type="l2_take"。"""
    svc = _mock_llm(_normal_response())
    await run_l2_take(l2_input, svc)

    svc.infer_tool.assert_called_once()
    call_kwargs = svc.infer_tool.call_args
    # 检查 keyword 参数
    assert call_kwargs.kwargs.get("task_type") == "l2_take" or call_kwargs[1].get(
        "task_type"
    ) == "l2_take"
    assert call_kwargs.kwargs.get("priority") == 2 or call_kwargs[1].get("priority") == 2


# ---------------------------------------------------------------------------
# P2 #2：script_lines 截断 1000 字符（orchestrator helper）
# ---------------------------------------------------------------------------


def test_truncate_script_lines_caps_at_1000_chars() -> None:
    """50 行各 50 字符，_truncate_script_lines 截断后总字符 <= 1000，超出的行被丢弃。"""
    from backend.core.orchestrator import Orchestrator

    lines = [
        {"line_no": i, "character": "A", "text": "X" * 50}
        for i in range(1, 51)
    ]
    result = Orchestrator._truncate_script_lines(lines, max_chars=1000)
    total_chars = sum(len(item["text"]) for item in result)
    assert total_chars <= 1000
    # 50 行总共 2500 字符，截断后应只有 20 行
    assert len(result) < 50


# ---------------------------------------------------------------------------
# P2 #4：单 segment > 2500 字符保留 tail
# ---------------------------------------------------------------------------


def test_truncate_segments_keeps_tail_of_oversized_segment() -> None:
    """单 segment 4000 字符 -> 截断后返回 1 个 segment，text 长度 <= 2500。"""
    from backend.pipelines.l2_take import _truncate_segments

    segments = [{"speaker": "A", "text": "Y" * 4000, "start_frame": 0, "end_frame": 1}]
    result, was_truncated = _truncate_segments(segments)
    assert was_truncated is True
    assert len(result) == 1
    assert len(result[0]["text"]) <= 2500
    # 其他字段保持原值
    assert result[0]["speaker"] == "A"
    assert result[0]["start_frame"] == 0


# ---------------------------------------------------------------------------
# v0.2 新增：corrected_segments 解析 + 无剧本场景 + transcript idx
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l2_take_corrected_segments_returned(l2_input: L2Input) -> None:
    """LLMService 返回含非空 corrected_segments 的 JSON，L2Output.corrected_segments 正确解析。

    验证：每项是 CorrectedSegment 实例，idx/original/corrected 字段均正确。
    """
    response = json.dumps(
        {
            "script_diff_summary": "第0段有错别字。",
            "line_matches": [
                {"line_no": 1, "diff_type": "match", "detail": None},
            ],
            "corrected_segments": [
                {"idx": 0, "original": "我不想走", "corrected": "我不想走（已修正）"},
                {"idx": 1, "original": "你必须留下来", "corrected": "你必须留下来（已修正）"},
            ],
        },
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    result = await run_l2_take(l2_input, svc)

    assert isinstance(result, L2Output)
    assert len(result.corrected_segments) == 2

    cs0 = result.corrected_segments[0]
    assert isinstance(cs0, CorrectedSegment)
    assert cs0.idx == 0
    assert cs0.original == "我不想走"
    assert cs0.corrected == "我不想走（已修正）"

    cs1 = result.corrected_segments[1]
    assert isinstance(cs1, CorrectedSegment)
    assert cs1.idx == 1


@pytest.mark.asyncio
async def test_run_l2_take_no_corrections_returned(l2_input: L2Input) -> None:
    """LLMService 返回 corrected_segments: []，L2Output.corrected_segments 为空列表，不抛错。"""
    response = json.dumps(
        {
            "script_diff_summary": "无偏差。",
            "line_matches": [],
            "corrected_segments": [],
        },
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    result = await run_l2_take(l2_input, svc)

    assert result.corrected_segments == []


@pytest.mark.asyncio
async def test_run_l2_take_no_script_lines(stub_segments: list[dict]) -> None:
    """script_lines=[]，pipeline 正常调用，解析含 corrected_segments 的 JSON。

    验证：L2Output.line_matches==[]、corrected_segments 非空、script_diff_summary is None。
    """
    inp = L2Input(
        take_id=10,
        scene_id=2,
        take_number=1,
        transcript_segments=stub_segments,
        script_lines=[],
        previous_notes=[],
    )
    response = json.dumps(
        {
            "script_diff_summary": None,
            "line_matches": [],
            "corrected_segments": [
                {"idx": 0, "original": "爱生活", "corrected": "爱具体的生活"},
            ],
        },
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    result = await run_l2_take(inp, svc)

    assert result.line_matches == []
    assert result.script_diff_summary is None
    assert len(result.corrected_segments) == 1
    assert isinstance(result.corrected_segments[0], CorrectedSegment)
    assert result.corrected_segments[0].original == "爱生活"
    assert result.corrected_segments[0].corrected == "爱具体的生活"


@pytest.mark.asyncio
async def test_user_message_includes_transcript_indices(l2_input: L2Input) -> None:
    """user message 中的 transcript_block 含 [0] / [1] 下标标记，供 corrected_segments.idx 引用。"""
    svc = _mock_llm(_normal_response())
    await run_l2_take(l2_input, svc)

    call_args = svc.infer_tool.call_args
    messages = call_args[0][0]
    user_message = next(m["content"] for m in messages if m["role"] == "user")

    # transcript_block 中每行应含 [0]、[1]、[2] 等下标
    assert "[0]" in user_message
    assert "[1]" in user_message
    assert "[2]" in user_message


# ---------------------------------------------------------------------------
# v0.2 解析负面测试：与 line_matches 对称的字段缺失/类型错抛错
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l2_take_missing_corrected_segments_field(l2_input: L2Input) -> None:
    """LLM 输出缺 corrected_segments 字段，抛 L2ParseError。"""
    response = json.dumps(
        {"script_diff_summary": "ok", "line_matches": []},
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    with pytest.raises(L2ParseError, match="corrected_segments"):
        await run_l2_take(l2_input, svc)


@pytest.mark.asyncio
async def test_run_l2_take_corrected_segments_not_list(l2_input: L2Input) -> None:
    """corrected_segments 不是 list，抛 L2ParseError。"""
    response = json.dumps(
        {"script_diff_summary": "ok", "line_matches": [], "corrected_segments": "oops"},
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    with pytest.raises(L2ParseError, match="corrected_segments"):
        await run_l2_take(l2_input, svc)


@pytest.mark.asyncio
async def test_run_l2_take_corrected_segments_negative_idx(l2_input: L2Input) -> None:
    """corrected_segments[*].idx 为负数，抛 L2ParseError。"""
    response = json.dumps(
        {
            "script_diff_summary": None,
            "line_matches": [],
            "corrected_segments": [{"idx": -1, "original": "a", "corrected": "b"}],
        },
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    with pytest.raises(L2ParseError, match="non-negative integer"):
        await run_l2_take(l2_input, svc)


@pytest.mark.asyncio
async def test_run_l2_take_corrected_segments_bool_idx(l2_input: L2Input) -> None:
    """corrected_segments[*].idx 为 bool（True/False），抛 L2ParseError。

    Python 中 isinstance(True, int) is True，必须显式拦截。
    """
    response = json.dumps(
        {
            "script_diff_summary": None,
            "line_matches": [],
            "corrected_segments": [{"idx": True, "original": "a", "corrected": "b"}],
        },
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    with pytest.raises(L2ParseError, match="non-negative integer"):
        await run_l2_take(l2_input, svc)


# ---------------------------------------------------------------------------
# 2026-06-06 无剧本分支新测试（spec §6.1）
# ---------------------------------------------------------------------------


@pytest.fixture
def no_script_input(stub_segments: list[dict]) -> L2Input:
    """script_lines=[] 的无剧本输入。"""
    return L2Input(
        take_id=20,
        scene_id=3,
        take_number=1,
        transcript_segments=stub_segments,
        script_lines=[],
        previous_notes=[],
    )


def _no_script_response(corrected_segments: list[dict] | None = None) -> str:
    """无剧本路径 tool 返回 JSON（只含 corrected_segments）。"""
    return json.dumps(
        {"corrected_segments": corrected_segments if corrected_segments is not None else []},
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_no_script_uses_no_script_task_type(
    no_script_input: L2Input,
) -> None:
    """script_lines=[] 时，infer_tool 收到 task_type='l2_take_no_script'。"""
    svc = _mock_llm(_no_script_response())
    await run_l2_take(no_script_input, svc)

    call_kwargs = svc.infer_tool.call_args
    actual_task_type = call_kwargs.kwargs.get("task_type") or call_kwargs[1].get("task_type")
    assert actual_task_type == "l2_take_no_script"


@pytest.mark.asyncio
async def test_has_script_uses_l2_take_task_type(l2_input: L2Input) -> None:
    """script_lines 非空时，infer_tool 收到 task_type='l2_take'（回归）。"""
    svc = _mock_llm(
        json.dumps(
            {"script_diff_summary": "ok", "line_matches": [], "corrected_segments": []},
            ensure_ascii=False,
        )
    )
    await run_l2_take(l2_input, svc)

    call_kwargs = svc.infer_tool.call_args
    actual_task_type = call_kwargs.kwargs.get("task_type") or call_kwargs[1].get("task_type")
    assert actual_task_type == "l2_take"


@pytest.mark.asyncio
async def test_no_script_user_message_no_script_block(
    no_script_input: L2Input,
) -> None:
    """无剧本时，user message 不含「剧本台词」节。"""
    svc = _mock_llm(_no_script_response())
    await run_l2_take(no_script_input, svc)

    call_args = svc.infer_tool.call_args
    messages = call_args[0][0]
    user_message = next(m["content"] for m in messages if m["role"] == "user")
    assert "剧本台词" not in user_message


@pytest.mark.asyncio
async def test_no_script_user_message_no_diff_task(
    no_script_input: L2Input,
) -> None:
    """无剧本时，user message 不含「①找出 insertion」任务说明。"""
    svc = _mock_llm(_no_script_response())
    await run_l2_take(no_script_input, svc)

    call_args = svc.infer_tool.call_args
    messages = call_args[0][0]
    user_message = next(m["content"] for m in messages if m["role"] == "user")
    assert "insertion" not in user_message
    assert "①" not in user_message


@pytest.mark.asyncio
async def test_no_script_output_empty_line_matches(
    no_script_input: L2Input,
) -> None:
    """无剧本路径输出解析后，line_matches=[] 且 script_diff_summary is None。"""
    svc = _mock_llm(_no_script_response())
    result = await run_l2_take(no_script_input, svc)

    assert result.line_matches == []
    assert result.script_diff_summary is None


@pytest.mark.asyncio
async def test_filter_identical_corrected_segments(l2_input: L2Input) -> None:
    """original==corrected 的段被丢弃，不出现在 L2Output.corrected_segments（有剧本路径兜底）。"""
    response = json.dumps(
        {
            "script_diff_summary": None,
            "line_matches": [],
            "corrected_segments": [
                {"idx": 0, "original": "不变文本", "corrected": "不变文本"},  # 应被过滤
                {"idx": 1, "original": "原始", "corrected": "修正"},            # 应保留
            ],
        },
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    result = await run_l2_take(l2_input, svc)

    assert len(result.corrected_segments) == 1
    assert result.corrected_segments[0].original == "原始"
    assert result.corrected_segments[0].corrected == "修正"


@pytest.mark.asyncio
async def test_detail_null_string_normalized(l2_input: L2Input) -> None:
    """line_matches 中 detail='null' 归一化为 Python None。"""
    response = json.dumps(
        {
            "script_diff_summary": None,
            "line_matches": [
                {"line_no": 1, "diff_type": "match", "detail": "null"},
            ],
            "corrected_segments": [],
        },
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    result = await run_l2_take(l2_input, svc)

    assert result.line_matches[0].detail is None


@pytest.mark.asyncio
async def test_detail_none_string_normalized(l2_input: L2Input) -> None:
    """line_matches 中 detail='none' 归一化为 Python None。"""
    response = json.dumps(
        {
            "script_diff_summary": None,
            "line_matches": [
                {"line_no": 1, "diff_type": "match", "detail": "none"},
            ],
            "corrected_segments": [],
        },
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    result = await run_l2_take(l2_input, svc)

    assert result.line_matches[0].detail is None


@pytest.mark.asyncio
async def test_detail_empty_string_normalized(l2_input: L2Input) -> None:
    """line_matches 中 detail='' 归一化为 Python None。"""
    response = json.dumps(
        {
            "script_diff_summary": None,
            "line_matches": [
                {"line_no": 1, "diff_type": "match", "detail": ""},
            ],
            "corrected_segments": [],
        },
        ensure_ascii=False,
    )
    svc = _mock_llm(response)
    result = await run_l2_take(l2_input, svc)

    assert result.line_matches[0].detail is None


# ---------------------------------------------------------------------------
# spec §6.2 smoke gate：真模型行为合规性验证
# ---------------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_no_script_correction_smoke() -> None:
    """spec §6.2 smoke gate：4B Gemma 在精简 tool 下不编造 summary/insertion。

    构造无剧本输入，transcript_segments 故意混入繁体 + 错别字：
    - 段 0：繁体「你覺得這樣怎麼樣」（繁简转换在 ASR 侧 stream_driver._emit 完成，
      L2 直接收到转录原文，模型是否对繁体段纠错不做强断言）
    - 段 1：明显同音错别字「那我就在这等候你的好消心」（心→息）
    - 段 2：正常文本「好的没问题」

    断言（头号风险验证）：
    - line_matches == []（精简 tool 没有此字段，模型不应编造）
    - script_diff_summary is None（精简 tool 没有此字段，模型不应编造）
    - corrected_segments 里无 original == corrected 的项（过滤兜底，验模型未原样透传）

    注意：corrected_segments 的具体内容取决于模型判断（不做强断言），
    但实际返回值会通过 print 原样输出供 Lead 实证审查。
    """
    import os

    model_path = os.environ.get("GEMMA_MODEL_PATH")
    if not model_path:
        pytest.skip("GEMMA_MODEL_PATH 未设置，跳过 no-script smoke gate")

    from backend.llm.service import _reset_service, get_service

    _reset_service()
    svc = get_service()
    try:
        inp = L2Input(
            take_id=999,
            scene_id=5,
            take_number=1,
            transcript_segments=[
                {
                    "speaker": "SPEAKER_00",
                    "text": "你覺得這樣怎麼樣",   # 繁体原文，繁简转换在 ASR 侧做，L2 直接收到此值
                    "start_frame": 0,
                    "end_frame": 16000,
                },
                {
                    "speaker": "SPEAKER_01",
                    "text": "那我就在这等候你的好消心",  # 心→息（同音错别字）
                    "start_frame": 16000,
                    "end_frame": 32000,
                },
                {
                    "speaker": "SPEAKER_00",
                    "text": "好的没问题",
                    "start_frame": 32000,
                    "end_frame": 48000,
                },
            ],
            script_lines=[],
            previous_notes=[],
        )

        result = await run_l2_take(inp, svc)

        # ── 原样打印真实返回，供 Lead 实证审查 ──
        print("\n[smoke] 真实模型返回：")
        print(f"  script_diff_summary = {result.script_diff_summary!r}")
        print(f"  line_matches        = {result.line_matches!r}")
        print("  corrected_segments  =")
        for cs in result.corrected_segments:
            print(f"    idx={cs.idx}  {cs.original!r} -> {cs.corrected!r}")
        if not result.corrected_segments:
            print("    （空列表，模型认为无需纠错）")

        # ── 头号风险断言 ──
        assert result.line_matches == [], (
            f"4B 模型仍编造了 line_matches（精简 tool 无此字段）: {result.line_matches!r}"
        )
        assert result.script_diff_summary is None, (
            f"4B 模型仍编造了 script_diff_summary（精简 tool 无此字段）: "
            f"{result.script_diff_summary!r}"
        )

        # original==corrected 已在 _validate_data_dict 过滤，断言过滤后无此类条目
        for cs in result.corrected_segments:
            assert cs.original != cs.corrected, (
                f"corrected_segments 中仍有 original==corrected: {cs!r}"
            )

    finally:
        await svc.aclose()
        _reset_service()
