"""L2 forced tool-call 红测试（TDD 红阶段）。

覆盖 docs/specs/2026-06-05-gemma4-function-calling.md §4/§6/§7 全部测试金字塔层次。

Layer 0  渲染验证（smoke，需要 GGUF 文件，合并进 Layer 5）
Layer 1  build_l2_tool schema 构造器验证
Layer 2  tools/tool_choice 透传到底层 client
Layer 3  infer_tool：StubToolClient 返回 tool_calls → infer_tool 正确解析；缺失时抛 LookupError
Layer 4  pipeline 集成：run_l2_take 内部走 infer_tool 路径
Layer 5  真模型 smoke（@pytest.mark.smoke，GEMMA_MODEL_PATH 未设则 skip）

约定：
- Layer 1-4 全部使用 stub/mock，不加载模型。
- Layer 5 smoke 仅在设置 GEMMA_MODEL_PATH 时运行。
- Layer 0 渲染验证并入 Layer 5（需要 GGUF 文件），不在快测套件运行。
"""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.llm.service import LLMService, _reset_service, get_service
from backend.pipelines.l2_take import (
    L2Input,
    L2Output,
    L2ParseError,
    LineMatch,
    _VALID_DIFF_TYPES,
    run_l2_take,
)


# ---------------------------------------------------------------------------
# 辅助：_StubToolClient
# 仿 StubClient，但 create_chat_completion 返回 tool_calls 形态
# ---------------------------------------------------------------------------


def _make_tool_response(arguments: dict) -> dict:
    """构造标准 tool_calls 响应（探针 B 结构）。"""
    return {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_stub_001",
                            "type": "function",
                            "function": {
                                "name": "report_script_analysis",
                                "arguments": json.dumps(arguments, ensure_ascii=False),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }


class _StubToolClient:
    """返回固定 tool_calls 响应的 stub client。"""

    def __init__(self, arguments: dict) -> None:
        self._arguments = arguments

    def create_chat_completion(
        self,
        messages: list[dict],
        **kwargs: Any,
    ) -> dict:
        return _make_tool_response(self._arguments)


class _StubToolClientNoToolCalls:
    """tool_calls 缺失（只有 content），模拟模型走了错误分支。"""

    def create_chat_completion(
        self,
        messages: list[dict],
        **kwargs: Any,
    ) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": "这是纯文本回复，不含 tool_calls",
                        "tool_calls": None,
                    },
                    "finish_reason": "stop",
                }
            ]
        }


class _StubToolClientEmptyToolCalls:
    """tool_calls 为空列表，同样视为缺失。"""

    def create_chat_completion(
        self,
        messages: list[dict],
        **kwargs: Any,
    ) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }


# ---------------------------------------------------------------------------
# 测试 Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_segments() -> list[dict]:
    return [
        {
            "segment_id": 100,
            "speaker": "SPEAKER_00",
            "text": "我不想走，请别拦着我。",
            "start_frame": 0,
            "end_frame": 16000,
        },
        {
            "segment_id": 101,
            "speaker": "SPEAKER_01",
            "text": "你必须留下来。",
            "start_frame": 16000,
            "end_frame": 32000,
        },
    ]


@pytest.fixture
def stub_script_lines() -> list[dict]:
    return [
        {"line_no": 1, "character": "主角", "text": "我不想走，请别拦着我。"},
        {"line_no": 2, "character": "配角", "text": "你必须留下来，不然一切都完了。"},
    ]


@pytest.fixture
def l2_input(stub_segments: list[dict], stub_script_lines: list[dict]) -> L2Input:
    return L2Input(
        take_id=1,
        scene_id=1,
        take_number=1,
        transcript_segments=stub_segments,
        script_lines=stub_script_lines,
        previous_notes=[],
    )


def _normal_tool_arguments() -> dict:
    """标准 tool_calls arguments 字典（三字段齐全）。"""
    return {
        "script_diff_summary": "台词基本匹配，第2行配角漏说「不然一切都完了」。",
        "line_matches": [
            {"line_no": 1, "diff_type": "match", "detail": None},
            {"line_no": 2, "diff_type": "missing", "detail": None},
        ],
        "corrected_segments": [],
    }


# ---------------------------------------------------------------------------
# Layer 1：build_l2_tool schema 构造器
# ---------------------------------------------------------------------------


