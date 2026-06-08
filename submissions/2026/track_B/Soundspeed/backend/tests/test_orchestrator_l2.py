"""1.H Orchestrator take handler + L2 触发测试。

TDD 红阶段：骨架方法抛 NotImplementedError，所有测试应当失败。

覆盖：
  - take.start handler：DAL.start_take 调用 + SessionState 更新 + publish take.changed
  - take.end handler：同步 take.changed + L2 后台 task + 完成后 take.changed（含 script_diff）
  - L2 失败仍 publish take.changed（script_diff=None）
  - take_line_matches 写库（line_no != -1）
  - previous_notes 从历史 take.script_diff 提取
  - 无 event loop 时 publish TAKE_END 抛 RuntimeError
  - 集成测试：activate_scene 端到端（StubClient + 真实 DAL + 真实 l2_runner）
"""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.events import (
    ASR_FINAL_CH1,
    TAKE_CHANGED,
    TAKE_END,
    TAKE_START,
    AsrFinalPayload,
    TakeChangedPayload,
    TakeEndPayload,
    TakeStartPayload,
)
from backend.core.orchestrator import create_orchestrator
from backend.core.session import SessionState
from backend.db.dal import DAL
from backend.pipelines.l2_take import CorrectedSegment, L2Output, LineMatch, run_l2_take


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stub_l2_runner(
    script_diff_summary: str | None = "台词吻合",
    line_matches: list[LineMatch] | None = None,
    corrected_segments: list[CorrectedSegment] | None = None,
) -> AsyncMock:
    """创建返回固定 L2Output 的 stub l2_runner。"""
    if line_matches is None:
        line_matches = [
            LineMatch(line_no=1, diff_type="match", detail=None),
        ]
    if corrected_segments is None:
        corrected_segments = []
    output = L2Output(
        script_diff_summary=script_diff_summary,
        line_matches=line_matches,
        corrected_segments=corrected_segments,
    )
    runner = AsyncMock(return_value=output)
    return runner


def _make_stub_llm_service() -> MagicMock:
    """创建 stub LLMService（不实际调用 LLM）。"""
    svc = MagicMock()
    svc.infer = AsyncMock(
        return_value='{"script_diff_summary": "ok", "line_matches": [], "corrected_segments": []}'
    )
    return svc


# ---------------------------------------------------------------------------
# take.start handler 测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_take_start_handler_inserts_take_row(tmp_dal: DAL) -> None:
    """publish TAKE_START → DAL.start_take 被调 + SessionState 更新 + publish TAKE_CHANGED。

    验证：
    - session.take_active=True
    - session.take_id 非 None
    - take.changed 被 publish 一次，payload.status='tbd', script_diff=None
    """
    scene_id = tmp_dal.create_scene("scene_s1")
    session = SessionState()
    session.activate_scene(scene_id)

    orch = create_orchestrator(tmp_dal, session)

    received_changed: list[TakeChangedPayload] = []
    orch.subscribe(TAKE_CHANGED, lambda p: received_changed.append(p))  # type: ignore[arg-type]

    payload = TakeStartPayload(scene_id=scene_id, shot="S1A", start_ts=time.time())
    orch.publish(TAKE_START, payload)

    # SessionState 更新
    assert session.take_active is True
    assert session.take_id is not None

    # DAL 已写入 take 行
    take = tmp_dal.get_take(session.take_id)
    assert take is not None

    # take.changed publish 一次
    assert len(received_changed) == 1
    changed = received_changed[0]
    assert changed.status == "tbd"
    assert changed.script_diff is None
    assert changed.scene_id == scene_id


@pytest.mark.asyncio
async def test_take_end_handler_triggers_l2(tmp_dal: DAL) -> None:
    """publish TAKE_END → 同步 take.changed → L2 后台 task → 完成后第二次 take.changed（script_diff 非空）。"""
    scene_id = tmp_dal.create_scene("scene_e1")
    stub_runner = _make_stub_l2_runner()
    stub_svc = _make_stub_llm_service()
    session = SessionState()
    session.activate_scene(scene_id)

    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner)

    # 先 take.start 建好 take
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    assert session.take_id is not None

    received_changed: list[TakeChangedPayload] = []
    orch.subscribe(TAKE_CHANGED, lambda p: received_changed.append(p))  # type: ignore[arg-type]

    # publish TAKE_END（需要在 event loop 里执行）
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))

    # 同步阶段：第一次 take.changed（script_diff=None）已 publish
    assert len(received_changed) >= 1
    assert received_changed[0].script_diff is None

    # 等 L2 后台 task 完成
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    # 第二次 take.changed（script_diff 来自 L2Output）
    assert len(received_changed) == 2
    second = received_changed[1]
    assert second.script_diff is not None
    assert isinstance(second.script_diff, dict)


