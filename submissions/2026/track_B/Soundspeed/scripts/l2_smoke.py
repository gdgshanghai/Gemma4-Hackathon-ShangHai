"""L2 端到端真模型冒烟探针（手动验收用，非自动化测试）。

用真 Gemma + 真 run_l2_take 跑一条新 take，验证 L2 在当前代码 + 当前环境下
确实能端到端正确运行。对齐 scripts/audio_smoke.py 的「工具脚本」定位，
零改动 L2 源码，只从外部驱动 orchestrator 并观察。

两个探针：
  1) 事件探针：订阅 llm.status / take.changed，打印状态机时序，确认
     loading/running → idle 走通，且第二次 take.changed 带非空 script_diff。
  2) 事件循环探针（沿用 test_llm_service.py 的 探针 范式）：并发心跳协程，
     测最大停顿。Gemma 首次加载若冻 event loop（runbook §6 头号风险），
     心跳会被推迟；首次加载已挪进 to_thread，预期停顿应接近心跳间隔。

用法（worktree 根目录）：
  GEMMA_MODEL_PATH=/Users/yedianyang/Documents/GitHub/Soundspeed/models/gemma-4-E4B-it-Q4_K_M.gguf \
  SOUNDSPEED_DB=./soundspeed_dev.db \
  /Users/yedianyang/Documents/GitHub/Soundspeed/.venv/bin/python scripts/l2_smoke.py

注意：会向 SOUNDSPEED_DB 追加一条新 take（append，不清库）。
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from backend.core.events import (
    ASR_FINAL_CH1,
    LLM_STATUS,
    TAKE_CHANGED,
    TAKE_END,
    TAKE_START,
    AsrFinalPayload,
    LlmStatusPayload,
    TakeChangedPayload,
    TakeEndPayload,
    TakeStartPayload,
)
from backend.core.orchestrator import create_orchestrator
from backend.core.session import SessionState
from backend.db.dal import DAL
from backend.llm.service import get_service
from backend.pipelines.l2_take import run_l2_take

# 故意制造偏差的剧本 + 转录：substitution（没→不）、typo（真相→真象）、insertion（多余台词）
SCRIPT_LINES = [
    ("角色A", "你昨天为什么没告诉我真相"),
    ("角色B", "因为我怕你会离开"),
]
TRANSCRIPT = [
    ("speaker_0", "你昨天为什么不告诉我真象"),  # 没→不（substitution）+ 相→象（错别字）
    ("speaker_1", "因为我怕你会离开"),          # match
    ("speaker_0", "这句剧本里根本就没有"),       # insertion
]

HEARTBEAT_INTERVAL = 0.05
FREEZE_THRESHOLD = 1.0   # 心跳最大停顿超此值判定 event loop 被冻
L2_TIMEOUT = 240.0       # 含首次模型加载，给足时间


async def _heartbeat(stop: asyncio.Event, stats: dict) -> None:
    """心跳探针：每 HEARTBEAT_INTERVAL 醒一次，记录最大实际间隔。"""
    last = time.perf_counter()
    max_gap = 0.0
    ticks = 0
    while not stop.is_set():
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        now = time.perf_counter()
        gap = now - last
        last = now
        ticks += 1
        if gap > max_gap:
            max_gap = gap
    stats["max_gap"] = max_gap
    stats["ticks"] = ticks


async def main() -> int:
    db_path = os.environ.get("SOUNDSPEED_DB", "./soundspeed_dev.db")
    model_path = os.environ.get("GEMMA_MODEL_PATH", "(未设置，将走 HF cache/下载)")
    print("=" * 68)
    print("L2 端到端真模型冒烟探针")
    print(f"  DB        : {db_path}")
    print(f"  模型路径  : {model_path}")
    print("=" * 68)

    dal = DAL(Path(db_path))

    # 1) 准备 scene：优先用 active scene，没有就新建
    scene_id = dal.get_active_scene_id()
    if scene_id is None:
        scene_id = dal.create_scene("l2_smoke_scene")
        print(f"无 active scene，新建 scene_id={scene_id}")
    else:
        print(f"复用 active scene_id={scene_id}")

    # 2) 注入剧本（新版本），供 L2 读取产出真实行级 diff
    raw = "\n".join(f"{c}：{t}" for c, t in SCRIPT_LINES)
    script_id = dal.insert_script(scene_id, raw)
    for i, (c, t) in enumerate(SCRIPT_LINES, start=1):
        dal.insert_script_line(script_id, i, c, t)
    print(f"注入剧本 script_id={script_id}，{len(SCRIPT_LINES)} 行")

    # 3) 真 LLMService + 真 run_l2_take
    svc = get_service()
    print(f"LLMService: model_present={svc.model_present} model_loaded={svc.model_loaded}")
    session = SessionState()
    session.activate_scene(scene_id)
    orch = create_orchestrator(dal, session, llm_service=svc, l2_runner=run_l2_take)

    # 4) 事件探针：收集 llm.status / take.changed
    t0 = time.perf_counter()
    events: list[tuple[float, str, object]] = []
    orch.subscribe(LLM_STATUS, lambda p: events.append((time.perf_counter() - t0, "llm.status", p)))
    orch.subscribe(TAKE_CHANGED, lambda p: events.append((time.perf_counter() - t0, "take.changed", p)))

    # 5) 心跳探针并发起跑
    stop = asyncio.Event()
    hb_stats: dict = {}
    hb_task = asyncio.create_task(_heartbeat(stop, hb_stats))

    # 6) 驱动一条 take：start → ASR(ch1) → end → 等 L2
    orch.publish(TAKE_START, TakeStartPayload(scene_id=scene_id, shot=None, start_ts=time.time()))
    take_id = session.take_id
    take_number = session.take_number
    print(f"take.start → take_id={take_id} take_number={take_number}")

    for j, (spk, text) in enumerate(TRANSCRIPT):
        orch.publish(
            ASR_FINAL_CH1,
            AsrFinalPayload(
                text=text,
                start_frame=j * 16000,
                end_frame=(j + 1) * 16000,
                speaker=spk,
                take_id=take_id,
                is_partial=False,
            ),
        )
    print(f"注入 {len(TRANSCRIPT)} 条 ch1 final 转录")

    t_end = time.perf_counter()
    orch.publish(TAKE_END, TakeEndPayload(end_ts=time.time()))
    print("take.end → L2 已 fire-and-forget，等待完成（含首次模型加载）…")

    l2_err: BaseException | None = None
    if orch._l2_task is not None:  # type: ignore[attr-defined]
        try:
            await asyncio.wait_for(orch._l2_task, timeout=L2_TIMEOUT)  # type: ignore[attr-defined]
        except BaseException as exc:  # noqa: BLE001
            l2_err = exc
    l2_elapsed = time.perf_counter() - t_end

    # done_callback 在 task 完成后跑（发 idle），让出一轮 loop 确保它执行
    await asyncio.sleep(0)
    stop.set()
    await hb_task
    await svc.aclose()

    # ── 报告 ──────────────────────────────────────────────────────────────
    print("\n" + "─" * 68)
    print("【事件循环探针】")
    max_gap = hb_stats.get("max_gap", 0.0)
    frozen = max_gap > FREEZE_THRESHOLD
    print(f"  心跳 {hb_stats.get('ticks', 0)} 拍，最大停顿 {max_gap * 1000:.0f}ms "
          f"（间隔 {HEARTBEAT_INTERVAL * 1000:.0f}ms，阈值 {FREEZE_THRESHOLD * 1000:.0f}ms）")
    print(f"  事件循环：{'⚠️ 疑似被冻' if frozen else '✅ 未被阻塞（首次加载在 to_thread）'}")

    print("\n【事件探针】llm.status / take.changed 时序：")
    status_states: list[str] = []
    changed_with_diff = 0
    for ts, topic, p in events:
        if isinstance(p, LlmStatusPayload):
            status_states.append(p.state)
            print(f"  {ts * 1000:7.0f}ms  llm.status   state={p.state}")
        elif isinstance(p, TakeChangedPayload):
            has = isinstance(p.script_diff, dict)
            changed_with_diff += int(has)
            print(f"  {ts * 1000:7.0f}ms  take.changed script_diff={'dict' if has else 'None'}")

    print(f"\n  L2 耗时（take.end → task done）：{l2_elapsed:.1f}s")
    if l2_err is not None:
        print(f"  ⚠️ L2 task 异常：{l2_err!r}")

    # ── DB 落库核对 ──────────────────────────────────────────────────────
    print("\n【DB 落库】")
    take = dal.get_take(take_id) if take_id is not None else None
    sd = take.script_diff if take else None
    line_matches = dal.list_take_line_matches(take_id) if take_id is not None else []
    summary = None
    if isinstance(sd, dict):
        summary = sd.get("script_diff_summary")
        lm = sd.get("line_matches", [])
        cs = sd.get("corrected_segments", [])
        by_type: dict[str, int] = {}
        for m in lm:
            by_type[m.get("diff_type", "?")] = by_type.get(m.get("diff_type", "?"), 0) + 1
        print(f"  take.script_diff = dict（解析成功）")
        print(f"  summary          : {summary!r}")
        print(f"  line_matches     : {len(lm)} 条 {by_type}")
        print(f"  corrected_segments: {len(cs)} 条")
        for c in cs:
            print(f"      idx={c.get('idx')}  {c.get('original')!r} → {c.get('corrected')!r}")
        print(f"  take_line_matches 表落库：{len(line_matches)} 行")
    else:
        print(f"  take.script_diff = {sd!r}（非 dict，L2 未产出结构化结果）")

    # ── 判定 ──────────────────────────────────────────────────────────────
    passed = (
        l2_err is None
        and isinstance(sd, dict)
        and changed_with_diff >= 1
        and "idle" in status_states
    )
    print("\n" + "=" * 68)
    if passed:
        print(f"✅ PASS：L2 在真 Gemma 下端到端正确运行（take {take_number}, take_id={take_id}）")
    else:
        print(f"❌ FAIL：见上方报告（l2_err={l2_err!r}, script_diff_is_dict={isinstance(sd, dict)}, "
              f"changed_with_diff={changed_with_diff}, idle={'idle' in status_states}）")
    print("=" * 68)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