def test_build_l2_tool_returns_openai_style_dict() -> None:
    """build_l2_tool() 返回 OpenAI 风格 tool dict，type="function"，name 正确。"""
    from backend.llm.tools.script import build_l2_tool  # type: ignore[import]

    tool = build_l2_tool()
    assert isinstance(tool, dict)
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "report_script_analysis"


def test_build_l2_tool_has_description() -> None:
    """build_l2_tool()["function"]["description"] 非空字符串。"""
    from backend.llm.tools.script import build_l2_tool  # type: ignore[import]

    tool = build_l2_tool()
    assert isinstance(tool["function"]["description"], str)
    assert len(tool["function"]["description"]) > 0


def test_build_l2_tool_parameters_is_valid_json_schema() -> None:
    """parameters 是合法 JSON Schema：type=object，properties 含三个顶层字段。"""
    from backend.llm.tools.script import build_l2_tool  # type: ignore[import]

    params = build_l2_tool()["function"]["parameters"]
    assert params["type"] == "object"
    props = params["properties"]
    assert "script_diff_summary" in props
    assert "line_matches" in props
    assert "corrected_segments" in props


def test_build_l2_tool_required_fields() -> None:
    """parameters.required 包含三个顶层字段（全部必须）。"""
    from backend.llm.tools.script import build_l2_tool  # type: ignore[import]

    params = build_l2_tool()["function"]["parameters"]
    required = set(params["required"])
    assert "script_diff_summary" in required
    assert "line_matches" in required
    assert "corrected_segments" in required


def test_build_l2_tool_line_matches_item_schema() -> None:
    """line_matches.items 包含 line_no(integer), diff_type(string/enum), detail(string)。"""
    from backend.llm.tools.script import build_l2_tool  # type: ignore[import]

    params = build_l2_tool()["function"]["parameters"]
    item_props = params["properties"]["line_matches"]["items"]["properties"]
    assert item_props["line_no"]["type"] == "integer"
    assert item_props["diff_type"]["type"] == "string"
    assert "enum" in item_props["diff_type"]
    assert item_props["detail"]["type"] == "string"


def test_build_l2_tool_diff_type_enum_same_source_as_valid_diff_types() -> None:
    """diff_type enum 值集合 == _VALID_DIFF_TYPES（同源断言，防漂移）。"""
    from backend.llm.tools.script import build_l2_tool  # type: ignore[import]

    params = build_l2_tool()["function"]["parameters"]
    enum_values = set(params["properties"]["line_matches"]["items"]["properties"]["diff_type"]["enum"])
    assert enum_values == _VALID_DIFF_TYPES, (
        f"diff_type enum {enum_values} 与 _VALID_DIFF_TYPES {_VALID_DIFF_TYPES} 不一致，请同步修改"
    )


def test_build_l2_tool_corrected_segments_item_schema() -> None:
    """corrected_segments.items 包含 idx(integer), original(string), corrected(string)。"""
    from backend.llm.tools.script import build_l2_tool  # type: ignore[import]

    params = build_l2_tool()["function"]["parameters"]
    item_props = params["properties"]["corrected_segments"]["items"]["properties"]
    assert item_props["idx"]["type"] == "integer"
    assert item_props["original"]["type"] == "string"
    assert item_props["corrected"]["type"] == "string"


# ---------------------------------------------------------------------------
# Layer 2：tools / tool_choice 透传到底层 client
# ---------------------------------------------------------------------------


class _CapturingToolClient:
    """记录 create_chat_completion kwargs，可配置返回 content 或 tool_calls。"""

    def __init__(self, return_tool_calls: bool = False) -> None:
        self.captured_kwargs: dict = {}
        self._return_tool_calls = return_tool_calls

    def create_chat_completion(self, messages: list[dict], **kwargs: Any) -> dict:
        self.captured_kwargs.update(kwargs)
        if self._return_tool_calls:
            return _make_tool_response(_normal_tool_arguments())
        return {"choices": [{"message": {"content": "ok"}}]}


