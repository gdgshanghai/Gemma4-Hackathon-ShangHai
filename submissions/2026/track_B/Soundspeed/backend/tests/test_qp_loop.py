"""两步走循环（L2）：StubService 喂固定 auto content + forced tool_calls。

断言：抠名正确、forced 取参正确、≤5 跳终止、出错回喂、终止条件、最终答案返回。
异常契约：asyncio.TimeoutError 放行给 caller；取参失败/未知工具包成 error 回喂不抛穿。
"""
from __future__ import annotations

import asyncio
import json

import pytest

from backend.pipelines.qp_query import _build_scene_catalog, _run_executor, _scrape_tool_name, run_tool_loop


def test_scrape_tool_name_functiongemma() -> None:
    # FunctionGemma auto content 格式（FC spec §3.2）：<|tool_call>call:NAME{...}
    text = "<|tool_call>call:count_takes{scene_ref:<|\"|>1<|\"|>}<tool_call|>"
    assert _scrape_tool_name(text) == "count_takes"


def test_scrape_tool_name_none_when_plain_text() -> None:
    assert _scrape_tool_name("第一场一共拍了 3 条。") is None
    assert _scrape_tool_name("") is None


class _ScriptedService:
    """按脚本依次返回 auto content（infer）/ forced tool_calls（infer_tool）。

    auto_replies：每跳 step A 的 content 串（含 <|tool_call> 则继续，否则为最终答案）。
    forced_args：每次 step B 返回的 arguments dict（按调用顺序）；
                 元素为 Exception 实例时 infer_tool 直接抛出该异常。
    """

    def __init__(self, auto_replies: list[str], forced_args: list) -> None:
        self._auto = list(auto_replies)
        self._forced = list(forced_args)
        self.infer_calls = 0
        self.infer_tool_calls = 0

    async def infer(self, messages, task_type, priority=None, timeout=None, tool_choice=None) -> str:
        self.infer_calls += 1
        return self._auto.pop(0)

    async def infer_tool(self, messages, task_type, priority=None, timeout=None, tool_choice=None) -> dict:
        self.infer_tool_calls += 1
        item = self._forced.pop(0)
        if isinstance(item, BaseException):
            raise item
        return {"function": {"name": tool_choice["function"]["name"], "arguments": json.dumps(item)}}


class _StubDAL:
    """executor 在循环里被调用，这里只需返回可序列化结果。"""

    def resolve_scene_id(self, ref):
        return 1 if ref in {"1", "第一场"} else None

    def count_takes(self, scene_id, status=None):
        return 3

    def list_scenes_readonly(self):
        return []


@pytest.mark.asyncio
async def test_loop_single_hop_then_answer() -> None:
    # hop1: 调 count_takes；hop2: 不再调工具，给最终答案
    svc = _ScriptedService(
        auto_replies=[
            "<|tool_call>call:count_takes{scene_ref:<|\"|>1<|\"|>}<tool_call|>",
            "第一场一共拍了 3 条。",
        ],
        forced_args=[{"scene_ref": "1"}],
    )
    messages = [{"role": "user", "content": "第一场拍了多少条"}]
    answer = await run_tool_loop(messages, service=svc, dal=_StubDAL())
    assert answer == "第一场一共拍了 3 条。"
    assert svc.infer_tool_calls == 1
    # 工具结果被回喂进 messages（纯文本格式，Task 7.5 实证：assistant 原始 content + user「工具…返回…」）
    assert any(m["role"] == "user" and m["content"].startswith("工具 ") for m in messages)


@pytest.mark.asyncio
async def test_loop_terminates_at_max_hops() -> None:
    # 每跳都调工具、永不收尾 → 走到 5 跳兜底
    looping = "<|tool_call>call:count_takes{scene_ref:<|\"|>1<|\"|>}<tool_call|>"
    svc = _ScriptedService(
        auto_replies=[looping] * 5,
        forced_args=[{"scene_ref": "1"}] * 5,
    )
    answer = await run_tool_loop(
        [{"role": "user", "content": "x"}], service=svc, dal=_StubDAL()
    )
    assert "超过上限" in answer or "轮数" in answer
    assert svc.infer_tool_calls == 5  # 恰好 5 跳
    assert svc.infer_calls == 5       # off-by-one 护栏：infer 调用次数也是 5


@pytest.mark.asyncio
async def test_loop_feeds_executor_error_back() -> None:
    # 找不到场次 → executor 返回 error，回喂后模型收尾
    svc = _ScriptedService(
        auto_replies=[
            "<|tool_call>call:count_takes{scene_ref:<|\"|>999<|\"|>}<tool_call|>",
            "数据库里没有第 999 场。",
        ],
        forced_args=[{"scene_ref": "999"}],
    )
    messages = [{"role": "user", "content": "第999场拍了多少"}]
    answer = await run_tool_loop(messages, service=svc, dal=_StubDAL())
    assert "999" in answer
    # error 串被回喂（纯文本 user 消息「工具 count_takes 返回：{...error...}」）
    fed = [m for m in messages if m["role"] == "user" and m["content"].startswith("工具 ")][0]
    assert "error" in fed["content"]


@pytest.mark.asyncio
async def test_loop_forced_parse_failure_feeds_error() -> None:
    # step B infer_tool 抛 LookupError（模型没走 FC）→ 循环不崩、error 回喂、模型能继续收尾
    svc = _ScriptedService(
        auto_replies=[
            "<|tool_call>call:count_takes{scene_ref:<|\"|>1<|\"|>}<tool_call|>",
            "好的，已查到结果。",
        ],
        forced_args=[LookupError("模型没走 FC")],
    )
    messages = [{"role": "user", "content": "第一场拍了多少"}]
    answer = await run_tool_loop(messages, service=svc, dal=_StubDAL())
    # 循环不崩，模型能收尾
    assert isinstance(answer, str) and answer
    # error 被回喂为 role=user「工具…返回…」消息
    fed = [m for m in messages if m["role"] == "user" and m["content"].startswith("工具 ")]
    assert fed, "取参失败的 error 应该被回喂进 messages"
    assert "error" in fed[0]["content"]


@pytest.mark.asyncio
async def test_loop_timeout_propagates() -> None:
    # infer_tool 抛 asyncio.TimeoutError → run_tool_loop 放行给 caller（不吞）
    svc = _ScriptedService(
        auto_replies=["<|tool_call>call:count_takes{scene_ref:<|\"|>1<|\"|>}<tool_call|>"],
        forced_args=[asyncio.TimeoutError()],
    )
    with pytest.raises(asyncio.TimeoutError):
        await run_tool_loop(
            [{"role": "user", "content": "x"}], service=svc, dal=_StubDAL()
        )


def test_run_executor_unknown_tool() -> None:
    # KeyError 分支：未知工具名 → 返回 error dict，不抛穿
    result = _run_executor("不存在的工具名xyz", {}, _StubDAL())
    assert "error" in result


def test_build_scene_catalog_empty() -> None:
    # list_scenes_readonly 返空 → 含「还没有任何场次」
    catalog = _build_scene_catalog(_StubDAL())
    assert "还没有任何场次" in catalog


def test_build_scene_catalog_with_scenes() -> None:
    class _DALWithScenes:
        def list_scenes_readonly(self):
            return [
                {"scene_code": "Scene_1", "int_ext": "室内", "location": "客厅", "time_of_day": "日"},
                {"scene_code": "Scene_2", "int_ext": None, "location": "天台", "time_of_day": "夜"},
            ]

    catalog = _build_scene_catalog(_DALWithScenes())
    assert "Scene_1" in catalog
    assert "Scene_2" in catalog
    assert "客厅" in catalog