@pytest.mark.asyncio
async def test_take_end_handler_l2_failure_still_publishes(tmp_dal: DAL) -> None:
    """L2 抛异常 → 仍 publish take.changed（script_diff=None）。"""
    from backend.pipelines.l2_take import L2ParseError

    scene_id = tmp_dal.create_scene("scene_f1")
    failing_runner = AsyncMock(side_effect=L2ParseError("LLM 输出解析失败"))
    stub_svc = _make_stub_llm_service()
    session = SessionState()
    session.activate_scene(scene_id)

    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=failing_runner)

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))

    received_changed: list[TakeChangedPayload] = []
    orch.subscribe(TAKE_CHANGED, lambda p: received_changed.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))

    # 等 task 完成（异常但 done）
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    # task 本身完成时 exception 存于 task，done_callback 处理
    try:
        await orch._l2_task  # type: ignore[attr-defined]
    except Exception:
        pass  # L2 失败时 task 会抛异常，此处忽略

    # 失败后仍 publish 降级 take.changed（script_diff=None）
    # 第一次：take.end 同步 publish；第二次：done_callback 降级 publish
    assert len(received_changed) == 2
    # 最后一次 script_diff=None
    assert received_changed[-1].script_diff is None


@pytest.mark.asyncio
async def test_take_end_preserves_user_mark_status_sync(tmp_dal: DAL) -> None:
    """录音中 Mark=keep，停录（无 L2）后 status 不被写死回 tbd——库与同步 take.changed 都保留 keep。

    回归：_on_take_end 曾硬编码 status='tbd'，把用户 Mark 冲掉（停录后状态回退 bug）。
    """
    scene_id = tmp_dal.create_scene("scene_mark_sync")
    session = SessionState()
    session.activate_scene(scene_id)
    # 无 llm_service → 不跑 L2，只走同步 end 路径
    orch = create_orchestrator(tmp_dal, session)

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot="1", start_ts=time.time()))
    take_id = session.take_id
    assert take_id is not None

    # 用户录音中 Mark = keep
    tmp_dal.set_take_status(take_id, "keep")

    received_changed: list[TakeChangedPayload] = []
    orch.subscribe(TAKE_CHANGED, lambda p: received_changed.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))

    # 库里 status 保留 keep（end_take 不写死 tbd）
    take = tmp_dal.get_take(take_id)
    assert take is not None
    assert take.status == "keep"
    # 同步 take.changed 也带 keep（前端据此更新 store，不回退）
    assert len(received_changed) == 1
    assert received_changed[0].status == "keep"


@pytest.mark.asyncio
async def test_take_end_preserves_user_mark_status_through_l2(tmp_dal: DAL) -> None:
    """录音中 Mark=keep，停录后 L2 完成的 take.changed 也保留 keep（第二回退源）。

    回归：L2 完成路径同样硬编码 status='tbd'，会在停录数秒后二次把 Mark 冲掉。
    """
    scene_id = tmp_dal.create_scene("scene_mark_l2")
    stub_runner = _make_stub_l2_runner()
    stub_svc = _make_stub_llm_service()
    session = SessionState()
    session.activate_scene(scene_id)
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner)

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot="1", start_ts=time.time()))
    take_id = session.take_id
    assert take_id is not None

    tmp_dal.set_take_status(take_id, "keep")

    received_changed: list[TakeChangedPayload] = []
    orch.subscribe(TAKE_CHANGED, lambda p: received_changed.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    # 库 + 两次 take.changed（同步 end + L2 完成）都保留 keep
    take = tmp_dal.get_take(take_id)
    assert take is not None
    assert take.status == "keep"
    assert len(received_changed) == 2
    assert all(c.status == "keep" for c in received_changed)


@pytest.mark.asyncio
async def test_take_end_writes_line_matches(tmp_dal: DAL) -> None:
    """L2 完成后 line_matches 中 line_no != -1 的写 take_line_matches；line_no=-1 跳过。"""
    scene_id = tmp_dal.create_scene("scene_lm1")
    script_id = tmp_dal.insert_script(scene_id, "剧本")
    tmp_dal.insert_script_line(script_id, line_no=1, character="A", text="行一台词")

    stub_runner = _make_stub_l2_runner(
        script_diff_summary="有偏差",
        line_matches=[
            LineMatch(line_no=1, diff_type="match", detail=None),
            LineMatch(line_no=-1, diff_type="insertion", detail="多余台词"),  # 应跳过
        ],
    )
    stub_svc = _make_stub_llm_service()
    session = SessionState()
    session.activate_scene(scene_id)

    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner)

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    take_id = session.take_id
    assert take_id is not None

    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    matches = tmp_dal.list_take_line_matches(take_id)
    # line_no=1 写入，line_no=-1 跳过
    assert len(matches) == 1


