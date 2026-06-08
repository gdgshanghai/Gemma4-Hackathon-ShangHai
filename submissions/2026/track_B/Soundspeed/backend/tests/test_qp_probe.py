"""QP 建循环前的真模型 probe（@pytest.mark.smoke，未设 GEMMA_MODEL_PATH 则 skip）。

钉死两条假设并把结论编码成断言（回归护网）。结论已回填 spec §5.1：

  假设 7 ✅ 证实：auto 跳返回 FunctionGemma **content 字符串**（`<|tool_call>call:NAME{...}`），
    不是结构化 tool_calls，不撞 service 护栏。两步走（auto 抠名 → forced 取参）成立。
  假设 6 ✗ 证伪 → 已解：OpenAI 风格 assistant{tool_calls}+role=tool 多跳回喂撞 Jinja 模板
    `UndefinedError: 'raise_exception' is undefined`（状态相关、不稳）。Task 9 step C 改用
    **纯文本回喂**：assistant=auto 原始 content（模型自吐 <|tool_call>）+ user=「工具 NAME 返回：{json}」。
    实测确定性稳定渲染 + 自然语言收尾。

forced 路径已由既有 L2 工作证明，本文件不重复。本 probe 不依赖 qp_query.py（Task 9）。

实测环境：macOS / llama-cpp-python 0.3.25 / unsloth gemma-4-E4B-it-Q4_K_M.gguf。
注：连续多次加载模型后 llama.cpp Metal 退出期有 GGML_ASSERT teardown 崩溃（已知上游 bug，
测试结果在崩溃前已产出，不影响断言；Task 11 e2e 单测内复用单一 client 规避多次加载）。
"""
from __future__ import annotations

import json
import os
import re

import pytest

from backend.llm.config import TASK_CONFIG
from backend.llm.service import LLMService, _reset_service, resolve_model_path

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not os.environ.get("GEMMA_MODEL_PATH"),
        reason="GEMMA_MODEL_PATH 未设置，跳过真模型 probe",
    ),
]

# 与计划 Task 9 的 _scrape_tool_name 同源正则（FunctionGemma：<|tool_call>call:NAME{...}）
_TOOL_NAME_RE = re.compile(r"<\|tool_call>call:(\w+)")
_QP_NAMES = {
    "count_takes",
    "get_scene_info",
    "list_characters",
    "search_script_lines",
    "query_database",
}


@pytest.fixture
def real_service():
    _reset_service()
    svc = LLMService()
    yield svc


@pytest.mark.smoke
def test_probe_auto_returns_content_not_toolcalls() -> None:
    """假设 7：直连 client，auto 模式返回 content 字符串、tool_calls 为空（非结构化）。"""
    from backend.llm.client import GemmaClient

    path = resolve_model_path(download=False)
    assert path, "HF cache / env 找不到 GGUF"
    client = GemmaClient(model_path=path)

    cfg = TASK_CONFIG["query_session"]
    messages = [
        {"role": "system", "content": cfg["system"]},
        {"role": "user", "content": "第一场拍了多少条？"},
    ]
    result = client.create_chat_completion(
        messages=messages, tools=cfg["tools"], tool_choice="auto", max_tokens=512, temperature=0.3
    )
    choice = result["choices"][0]
    msg = choice["message"]
    print(f"\n[RAW auto] finish_reason={choice.get('finish_reason')!r} "
          f"content={msg.get('content')!r} tool_calls={msg.get('tool_calls')!r}")
    # 假设 7 核心断言：auto 走 content 路径（content 是 str、不是 None），不吐结构化 tool_calls。
    assert isinstance(msg.get("content"), str) and msg["content"]
    assert not msg.get("tool_calls")


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_probe_auto_via_service_returns_str(real_service) -> None:
    """假设 7（service 层）：service.infer 在 auto 跳返回 str，不撞护栏（不抛 LookupError）。"""
    messages = [
        {"role": "system", "content": TASK_CONFIG["query_session"]["system"]},
        {"role": "user", "content": "第一场拍了多少条？"},
    ]
    # 若 auto 吐 content=None+finish_reason=tool_calls，infer 会抛 LookupError → 测试失败（捕捉回归）。
    text = await real_service.infer(messages, task_type="query_session", timeout=180.0)
    name = _TOOL_NAME_RE.search(text or "")
    print(f"\n[service.infer auto] text={text!r} scraped={name.group(1) if name else None!r}")
    assert isinstance(text, str)
    await real_service.aclose()


@pytest.mark.smoke
def test_probe_task9_feedback_format_renders() -> None:
    """假设 6 解：Task 9 step C 选定的纯文本回喂格式稳定渲染（不撞模板错）+ 自然语言收尾（不再调工具）。

    格式：assistant=auto 原始 content（模型自吐 <|tool_call>）+ user=「工具 NAME 返回：{json}」。
    跑 3 次验确定性。
    """
    from backend.llm.client import GemmaClient

    path = resolve_model_path(download=False)
    client = GemmaClient(model_path=path)
    cfg = TASK_CONFIG["query_session"]
    auto_content = '<|tool_call>call:count_takes{scene_ref:<|"|>第1场<|"|>}<tool_call|>'
    result = {"scene_ref": "第1场", "count": 3}
    messages = [
        {"role": "system", "content": "你是场记查询助手。查到结果后用一句话直接回答，不要再调工具。"},
        {"role": "user", "content": "第一场拍了多少条？"},
        {"role": "assistant", "content": auto_content},
        {"role": "user", "content": f"工具 count_takes 返回：{json.dumps(result, ensure_ascii=False)}"},
    ]
    for i in range(3):
        # 不 try/except：若模板炸（assumption 6 回归）这里直接抛 → 测试失败暴露问题。
        r = client.create_chat_completion(
            messages=messages, tools=cfg["tools"], tool_choice="auto", max_tokens=256, temperature=0.3
        )
        content = r["choices"][0]["message"].get("content")
        print(f"\n[task9-fmt iter {i}] content={content!r}")
        assert isinstance(content, str) and content  # 渲染成功 + 有回复
        assert "<|tool_call>" not in content  # 自然语言收尾，不再调工具


@pytest.mark.smoke
def test_probe_openai_toolrole_format_unreliable() -> None:
    """记录：OpenAI 风格 role=tool 多跳回喂在本模板下不可靠（已观察到 raise_exception 模板错，状态相关）。

    本测试只打印结果不硬断言——它是「为什么 Task 9 step C 不用 OpenAI 格式」的实证留痕。
    干净单加载进程里可能 OK，但多加载/某些状态下抛 UndefinedError，故 Task 9 弃用此格式。
    """
    from backend.llm.client import GemmaClient

    path = resolve_model_path(download=False)
    client = GemmaClient(model_path=path)
    cfg = TASK_CONFIG["query_session"]
    messages = [
        {"role": "system", "content": "你是场记查询助手。查到结果后用一句话直接回答。"},
        {"role": "user", "content": "第一场拍了多少条？"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "c0", "type": "function",
                 "function": {"name": "count_takes", "arguments": '{"scene_ref": "1"}'}}
            ],
        },
        {"role": "tool", "tool_call_id": "c0", "name": "count_takes", "content": '{"count": 3}'},
    ]
    try:
        r = client.create_chat_completion(
            messages=messages, tools=cfg["tools"], tool_choice="auto", max_tokens=256, temperature=0.3
        )
        print(f"\n[openai role=tool] OK -> {r['choices'][0]['message'].get('content')!r}")
    except Exception as exc:  # noqa: BLE001  记录模板错，不让它使测试失败
        print(f"\n[openai role=tool] RAISED -> {type(exc).__name__}: {exc}")
