"""3.B SP Pipeline 单元测试（完整输出 v5：Gemma 逐行吐 [说话人,台词]，无 grammar）。

覆盖：
  - parse_scene_block：对白 / 描述(空说话人) / 场头 slugline / markdown fence
  - 无 grammar 兜底：模型输出非法 → 冒号启发式 _fallback_lines（台词不丢、不抛）
  - run_sp_parse 多块、空输入
  - 纯函数：_is_scene_header / split_scenes_by_slugline / _parse_slugline /
            _parse_lines_output / _fallback_lines
全部用 AsyncMock 注入 llm_service.infer，不加载真实模型。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.llm.service import LLMService
from backend.pipelines.sp_script import (
    ParsedLine,
    ParsedScene,
    Slugline,
    _fallback_lines,
    _is_scene_header,
    _merge_parentheticals,
    _parse_fc_lines,
    _parse_lines_output,
    _parse_slugline,
    normalize_character,
    parse_scene_block,
    parse_scene_block_fc,
    run_sp_parse,
    split_scenes_by_slugline,
)


def _mock_llm(*responses: str) -> MagicMock:
    """注入 AsyncMock.infer：单个 → return_value；多个 → side_effect 顺序。"""
    svc = MagicMock(spec=LLMService)
    if len(responses) == 1:
        svc.infer = AsyncMock(return_value=responses[0])
    else:
        svc.infer = AsyncMock(side_effect=list(responses))
    return svc


# ── parse_scene_block（完整输出主路径）──────────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_dialogue_lines():
    svc = _mock_llm('[["罗湘","你好。"],["阿明","走吧。"]]')
    scenes = await parse_scene_block("罗湘：你好。\n阿明：走吧。", svc)
    assert len(scenes) == 1
    lines = scenes[0].lines
    assert (lines[0].character, lines[0].text) == ("罗湘", "你好。")
    assert (lines[1].character, lines[1].text) == ("阿明", "走吧。")


@pytest.mark.asyncio
async def test_parse_description_empty_speaker():
    svc = _mock_llm('[["罗湘","你好。"],["","罗湘走到窗边。"]]')
    scenes = await parse_scene_block("罗湘：你好。\n罗湘走到窗边。", svc)
    lines = scenes[0].lines
    assert lines[0].character == "罗湘"
    assert lines[1].character is None  # 空说话人 → 描述
    assert lines[1].text == "罗湘走到窗边。"


@pytest.mark.asyncio
async def test_parse_with_scene_header():
    svc = _mock_llm('[["罗湘","你好。"]]')
    scenes = await parse_scene_block("场3 内 咖啡馆 日\n罗湘：你好。", svc)
    s = scenes[0]
    assert s.scene_code == "3"
    assert s.slugline.int_ext == "内"
    assert s.slugline.time_of_day == "日"
    assert "咖啡馆" in (s.slugline.location or "")
    assert len(s.lines) == 1
    assert s.lines[0].character == "罗湘"


@pytest.mark.asyncio
async def test_parse_strips_markdown_fence():
    svc = _mock_llm('```json\n[["罗湘","你好。"]]\n```')
    scenes = await parse_scene_block("罗湘：你好。", svc)
    assert scenes[0].lines[0].character == "罗湘"


@pytest.mark.asyncio
async def test_parse_fallback_on_invalid_output_no_raise():
    # 模型吐非法（非数组）→ 不抛；走冒号启发式兜底，台词不丢
    svc = _mock_llm("抱歉我无法解析")
    scenes = await parse_scene_block("罗湘：你好。\n（罗湘坐下）", svc)
    lines = scenes[0].lines
    assert lines[0].character == "罗湘" and lines[0].text == "你好。"  # 冒号→对白
    assert lines[1].character is None  # 无冒号→描述
    assert lines[1].text == "（罗湘坐下）"


@pytest.mark.asyncio
async def test_parse_empty_block_no_infer():
    svc = _mock_llm("[]")
    scenes = await parse_scene_block("场3 内 咖啡馆 日", svc)  # 只有场头、无正文
    assert scenes[0].scene_code == "3"
    assert scenes[0].lines == []
    svc.infer.assert_not_called()


# ── run_sp_parse（多块）────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_sp_parse_multi_block():
    svc = _mock_llm('[["罗湘","一。"]]', '[["阿明","二。"]]')
    raw = "场1 内 咖啡馆 日\n罗湘：一。\n\n场2 外 广场 夜\n阿明：二。"
    scenes = await run_sp_parse(raw, svc)
    assert svc.infer.call_count == 2
    assert len(scenes) == 2
    assert scenes[0].scene_code == "1" and scenes[0].lines[0].character == "罗湘"
    assert scenes[1].scene_code == "2" and scenes[1].lines[0].character == "阿明"


@pytest.mark.asyncio
async def test_run_sp_parse_empty_returns_empty():
    svc = _mock_llm("[]")
    assert await run_sp_parse("", svc) == []
    assert await run_sp_parse("   \n  ", svc) == []
    svc.infer.assert_not_called()


# ── 纯函数 ─────────────────────────────────────────────────────────────────────


def test_parse_lines_output_valid():
    out = _parse_lines_output('[["罗湘","你好。"],["","描述行"]]', ["罗湘：你好。", "描述行"])
    assert (out[0].character, out[0].text) == ("罗湘", "你好。")
    assert (out[1].character, out[1].text) == (None, "描述行")


def test_parse_lines_output_wrapped_text():
    # 模型在数组外裹文字 → 仍取 [..] 子串
    out = _parse_lines_output('输出：[["甲","台词"]] 完毕', ["甲：台词"])
    assert (out[0].character, out[0].text) == ("甲", "台词")


def test_parse_lines_output_invalid_falls_back():
    # 非法 → 冒号启发式兜底（台词不丢）
    out = _parse_lines_output("garbage", ["甲：你好", "一句描述"])
    assert (out[0].character, out[0].text) == ("甲", "你好")
    assert (out[1].character, out[1].text) == (None, "一句描述")


def test_fallback_lines():
    out = _fallback_lines(["罗湘：你好。", "罗湘走到窗边。"])
    assert out[0].character == "罗湘" and out[0].text == "你好。"
    assert out[1].character is None  # 无冒号 → 描述


def test_is_scene_header():
    assert _is_scene_header("场3")
    assert _is_scene_header("内 咖啡馆 日")
    assert _is_scene_header("大漠·沙梁 日 外")  # 反序 slugline
    assert not _is_scene_header("罗湘：我们到屋内坐坐吧")  # 台词
    assert not _is_scene_header("他慢慢走出了门外")  # 普通叙述
    assert not _is_scene_header("")
    # 收紧：含句读的叙述不再误判（真实剧本 33→27 误切的根源）
    assert not _is_scene_header("外婆推回给她。")  # "外"开头但是叙述（含句号）
    assert not _is_scene_header("窗外，一辆夜间无人机嗡嗡飞过。")  # 含内外+时间但含句读
    assert not _is_scene_header("内心深处的不安")  # "内"非独立 token（后接非空白）


def test_split_numbered_only_splits_on_labels_and_drops_frontmatter():
    raw = (
        "记忆的温度\n电影剧本\n全 2 场\n\n"  # 首页信息：应丢弃，不成场
        "第1场 内景 咖啡馆 日\n罗湘：你好。\n"
        "外景 门口 夜\n"  # 无号「连续」slugline：应并入第1场，不单切
        "罗湘走出门外，天色已暗。\n"  # 含「外」的叙述：应并入，不单切
        "第2场 外景 广场 夜\n阿明：再见。\n"
    )
    blocks = split_scenes_by_slugline(raw)
    assert len(blocks) == 2  # 只在 第N场 处切
    assert blocks[0].startswith("第1场") and blocks[1].startswith("第2场")
    assert "外景 门口 夜" in blocks[0]  # 连续 slugline 并入第1场
    assert "记忆的温度" not in "".join(blocks)  # 首页信息丢弃


def test_split_no_number_falls_back_to_slugline():
    raw = "内 咖啡馆 日\n罗湘：你好。\n\n外 广场 夜\n阿明：再见。"
    blocks = split_scenes_by_slugline(raw)
    assert len(blocks) == 2  # 无场号 → 回退 slugline 启发式


# ── 括号语气合并（_merge_parentheticals）──────────────────────────────────────


def test_merge_parentheticals_into_next_dialogue():
    out = _merge_parentheticals([ParsedLine("夏雨", "（笑）"), ParsedLine("夏雨", "你说得对。")])
    assert len(out) == 1
    assert (out[0].character, out[0].text) == ("夏雨", "（笑）你说得对。")


def test_merge_parentheticals_speaker_from_next_line():
    out = _merge_parentheticals([ParsedLine(None, "（停顿）"), ParsedLine("沈默", "我们走。")])
    assert (out[0].character, out[0].text) == ("沈默", "（停顿）我们走。")


def test_merge_parentheticals_inline_untouched():
    out = _merge_parentheticals([ParsedLine("夏雨", "（笑）你说得对。")])
    assert len(out) == 1 and out[0].text == "（笑）你说得对。"  # 非纯括号行 → 不动


def test_merge_parentheticals_consecutive_and_halfwidth():
    out = _merge_parentheticals(
        [ParsedLine(None, "（笑）"), ParsedLine(None, "(停顿)"), ParsedLine("夏雨", "走吧")]
    )
    assert len(out) == 1
    assert (out[0].character, out[0].text) == ("夏雨", "（笑）(停顿)走吧")


def test_merge_parentheticals_trailing_kept_as_description():
    out = _merge_parentheticals([ParsedLine("夏雨", "你好"), ParsedLine(None, "（完）")])
    assert len(out) == 2
    assert out[1].character is None and out[1].text == "（完）"


@pytest.mark.asyncio
async def test_parse_scene_block_merges_standalone_parenthetical():
    svc = _mock_llm('[["夏雨","（笑）"],["夏雨","你说得对。"]]')
    scenes = await parse_scene_block("夏雨：（笑）\n你说得对。", svc)
    lines = scenes[0].lines
    assert len(lines) == 1
    assert (lines[0].character, lines[0].text) == ("夏雨", "（笑）你说得对。")


# ── 角色名归一（normalize_character）─────────────────────────────────────────


def test_normalize_character_strips_voiceover():
    assert normalize_character("夏雨（V.O.）") == "夏雨"
    assert normalize_character("夏雨(V.O.)") == "夏雨"  # 半角括号
    assert normalize_character("沈默（记忆中的自己）") == "沈默"


def test_normalize_character_plain_unchanged():
    assert normalize_character("顾朗") == "顾朗"
    assert normalize_character(None) is None


def test_normalize_character_paren_only_kept():
    # 整名就是括号（如旁白），剥后为空 → 保留原名，不归零
    assert normalize_character("（旁白）") == "（旁白）"


def test_normalize_character_multiple_trailing():
    assert normalize_character("夏雨（青年）（V.O.）") == "夏雨"


@pytest.mark.asyncio
async def test_fc_parse_normalizes_voiceover_character():
    """FC 解析出『夏雨（V.O.）』落库前归一为『夏雨』（与对白行同一角色合并）。"""
    svc = _mock_llm_tool(_tool_call([
        {"speaker": "夏雨", "text": "你来了。"},
        {"speaker": "夏雨（V.O.）", "text": "那一年的冬天很冷。"},
    ]))
    scenes = await parse_scene_block_fc("夏雨：你来了。\n夏雨（V.O.）：那一年的冬天很冷。", svc)
    chars = [ln.character for ln in scenes[0].lines]
    assert chars == ["夏雨", "夏雨"]  # 两行归一到同一角色


def test_parse_slugline():
    code, sl = _parse_slugline("场3 内 咖啡馆 日")
    assert code == "3"
    assert sl.int_ext == "内"
    assert sl.time_of_day == "日"
    assert "咖啡馆" in (sl.location or "")


def test_split_scenes_by_slugline():
    raw = "场1 内 咖啡馆 日\n罗湘：你好。\n\n场2 外 广场 夜\n阿明：再见。"
    blocks = split_scenes_by_slugline(raw)
    assert len(blocks) == 2
    assert blocks[0].startswith("场1")
    assert blocks[1].startswith("场2")
    assert split_scenes_by_slugline("") == []


def test_dataclasses():
    s = ParsedScene(
        scene_code=None,
        slugline=Slugline(int_ext=None, time_of_day=None, location=None),
        lines=[ParsedLine(character=None, text="动作")],
    )
    assert s.lines[0].character is None
    assert s.lines[0].text == "动作"


# ── 原生 function calling 路径（parse_scene_block_fc / _parse_fc_lines）──────────


def _tool_call(lines: list) -> dict:
    """构造 report_parsed_lines 的 tool_call dict（arguments 为 JSON 字符串）。"""
    return {
        "type": "function",
        "function": {"name": "report_parsed_lines", "arguments": json.dumps({"lines": lines})},
    }


def _mock_llm_tool(tool_call: dict | None = None, *, raises: Exception | None = None) -> MagicMock:
    """注入 AsyncMock.infer_tool：返回 tool_call 或抛 raises。"""
    svc = MagicMock(spec=LLMService)
    if raises is not None:
        svc.infer_tool = AsyncMock(side_effect=raises)
    else:
        svc.infer_tool = AsyncMock(return_value=tool_call)
    return svc


@pytest.mark.asyncio
async def test_fc_parse_dialogue_and_description():
    svc = _mock_llm_tool(_tool_call([
        {"speaker": "罗湘", "text": "你好。"},
        {"speaker": "", "text": "罗湘走到窗边。"},  # 空说话人 → 描述
    ]))
    scenes = await parse_scene_block_fc("罗湘：你好。\n罗湘走到窗边。", svc)
    lines = scenes[0].lines
    assert (lines[0].character, lines[0].text) == ("罗湘", "你好。")
    assert lines[1].character is None and lines[1].text == "罗湘走到窗边。"


@pytest.mark.asyncio
async def test_fc_parse_with_scene_header():
    svc = _mock_llm_tool(_tool_call([{"speaker": "罗湘", "text": "你好。"}]))
    scenes = await parse_scene_block_fc("场3 内 咖啡馆 日\n罗湘：你好。", svc)
    s = scenes[0]
    assert s.scene_code == "3"
    assert s.slugline.int_ext == "内" and s.slugline.time_of_day == "日"
    assert "咖啡馆" in (s.slugline.location or "")
    assert s.lines[0].character == "罗湘"


@pytest.mark.asyncio
async def test_fc_parse_empty_block_no_infer():
    svc = _mock_llm_tool(_tool_call([]))
    scenes = await parse_scene_block_fc("场3 内 咖啡馆 日", svc)  # 只有场头
    assert scenes[0].scene_code == "3"
    assert scenes[0].lines == []
    svc.infer_tool.assert_not_called()


@pytest.mark.asyncio
async def test_fc_parse_lookup_error_falls_back_no_raise():
    # 模型没走 FC（infer_tool 抛 LookupError）→ 不抛；冒号启发式兜底，台词不丢
    svc = _mock_llm_tool(raises=LookupError("no tool_calls"))
    scenes = await parse_scene_block_fc("罗湘：你好。\n（罗湘坐下）", svc)
    lines = scenes[0].lines
    assert (lines[0].character, lines[0].text) == ("罗湘", "你好。")
    assert lines[1].character is None and lines[1].text == "（罗湘坐下）"


@pytest.mark.asyncio
async def test_fc_parse_invalid_arguments_falls_back():
    # arguments 非法 JSON → 兜底（不崩、台词不丢）
    bad = {"type": "function", "function": {"name": "report_parsed_lines", "arguments": "{not json"}}
    svc = _mock_llm_tool(bad)
    scenes = await parse_scene_block_fc("甲：你好", svc)
    assert (scenes[0].lines[0].character, scenes[0].lines[0].text) == ("甲", "你好")


def test_parse_fc_lines_valid():
    out = _parse_fc_lines(
        _tool_call([{"speaker": "罗湘", "text": "你好。"}, {"speaker": "", "text": "描述行"}]),
        ["罗湘：你好。", "描述行"],
    )
    assert (out[0].character, out[0].text) == ("罗湘", "你好。")
    assert (out[1].character, out[1].text) == (None, "描述行")


def test_parse_fc_lines_tolerates_array_items():
    # 模型偶发吐 [说话人,台词] 数组而非 {speaker,text} → 仍能解析
    out = _parse_fc_lines(_tool_call([["甲", "台词"]]), ["甲：台词"])
    assert (out[0].character, out[0].text) == ("甲", "台词")


def test_parse_fc_lines_invalid_falls_back():
    bad = {"function": {"arguments": "garbage"}}
    out = _parse_fc_lines(bad, ["甲：你好", "一句描述"])
    assert (out[0].character, out[0].text) == ("甲", "你好")
    assert (out[1].character, out[1].text) == (None, "一句描述")