@pytest.mark.asyncio
async def test_take_end_assembles_previous_notes(tmp_dal: DAL) -> None:
    """previous_notes 从历史 take 的 script_diff 提取 script_diff_summary。"""
    scene_id = tmp_dal.create_scene("scene_pn1")

    # 预置两条历史 take，带 script_diff
    old_take1, _ = tmp_dal.start_take(scene_id, "1", time.time() - 200)
    tmp_dal.update_take_l2_output(
        old_take1,
        {"script_diff_summary": "第1条take偏差记录", "line_matches": []},
    )
    old_take2, _ = tmp_dal.start_take(scene_id, "1", time.time() - 100)
    tmp_dal.update_take_l2_output(
        old_take2,
        {"script_diff_summary": "第2条take偏差记录", "line_matches": []},
    )

    # 收集传给 l2_runner 的 L2Input
    captured_inputs: list = []

    async def capturing_runner(input_data, llm_service):  # type: ignore[no-untyped-def]
        captured_inputs.append(input_data)
        return L2Output(script_diff_summary=None, line_matches=[], corrected_segments=[])

    stub_svc = _make_stub_llm_service()
    session = SessionState()
    session.activate_scene(scene_id)

    orch = create_orchestrator(
        tmp_dal, session, llm_service=stub_svc, l2_runner=capturing_runner
    )

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    assert len(captured_inputs) == 1
    previous_notes = captured_inputs[0].previous_notes
    # 历史两条 take 的 script_diff_summary 应被提取为 previous_notes
    assert any("第1条take偏差记录" in n for n in previous_notes)
    assert any("第2条take偏差记录" in n for n in previous_notes)


def test_orchestrator_requires_async_context(tmp_dal: DAL) -> None:
    """在无 event loop 的纯同步上下文 publish TAKE_END，handler 内部抛 RuntimeError。

    验证 Q6 决策：get_running_loop 失败 → RuntimeError，不降级 asyncio.run。
    publish 本身吞掉异常（记 ERROR log），但底层 _on_take_end 会调用 get_running_loop。
    此测试在 pytest 默认同步上下文，无 event loop。
    """
    import logging

    scene_id = tmp_dal.create_scene("scene_sync")
    session = SessionState()
    session.activate_scene(scene_id)
    stub_svc = _make_stub_llm_service()
    stub_runner = _make_stub_l2_runner()

    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner)

    # take.start 先在同步上下文执行（不需要 event loop）
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))

    # 记录 error log
    error_records: list = []

    class CapturingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            error_records.append(record)

    import backend.core.orchestrator as _orch_mod

    orch_logger = logging.getLogger(_orch_mod.__name__)
    handler = CapturingHandler()
    orch_logger.addHandler(handler)
    original_level = orch_logger.level
    orch_logger.setLevel(logging.ERROR)

    try:
        # 无 event loop 的同步上下文 publish TAKE_END
        # _on_take_end 内部 asyncio.get_running_loop() 会抛 RuntimeError
        # publish 吞掉异常记 ERROR log
        orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    finally:
        orch_logger.removeHandler(handler)
        orch_logger.setLevel(original_level)

    # 验证：有 ERROR 级别日志（RuntimeError 被 publish 的 try/except 记录）
    assert any(r.levelno >= logging.ERROR for r in error_records), (
        "无 event loop 时 _on_take_end 应触发 RuntimeError，publish 记录 ERROR"
    )


# ---------------------------------------------------------------------------
# 集成测试：activate_scene 端到端
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_scene_end_to_end(tmp_dal: DAL) -> None:
    """端到端测试：activate_scene → take.start → ASR → take.end → L2 完成。

    使用真实 DAL（tmp_dal）+ StubClient 注入的 LLMService + 真实 l2_runner。
    验证：
    - take 行写入 DB，status='tbd'
    - script_diff 字段非空（StubClient 返回合法 L2 JSON）
    """
    # 准备场次和剧本
    scene_id = tmp_dal.create_scene("scene_e2e")
    script_id = tmp_dal.insert_script(scene_id, "台词剧本")
    tmp_dal.insert_script_line(script_id, line_no=1, character="演员A", text="我不走。")

    # StubClient LLMService：返回合法 L2 tool_call（FC 路径）
    l2_json = json.dumps({
        "script_diff_summary": "演员台词吻合",
        "line_matches": [
            {"line_no": 1, "diff_type": "match", "detail": None},
        ],
        "corrected_segments": [],
    })
    stub_svc = MagicMock()
    stub_svc.infer_tool = AsyncMock(return_value={
        "id": "call_e2e_stub",
        "type": "function",
        "function": {
            "name": "report_script_analysis",
            "arguments": l2_json,
        },
    })

    session = SessionState()
    session.activate_scene(scene_id)

    orch = create_orchestrator(
        tmp_dal,
        session,
        llm_service=stub_svc,
        l2_runner=run_l2_take,
    )

    # 1. take.start
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    take_id = session.take_id
    assert take_id is not None

    # 2. ASR segments
    orch.publish(
        ASR_FINAL_CH1,
        AsrFinalPayload(
            text="我不走。",
            start_frame=0,
            end_frame=16000,
            speaker="SPEAKER_00",
            take_id=take_id,
            is_partial=False,
        ),
    )
    orch.publish(
        ASR_FINAL_CH1,
        AsrFinalPayload(
            text="你必须走。",
            start_frame=16000,
            end_frame=32000,
            speaker="SPEAKER_01",
            take_id=take_id,
            is_partial=False,
        ),
    )

    # 3. take.end
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))

    # 4. 等 L2 task 完成
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    # 5. 验证 DB 状态
    take = tmp_dal.get_take(take_id)
    assert take is not None
    assert take.status == "tbd"
    assert take.script_diff is not None
    assert isinstance(take.script_diff, dict)
    assert "script_diff_summary" in take.script_diff

    # 6. take_line_matches 有 ≥1 条（line_no=1 的 match）
    matches = tmp_dal.list_take_line_matches(take_id)
    assert len(matches) >= 1