@pytest.mark.asyncio
async def test_infer_tool_passes_tools_to_client() -> None:
    """infer_tool 调用时，底层 create_chat_completion 收到 tools 参数。

    TASK_CONFIG["l2_take"] 含 tools 字段时，service 不过滤，透传到 client。
    """
    _reset_service()
    svc = get_service()
    client = _CapturingToolClient(return_tool_calls=True)
    svc._client = client  # type: ignore[assignment]

    messages = [{"role": "user", "content": "test"}]
    await svc.infer_tool(messages, task_type="l2_take")

    assert "tools" in client.captured_kwargs, "tools 应透传到 create_chat_completion"
    _reset_service()


@pytest.mark.asyncio
async def test_infer_tool_passes_tool_choice_to_client() -> None:
    """infer_tool 调用时，底层 create_chat_completion 收到 tool_choice 参数（强制调用）。"""
    _reset_service()
    svc = get_service()
    client = _CapturingToolClient(return_tool_calls=True)
    svc._client = client  # type: ignore[assignment]

    messages = [{"role": "user", "content": "test"}]
    await svc.infer_tool(messages, task_type="l2_take")

    assert "tool_choice" in client.captured_kwargs, "tool_choice 应透传到 create_chat_completion"
    _reset_service()


@pytest.mark.asyncio
async def test_infer_tool_tool_choice_is_forced_function() -> None:
    """tool_choice 的值是 {"type": "function", "function": {"name": "report_script_analysis"}}。"""
    from backend.llm.config import TASK_CONFIG  # type: ignore[import]

    _reset_service()
    svc = get_service()
    client = _CapturingToolClient(return_tool_calls=True)
    svc._client = client  # type: ignore[assignment]

    messages = [{"role": "user", "content": "test"}]
    await svc.infer_tool(messages, task_type="l2_take")

    cfg_tool_choice = TASK_CONFIG["l2_take"]["tool_choice"]
    assert client.captured_kwargs.get("tool_choice") == cfg_tool_choice
    _reset_service()


@pytest.mark.asyncio
async def test_infer_tool_meta_keys_still_filtered() -> None:
    """tools/tool_choice 能透传，而 system/priority/_reserved 仍被过滤。"""
    _reset_service()
    svc = get_service()
    client = _CapturingToolClient(return_tool_calls=True)
    svc._client = client  # type: ignore[assignment]

    messages = [{"role": "user", "content": "test"}]
    await svc.infer_tool(messages, task_type="l2_take")

    assert "system" not in client.captured_kwargs
    assert "priority" not in client.captured_kwargs
    assert "_reserved" not in client.captured_kwargs
    _reset_service()


# ---------------------------------------------------------------------------
# Layer 3：infer_tool 返回值与异常
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_infer_tool_returns_tool_call_dict() -> None:
    """_StubToolClient 返回 tool_calls → infer_tool 返回 tool_calls[0] dict。"""
    _reset_service()
    svc = get_service()
    svc._client = _StubToolClient(_normal_tool_arguments())  # type: ignore[assignment]

    messages = [{"role": "user", "content": "test"}]
    result = await svc.infer_tool(messages, task_type="l2_take")

    assert isinstance(result, dict)
    assert result["type"] == "function"
    assert result["function"]["name"] == "report_script_analysis"
    # arguments 是 JSON 字符串
    args = json.loads(result["function"]["arguments"])
    assert "script_diff_summary" in args
    _reset_service()


@pytest.mark.asyncio
async def test_infer_tool_tool_calls_none_raises_lookup_error() -> None:
    """tool_calls 为 None → infer_tool 抛 LookupError。"""
    _reset_service()
    svc = get_service()
    svc._client = _StubToolClientNoToolCalls()  # type: ignore[assignment]

    messages = [{"role": "user", "content": "test"}]
    with pytest.raises(LookupError):
        await svc.infer_tool(messages, task_type="l2_take")
    _reset_service()


@pytest.mark.asyncio
async def test_infer_tool_tool_calls_empty_raises_lookup_error() -> None:
    """tool_calls 为空列表 → infer_tool 抛 LookupError。"""
    _reset_service()
    svc = get_service()
    svc._client = _StubToolClientEmptyToolCalls()  # type: ignore[assignment]

    messages = [{"role": "user", "content": "test"}]
    with pytest.raises(LookupError):
        await svc.infer_tool(messages, task_type="l2_take")
    _reset_service()


