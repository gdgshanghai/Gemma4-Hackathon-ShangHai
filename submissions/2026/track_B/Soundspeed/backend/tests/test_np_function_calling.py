"""文本 note forced tool-call 红测试（TDD 红阶段，4.x 改造对标 L2 #25）。

把文本 NP（run_np_note）从「裸 JSON 文本 infer」改成 Gemma 原生 function calling：
note_struct 配 tools + 强制 tool_choice → run_np_note 走 infer_tool → 解析
tool_calls[0].function.arguments（合法 JSON）→ 复用 note 字段校验 → NPOutput。

分层（仿 test_l2_function_calling.py）：
Layer 1  build_note_tool schema 构造器（name / 必填字段 / category enum / 类型）
Layer 2  TASK_CONFIG["note_struct"] 含 tools + 强制 tool_choice；registry 注册
Layer 3  pipeline 集成：run_np_note 内部走 infer_tool 路径 + 解析 + 错误分类
Layer 4  真模型 smoke（@pytest.mark.smoke，GEMMA_MODEL_PATH 未设则 skip）

约定：Layer 1-3 全 stub/mock，不加载模型；语音路径（run_np_voice）属 Tier 2，本文件不碰。
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# pipelines 包必须先于 backend.llm.config/service 导入：config 模块级构造 l2_take/note_struct
# 的 tools 会触发 pipelines.__init__ → l2_take → config 循环；先 import pipelines 子模块可让
# 包按安全顺序初始化（与 test_l2_function_calling.py 同源的既有脆弱性，pipelines-first 规避）。
from backend.pipelines.np_note import (
    NPInput,
    NPOutput,
    NPParseError,
    run_np_note,
)
from backend.llm.service import LLMService

# 5 个合法类别（与 np_note 校验同源；schema enum 也取它）
_CATEGORIES = ["note", "issue", "keep", "ng", "pass"]
# 工具名（build_note_tool / config tool_choice / registry 三处须一致）
_NOTE_TOOL_NAME = "structure_note"
# 文本 run_np_note（infer_tool）与语音 run_np_voice（infer_voice_tool）共用 note_struct，
# 两者都走 forced tool-call（无 content-mode 调用，故 tools 加到此 key 不会误伤）。
_TASK = "note_struct"


# ---------------------------------------------------------------------------
# 辅助：构造 tool_calls 响应 + 注入 infer_tool 的 LLMService mock
# ---------------------------------------------------------------------------


def _normal_note_arguments() -> dict:
    return {"take_id": 103, "category": "keep", "content": "结尾很好，可以用"}


def _make_note_tool_call(arguments: dict) -> dict:
    """infer_tool 的返回形态：tool_calls[0]（type/function，arguments 是 JSON 字符串）。"""
    return {
        "id": "call_note_stub_001",
        "type": "function",
        "function": {
            "name": _NOTE_TOOL_NAME,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }


def _mock_note_llm(arguments: dict) -> MagicMock:
    """注入 AsyncMock.infer_tool 的 LLMService mock（返回固定 tool_call）。"""
    svc = MagicMock(spec=LLMService)
    svc.infer_tool = AsyncMock(return_value=_make_note_tool_call(arguments))
    return svc


def _np_input() -> NPInput:
    return NPInput(
        raw_text="第三条结尾很好，可以用",
        parsed_category="note",
        current_scene_id=1,
        current_take_id=103,
        take_context=[
            {"take_id": 103, "scene_code": "Scene_1", "shot": "Shot1", "take_number": 3},
        ],
        ts=123.0,
        current_scene_code="Scene_1",
        current_shot="Shot1",
        current_take_number=3,
    )


# ---------------------------------------------------------------------------
# Layer 1：build_note_tool schema
# ---------------------------------------------------------------------------


def test_build_note_tool_is_function_type() -> None:
    from backend.llm.tools.note import build_note_tool

    tool = build_note_tool()
    assert tool["type"] == "function"
    assert tool["function"]["name"] == _NOTE_TOOL_NAME


def test_build_note_tool_required_fields() -> None:
    from backend.llm.tools.note import build_note_tool

    params = build_note_tool()["function"]["parameters"]
    assert params["type"] == "object"
    assert set(params["required"]) == {"take_id", "category", "content"}


def test_build_note_tool_field_types() -> None:
    from backend.llm.tools.note import build_note_tool

    props = build_note_tool()["function"]["parameters"]["properties"]
    assert props["take_id"]["type"] == "integer"
    assert props["content"]["type"] == "string"
    assert props["category"]["type"] == "string"


def test_build_note_tool_category_enum_matches_validator() -> None:
    """schema 的 category enum 必须正好是 5 个合法类别（与校验同源，防漂移）。"""
    from backend.llm.tools.note import build_note_tool

    enum = build_note_tool()["function"]["parameters"]["properties"]["category"]["enum"]
    assert sorted(enum) == sorted(_CATEGORIES)


# ---------------------------------------------------------------------------
# Layer 2：TASK_CONFIG["note_struct"] 含 tools + 强制 tool_choice；registry 注册
# ---------------------------------------------------------------------------


def test_text_task_config_has_tools() -> None:
    from backend.llm.config import TASK_CONFIG

    cfg = TASK_CONFIG[_TASK]
    assert "tools" in cfg
    assert cfg["tools"][0]["function"]["name"] == _NOTE_TOOL_NAME


def test_text_task_config_forces_tool_choice() -> None:
    from backend.llm.config import TASK_CONFIG

    cfg = TASK_CONFIG[_TASK]
    assert cfg["tool_choice"] == {
        "type": "function",
        "function": {"name": _NOTE_TOOL_NAME},
    }


def test_note_tool_registered() -> None:
    from backend.llm.tools import registry

    assert _NOTE_TOOL_NAME in registry.list_tools()
    assert registry.get_tool_schema(_NOTE_TOOL_NAME)["function"]["name"] == _NOTE_TOOL_NAME


# ---------------------------------------------------------------------------
# Layer 3：run_np_note pipeline 集成（走 infer_tool 路径）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_np_note_uses_infer_tool() -> None:
    """run_np_note 走 infer_tool（非 infer），task_type=note_struct。"""
    svc = _mock_note_llm(_normal_note_arguments())

    await run_np_note(_np_input(), svc)

    svc.infer_tool.assert_awaited_once()
    _, kwargs = svc.infer_tool.call_args
    assert kwargs.get("task_type") == _TASK


@pytest.mark.asyncio
async def test_run_np_note_parses_tool_call_arguments() -> None:
    """tool_call.function.arguments(JSON) → NPOutput(take_id/category/content)。"""
    svc = _mock_note_llm(_normal_note_arguments())

    out = await run_np_note(_np_input(), svc)

    assert isinstance(out, NPOutput)
    assert out.take_id == 103
    assert out.category == "keep"
    assert out.content == "结尾很好，可以用"


@pytest.mark.asyncio
async def test_run_np_note_lookup_error_becomes_parse_error() -> None:
    """infer_tool 抛 LookupError（模型没走 FC）→ NPParseError。"""
    svc = MagicMock(spec=LLMService)
    svc.infer_tool = AsyncMock(side_effect=LookupError("no tool_calls"))

    with pytest.raises(NPParseError):
        await run_np_note(_np_input(), svc)


@pytest.mark.asyncio
async def test_run_np_note_bad_arguments_json_becomes_parse_error() -> None:
    """tool_call.arguments 非合法 JSON → NPParseError。"""
    svc = MagicMock(spec=LLMService)
    bad = {
        "id": "x",
        "type": "function",
        "function": {"name": _NOTE_TOOL_NAME, "arguments": "{not json"},
    }
    svc.infer_tool = AsyncMock(return_value=bad)

    with pytest.raises(NPParseError):
        await run_np_note(_np_input(), svc)


@pytest.mark.asyncio
async def test_run_np_note_invalid_category_becomes_parse_error() -> None:
    """arguments 里 category 非法 → 复用 note 字段校验 → NPParseError。"""
    svc = _mock_note_llm({"take_id": 1, "category": "bogus", "content": "x"})

    with pytest.raises(NPParseError):
        await run_np_note(_np_input(), svc)


# ---------------------------------------------------------------------------
# Layer 4：真模型 smoke（@smoke，GEMMA_MODEL_PATH 未设则 skip）
# ---------------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_run_np_note_fc_real_model_smoke() -> None:
    """真 Gemma 4 走 note_struct forced tool-call：文本 note → tool_calls → NPOutput。

    注意：经多模态单实例（mmproj handler）跑 forced tool-call 的真效果，是 merge 后唯一
    没被 stub 覆盖的路径（advisor 标记）。本 smoke 即覆盖它。
    """
    if not os.getenv("GEMMA_MODEL_PATH"):
        pytest.skip("需要 GEMMA_MODEL_PATH 指向真实 GGUF")

    from backend.llm.service import _reset_service, get_service

    _reset_service()
    svc = get_service()
    try:
        out = await run_np_note(_np_input(), svc, timeout=120.0)
        assert isinstance(out, NPOutput)
        assert out.category in _CATEGORIES
        assert isinstance(out.take_id, int)
    finally:
        _reset_service()