# ---------------------------------------------------------------------------
# P1 #1：无 deps 时跳过 L2 schedule（降级路径）
# ---------------------------------------------------------------------------


def test_take_end_without_l2_runner_skips_schedule(tmp_dal: DAL) -> None:
    """不传 l2_runner，publish TAKE_END → 只 publish 一次 take.changed（tbd, script_diff=None），不 schedule L2。"""
    scene_id = tmp_dal.create_scene("scene_p1a")
    session = SessionState()
    session.activate_scene(scene_id)
    stub_svc = _make_stub_llm_service()

    # 不传 l2_runner
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc)

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=1.0))
    assert session.take_id is not None

    received_changed: list[TakeChangedPayload] = []
    orch.subscribe(TAKE_CHANGED, lambda p: received_changed.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_END, TakeEndPayload(end_ts=2.0))

    # 只 publish 一次 take.changed，无 background task
    assert len(received_changed) == 1
    assert received_changed[0].status == "tbd"
    assert received_changed[0].script_diff is None
    assert orch._l2_task is None  # type: ignore[attr-defined]


def test_take_end_without_llm_service_skips_schedule(tmp_dal: DAL) -> None:
    """不传 llm_service，publish TAKE_END → 只 publish 一次 take.changed，不 schedule L2。"""
    scene_id = tmp_dal.create_scene("scene_p1b")
    session = SessionState()
    session.activate_scene(scene_id)
    stub_runner = _make_stub_l2_runner()

    # 不传 llm_service
    orch = create_orchestrator(tmp_dal, session, l2_runner=stub_runner)

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=1.0))
    assert session.take_id is not None

    received_changed: list[TakeChangedPayload] = []
    orch.subscribe(TAKE_CHANGED, lambda p: received_changed.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_END, TakeEndPayload(end_ts=2.0))

    assert len(received_changed) == 1
    assert received_changed[0].script_diff is None
    assert orch._l2_task is None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# P1 #2：take.start 调 activate_scene
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_take_start_activates_scene(tmp_dal: DAL) -> None:
    """publish TAKE_START → session.scene_id 被设为 payload.scene_id。"""
    scene_id = tmp_dal.create_scene("scene_p2a")
    session = SessionState()
    # 故意不预先 activate_scene，让 take.start handler 来设

    orch = create_orchestrator(tmp_dal, session)

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=1.0))

    assert session.scene_id == scene_id


@pytest.mark.asyncio
async def test_take_end_uses_session_scene(tmp_dal: DAL) -> None:
    """take.start 设定 scene_id，take.end 后 L2 用到的 scene_id 与 take.start 一致。"""
    scene_id = tmp_dal.create_scene("scene_p2b")
    session = SessionState()
    # 不预先设置 scene_id

    captured_inputs: list = []

    async def capturing_runner(input_data, llm_service):  # type: ignore[no-untyped-def]
        captured_inputs.append(input_data)
        return L2Output(script_diff_summary=None, line_matches=[], corrected_segments=[])

    stub_svc = _make_stub_llm_service()
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=capturing_runner)

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=1.0))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=2.0))

    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    assert len(captured_inputs) == 1
    assert captured_inputs[0].scene_id == scene_id


