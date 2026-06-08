"""NP Pipeline orchestrator 异步链路测试（4.x Bug C）：client_id 透传到 note.processed。

Bug C 的根：前端乐观 pending 要按 client_id 精确移除——content 会被 NP 的 LLM 改写（去指代词），
pending.ts（前端 Date.now()）与 note.processed.ts（后端 time.time()）又不同源，旧的三元匹配必失败，
pending 永久卡「处理中」。修复要求后端把前端传入的 client_id 原样透传回 note.processed。
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.events import (
    NOTE_FAILED,
    NOTE_PROCESSED,
    TAKE_CHANGED,
    TAKE_START,
    NoteFailedPayload,
    NoteProcessedPayload,
    TakeChangedPayload,
    TakeStartPayload,
)
from backend.core.orchestrator import create_orchestrator
from backend.core.session import SessionState
from backend.db.dal import DAL
from backend.pipelines.np_note import NPOutput, NPParseError


@pytest.mark.asyncio
async def test_run_np_async_propagates_client_id(tmp_dal: DAL) -> None:
    """run_np_async 的 client_id 原样透传到 note.processed payload，且 content 确实被改写。"""
    scene_id = tmp_dal.create_scene("scene_np1")
    session = SessionState()
    session.activate_scene(scene_id)

    stub_np = AsyncMock()
    orch = create_orchestrator(
        tmp_dal, session, llm_service=MagicMock(), np_runner=stub_np
    )

    # 建 take，让 np_runner 归到一个真实 take_id（insert_note 需要 take 存在）
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    assert session.take_id is not None

    # np_runner 归到该 take 且改写 content（模拟 LLM 去掉指代词「这条」）
    stub_np.return_value = NPOutput(
        take_id=session.take_id, category="keep", content="很好可以用"
    )

    captured: list[NoteProcessedPayload] = []
    orch.subscribe(NOTE_PROCESSED, lambda p: captured.append(p))  # type: ignore[arg-type]

    orch.run_np_async(
        raw_text="这条很好可以用",
        parsed_category="keep",
        ts=111.0,
        client_id="cid-abc-123",
    )
    assert orch._np_task is not None  # type: ignore[attr-defined]
    await orch._np_task  # type: ignore[attr-defined]

    assert len(captured) == 1
    payload = captured[0]
    assert payload.client_id == "cid-abc-123"  # 原样透传 → 前端据此精确移除 pending
    assert payload.take_id == session.take_id
    # content 被改写（raw「这条很好可以用」→「很好可以用」），证明 content 不能当匹配键，client_id 才可靠
    assert payload.content == "很好可以用"


@pytest.mark.asyncio
async def test_run_np_async_client_id_none_when_omitted(tmp_dal: DAL) -> None:
    """未传 client_id（旧前端/异常）时 payload.client_id 为 None，前端据此走「不误删」分支。"""
    scene_id = tmp_dal.create_scene("scene_np2")
    session = SessionState()
    session.activate_scene(scene_id)

    stub_np = AsyncMock()
    orch = create_orchestrator(
        tmp_dal, session, llm_service=MagicMock(), np_runner=stub_np
    )
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    assert session.take_id is not None
    stub_np.return_value = NPOutput(take_id=session.take_id, category="note", content="备注")

    captured: list[NoteProcessedPayload] = []
    orch.subscribe(NOTE_PROCESSED, lambda p: captured.append(p))  # type: ignore[arg-type]

    orch.run_np_async(raw_text="备注", parsed_category="note", ts=1.0)
    assert orch._np_task is not None  # type: ignore[attr-defined]
    await orch._np_task  # type: ignore[attr-defined]

    assert len(captured) == 1
    assert captured[0].client_id is None


@pytest.mark.asyncio
async def test_run_np_async_threads_shot_and_scene_code(tmp_dal: DAL) -> None:
    """4.H：take_context 每条带 shot，当前场 scene_code 解析进 NPInput（场镜次 prompt 补全）。"""
    scene_id = tmp_dal.create_scene("Scene_1")
    # 一条历史 take（shot=A），无活跃 take → take_context 不排除它
    hist_id, _ = tmp_dal.start_take(scene_id=scene_id, shot="A", start_ts=1.0)
    session = SessionState()
    session.activate_scene(scene_id)

    stub_np = AsyncMock()
    orch = create_orchestrator(
        tmp_dal, session, llm_service=MagicMock(), np_runner=stub_np
    )
    stub_np.return_value = NPOutput(take_id=hist_id, category="note", content="x")

    orch.run_np_async(raw_text="备注", parsed_category="note", ts=1.0)
    assert orch._np_task is not None  # type: ignore[attr-defined]
    await orch._np_task  # type: ignore[attr-defined]

    np_input = stub_np.call_args.args[0]
    assert np_input.current_scene_code == "Scene_1"  # scene_id → scene_code 已解析
    ctx_by_id = {t["take_id"]: t for t in np_input.take_context}
    assert ctx_by_id[hist_id]["shot"] == "A"  # shot 从 DAL 透传进上下文


# ---- 4.I：NP 失败兜底 note.failed ----
# 失败时不发 note.processed，改发 note.failed（带 client_id + 机制可检测的 reason），
# 让前端把对应 pending 从「处理中」转失败态，而非永久卡死。


@pytest.mark.asyncio
async def test_run_np_async_take_not_found_emits_note_failed(tmp_dal: DAL) -> None:
    """LLM 归到不存在的 take_id → insert_note 撞 FK → note.failed(take_not_found)，不发 processed。"""
    scene_id = tmp_dal.create_scene("scene_fail1")
    session = SessionState()
    session.activate_scene(scene_id)

    stub_np = AsyncMock()
    orch = create_orchestrator(
        tmp_dal, session, llm_service=MagicMock(), np_runner=stub_np
    )
    stub_np.return_value = NPOutput(take_id=999999, category="note", content="x")

    failed: list[NoteFailedPayload] = []
    processed: list[NoteProcessedPayload] = []
    orch.subscribe(NOTE_FAILED, lambda p: failed.append(p))  # type: ignore[arg-type]
    orch.subscribe(NOTE_PROCESSED, lambda p: processed.append(p))  # type: ignore[arg-type]

    orch.run_np_async(raw_text="备注", parsed_category="note", ts=7.0, client_id="cid-x")
    assert orch._np_task is not None  # type: ignore[attr-defined]
    await orch._np_task  # type: ignore[attr-defined]

    assert len(processed) == 0  # 失败不落库、不发 processed
    assert len(failed) == 1
    assert failed[0].reason == "take_not_found"
    assert failed[0].client_id == "cid-x"  # 原样透传供前端精确定位
    assert failed[0].ts == 7.0


@pytest.mark.asyncio
async def test_run_np_async_parse_error_emits_note_failed(tmp_dal: DAL) -> None:
    """np_runner 抛 NPParseError（LLM 输出非法 JSON）→ note.failed(parse_error)。"""
    scene_id = tmp_dal.create_scene("scene_fail2")
    session = SessionState()
    session.activate_scene(scene_id)

    stub_np = AsyncMock(side_effect=NPParseError("bad json"))
    orch = create_orchestrator(
        tmp_dal, session, llm_service=MagicMock(), np_runner=stub_np
    )
    failed: list[NoteFailedPayload] = []
    orch.subscribe(NOTE_FAILED, lambda p: failed.append(p))  # type: ignore[arg-type]

    orch.run_np_async(raw_text="备注", parsed_category="note", ts=1.0, client_id="cid-y")
    assert orch._np_task is not None  # type: ignore[attr-defined]
    await orch._np_task  # type: ignore[attr-defined]

    assert len(failed) == 1
    assert failed[0].reason == "parse_error"
    assert failed[0].client_id == "cid-y"


@pytest.mark.asyncio
async def test_run_np_async_timeout_emits_note_failed(tmp_dal: DAL) -> None:
    """np_runner 抛 asyncio.TimeoutError（infer 超时）→ note.failed(timeout)，client_id 缺省为 None。"""
    scene_id = tmp_dal.create_scene("scene_fail3")
    session = SessionState()
    session.activate_scene(scene_id)

    stub_np = AsyncMock(side_effect=asyncio.TimeoutError())
    orch = create_orchestrator(
        tmp_dal, session, llm_service=MagicMock(), np_runner=stub_np
    )
    failed: list[NoteFailedPayload] = []
    orch.subscribe(NOTE_FAILED, lambda p: failed.append(p))  # type: ignore[arg-type]

    orch.run_np_async(raw_text="备注", parsed_category="note", ts=1.0)
    assert orch._np_task is not None  # type: ignore[attr-defined]
    await orch._np_task  # type: ignore[attr-defined]

    assert len(failed) == 1
    assert failed[0].reason == "timeout"
    assert failed[0].client_id is None


# ---------------------------------------------------------------------------
# 语音 NP orchestrator 链路（4.J-4）：run_np_voice_async —— 透传 audio + 转写正文存 raw_text +
# 共用 4.I 失败兜底。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_np_voice_async_processed_threads_audio_and_stores_transcript(
    tmp_dal: DAL,
) -> None:
    """run_np_voice_async：audio 透传给 voice_runner，note.processed 带 client_id，
    raw_text 存模型转写正文（§8，语音无原始文字）。"""
    scene_id = tmp_dal.create_scene("scene_voice1")
    session = SessionState()
    session.activate_scene(scene_id)

    stub_voice = AsyncMock()
    orch = create_orchestrator(
        tmp_dal, session, llm_service=MagicMock(), voice_runner=stub_voice
    )
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    assert session.take_id is not None
    stub_voice.return_value = NPOutput(
        take_id=session.take_id, category="keep", content="结尾好可以用"
    )

    captured: list[NoteProcessedPayload] = []
    orch.subscribe(NOTE_PROCESSED, lambda p: captured.append(p))  # type: ignore[arg-type]

    orch.run_np_voice_async(audio=b"WAVBYTES", ts=222.0, client_id="cid-voice")
    assert orch._np_task is not None  # type: ignore[attr-defined]
    await orch._np_task  # type: ignore[attr-defined]

    assert len(captured) == 1
    assert captured[0].client_id == "cid-voice"
    assert captured[0].take_id == session.take_id
    assert captured[0].content == "结尾好可以用"
    # voice_runner 第二位参数是 audio 字节
    assert stub_voice.call_args.args[1] == b"WAVBYTES"
    # raw_text 存模型转写正文（语音路径无原始文字，§8）
    notes = tmp_dal.list_notes(session.take_id)
    assert notes[-1].payload["raw_text"] == "结尾好可以用"


@pytest.mark.asyncio
async def test_run_np_voice_async_parse_error_emits_note_failed(tmp_dal: DAL) -> None:
    """voice_runner 抛 NPParseError → note.failed(parse_error)，复用文本失败分类。"""
    scene_id = tmp_dal.create_scene("scene_voice2")
    session = SessionState()
    session.activate_scene(scene_id)

    stub_voice = AsyncMock(side_effect=NPParseError("bad json from audio"))
    orch = create_orchestrator(
        tmp_dal, session, llm_service=MagicMock(), voice_runner=stub_voice
    )
    failed: list[NoteFailedPayload] = []
    orch.subscribe(NOTE_FAILED, lambda p: failed.append(p))  # type: ignore[arg-type]

    orch.run_np_voice_async(audio=b"x", ts=3.0, client_id="cid-vpe")
    assert orch._np_task is not None  # type: ignore[attr-defined]
    await orch._np_task  # type: ignore[attr-defined]

    assert len(failed) == 1
    assert failed[0].reason == "parse_error"
    assert failed[0].client_id == "cid-vpe"


@pytest.mark.asyncio
async def test_run_np_voice_async_take_not_found_emits_note_failed(tmp_dal: DAL) -> None:
    """模型归到不存在 take_id → insert_note 撞 FK → note.failed(take_not_found)。"""
    scene_id = tmp_dal.create_scene("scene_voice3")
    session = SessionState()
    session.activate_scene(scene_id)

    stub_voice = AsyncMock(
        return_value=NPOutput(take_id=999999, category="note", content="听到的内容")
    )
    orch = create_orchestrator(
        tmp_dal, session, llm_service=MagicMock(), voice_runner=stub_voice
    )
    failed: list[NoteFailedPayload] = []
    processed: list[NoteProcessedPayload] = []
    orch.subscribe(NOTE_FAILED, lambda p: failed.append(p))  # type: ignore[arg-type]
    orch.subscribe(NOTE_PROCESSED, lambda p: processed.append(p))  # type: ignore[arg-type]

    orch.run_np_voice_async(audio=b"x", ts=4.0, client_id="cid-vnf")
    assert orch._np_task is not None  # type: ignore[attr-defined]
    await orch._np_task  # type: ignore[attr-defined]

    assert len(failed) == 1
    assert failed[0].reason == "take_not_found"
    assert len(processed) == 0


@pytest.mark.asyncio
async def test_run_np_voice_async_model_unavailable_emits_note_failed(tmp_dal: DAL) -> None:
    """mmproj 不可用 → 纯文本 client → 音频推理 RuntimeError → note.failed(model_unavailable)。

    安全网：setup 失败在源头抛 ModelUnavailableError（client 无 handler / multimodal mtmd 自检失败），
    _finalize_np 干净映射成 model_unavailable，不能命中 `else: raise` 静默退出（否则前端 pending
    永久卡，复活 4.I 的 bug）。
    """
    from backend.llm.errors import ModelUnavailableError  # noqa: PLC0415

    scene_id = tmp_dal.create_scene("scene_voice4")
    session = SessionState()
    session.activate_scene(scene_id)

    stub_voice = AsyncMock(
        side_effect=ModelUnavailableError("纯文本 GemmaClient 不支持音频推理（未挂多模态 handler）")
    )
    orch = create_orchestrator(
        tmp_dal, session, llm_service=MagicMock(), voice_runner=stub_voice
    )
    failed: list[NoteFailedPayload] = []
    orch.subscribe(NOTE_FAILED, lambda p: failed.append(p))  # type: ignore[arg-type]

    orch.run_np_voice_async(audio=b"x", ts=5.0, client_id="cid-mu")
    assert orch._np_task is not None  # type: ignore[attr-defined]
    await orch._np_task  # type: ignore[attr-defined]

    assert len(failed) == 1
    assert failed[0].reason == "model_unavailable"
    assert failed[0].client_id == "cid-mu"


# ── option 1：note 类别接 take.status（Mark）──────────────────────────────────
# keep/ng/pass 三类直接把该 take 标成对应 status（场记口播即打 Mark）；note/issue 不碰状态。


async def _setup_orch_with_take(tmp_dal: DAL, scene_code: str):
    """建场 + 起一条 take，返回 (orch, stub_np, take_id)。"""
    scene_id = tmp_dal.create_scene(scene_code)
    session = SessionState()
    session.activate_scene(scene_id)
    stub_np = AsyncMock()
    orch = create_orchestrator(tmp_dal, session, llm_service=MagicMock(), np_runner=stub_np)
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    assert session.take_id is not None
    return orch, stub_np, session.take_id


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["keep", "ng", "pass"])
async def test_np_status_category_sets_take_status_and_broadcasts(
    tmp_dal: DAL, category: str
) -> None:
    """category∈{keep,ng,pass} → set_take_status(take_id, category) + publish take.changed。"""
    orch, stub_np, take_id = await _setup_orch_with_take(tmp_dal, f"sc_mark_{category}")
    stub_np.return_value = NPOutput(take_id=take_id, category=category, content="x")

    changed: list[TakeChangedPayload] = []
    orch.subscribe(TAKE_CHANGED, lambda p: changed.append(p))  # type: ignore[arg-type]

    orch.run_np_async(raw_text="x", parsed_category=category, ts=1.0, client_id="c1")
    await orch._np_task  # type: ignore[attr-defined]

    take = tmp_dal.get_take(take_id)
    assert take is not None and take.status == category
    assert any(c.take_id == take_id and c.status == category for c in changed)


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["note", "issue"])
async def test_np_plain_category_leaves_status_unchanged(
    tmp_dal: DAL, category: str
) -> None:
    """category∈{note,issue} → 不碰 take.status，不广播状态变更。"""
    orch, stub_np, take_id = await _setup_orch_with_take(tmp_dal, f"sc_plain_{category}")
    before = tmp_dal.get_take(take_id).status  # type: ignore[union-attr]
    stub_np.return_value = NPOutput(take_id=take_id, category=category, content="收音有点小")

    changed: list[TakeChangedPayload] = []
    orch.subscribe(TAKE_CHANGED, lambda p: changed.append(p))  # type: ignore[arg-type]

    orch.run_np_async(raw_text="收音有点小", parsed_category=category, ts=1.0, client_id="c2")
    await orch._np_task  # type: ignore[attr-defined]

    take = tmp_dal.get_take(take_id)
    assert take is not None and take.status == before  # 未变
    assert changed == []


def test_status_categories_coupling_holds(tmp_dal: DAL) -> None:
    """守不变量：_finalize_np 用 set_take_status(take_id, category) 靠「category 名 == status 值」同名耦合。
    若哪天单边改了 note 类别名 / status 枚举名，这条会红——避免 Mark 静默断掉（altitude 守卫）。"""
    from backend.core.orchestrator import _STATUS_CATEGORIES
    from backend.pipelines.np_note import _VALID_NOTE_CATEGORIES

    # ① 每个会打 Mark 的 category 都是合法 note 类别（模型 schema enum 产得出）
    assert _STATUS_CATEGORIES <= set(_VALID_NOTE_CATEGORIES)

    # ② 每个又都是合法 take.status（set_take_status 不抛 ValueError → 同名耦合成立）
    scene_id = tmp_dal.create_scene("sc_invariant")
    take_id, _ = tmp_dal.start_take(scene_id=scene_id, shot="", start_ts=0.0)
    for cat in _STATUS_CATEGORIES:
        tmp_dal.set_take_status(take_id, cat)  # 任一抛 ValueError 即耦合已断裂


@pytest.mark.asyncio
async def test_np_mark_failure_after_insert_does_not_orphan_pending(
    tmp_dal: DAL, monkeypatch: pytest.MonkeyPatch
) -> None:
    """set_take_status 在 insert_note 成功后抛非 typed 异常时，仍发 note.processed（note 已落库），不留孤儿 pending。

    回归 review [2]：insert_note 与 set_take_status 是两个独立事务。note 已 durable 入库后，
    若 Mark 抛非 typed 异常（如单连接跨线程并发的 sqlite3.OperationalError），旧实现走 else: raise →
    既不发 note.processed 也不发 note.failed → 前端 pending 永久卡「处理中」（复活 4.I 要消灭的孤儿）。
    修复：note 落库即无条件发 note.processed；Mark 是独立副作用，失败只记日志、不回退已发的 processed。
    """
    scene_id = tmp_dal.create_scene("scene_mark_fail")
    session = SessionState()
    session.activate_scene(scene_id)

    stub_np = AsyncMock()
    orch = create_orchestrator(
        tmp_dal, session, llm_service=MagicMock(), np_runner=stub_np
    )
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    assert session.take_id is not None
    stub_np.return_value = NPOutput(take_id=session.take_id, category="keep", content="好")

    # Mark 阶段抛非 typed 异常（模拟单连接跨线程并发 → database is locked）。
    def boom(*_a: object, **_k: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(tmp_dal, "set_take_status", boom)

    processed: list[NoteProcessedPayload] = []
    failed: list[NoteFailedPayload] = []
    take_changed: list[TakeChangedPayload] = []
    orch.subscribe(NOTE_PROCESSED, lambda p: processed.append(p))  # type: ignore[arg-type]
    orch.subscribe(NOTE_FAILED, lambda p: failed.append(p))  # type: ignore[arg-type]
    orch.subscribe(TAKE_CHANGED, lambda p: take_changed.append(p))  # type: ignore[arg-type]

    orch.run_np_async(raw_text="好", parsed_category="keep", ts=222.0, client_id="cid-mark-fail")
    assert orch._np_task is not None  # type: ignore[attr-defined]
    # Mark 失败不应让 task 上抛；用 gather 兜住以防回归到 else: raise
    await asyncio.gather(orch._np_task, return_exceptions=True)  # type: ignore[attr-defined]

    # note 已 durable 入库 → 必发 note.processed（解除 pending），client_id 透传，不留孤儿
    assert len(processed) == 1
    assert processed[0].client_id == "cid-mark-fail"
    assert len(failed) == 0
    # Mark 失败：take.changed 不发，但 note 确实落库
    assert take_changed == []
    assert len(tmp_dal.list_notes(session.take_id)) == 1
