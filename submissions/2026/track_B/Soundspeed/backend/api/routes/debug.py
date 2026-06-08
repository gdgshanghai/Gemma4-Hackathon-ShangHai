"""dev-only 合成端点（1.J-1.L §2.4 + 剧本注入）。

仅在 SOUNDSPEED_DEV=1 时由 create_app 挂载，生产不暴露。

端点列表：
  POST /api/v1/debug/asr      合成 AsrPartial/FinalPayload → orchestrator.publish
  POST /api/v1/debug/script   注入剧本行 → scripts + script_lines，供 L2 diff 使用
  POST /api/v1/debug/reset-db 清空所有业务表 → seed_dev_scene 重播种一个 active 空场

/debug/asr 用途：1.C（结构化 ASR 输出）落地前手动驱动 1.J transcript 面板验收。
  take_id=None → _on_asr_final 通过 _resolve_take_id 回退 session.take_id；
  active take 时 final ASR 既推 WS 也存库（take detail 可见 segments）。
  start_frame / end_frame：start_frame=int(time.time()*1000)，end_frame=start_frame+1000
  （满足 CHECK(end_frame > start_frame)，相等触发 IntegrityError 被 publish() 吞掉）。

/debug/script 用途：为当前 scene 注入剧本台词，L2 _run_l2_async 通过
  get_latest_script + list_script_lines 读取，使下一次 take.end 产出真实行级 diff。
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.api.auth import require_admin
from backend.db.seed import seed_dev_scene
from backend.core.events import (
    ASR_FINAL_CH1,
    ASR_FINAL_CH2,
    ASR_PARTIAL_CH1,
    ASR_PARTIAL_CH2,
    AsrFinalPayload,
    AsrPartialPayload,
)

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])


class DebugAsrBody(BaseModel):
    """POST /api/v1/debug/asr 请求体。"""

    ch: int
    text: str
    speaker: str | None = None
    is_partial: bool


@router.post("/asr")
async def debug_asr(
    body: DebugAsrBody,
    request: Request,
    _: None = Depends(require_admin),
) -> dict[str, str]:
    """合成 ASR 事件并 publish 到 orchestrator。

    ch 必须为 1 或 2，否则 422。
    end_frame = start_frame + 1000（满足 CHECK(end_frame > start_frame)，
    相等会触发 sqlite3.IntegrityError 被 publish() 吞掉，段静默不存库）。
    """
    if body.ch not in (1, 2):
        raise HTTPException(status_code=422, detail="ch must be 1 or 2")

    orch = request.app.state.orchestrator
    start_frame = int(time.time() * 1000)
    end_frame = start_frame + 1000  # 严格大于，满足 CHECK(end_frame > start_frame)

    if body.is_partial:
        topic = ASR_PARTIAL_CH1 if body.ch == 1 else ASR_PARTIAL_CH2
        payload: AsrPartialPayload | AsrFinalPayload = AsrPartialPayload(
            text=body.text,
            start_frame=start_frame,
            end_frame=end_frame,
            speaker=body.speaker,
            take_id=None,
            is_partial=True,
        )
    else:
        topic = ASR_FINAL_CH1 if body.ch == 1 else ASR_FINAL_CH2
        payload = AsrFinalPayload(
            text=body.text,
            start_frame=start_frame,
            end_frame=end_frame,
            speaker=body.speaker,
            take_id=None,
            is_partial=False,
        )

    orch.publish(topic, payload)
    return {"status": "ok"}


# ── /debug/script：注入剧本行 ─────────────────────────────────────────────────


class ScriptLineIn(BaseModel):
    """剧本行输入。"""

    character: str | None = None
    text: str


class DebugScriptBody(BaseModel):
    """POST /api/v1/debug/script 请求体。"""

    scene_id: int | None = None
    lines: list[ScriptLineIn]
    int_ext: str | None = None      # slugline 内外景（可选，注入时同步写 scenes 表）
    time_of_day: str | None = None  # slugline 时间（可选）
    location: str | None = None     # slugline 地点（可选）


@router.post("/script")
async def debug_script(
    body: DebugScriptBody,
    request: Request,
    _: None = Depends(require_admin),
) -> dict[str, object]:
    """注入剧本到 scripts + script_lines 表，供 L2 _run_l2_async 读取产出真实 diff。

    scene_id 优先用请求体，缺失时回退 dal.get_active_scene_id()。
    过滤空行（text.strip() 为空）；过滤后无行 → 422。
    raw_text 用全角冒号拼接（与导入格式一致）。
    line_no 从 1 起，按 lines 顺序排。
    """
    dal = request.app.state.orchestrator.dal

    # 解析 scene_id
    scene_id = body.scene_id
    if scene_id is None:
        scene_id = dal.get_active_scene_id()
    if scene_id is None:
        raise HTTPException(status_code=422, detail="no active scene")

    # 过滤空行
    valid_lines = [ln for ln in body.lines if ln.text.strip()]
    if not valid_lines:
        raise HTTPException(status_code=422, detail="no lines")

    # 组装 raw_text（全角冒号，与剧本文本格式一致）
    raw_text = "\n".join(
        f"{ln.character}：{ln.text}" if ln.character else ln.text
        for ln in valid_lines
    )

    script_id = dal.insert_script(scene_id, raw_text)
    for i, ln in enumerate(valid_lines, start=1):
        dal.insert_script_line(script_id, i, ln.character, ln.text)

    # 若 heading 字段任一非空，同步更新 scene 的 slugline 列（部分更新，不清空已有值）
    if body.int_ext is not None or body.time_of_day is not None or body.location is not None:
        dal.update_scene_heading(
            scene_id,
            int_ext=body.int_ext,
            time_of_day=body.time_of_day,
            location=body.location,
        )

    return {
        "script_id": script_id,
        "scene_id": scene_id,
        "line_count": len(valid_lines),
    }


# ── /debug/reset-db：一键清空数据库并重新播种（dev 专用）────────────────────


@router.post("/reset-db")
async def debug_reset_db(
    request: Request,
    _: None = Depends(require_admin),
) -> dict[str, object]:
    """清空全部业务数据，然后重新播种一个 active 的空场（和 DEV 启动播种一致）。

    语义：dal.reset_all() → seed_dev_scene(dal) → 返回 {"status": "ok", "reseeded": true}。
    此路由仅在 SOUNDSPEED_DEV=1 时由 create_app 挂载，天然 dev-only。
    """
    dal = request.app.state.orchestrator.dal
    dal.reset_all()
    seed_dev_scene(dal)
    return {"status": "ok", "reseeded": True}