# ---------------------------------------------------------------------------
# P2 #1：L2 后台 task 用闭包绑定 scene_id，不读 session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_take_end_l2_uses_take_scene_not_session(tmp_dal: DAL) -> None:
    """L2 后台 task 使用 take.start 时的 scene_id，不受后续 take.start 修改 session.scene_id 影响。"""
    scene_id_1 = tmp_dal.create_scene("scene_race1")
    scene_id_2 = tmp_dal.create_scene("scene_race2")

    # 给 scene_1 和 scene_2 各插入不同 script
    script_id_1 = tmp_dal.insert_script(scene_id_1, "剧本场次一")
    tmp_dal.insert_script_line(script_id_1, line_no=1, character="A", text="台词一")
    script_id_2 = tmp_dal.insert_script(scene_id_2, "剧本场次二")
    tmp_dal.insert_script_line(script_id_2, line_no=1, character="B", text="台词二")

    captured_script_ids: list[int | None] = []

    async def capturing_runner(input_data, llm_service):  # type: ignore[no-untyped-def]
        # 从 script_lines 的 line text 内容推断用了哪个 scene 的 script
        # （或者直接看 input_data.scene_id 就够了）
        captured_script_ids.append(input_data.scene_id)
        return L2Output(script_diff_summary=None, line_matches=[], corrected_segments=[])

    stub_svc = _make_stub_llm_service()
    session = SessionState()

    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=capturing_runner)

    # take A：scene_1
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id_1, shot=None, start_ts=1.0))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=2.0))
    l2_task_a = orch._l2_task  # type: ignore[attr-defined]

    # 不等 L2 完成，立即 take B：scene_2
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id_2, shot=None, start_ts=3.0))
    # take A 的 L2 task 现在执行，session.scene_id 已是 scene_id_2

    assert l2_task_a is not None
    await l2_task_a

    # take A 的 L2 应使用 scene_id_1，不是 scene_id_2
    assert len(captured_script_ids) == 1
    assert captured_script_ids[0] == scene_id_1


# ---------------------------------------------------------------------------
# P2 #3：previous_notes 限长（5 条 / 800 字符）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_previous_notes_caps_at_5_takes(tmp_dal: DAL) -> None:
    """10 条历史 take → previous_notes 只取最近 5 条。"""
    scene_id = tmp_dal.create_scene("scene_pn5")

    # 插入 10 条带 summary 的历史 take（shot="1" 组，自动分配号 1-10）
    for i in range(1, 11):
        tid, _ = tmp_dal.start_take(scene_id, "1", float(i))
        tmp_dal.update_take_l2_output(tid, {"script_diff_summary": f"summary_{i:02d}", "line_matches": []})

    captured_inputs: list = []

    async def capturing_runner(input_data, llm_service):  # type: ignore[no-untyped-def]
        captured_inputs.append(input_data)
        return L2Output(script_diff_summary=None, line_matches=[], corrected_segments=[])

    stub_svc = _make_stub_llm_service()
    session = SessionState()
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=capturing_runner)

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=11.0))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=12.0))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    notes = captured_inputs[0].previous_notes
    assert len(notes) <= 5


@pytest.mark.asyncio
async def test_previous_notes_caps_total_chars(tmp_dal: DAL) -> None:
    """5 条 take，每条 summary 400 字符 → previous_notes 总字符 ≤ 800。"""
    scene_id = tmp_dal.create_scene("scene_pn_chars")

    long_summary = "X" * 400
    for i in range(1, 6):
        tid, _ = tmp_dal.start_take(scene_id, "1", float(i))
        tmp_dal.update_take_l2_output(tid, {"script_diff_summary": long_summary, "line_matches": []})

    captured_inputs: list = []

    async def capturing_runner(input_data, llm_service):  # type: ignore[no-untyped-def]
        captured_inputs.append(input_data)
        return L2Output(script_diff_summary=None, line_matches=[], corrected_segments=[])

    stub_svc = _make_stub_llm_service()
    session = SessionState()
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=capturing_runner)

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=6.0))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=7.0))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    notes = captured_inputs[0].previous_notes
    total_chars = sum(len(n) for n in notes)
    assert total_chars <= 800


# ---------------------------------------------------------------------------
# create_orchestrator 工厂自动绑定 l2_runner
# ---------------------------------------------------------------------------


def test_create_orchestrator_auto_binds_l2_runner_when_llm_service_provided(
    tmp_dal: DAL,
) -> None:
    """create_orchestrator(llm_service=svc) 不传 l2_runner，自动绑定 run_l2_take。"""
    stub_svc = _make_stub_llm_service()
    session = SessionState()
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc)
    assert orch._deps.l2_runner is run_l2_take  # type: ignore[attr-defined]


def test_create_orchestrator_keeps_explicit_l2_runner(tmp_dal: DAL) -> None:
    """显式传 l2_runner 时不被 run_l2_take 覆盖。"""
    stub_svc = _make_stub_llm_service()
    stub_runner = _make_stub_l2_runner()
    session = SessionState()
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner)
    assert orch._deps.l2_runner is stub_runner  # type: ignore[attr-defined]