@pytest.mark.asyncio
async def test_infer_tool_shares_queue_and_priority_with_infer() -> None:
    """infer_tool 接受 priority 与 timeout 参数（接口签名验证）。"""
    _reset_service()
    svc = get_service()
    svc._client = _StubToolClient(_normal_tool_arguments())  # type: ignore[assignment]

    messages = [{"role": "user", "content": "test"}]
    # 能传 priority / timeout 不抛 TypeError 即算通过
    result = await svc.infer_tool(messages, task_type="l2_take", priority=2, timeout=30.0)
    assert result is not None
    _reset_service()


# ---------------------------------------------------------------------------
# Layer 4：pipeline 集成（镜像现有 run_l2_take 测试，走 infer_tool 路径）
# ---------------------------------------------------------------------------


def _mock_tool_llm(arguments: dict) -> MagicMock:
    """创建注入 AsyncMock.infer_tool 的 LLMService mock。"""
    svc = MagicMock(spec=LLMService)
    tool_call = {
        "id": "call_mock_001",
        "type": "function",
        "function": {
            "name": "report_script_analysis",
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }
    svc.infer_tool = AsyncMock(return_value=tool_call)
    return svc


@pytest.mark.asyncio
async def test_run_l2_take_fc_normal(l2_input: L2Input) -> None:
    """tool_calls 正常三字段 → L2Output 字段正确，diff_type 全部合法枚举。"""
    svc = _mock_tool_llm(_normal_tool_arguments())
    result = await run_l2_take(l2_input, svc)

    assert isinstance(result, L2Output)
    assert result.script_diff_summary is not None
    assert len(result.line_matches) == 2
    for lm in result.line_matches:
        assert isinstance(lm, LineMatch)
        assert lm.diff_type in _VALID_DIFF_TYPES


@pytest.mark.asyncio
async def test_run_l2_take_fc_empty_line_matches(l2_input: L2Input) -> None:
    """tool_calls arguments 含空 line_matches → L2Output.line_matches==[]，不抛错。"""
    svc = _mock_tool_llm(
        {
            "script_diff_summary": None,
            "line_matches": [],
            "corrected_segments": [],
        }
    )
    result = await run_l2_take(l2_input, svc)

    assert result.line_matches == []


@pytest.mark.asyncio
async def test_run_l2_take_fc_empty_corrected_segments(l2_input: L2Input) -> None:
    """tool_calls arguments 含空 corrected_segments → L2Output.corrected_segments==[]。"""
    svc = _mock_tool_llm(_normal_tool_arguments())
    result = await run_l2_take(l2_input, svc)

    assert result.corrected_segments == []


@pytest.mark.asyncio
async def test_run_l2_take_fc_insertion_line_no_minus_one(l2_input: L2Input) -> None:
    """tool_calls 含 line_no=-1, diff_type="insertion" → 正常解析为 LineMatch。"""
    svc = _mock_tool_llm(
        {
            "script_diff_summary": "演员添加了剧本外台词。",
            "line_matches": [
                {"line_no": 1, "diff_type": "match", "detail": None},
                {"line_no": -1, "diff_type": "insertion", "detail": "额外台词：「等等」"},
            ],
            "corrected_segments": [],
        }
    )
    result = await run_l2_take(l2_input, svc)

    insertion_matches = [lm for lm in result.line_matches if lm.diff_type == "insertion"]
    assert len(insertion_matches) == 1
    assert insertion_matches[0].line_no == -1


@pytest.mark.asyncio
async def test_run_l2_take_fc_invalid_diff_type_raises(l2_input: L2Input) -> None:
    """tool_calls arguments diff_type="unknown" → 抛 L2ParseError（复用现有 validator）。"""
    svc = _mock_tool_llm(
        {
            "script_diff_summary": "有非法枚举",
            "line_matches": [
                {"line_no": 1, "diff_type": "unknown", "detail": None},
            ],
            "corrected_segments": [],
        }
    )
    with pytest.raises(L2ParseError):
        await run_l2_take(l2_input, svc)


@pytest.mark.asyncio
async def test_run_l2_take_fc_negative_idx_raises(l2_input: L2Input) -> None:
    """corrected_segments[*].idx 为负数 → 抛 L2ParseError（非负整数校验）。"""
    svc = _mock_tool_llm(
        {
            "script_diff_summary": None,
            "line_matches": [],
            "corrected_segments": [
                {"idx": -1, "original": "a", "corrected": "b"},
            ],
        }
    )
    with pytest.raises(L2ParseError, match="non-negative integer"):
        await run_l2_take(l2_input, svc)


@pytest.mark.asyncio
async def test_run_l2_take_fc_missing_field_raises(l2_input: L2Input) -> None:
    """tool_calls arguments 缺少 line_matches 字段 → 抛 L2ParseError。"""
    svc = _mock_tool_llm(
        {
            "script_diff_summary": "缺字段",
        }
    )
    with pytest.raises(L2ParseError):
        await run_l2_take(l2_input, svc)


@pytest.mark.asyncio
async def test_run_l2_take_fc_tool_calls_missing_raises(l2_input: L2Input) -> None:
    """infer_tool 抛 LookupError（tool_calls 缺失）→ run_l2_take 包装成 L2ParseError。"""
    svc = MagicMock(spec=LLMService)
    svc.infer_tool = AsyncMock(side_effect=LookupError("tool_calls missing"))

    with pytest.raises(L2ParseError):
        await run_l2_take(l2_input, svc)


@pytest.mark.asyncio
async def test_run_l2_take_fc_calls_infer_tool_not_infer(l2_input: L2Input) -> None:
    """run_l2_take 改走 infer_tool 路径，不再调用 infer。"""
    svc = _mock_tool_llm(_normal_tool_arguments())
    await run_l2_take(l2_input, svc)

    svc.infer_tool.assert_called_once()
    # infer 不应被调用
    assert not svc.infer.called


# ---------------------------------------------------------------------------
# 缺口③：seg_idx + 并置文档（juxtaposition）
# ---------------------------------------------------------------------------


def test_build_l2_tool_line_matches_has_seg_idx() -> None:
    """line_matches.items 含 seg_idx（integer 数组），但不入 required。"""
    from backend.llm.tools.script import build_l2_tool

    params = build_l2_tool()["function"]["parameters"]
    item = params["properties"]["line_matches"]["items"]
    assert item["properties"]["seg_idx"]["type"] == "array"
    assert item["properties"]["seg_idx"]["items"]["type"] == "integer"
    assert "seg_idx" not in item["required"]  # 漏说行可省略


def _args_with_seg_idx() -> dict:
    """两行剧本：行1 match 对应转录段0，行2 substitution 对应转录段1。"""
    return {
        "script_diff_summary": "行2配角把台词说短了。",
        "line_matches": [
            {"line_no": 1, "diff_type": "match", "detail": None, "seg_idx": [0]},
            {"line_no": 2, "diff_type": "substitution", "detail": "你必须留下来。", "seg_idx": [1]},
        ],
        "corrected_segments": [],
    }


@pytest.mark.asyncio
async def test_run_l2_take_parses_seg_idx(l2_input: L2Input) -> None:
    """LineMatch.seg_idx 从 tool arguments 正确解析为 tuple[int]。"""
    svc = _mock_tool_llm(_args_with_seg_idx())
    result = await run_l2_take(l2_input, svc)

    by_no = {m.line_no: m for m in result.line_matches}
    assert by_no[1].seg_idx == (0,)
    assert by_no[2].seg_idx == (1,)


@pytest.mark.asyncio
async def test_run_l2_take_seg_idx_filters_invalid(l2_input: L2Input) -> None:
    """seg_idx 含非整数/负数/bool → 容错过滤，不抛错。"""
    args = _args_with_seg_idx()
    args["line_matches"][0]["seg_idx"] = [0, -1, "x", True, 1]
    svc = _mock_tool_llm(args)
    result = await run_l2_take(l2_input, svc)

    by_no = {m.line_no: m for m in result.line_matches}
    assert by_no[1].seg_idx == (0, 1)  # -1/"x"/True 被过滤


@pytest.mark.asyncio
async def test_run_l2_take_builds_juxtaposition(l2_input: L2Input) -> None:
    """有剧本路径：juxtaposition 以剧本行为骨架，贴上对齐转录原文 + speaker。"""
    svc = _mock_tool_llm(_args_with_seg_idx())
    result = await run_l2_take(l2_input, svc)

    jx = result.juxtaposition
    assert len(jx) == 2  # 骨架 = 2 行剧本
    # 行1：剧本台词 + 实际说的（转录段0原文）+ speaker
    assert jx[0].line_no == 1
    assert jx[0].character == "主角"
    assert jx[0].script_text == "我不想走，请别拦着我。"
    assert jx[0].spoken_text == "我不想走，请别拦着我。"  # 转录段0
    assert jx[0].speaker == "SPEAKER_00"
    # 行2：剧本台词与实际说的并置（实际取转录段1原文，非 detail）
    assert jx[1].spoken_text == "你必须留下来。"  # 转录段1原文
    assert jx[1].speaker == "SPEAKER_01"


@pytest.mark.asyncio
async def test_run_l2_take_juxtaposition_missing_line_no_spoken(l2_input: L2Input) -> None:
    """漏说的行（seg_idx=[]）在并置里 spoken_text/speaker 为 None。"""
    args = {
        "script_diff_summary": "行2漏说。",
        "line_matches": [
            {"line_no": 1, "diff_type": "match", "detail": None, "seg_idx": [0]},
            {"line_no": 2, "diff_type": "missing", "detail": None, "seg_idx": []},
        ],
        "corrected_segments": [],
    }
    result = await run_l2_take(l2_input, _mock_tool_llm(args))

    jx = {j.line_no: j for j in result.juxtaposition}
    assert jx[2].spoken_text is None
    assert jx[2].speaker is None
    assert jx[2].script_text == "你必须留下来，不然一切都完了。"  # 剧本侧仍呈现


@pytest.mark.asyncio
async def test_run_l2_take_juxtaposition_backbone_covers_omitted_lines(l2_input: L2Input) -> None:
    """LLM 漏给某行 line_match，骨架仍把该剧本行列出（spoken=None）。"""
    args = {
        "script_diff_summary": "只报了行1。",
        "line_matches": [
            {"line_no": 1, "diff_type": "match", "detail": None, "seg_idx": [0]},
        ],
        "corrected_segments": [],
    }
    result = await run_l2_take(l2_input, _mock_tool_llm(args))

    jx = {j.line_no: j for j in result.juxtaposition}
    assert set(jx) == {1, 2}  # 行2 即便 LLM 没报也在
    assert jx[2].spoken_text is None
    assert jx[2].diff_type is None  # 无对应 line_match


@pytest.mark.asyncio
async def test_run_l2_take_juxtaposition_insertion_appended(l2_input: L2Input) -> None:
    """insertion（line_no=-1）追加在并置末尾，剧本侧留空，实际侧取转录原文。"""
    args = {
        "script_diff_summary": "末尾多说一句。",
        "line_matches": [
            {"line_no": 1, "diff_type": "match", "detail": None, "seg_idx": [0]},
            {"line_no": 2, "diff_type": "match", "detail": None, "seg_idx": []},
            {"line_no": -1, "diff_type": "insertion", "detail": None, "seg_idx": [1]},
        ],
        "corrected_segments": [],
    }
    result = await run_l2_take(l2_input, _mock_tool_llm(args))

    jx = result.juxtaposition
    assert jx[-1].line_no == -1
    assert jx[-1].script_text is None
    assert jx[-1].spoken_text == "你必须留下来。"  # 转录段1原文
    assert jx[-1].diff_type == "insertion"


@pytest.mark.asyncio
async def test_run_l2_take_juxtaposition_insertion_detail_fallback(l2_input: L2Input) -> None:
    """insertion 没给 seg_idx 时退回用 detail 文本兜底。"""
    args = {
        "script_diff_summary": "多说一句但没给下标。",
        "line_matches": [
            {"line_no": 1, "diff_type": "match", "detail": None, "seg_idx": [0]},
            {"line_no": 2, "diff_type": "match", "detail": None, "seg_idx": [1]},
            {"line_no": -1, "diff_type": "insertion", "detail": "导演我们再来一条"},
        ],
        "corrected_segments": [],
    }
    result = await run_l2_take(l2_input, _mock_tool_llm(args))

    assert result.juxtaposition[-1].spoken_text == "导演我们再来一条"


@pytest.mark.asyncio
async def test_run_l2_take_juxtaposition_carries_segment_ids(l2_input: L2Input) -> None:
    """juxtaposition 每行带真实 segment_id（前端据此重接可编辑的最新转录段）。"""
    svc = _mock_tool_llm(_args_with_seg_idx())
    result = await run_l2_take(l2_input, svc)

    jx = {j.line_no: j for j in result.juxtaposition}
    assert jx[1].segment_ids == (100,)  # 行1 → 转录段0 的 segment_id
    assert jx[2].segment_ids == (101,)  # 行2 → 转录段1 的 segment_id


@pytest.mark.asyncio
async def test_run_l2_take_juxtaposition_missing_line_has_empty_segment_ids(
    l2_input: L2Input,
) -> None:
    """漏说行（seg_idx=[]）的 segment_ids 为空 tuple。"""
    args = {
        "script_diff_summary": "行2漏说。",
        "line_matches": [
            {"line_no": 1, "diff_type": "match", "detail": None, "seg_idx": [0]},
            {"line_no": 2, "diff_type": "missing", "detail": None, "seg_idx": []},
        ],
        "corrected_segments": [],
    }
    result = await run_l2_take(l2_input, _mock_tool_llm(args))
    jx = {j.line_no: j for j in result.juxtaposition}
    assert jx[2].segment_ids == ()


def test_resolve_spoken_multi_segment_joins_and_takes_first_speaker() -> None:
    """多段 seg_idx：原文按序拼接，speaker 取首个非空段，segment_ids 按序收集。"""
    from backend.pipelines.l2_take import _resolve_spoken

    segs = [
        {"segment_id": 7, "speaker": "顾朗", "text": "你来了"},
        {"segment_id": 8, "speaker": "顾朗", "text": "我等你很久了"},
    ]
    text, speaker, seg_ids = _resolve_spoken(segs, (0, 1))
    assert text == "你来了我等你很久了"
    assert speaker == "顾朗"
    assert seg_ids == (7, 8)


def test_resolve_spoken_out_of_range_idx_skipped() -> None:
    """越界下标静默跳过；全越界 → (None, None, ())。缺 segment_id 的段不计入 seg_ids。"""
    from backend.pipelines.l2_take import _resolve_spoken

    segs = [{"speaker": "A", "text": "x"}]
    assert _resolve_spoken(segs, (5, 9)) == (None, None, ())
    assert _resolve_spoken(segs, (0, 5)) == ("x", "A", ())


@pytest.mark.asyncio
async def test_run_l2_take_no_script_has_empty_juxtaposition(stub_segments: list[dict]) -> None:
    """无剧本路径：juxtaposition 为空列表（前端显示无剧本）。"""
    inp = L2Input(
        take_id=1, scene_id=1, take_number=1,
        transcript_segments=stub_segments, script_lines=[], previous_notes=[],
    )
    svc = MagicMock(spec=LLMService)
    tool_call = {
        "type": "function",
        "function": {
            "name": "report_corrections_only",
            "arguments": json.dumps({"corrected_segments": []}),
        },
    }
    svc.infer_tool = AsyncMock(return_value=tool_call)
    result = await run_l2_take(inp, svc)
    assert result.juxtaposition == []


# ---------------------------------------------------------------------------
# L2 超时（含首次 CPU 模型加载）：默认 300s，SOUNDSPEED_L2_TIMEOUT 可覆盖
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_l2_take_default_timeout_is_300(l2_input: L2Input, monkeypatch) -> None:
    """不传 timeout 且无 env → infer_tool 收到 300s（CPU 上首条 take 含懒加载，60s 不够）。"""
    monkeypatch.delenv("SOUNDSPEED_L2_TIMEOUT", raising=False)
    svc = _mock_tool_llm(_normal_tool_arguments())
    await run_l2_take(l2_input, svc)
    assert svc.infer_tool.call_args.kwargs["timeout"] == 300.0


@pytest.mark.asyncio
async def test_run_l2_take_timeout_env_override(l2_input: L2Input, monkeypatch) -> None:
    """SOUNDSPEED_L2_TIMEOUT 覆盖默认超时。"""
    monkeypatch.setenv("SOUNDSPEED_L2_TIMEOUT", "123")
    svc = _mock_tool_llm(_normal_tool_arguments())
    await run_l2_take(l2_input, svc)
    assert svc.infer_tool.call_args.kwargs["timeout"] == 123.0


@pytest.mark.asyncio
async def test_run_l2_take_explicit_timeout_wins(l2_input: L2Input, monkeypatch) -> None:
    """显式传 timeout 优先于 env（测试可用小值驱动超时场景）。"""
    monkeypatch.setenv("SOUNDSPEED_L2_TIMEOUT", "999")
    svc = _mock_tool_llm(_normal_tool_arguments())
    await run_l2_take(l2_input, svc, timeout=5.0)
    assert svc.infer_tool.call_args.kwargs["timeout"] == 5.0


# ---------------------------------------------------------------------------
# Layer 5：真模型 smoke（Layer 0 渲染验证并入此处）
# ---------------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_run_l2_take_fc_real_model_structure(
    stub_segments: list[dict], stub_script_lines: list[dict]
) -> None:
    """真实 GemmaClient + forced tool_choice，断言 L2Output 结构属性。

    不断言具体内容，只断言：
    - 返回 L2Output 实例
    - line_matches 是 list
    - 所有 diff_type 在 _VALID_DIFF_TYPES 内
    - corrected_segments 是 list

    Layer 0 渲染验证：渲染出的 prompt 包含工具声明 token。
    """
    model_path = os.environ.get("GEMMA_MODEL_PATH")
    if not model_path:
        pytest.skip("GEMMA_MODEL_PATH 未设置，跳过 smoke test")

    from backend.llm.service import _reset_service, get_service

    _reset_service()
    svc = get_service()
    try:
        inp = L2Input(
            take_id=99,
            scene_id=1,
            take_number=1,
            transcript_segments=stub_segments,
            script_lines=stub_script_lines,
            previous_notes=[],
        )
        result = await run_l2_take(inp, svc)

        assert isinstance(result, L2Output)
        assert isinstance(result.line_matches, list)
        assert isinstance(result.corrected_segments, list)
        for lm in result.line_matches:
            assert lm.diff_type in _VALID_DIFF_TYPES, (
                f"diff_type={lm.diff_type!r} 不在 _VALID_DIFF_TYPES"
            )
    finally:
        await svc.aclose()
        _reset_service()


