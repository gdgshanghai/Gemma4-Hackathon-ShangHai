"""infer_voice_tool 新增 tool_choice 形参 → 透传到 _submit。"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from backend.llm.service import LLMService


class _FakeClient:
    def __init__(self):
        self.last_kwargs = {}

    async def chat_async(self, **kwargs):
        self.last_kwargs = kwargs
        return {"choices": [{"message": {"content": "", "tool_calls": [
            {"function": {"name": "count_takes", "arguments": '{"scene_id":1}'}}
        ]}}]}


def _make_future(result: dict) -> asyncio.Future:
    """在当前事件循环创建一个已 resolved 的 Future，用于 mock _submit。"""
    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    fut.set_result(result)
    return fut


_TOOL_CALL_COUNT_TAKES = {"choices": [{"message": {"content": "", "tool_calls": [
    {"function": {"name": "count_takes", "arguments": '{"scene_id":1}'}}
]}}]}

_TOOL_CALL_STRUCTURE_NOTE = {"choices": [{"message": {"content": "", "tool_calls": [
    {"function": {"name": "structure_note", "arguments": "{}"}}
]}}]}


def test_infer_voice_tool_passes_tool_choice(monkeypatch):
    """tool_choice 形参正确透传到 _submit（镜像 infer_tool 行为）。"""
    svc = object.__new__(LLMService)

    submitted_tc = {}

    async def _fake_submit(messages, *, task_type, priority, timeout, want_tool_call=False, tool_choice=None, audio=None):
        submitted_tc["tool_choice"] = tool_choice
        return _make_future(_TOOL_CALL_COUNT_TAKES)

    monkeypatch.setattr(svc, "_submit", _fake_submit)

    forced = {"type": "function", "function": {"name": "count_takes"}}
    asyncio.run(svc.infer_voice_tool(
        [{"role": "user", "content": "x"}],
        audio=b"\x00" * 100,
        task_type="query_session",
        tool_choice=forced,
    ))
    assert submitted_tc["tool_choice"] == forced


def test_infer_voice_tool_tool_choice_default_none(monkeypatch):
    """tool_choice 默认 None（不传时不改变 _submit 的 tool_choice 行为）。"""
    svc = object.__new__(LLMService)
    submitted_tc = {"called": False}

    async def _fake_submit(messages, *, task_type, priority, timeout, want_tool_call=False, tool_choice=None, audio=None):
        submitted_tc["tool_choice"] = tool_choice
        submitted_tc["called"] = True
        return _make_future(_TOOL_CALL_STRUCTURE_NOTE)

    monkeypatch.setattr(svc, "_submit", _fake_submit)
    asyncio.run(svc.infer_voice_tool(
        [{"role": "user", "content": "x"}],
        audio=b"\x00" * 100,
        task_type="note_struct",
    ))
    assert submitted_tc["tool_choice"] is None
    assert submitted_tc["called"] is True