def test_create_orchestrator_no_llm_service_keeps_l2_runner_none(tmp_dal: DAL) -> None:
    """不传 llm_service 时 l2_runner 不自动绑定，保持 None。"""
    session = SessionState()
    orch = create_orchestrator(tmp_dal, session)
    assert orch._deps.l2_runner is None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# v0.2 新增：corrected_segments 落库验证
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_take_end_persists_corrected_segments(tmp_dal: DAL) -> None:
    """L2 完成后 takes.script_diff 含 corrected_segments 字段，数据正确。

    验证：corrected_segments 写入 script_diff JSON，字段完整（idx/original/corrected）。
    """
    scene_id = tmp_dal.create_scene("scene_cs1")
    session = SessionState()
    session.activate_scene(scene_id)

    stub_runner = _make_stub_l2_runner(
        script_diff_summary="第0段有错别字",
        line_matches=[LineMatch(line_no=-1, diff_type="insertion", detail=None)],
        corrected_segments=[
            CorrectedSegment(idx=0, original="爱生活", corrected="爱具体的生活"),
        ],
    )
    stub_svc = _make_stub_llm_service()

    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner)

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    take_id = session.take_id
    assert take_id is not None

    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    take = tmp_dal.get_take(take_id)
    assert take is not None
    assert take.script_diff is not None
    assert isinstance(take.script_diff, dict)

    # 验证 corrected_segments 字段存在且数据正确
    cs_list = take.script_diff.get("corrected_segments")
    assert cs_list is not None
    assert len(cs_list) == 1
    cs = cs_list[0]
    assert cs["idx"] == 0
    assert cs["original"] == "爱生活"
    assert cs["corrected"] == "爱具体的生活"


