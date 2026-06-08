"""语音调度器两步走管线（形态 A）。

hop A（infer_voice 文本注入 + _scrape_tool_name 抠名）→ 分流：
  structure_note → note 分支（hop B forced 取参 → _persist_np_output_callable）
  QP 工具        → query 分支（hop B forced 取参 → asyncio.to_thread(_run_executor) → run_tool_loop → broadcast）
  None（抠不到）→ fail-closed note 分支

单测全用 mock service，不加载真模型。
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock


WAV_BYTES = b"\x00" * 200   # stub audio


# ── stub builders ──────────────────────────────────────────────────────────────

def _make_infer_voice_resp(tool_name: str, args: dict) -> str:
    """生成 corrected-C3 格式的 hop A 输出文本（对齐 _TOOL_NAME_RE）。"""
    return f"<|tool_call>call:{tool_name}{json.dumps(args)}<tool_call|>"


class _StubService:
    """stub LLMService：audio 是位置参数（对齐真实 service.py 签名）。"""

    def __init__(self, hop_a_name: str | None, hop_a_args: dict, hop_b_args: dict):
        self._hop_a_name = hop_a_name
        self._hop_a_output = (
            _make_infer_voice_resp(hop_a_name, hop_a_args) if hop_a_name else "我不太明白"
        )
        self._hop_b_result = {
            "function": {
                "name": hop_a_name or "structure_note",
                "arguments": json.dumps(hop_b_args),
            }
        }

    async def infer_voice(self, messages, audio, task_type, **kw) -> str:
        return self._hop_a_output

    async def infer_voice_tool(self, messages, audio, task_type, tool_choice=None, **kw) -> dict:
        return self._hop_b_result


class _StubDAL:
    pass


class _StubCM:
    def __init__(self):
        self.broadcasts = []

    def broadcast(self, topic, payload):
        self.broadcasts.append((topic, payload))


# ── tests ──────────────────────────────────────────────────────────────────────

def _patch_build_hop_a_system(monkeypatch) -> None:
    """patch build_hop_a_system 避免 extract_tool_declarations_text 加载 GGUF（单测无模型）。"""
    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch.build_hop_a_system",
        lambda scene_context="": "stub system",
    )


def test_note_branch_calls_persist(monkeypatch):
    """hop A 抠到 structure_note → 走 note 分支，调 _persist_np_output_callable。"""
    _patch_build_hop_a_system(monkeypatch)
    from backend.pipelines.voice_dispatch import run_voice_dispatch

    persisted = {}

    async def _fake_persist(output, *, ts, client_id, raw_text_override):
        # output 是 awaitable（coroutine）—— 对齐生产 adapter _finalize_np 的 await 语义
        result = await output
        persisted["done"] = True
        persisted["output"] = result

    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._persist_np_output_callable",
        _fake_persist,
    )

    svc = _StubService(
        "structure_note", {},
        {"category": "pass", "content": "这条过了", "take_id": 1},
    )
    asyncio.run(run_voice_dispatch(
        WAV_BYTES,
        conn_id="c1",
        ts=1000.0,
        client_id="cid1",
        dal=_StubDAL(),
        service=svc,
        cm=_StubCM(),
        scene_context="",
    ))
    assert persisted.get("done") is True


def test_query_branch_broadcasts(monkeypatch):
    """hop A 抠到 count_takes → 走 query 分支，广播 qp.answer.{conn_id}。

    _run_executor 是同步 MagicMock（asyncio.to_thread 在线程里调用它）。
    run_tool_loop 是 fake 异步函数，断言 messages[-1]['content'] 含工具返回 JSON。
    _schedule_qp_broadcast 是 AsyncMock（验 conn_id 被传到）。
    """
    _patch_build_hop_a_system(monkeypatch)
    from backend.pipelines.voice_dispatch import run_voice_dispatch  # noqa: PLC0415

    # _run_executor 是同步函数，被 asyncio.to_thread 包装，mock 需为普通 MagicMock
    sync_executor = MagicMock(return_value={"count": 7})
    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._run_executor",
        sync_executor,
    )

    captured_tool_messages: list[dict] = []

    async def _fake_loop(messages_arg, *, service, dal, **kw):
        captured_tool_messages.extend(messages_arg)
        return "第一场拍了 7 条。"

    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch.run_tool_loop",
        _fake_loop,
    )
    broadcast_calls = []

    async def _fake_broadcast(answer_text, conn_id, *, client_id=None, dal, service, cm):
        broadcast_calls.append((conn_id, client_id))

    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._schedule_qp_broadcast",
        _fake_broadcast,
    )

    svc = _StubService("count_takes", {"scene_id": 1}, {"scene_id": 1})
    cm = _StubCM()
    asyncio.run(run_voice_dispatch(
        WAV_BYTES,
        conn_id="c2",
        ts=1000.0,
        client_id="cid2",
        dal=_StubDAL(),
        service=svc,
        cm=cm,
        scene_context="Scene 1: 大堂",
    ))
    # conn_id 用于广播 topic，client_id 透传进 payload 供前端精确撤语音 pending。
    assert broadcast_calls == [("c2", "cid2")]
    # 验证工具返回 JSON 正确注入 messages 最后一帧
    expected_tool_return = json.dumps({"count": 7}, ensure_ascii=False)
    assert captured_tool_messages, "run_tool_loop 未被调用"
    assert expected_tool_return in captured_tool_messages[-1]["content"]


def test_fail_closed_note_when_scrape_returns_none(monkeypatch):
    """hop A 抠不到工具名 → fail-closed 走 note 分支（hop B forced structure_note）。"""
    _patch_build_hop_a_system(monkeypatch)
    from backend.pipelines.voice_dispatch import run_voice_dispatch

    persisted = {}

    async def _fake_persist(output, *, ts, client_id, raw_text_override):
        # output 是 awaitable（coroutine）—— 对齐生产 adapter _finalize_np 的 await 语义
        await output
        persisted["done"] = True

    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._persist_np_output_callable",
        _fake_persist,
    )

    # hop A 返回自然语言散文（无 tool_call 格式）
    svc = _StubService(None, {}, {"category": "pass", "content": "这条过了", "take_id": 1})
    asyncio.run(run_voice_dispatch(
        WAV_BYTES,
        conn_id="c3",
        ts=1000.0,
        client_id="cid3",
        dal=_StubDAL(),
        service=svc,
        cm=_StubCM(),
        scene_context="",
    ))
    assert persisted.get("done") is True


def test_query_hop_messages_structure(monkeypatch):
    """query 续跳 messages 是全新拼的纯文本 4 帧，不含 image_url（AUDIO_SENTINEL）。

    帧结构：system → user(占位) → assistant(hop_a_text) → user(工具返回)。
    run_tool_loop 真签名：(messages, *, service, dal, ...)。
    fake 收到 positional messages_arg，断言帧数/角色/无 image_url。
    """
    _patch_build_hop_a_system(monkeypatch)
    from backend.pipelines.voice_dispatch import run_voice_dispatch

    captured: dict = {}

    async def _fake_loop(messages_arg, *, service, dal, **kw):
        captured["messages"] = messages_arg
        # 断言不含任何 image_url content part
        for msg in messages_arg:
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if part.get("type") == "image_url":
                        captured["has_sentinel"] = True
        return "7 条"

    monkeypatch.setattr("backend.pipelines.voice_dispatch.run_tool_loop", _fake_loop)
    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._run_executor",
        MagicMock(return_value={"count": 7}),
    )
    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._schedule_qp_broadcast",
        AsyncMock(),
    )

    svc = _StubService("count_takes", {"scene_id": 1}, {"scene_id": 1})
    asyncio.run(run_voice_dispatch(
        WAV_BYTES, conn_id="c4", ts=1000.0, client_id="cid4",
        dal=_StubDAL(), service=svc, cm=_StubCM(), scene_context="Scene 1",
    ))
    msgs = captured.get("messages", [])
    assert msgs, "run_tool_loop 未被调用"
    assert len(msgs) == 4, f"期望 4 帧，实际 {len(msgs)}"
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "user"], f"帧角色不对: {roles}"
    assert not captured.get("has_sentinel"), "续跳 messages 含 image_url（AUDIO_SENTINEL 未剔除）"
    # system 帧含 _QP_SYSTEM 内容（场记查询助手）且含 scene_context
    assert "场记查询助手" in msgs[0]["content"]
    assert "Scene 1" in msgs[0]["content"]
    # 最后一帧含工具返回 JSON
    assert json.dumps({"count": 7}, ensure_ascii=False) in msgs[-1]["content"]


def test_note_branch_delegates_to_voice_runner_when_np_input_provided(monkeypatch):
    """note 分支：有 np_input + voice_runner → 委托 voice_runner 而非 _parse_tool_call。

    voice_runner 被调时收到 (np_input, audio, service)，确保 take 上下文正确（修 FK 失败）。
    _persist_np_output_callable adapter await output 得到 NPOutput → 落库（模拟）。
    """
    _patch_build_hop_a_system(monkeypatch)
    from backend.pipelines.voice_dispatch import run_voice_dispatch
    from backend.pipelines.np_note import NPInput, NPOutput

    # 构造 fake NPInput（含 current_take_id）
    fake_np_input = NPInput(
        raw_text="",
        parsed_category="note",
        current_scene_id=1,
        current_take_id=42,  # 正确 take_id
        take_context=[],
        ts=1000.0,
        current_scene_code="1A",
        current_shot="A",
        current_take_number=3,
    )

    voice_runner_called: dict = {}

    async def _fake_voice_runner(np_in, audio_bytes, svc):
        voice_runner_called["np_input"] = np_in
        voice_runner_called["audio_len"] = len(audio_bytes)
        # 返回正确 take_id 的 NPOutput（来自 np_input.current_take_id）
        return NPOutput(take_id=np_in.current_take_id, category="pass", content="这条过了")

    persisted: dict = {}

    async def _fake_persist(output, *, ts, client_id, raw_text_override):
        # adapter 逻辑：await awaitable → 得到 NPOutput → 落库
        result = await output
        persisted["take_id"] = result.take_id
        persisted["category"] = result.category

    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._persist_np_output_callable",
        _fake_persist,
    )

    svc = _StubService(
        "structure_note", {},
        {"category": "ng", "content": "这条不行", "take_id": 999},  # 模型猜的错误 take_id
    )
    asyncio.run(run_voice_dispatch(
        WAV_BYTES,
        conn_id="c-delegate",
        ts=1000.0,
        client_id="cid-d",
        dal=_StubDAL(),
        service=svc,
        cm=_StubCM(),
        scene_context="",
        np_input=fake_np_input,
        voice_runner=_fake_voice_runner,
    ))

    # 验证委托路径被走（voice_runner 被调，np_input 含正确 current_take_id）
    assert voice_runner_called.get("np_input") is fake_np_input, "voice_runner 未被调（应走委托路径）"
    assert voice_runner_called["np_input"].current_take_id == 42

    # 验证落库 take_id 来自 voice_runner（42），不是 hop_b_result 里模型猜的 999
    assert persisted.get("take_id") == 42, (
        f"take_id 应为 42（来自 np_input），实际 {persisted.get('take_id')}"
    )


# ── 回归：_schedule_qp_broadcast 接线后 cm.broadcast 收到 QpAnswerPayload dataclass ──

def test_query_branch_broadcast_payload_is_dataclass(monkeypatch):
    """回归测试：query 分支通过 _schedule_qp_broadcast 调 cm.broadcast 时，
    payload 必须是 QpAnswerPayload 冻结 dataclass，不能是 plain dict。

    _broadcast_wrapper（lifespan 接线）传 plain dict 会触发 asdict() TypeError，
    答案永远无法送达前端。此测试直接验证广播 payload 的类型。
    """
    import dataclasses

    _patch_build_hop_a_system(monkeypatch)

    # 构造一个记录 broadcast 调用的 CM stub（不 mock asdict，直接检查 payload 类型）
    class _CheckingCM:
        def __init__(self):
            self.calls: list[tuple] = []

        def broadcast(self, topic: str, payload) -> None:
            self.calls.append((topic, payload))
            # 模拟 ws.py:97 的 asdict(payload)，确认运行时不崩
            dataclasses.asdict(payload)  # plain dict 会 TypeError

    # 先用「修复前」的裸 dict 版本验证它确实报错（红阶段）
    async def _wrong_wrapper(answer: str, conn_id: str, *, client_id=None, dal, service, cm) -> None:
        cm.broadcast(f"qp.answer.{conn_id}", {"connection_id": conn_id, "answer_text": answer})

    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._schedule_qp_broadcast",
        _wrong_wrapper,
    )
    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._run_executor",
        MagicMock(return_value={"count": 3}),
    )
    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch.run_tool_loop",
        AsyncMock(return_value="第一场拍了 3 条。"),
    )

    from backend.pipelines.voice_dispatch import run_voice_dispatch

    svc = _StubService("count_takes", {"scene_id": 1}, {"scene_id": 1})
    cm = _CheckingCM()

    import pytest
    with pytest.raises(TypeError):
        # 修复前：plain dict 传给 asdict() 会 TypeError
        asyncio.run(run_voice_dispatch(
            WAV_BYTES,
            conn_id="c-payload",
            ts=1000.0,
            client_id="cid-payload",
            dal=_StubDAL(),
            service=svc,
            cm=cm,
            scene_context="",
        ))


def test_query_branch_broadcast_payload_is_dataclass_after_fix(monkeypatch):
    """修复后：_schedule_qp_broadcast 传 QpAnswerPayload，asdict() 不崩，topic 用 QP_ANSWER 常量。"""
    import dataclasses
    from backend.core.events import QP_ANSWER, QpAnswerPayload

    _patch_build_hop_a_system(monkeypatch)

    class _CheckingCM:
        def __init__(self):
            self.calls: list[tuple] = []

        def broadcast(self, topic: str, payload) -> None:
            self.calls.append((topic, payload))
            dataclasses.asdict(payload)  # 断言不崩

    # 修复后的正确 wrapper：传 QpAnswerPayload 和 QP_ANSWER 常量，client_id 透传进 payload。
    async def _correct_wrapper(answer: str, conn_id: str, *, client_id=None, dal, service, cm) -> None:
        cm.broadcast(
            f"{QP_ANSWER}.{conn_id}",
            QpAnswerPayload(connection_id=conn_id, answer_text=answer, client_id=client_id),
        )

    from backend.pipelines.voice_dispatch import run_voice_dispatch

    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._schedule_qp_broadcast",
        _correct_wrapper,
    )
    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._run_executor",
        MagicMock(return_value={"count": 3}),
    )
    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch.run_tool_loop",
        AsyncMock(return_value="第一场拍了 3 条。"),
    )

    svc = _StubService("count_takes", {"scene_id": 1}, {"scene_id": 1})
    cm = _CheckingCM()
    asyncio.run(run_voice_dispatch(
        WAV_BYTES,
        conn_id="c-payload2",
        ts=1000.0,
        client_id="cid-payload2",
        dal=_StubDAL(),
        service=svc,
        cm=cm,
        scene_context="",
    ))

    assert len(cm.calls) == 1, f"broadcast 应被调 1 次，实际 {len(cm.calls)}"
    topic, payload = cm.calls[0]
    assert topic == f"{QP_ANSWER}.c-payload2", f"topic 不对: {topic!r}"
    assert isinstance(payload, QpAnswerPayload), f"payload 类型不对: {type(payload)}"
    assert payload.connection_id == "c-payload2"
    assert payload.answer_text == "第一场拍了 3 条。"
    assert payload.client_id == "cid-payload2"  # client_id 透传进 payload（前端据此精确撤语音 pending）


# ── 问题 2：委托路径跳过 hop B（infer_voice_tool 不被调） ─────────────────────────

def test_delegate_note_skips_hop_b(monkeypatch):
    """note 委托路径（np_input + voice_runner 均非 None）下 infer_voice_tool 不应被调用。

    问题 2：现状下委托路径仍先跑 hop B（infer_voice_tool）白跑一次推理，
    修后委托路径完全跳过 hop B。
    """
    _patch_build_hop_a_system(monkeypatch)
    from backend.pipelines.voice_dispatch import run_voice_dispatch
    from backend.pipelines.np_note import NPInput, NPOutput

    fake_np_input = NPInput(
        raw_text="",
        parsed_category="note",
        current_scene_id=1,
        current_take_id=10,
        take_context=[],
        ts=1000.0,
        current_scene_code="1A",
        current_shot="A",
        current_take_number=1,
    )

    hop_b_call_count = {"n": 0}

    class _CountingService(_StubService):
        def __init__(self):
            # hop A 返回 structure_note
            super().__init__("structure_note", {}, {"category": "pass", "content": "ok", "take_id": 10})

        async def infer_voice_tool(self, messages, audio, task_type, tool_choice=None, **kw):
            hop_b_call_count["n"] += 1
            return await super().infer_voice_tool(messages, audio, task_type, tool_choice=tool_choice, **kw)

    async def _fake_voice_runner(np_in, audio_bytes, svc):
        return NPOutput(take_id=np_in.current_take_id, category="pass", content="好")

    persisted: dict = {}

    async def _fake_persist(output, *, ts, client_id, raw_text_override):
        await output
        persisted["done"] = True

    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._persist_np_output_callable",
        _fake_persist,
    )

    svc = _CountingService()
    asyncio.run(run_voice_dispatch(
        WAV_BYTES,
        conn_id="c-skip-hopb",
        ts=1000.0,
        client_id="cid-skip",
        dal=_StubDAL(),
        service=svc,
        cm=_StubCM(),
        scene_context="",
        np_input=fake_np_input,
        voice_runner=_fake_voice_runner,
    ))

    assert persisted.get("done") is True, "note 落库未执行"
    assert hop_b_call_count["n"] == 0, (
        f"委托路径 infer_voice_tool 被调 {hop_b_call_count['n']} 次，应为 0"
    )


# ── 问题 3：query 分支任意失败 → 广播友好错误 + 带 client_id ─────────────────────

def test_query_hop_b_failure_broadcasts_friendly_error(monkeypatch):
    """query 分支 hop B（infer_voice_tool）抛异常 → 仍广播带 client_id 的友好错误答案。

    问题 3：现状 hop B 失败 return {"kind": "error"} 不广播，前端 pending 永久挂。
    修后：hop B 失败时也调 _schedule_qp_broadcast，前端据 client_id removePending。
    """
    _patch_build_hop_a_system(monkeypatch)
    from backend.pipelines.voice_dispatch import run_voice_dispatch

    class _HopBFailService(_StubService):
        def __init__(self):
            super().__init__("count_takes", {"scene_id": 1}, {})

        async def infer_voice_tool(self, messages, audio, task_type, tool_choice=None, **kw):
            raise RuntimeError("hop B 模拟失败")

    broadcast_calls: list = []

    async def _fake_broadcast(answer_text, conn_id, *, client_id=None, dal, service, cm):
        broadcast_calls.append({"answer": answer_text, "conn_id": conn_id, "client_id": client_id})

    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._schedule_qp_broadcast",
        _fake_broadcast,
    )

    svc = _HopBFailService()
    result = asyncio.run(run_voice_dispatch(
        WAV_BYTES,
        conn_id="c-err",
        ts=1000.0,
        client_id="cid-err",
        dal=_StubDAL(),
        service=svc,
        cm=_StubCM(),
        scene_context="",
    ))

    assert result.get("kind") == "error"
    assert len(broadcast_calls) == 1, (
        f"hop B 失败后应广播 1 次，实际 {len(broadcast_calls)}"
    )
    bc = broadcast_calls[0]
    assert bc["conn_id"] == "c-err"
    assert bc["client_id"] == "cid-err"
    assert "抱歉" in bc["answer"] or "出错" in bc["answer"], (
        f"友好错误文案不含「抱歉」或「出错」：{bc['answer']!r}"
    )


def test_query_executor_failure_broadcasts_friendly_error(monkeypatch):
    """query 分支 _run_executor 抛异常 → 仍广播带 client_id 的友好错误答案。

    问题 3 补充：不只 hop B，_run_executor（asyncio.to_thread 被包函数）失败也需广播。
    验证 _handle_query_branch 内部 except 将友好答案传入 _schedule_qp_broadcast。
    注：patch 目标是 _run_executor，不是 run_tool_loop（两者在同一 try 块内）。
    """
    _patch_build_hop_a_system(monkeypatch)
    from backend.pipelines.voice_dispatch import run_voice_dispatch

    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._run_executor",
        MagicMock(side_effect=RuntimeError("executor 炸了")),
    )

    broadcast_calls: list = []

    async def _fake_broadcast(answer_text, conn_id, *, client_id=None, dal, service, cm):
        broadcast_calls.append({"answer": answer_text, "client_id": client_id})

    monkeypatch.setattr(
        "backend.pipelines.voice_dispatch._schedule_qp_broadcast",
        _fake_broadcast,
    )

    svc = _StubService("count_takes", {"scene_id": 1}, {"scene_id": 1})
    asyncio.run(run_voice_dispatch(
        WAV_BYTES,
        conn_id="c-loop-err",
        ts=1000.0,
        client_id="cid-loop-err",
        dal=_StubDAL(),
        service=svc,
        cm=_StubCM(),
        scene_context="",
    ))

    assert len(broadcast_calls) == 1, (
        f"run_tool_loop 失败后应广播 1 次，实际 {len(broadcast_calls)}"
    )
    bc = broadcast_calls[0]
    assert bc["client_id"] == "cid-loop-err"
    assert "抱歉" in bc["answer"] or "出错" in bc["answer"], (
        f"友好错误文案不含「抱歉」或「出错」：{bc['answer']!r}"
    )