# ---------------------------------------------------------------------------
# 2026-06-06 无剧本 tool schema 单测（spec §6.1 test_l2_tool_schema）
# ---------------------------------------------------------------------------


def test_no_script_tool_has_only_corrected_segments() -> None:
    """build_l2_no_script_tool schema 不含 script_diff_summary / line_matches。"""
    from backend.llm.tools.script import build_l2_no_script_tool

    params = build_l2_no_script_tool()["function"]["parameters"]
    props = params["properties"]
    assert "corrected_segments" in props
    assert "script_diff_summary" not in props
    assert "line_matches" not in props


def test_no_script_tool_required_fields() -> None:
    """build_l2_no_script_tool required 只有 ['corrected_segments']。"""
    from backend.llm.tools.script import build_l2_no_script_tool

    params = build_l2_no_script_tool()["function"]["parameters"]
    assert params["required"] == ["corrected_segments"]


# ---------------------------------------------------------------------------
# Layer 5 smoke
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_jinja_template_renders_tool_declaration() -> None:
    """Layer 0：vocab_only=True 读 GGUF tokenizer.chat_template，
    jinja 渲染 messages+tools 后输出含 <|tool>declaration:report_script_analysis。

    不加载权重，仅验证模板渲染正确。
    """
    model_path = os.environ.get("GEMMA_MODEL_PATH")
    if not model_path:
        pytest.skip("GEMMA_MODEL_PATH 未设置，跳过 smoke test")

    from llama_cpp import Llama  # type: ignore[import]
    from backend.llm.tools.script import build_l2_tool  # type: ignore[import]

    llm = Llama(model_path=model_path, vocab_only=True, verbose=False)
    chat_template = llm.metadata.get("tokenizer.chat_template", "")
    assert chat_template, "GGUF 中未找到 tokenizer.chat_template"

    import jinja2

    env = jinja2.Environment()
    template = env.from_string(chat_template)

    messages = [{"role": "user", "content": "test"}]
    tools = [build_l2_tool()]
    rendered = template.render(
        messages=messages,
        tools=tools,
        add_generation_prompt=True,
    )

    assert "report_script_analysis" in rendered, (
        f"渲染后 prompt 未含工具声明，前 500 字符：{rendered[:500]}"
    )