# ---------------------------------------------------------------------------
# 1.J-1.L 新增：llm.status 发射测试
#
# LLM_STATUS / LlmStatusPayload 导入放函数体内（RED 阶段这两个符号尚不存在，
# 顶层 import 会炸掉整个文件 collection，令基线一起变红，分不清原因）。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l2_emits_loading_when_model_not_loaded(tmp_dal: DAL) -> None:
    """llm_service.model_loaded=False → _run_l2_async 发出 state="loading"。"""
    from backend.core.events import LLM_STATUS, LlmStatusPayload  # noqa: PLC0415

    scene_id = tmp_dal.create_scene("scene_llm_load")
    stub_runner = _make_stub_l2_runner()
    stub_svc = _make_stub_llm_service()
    stub_svc.model_loaded = False  # 显式设，不依赖 MagicMock 默认真值

    session = SessionState()
    session.activate_scene(scene_id)
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner)

    emitted: list[LlmStatusPayload] = []
    orch.subscribe(LLM_STATUS, lambda p: emitted.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    states = [p.state for p in emitted]
    assert "loading" in states
    assert states[0] == "loading"


@pytest.mark.asyncio
async def test_l2_emits_running_when_model_loaded(tmp_dal: DAL) -> None:
    """llm_service.model_loaded=True → _run_l2_async 发出 state="running"。"""
    from backend.core.events import LLM_STATUS, LlmStatusPayload  # noqa: PLC0415

    scene_id = tmp_dal.create_scene("scene_llm_run")
    stub_runner = _make_stub_l2_runner()
    stub_svc = _make_stub_llm_service()
    stub_svc.model_loaded = True  # 模型已加载

    session = SessionState()
    session.activate_scene(scene_id)
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner)

    emitted: list[LlmStatusPayload] = []
    orch.subscribe(LLM_STATUS, lambda p: emitted.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    states = [p.state for p in emitted]
    assert "running" in states
    assert states[0] == "running"


@pytest.mark.asyncio
async def test_l2_emits_idle_on_success(tmp_dal: DAL) -> None:
    """L2 成功路径：idle 恰好发一次，在 running/loading 之后。

    2-emission 模型：_run_l2_async 发一次 running/loading，_l2_done_callback 发一次 idle。
    断 idle 精确一次（不多不少），杜绝双发回归。
    """
    from backend.core.events import LLM_STATUS, LlmStatusPayload  # noqa: PLC0415

    scene_id = tmp_dal.create_scene("scene_idle_ok")
    stub_runner = _make_stub_l2_runner()
    stub_svc = _make_stub_llm_service()
    stub_svc.model_loaded = True

    session = SessionState()
    session.activate_scene(scene_id)
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner)

    emitted: list[LlmStatusPayload] = []
    orch.subscribe(LLM_STATUS, lambda p: emitted.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    states = [p.state for p in emitted]
    # 2-emission：[running, idle]（model_loaded=True → running；callback → idle）
    assert states.count("idle") == 1, f"idle 应恰好发一次，实际: {states}"
    assert states[-1] == "idle"


@pytest.mark.asyncio
async def test_l2_emits_idle_on_failure(tmp_dal: DAL) -> None:
    """L2 失败路径：runner 抛异常，idle 恰好发一次。

    2-emission 模型同成功路径；失败时 callback 跳过 exc is None 分支，发降级 take.changed。
    断 idle 精确一次，杜绝双发回归。
    """
    from backend.core.events import LLM_STATUS, LlmStatusPayload  # noqa: PLC0415
    from backend.pipelines.l2_take import L2ParseError  # noqa: PLC0415

    scene_id = tmp_dal.create_scene("scene_idle_fail")
    failing_runner = AsyncMock(side_effect=L2ParseError("解析失败"))
    stub_svc = _make_stub_llm_service()
    stub_svc.model_loaded = True

    session = SessionState()
    session.activate_scene(scene_id)
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=failing_runner)

    emitted: list[LlmStatusPayload] = []
    orch.subscribe(LLM_STATUS, lambda p: emitted.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    try:
        await orch._l2_task  # type: ignore[attr-defined]
    except Exception:
        pass  # 失败路径 task 抛异常，此处忽略

    states = [p.state for p in emitted]
    assert states.count("idle") == 1, f"idle 应恰好发一次，实际: {states}"
    assert states[-1] == "idle"


@pytest.mark.asyncio
async def test_l2_emits_idle_on_cancellation(tmp_dal: DAL) -> None:
    """L2 取消路径（P1-2 fix）：task.cancel() 后 idle 仍发出（恰好一次）。

    机制：_l2_done_callback 在 idle publish 之后才检查 task.cancelled()，
    保证取消路径不漏发 idle。实际场景：shutdown 时 loop 已停，broadcast no-op；
    此测试在 running loop 内取消，验证 idle 确实到达 subscriber。
    """
    from backend.core.events import LLM_STATUS, LlmStatusPayload  # noqa: PLC0415

    scene_id = tmp_dal.create_scene("scene_idle_cancel")
    # 用 asyncio.Event 让 runner 挂住，再 cancel task
    import asyncio  # noqa: PLC0415

    blocked = asyncio.Event()

    async def hanging_runner(input_data: object, llm_service: object) -> None:
        await blocked.wait()  # 永远挂住，直到 task 被 cancel

    stub_svc = _make_stub_llm_service()
    stub_svc.model_loaded = True

    session = SessionState()
    session.activate_scene(scene_id)
    orch = create_orchestrator(
        tmp_dal, session, llm_service=stub_svc, l2_runner=hanging_runner
    )

    emitted: list[LlmStatusPayload] = []
    orch.subscribe(LLM_STATUS, lambda p: emitted.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    task = orch._l2_task  # type: ignore[attr-defined]
    assert task is not None

    # 等 _run_l2_async 进入 hanging_runner（已发 running），再取消
    await asyncio.sleep(0)  # 让 task 启动并到达 await blocked.wait()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    states = [p.state for p in emitted]
    assert states.count("idle") == 1, f"取消路径 idle 应恰好发一次，实际: {states}"
    assert states[-1] == "idle"


# ---------------------------------------------------------------------------
# 模型缺失自动下载：llm.status "downloading" 发射测试
#
# LlmStatusPayload 导入放函数体内，与既有发射测试保持同一约定。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l2_emits_downloading_when_model_not_present(tmp_dal: DAL) -> None:
    """model_present=False → _run_l2_async 发出 downloading，之后再发 loading/running。

    断言 downloading 在 loading/running 之前出现。
    ensure_model_ready 用 AsyncMock（被 await 调用）。
    """
    from backend.core.events import LLM_STATUS, LlmStatusPayload  # noqa: PLC0415

    scene_id = tmp_dal.create_scene("scene_dl_emit")
    stub_runner = _make_stub_l2_runner()
    stub_svc = _make_stub_llm_service()
    stub_svc.model_present = False          # 模型不在本地
    stub_svc.model_loaded = False           # 加载后第一次推理
    stub_svc.ensure_model_ready = AsyncMock()  # 模拟 await ensure_model_ready()

    session = SessionState()
    session.activate_scene(scene_id)
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner)

    emitted: list[LlmStatusPayload] = []
    orch.subscribe(LLM_STATUS, lambda p: emitted.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    states = [p.state for p in emitted]
    assert "downloading" in states, f"应发出 downloading，实际: {states}"
    dl_idx = states.index("downloading")
    # downloading 必须在第一个 loading/running 之前
    first_load_run = next(
        (i for i, s in enumerate(states) if s in ("loading", "running")), None
    )
    assert first_load_run is not None
    assert dl_idx < first_load_run, f"downloading 应先于 loading/running，实际: {states}"
    # ensure_model_ready 被调用一次
    stub_svc.ensure_model_ready.assert_awaited_once()


@pytest.mark.asyncio
async def test_l2_no_downloading_when_model_present(tmp_dal: DAL) -> None:
    """model_present=True → downloading 不出现，ensure_model_ready 不调用。"""
    from backend.core.events import LLM_STATUS, LlmStatusPayload  # noqa: PLC0415

    scene_id = tmp_dal.create_scene("scene_no_dl")
    stub_runner = _make_stub_l2_runner()
    stub_svc = _make_stub_llm_service()
    stub_svc.model_present = True           # 模型已在
    stub_svc.model_loaded = True
    stub_svc.ensure_model_ready = AsyncMock()

    session = SessionState()
    session.activate_scene(scene_id)
    orch = create_orchestrator(tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner)

    emitted: list[LlmStatusPayload] = []
    orch.subscribe(LLM_STATUS, lambda p: emitted.append(p))  # type: ignore[arg-type]

    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    assert orch._l2_task is not None  # type: ignore[attr-defined]
    await orch._l2_task  # type: ignore[attr-defined]

    states = [p.state for p in emitted]
    assert "downloading" not in states, f"model_present=True 不应发 downloading，实际: {states}"
    stub_svc.ensure_model_ready.assert_not_awaited()


# ---------------------------------------------------------------------------
# smoke：orchestrator 端到端真模型（GEMMA_MODEL_PATH 环境变量控制）
# ---------------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_orchestrator_l2_real_model_end_to_end(tmp_dal: DAL) -> None:
    """端到端真模型 smoke：真 LLMService + 真 run_l2_take + 预置转录 → script_diff 落库。

    运行条件：需设置 GEMMA_MODEL_PATH 指向本地 GGUF 文件。
    未设置时直接 skip，不影响 CI 全量套件。

    验证：
    - take.script_diff 是 dict，且含必需的三个顶层键
    - line_matches 是 list，每条 diff_type 在合法值集合内
    - TAKE_CHANGED 至少发 2 次，最后一次 script_diff 为 dict（非 None）
    """
    import os  # noqa: PLC0415

    if not os.environ.get("GEMMA_MODEL_PATH"):
        pytest.skip("GEMMA_MODEL_PATH 未设，跳过 smoke")

    from backend.llm.service import LLMService  # noqa: PLC0415

    svc = LLMService()

    # 预置场次和剧本
    scene_id = tmp_dal.create_scene("scene_e2e_smoke")
    sid = tmp_dal.insert_script(scene_id, "测试剧本")
    tmp_dal.insert_script_line(sid, 1, "警长", "你最好别插手这件事。")
    tmp_dal.insert_script_line(sid, 2, "阿强", "我已经插手了。")

    session = SessionState()
    session.activate_scene(scene_id)

    # 不传 l2_runner → create_orchestrator 自动绑定 run_l2_take
    orch = create_orchestrator(tmp_dal, session, llm_service=svc)

    # take.start
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    take_id = session.take_id
    assert take_id is not None

    # 预置 ch1 转录（含错别字「茶手」测纠错）
    tmp_dal.insert_segment(take_id, ch=1, speaker=None, text="你最好别茶手这件事", start_frame=0, end_frame=2000)
    tmp_dal.insert_segment(take_id, ch=1, speaker=None, text="我已经插手了", start_frame=2000, end_frame=4000)

    received: list[TakeChangedPayload] = []
    orch.subscribe(TAKE_CHANGED, lambda p: received.append(p))  # type: ignore[arg-type]

    # take.end → 触发 _run_l2_async
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))

    assert orch._l2_task is not None  # type: ignore[attr-defined]
    try:
        await orch._l2_task  # type: ignore[attr-defined]
    finally:
        await svc.aclose()

    # --- 断言（结构性，不断言模型具体文本） ---

    take = tmp_dal.get_take(take_id)
    assert take is not None
    assert isinstance(take.script_diff, dict), "script_diff 应是 dict"

    required_keys = {"script_diff_summary", "line_matches", "corrected_segments"}
    assert required_keys.issubset(take.script_diff), (
        f"script_diff 缺少必需键，实际键: {set(take.script_diff)}"
    )

    assert isinstance(take.script_diff["line_matches"], list)

    valid_diff_types = {"match", "missing", "substitution", "insertion"}
    for lm in take.script_diff["line_matches"]:
        assert lm["diff_type"] in valid_diff_types, (
            f"非法 diff_type: {lm['diff_type']!r}"
        )

    # TAKE_CHANGED 至少发 2 次（take.end 同步 + L2 完成后）
    assert len(received) >= 2, f"TAKE_CHANGED 应至少 2 次，实际: {len(received)}"

    # 最后一次 script_diff 必须是 dict（非 None）
    assert isinstance(received[-1].script_diff, dict), (
        "最后一次 TAKE_CHANGED 的 script_diff 应是 dict"
    )
