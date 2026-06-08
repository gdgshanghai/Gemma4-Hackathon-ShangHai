"""take 端点（contract C3）：POST /api/v1/take/start | /api/v1/take/end + GET 端点（1.J-1.L）。

请求契约（design §3）：
  - POST /take/start body = {scene_id:int, shot:str|null}
  - POST /take/end   body 空（end_ts 服务端生成）
  - ts 一律服务端 time.time() 生成
  - 映射到 TakeStartPayload(scene_id, shot, start_ts) / TakeEndPayload(end_ts)

端点必须 async def（决策 1）：
  take.end 的 fire-and-forget L2 靠 asyncio.get_running_loop()
  （orchestrator.py，仅在注入 llm_service/l2_runner 时走到）。async 端点由
  FastAPI 在 event loop 内直接 await，get_running_loop() 能拿到 loop，L2 task 被调度。
  若改成 def，FastAPI 丢线程池跑 → 无 running loop → get_running_loop() 抛 RuntimeError
  → 被 publish() 吞掉 → 生产 L2 静默不触发。
  GET 端点同理：DAL 单连接 check_same_thread=False，同步路由跑线程池会与 event-loop 线程
  上的 L2 async 任务并发操作同一 _conn（SQLite 对同一连接对象的并发调用不安全）。

take/end 的 NP Pipeline 已接入（4.x）：POST /notes 触发 NP，归置 note 到对应 take。

TakeDTO 有意省略 performer_issues / audio_quality（codex P2）：
  这两个字段属 NP Pipeline 输出，1.J-1.L 不暴露，故意不进 DTO。
  前端从 script_diff.line_matches 读行比对（codex P1），不单列 line_matches 字段。
"""
from __future__ import annotations

import asyncio
import difflib
import logging
import time
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from backend.api.auth import require_admin
from backend.api.routes.query import schedule_qp_broadcast
from backend.core.export import (
    FileNameFormat,
    SegFormat,
    build_export_rows,
    rows_to_csv,
)
from backend.core.events import (
    SCENE_CHANGED,
    TAKE_CHANGED,
    TAKE_DELETED,
    TAKE_END,
    TAKE_START,
    SceneChangedPayload,
    TakeChangedPayload,
    TakeDeletedPayload,
    TakeEndPayload,
    TakeStartPayload,
)
from backend.pipelines.memo_route import classify_memo
from backend.pipelines.note_parse import NoteParseError, parse_note
from backend.pipelines.voice_dispatch import run_voice_dispatch

logger = logging.getLogger(__name__)

# voice dispatch fire-and-forget task 持有集：防 asyncio.create_task 结果被 GC（Python 文档建议）。
# 对齐 query.py 的 _qp_tasks 模式。
_voice_dispatch_tasks: set[asyncio.Task] = set()

router = APIRouter(prefix="/api/v1", tags=["takes"])


# ── DTO 定义（1.J-1.L GET 端点响应结构）──────────────────────────────────────


class SegmentOut(BaseModel):
    """transcript_segments 行的响应投影（spec §2.1 shape）。

    有意省略 take_id：前端 TranscriptSegmentDTO 不含此字段，减少响应体冗余。
    """

    segment_id: int
    ch: int
    speaker: str | None
    text: str
    start_frame: int
    end_frame: int

    model_config = ConfigDict(from_attributes=True)


class TakeDTO(BaseModel):
    """take 行的响应投影（12 字段，有意省略 performer_issues / audio_quality）。

    有意省略字段：performer_issues、audio_quality 属 NP Pipeline 输出，1.J-1.L 不暴露。
    前端从 script_diff.line_matches 读行比对（codex P1），不单列 line_matches 字段。
    take_suffix：冲突后缀，默认 ''；显示时前端拼接为 'Take 3+'，后端只存值。
    deleted_at：软删时间戳，NULL 表示未删除；restore 后返回 None。
    """

    take_id: int
    scene_id: int
    shot: str | None
    take_number: int
    take_suffix: str
    start_ts: float
    end_ts: float | None
    status: str
    script_diff: dict | None
    notes: str | None
    deleted_at: float | None
    created_at: float
    updated_at: float
    # diarization 回填后的结构化转录（ASR + speaker 整合，v4）；未回填时为 None
    structured_transcript: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class TakeDetailDTO(TakeDTO):
    """take 详情：TakeDTO + segments 列表。"""

    segments: list[SegmentOut]


# ── POST 端点（contract C3）────────────────────────────────────────────────────


class TakeStartBody(BaseModel):
    """POST /take/start 请求体。"""

    scene_id: int
    shot: str | None = None
    # 本 take 在场的已注册演员 id（diarization 回填只在这些演员里匹配；空 → 全匿名说话人N）
    speaker_ids: list[int] = []
    # 用户手动指定的待录 take 号（底部 Take 弹窗）。None → 后端按 (scene,shot) 自动 MAX+1。
    # ge=1：take 号从 1 起，挡掉 0/负数。
    take_number: int | None = Field(default=None, ge=1)


@router.post("/take/start")
async def take_start(
    body: TakeStartBody,
    request: Request,
    _: None = Depends(require_admin),
) -> dict[str, str]:
    """起一个 take：服务端生成 start_ts，publish TAKE_START。

    校验 scene_id == get_active_scene_id()，不一致 → 409 scene_not_active。
    校验必须在路由层同步执行，不能推进 orchestrator 异步 handler。
    """
    orchestrator = request.app.state.orchestrator
    dal = orchestrator.dal
    active_scene_id = dal.get_active_scene_id()
    if body.scene_id != active_scene_id:
        raise HTTPException(
            status_code=409,
            detail={"error": "scene_not_active", "active_scene_id": active_scene_id},
        )
    payload = TakeStartPayload(
        scene_id=body.scene_id,
        shot=body.shot,
        start_ts=time.time(),
        speaker_ids=tuple(body.speaker_ids),
        take_number=body.take_number,
    )
    orchestrator.publish(TAKE_START, payload)
    return {"status": "ok"}


@router.post("/take/end")
async def take_end(
    request: Request,
    _: None = Depends(require_admin),
) -> dict[str, str]:
    """结束当前 take：服务端生成 end_ts，publish TAKE_END（body 空）。

    async def 是决策 1 的硬约束——见模块 docstring。
    """
    orchestrator = request.app.state.orchestrator
    payload = TakeEndPayload(end_ts=time.time())
    orchestrator.publish(TAKE_END, payload)
    return {"status": "ok"}


# ── GET 端点（1.J-1.L）────────────────────────────────────────────────────────


@router.get("/takes")
async def list_takes(
    request: Request,
    scene_id: int | None = None,
    _: None = Depends(require_admin),
) -> dict[str, list[TakeDTO]]:
    """列出 take（可按 scene_id 过滤），不含 segments（避免 N+1）。

    省略 scene_id 返回全部（dal.list_takes(None)）。
    """
    dal = request.app.state.orchestrator.dal
    takes = dal.list_takes(scene_id)
    return {"takes": [TakeDTO.model_validate(t, from_attributes=True) for t in takes]}


@router.get("/takes/export")
async def export_takes_csv(
    request: Request,
    scene_prefix: str = "",
    scene_pad: int = Query(2, ge=0, le=6),
    shot_prefix: str = "S",
    shot_pad: int = Query(0, ge=0, le=6),
    take_prefix: str = "T",
    take_pad: int = Query(3, ge=0, le=6),
    sep: str = "_",
    ts_from: float | None = None,
    ts_to: float | None = None,
    _: None = Depends(require_admin),
) -> Response:
    """导出 take 为 CSV（Sound Report）：text/csv + attachment 下载。

    必须注册在 GET /takes/{take_id} 之前——否则 FastAPI 会把 "export" 当 take_id 解析（422）。
    导出日期服务端生成（本地日期），首行写「导出日期：YYYY-MM-DD」，第二行表头。

    FileName 列板式由 7 个 query 参数控制（前端从用户配置的命名格式传入，对齐 UI 显示）；
    全缺省即 DEFAULT_FILENAME_FORMAT（01_S1_T001）。Content-Disposition 经 CORS expose 暴露，
    供前端跨域读取文件名。

    ts_from/ts_to（Unix 秒，半开区间）：导出范围。前端「导出今天」传本地零点起 24h；
    「导出全部」不传，导全部 take。
    """
    dal = request.app.state.orchestrator.dal
    fmt = FileNameFormat(
        scene=SegFormat(scene_prefix, scene_pad),
        shot=SegFormat(shot_prefix, shot_pad),
        take=SegFormat(take_prefix, take_pad),
        sep=sep,
    )
    rows = build_export_rows(dal, fmt, ts_from=ts_from, ts_to=ts_to)
    export_date = datetime.now().strftime("%Y-%m-%d")
    body = rows_to_csv(rows, export_date)
    filename = f"soundspeed_takes_{export_date}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/takes/{take_id}")
async def get_take(
    take_id: int,
    request: Request,
    _: None = Depends(require_admin),
) -> TakeDetailDTO:
    """返回 take 详情（含 segments），take 不存在 → 404。"""
    dal = request.app.state.orchestrator.dal
    take = dal.get_take(take_id)
    if take is None:
        raise HTTPException(status_code=404, detail="take not found")
    segments = dal.list_segments(take_id)
    return TakeDetailDTO.model_validate(
        {**take.__dict__, "segments": segments},
        from_attributes=True,
    )


class PatchSegmentBody(BaseModel):
    """PATCH /takes/{take_id}/segments/{segment_id} 请求体。

    speaker 为必填字段（缺字段 → pydantic 422），值可为 null（置「未知」）。
    """

    speaker: str | None


@router.patch("/takes/{take_id}/segments/{segment_id}")
async def correct_segment_speaker(
    take_id: int,
    segment_id: int,
    body: PatchSegmentBody,
    request: Request,
    _: None = Depends(require_admin),
) -> SegmentOut:
    """纠正单条 segment 的 speaker（说话人归属）。L2 不重跑、不发 WS。

    处理顺序定死边界：空白串 422 → 不存在/不属该 take 404 → ch2 422 → update。
    """
    if isinstance(body.speaker, str) and not body.speaker.strip():
        raise HTTPException(status_code=422, detail="speaker must not be blank")

    dal = request.app.state.orchestrator.dal
    seg = dal.get_segment(segment_id)
    if seg is None or seg.take_id != take_id:
        raise HTTPException(status_code=404, detail="segment not found in take")
    if seg.ch == 2:
        raise HTTPException(status_code=422, detail="ch2 segment speaker is immutable")

    dal.update_segment_speaker(segment_id, body.speaker)
    updated = dal.get_segment(segment_id)
    return SegmentOut.model_validate(updated, from_attributes=True)


@router.get("/scenes")
async def list_scenes(
    request: Request,
    _: None = Depends(require_admin),
) -> dict[str, list[dict]]:
    """列出所有场次（含 slugline 三列：int_ext / time_of_day / location）。

    dal.list_scenes() 返回 list[dict]，直接透传（不需要 DTO 投影）。
    """
    dal = request.app.state.orchestrator.dal
    return {"scenes": dal.list_scenes()}


@router.get("/scenes/characters")
async def list_all_characters(
    request: Request,
    _: None = Depends(require_admin),
) -> dict[str, list[str]]:
    """整部戏（全场次最新剧本）去重角色清单，供声纹注册"选角色"下拉用。

    一个演员的角色横跨多场，故取全场次并集而非单场。无剧本时返回空列表。
    路径放在 /scenes/{scene_id}/script 之前不冲突（characters 非数字段）。
    归一角色名（剥（V.O.）等尾部注记）后再去重，覆盖解析归一上线前的历史数据。
    """
    from backend.pipelines.sp_script import normalize_character

    dal = request.app.state.orchestrator.dal
    norms = {normalize_character(raw) for raw in dal.list_all_characters()}
    return {"characters": sorted(n for n in norms if n)}


# ── 读剧本端点（scene heading 票加，2026-06-01）────────────────────────────────


class ScriptLineOut(BaseModel):
    """剧本行投影（spec §2.3）。"""

    line_no: int
    character: str | None
    text: str


class ScriptOut(BaseModel):
    """单场次剧本响应（spec §2.3）。"""

    script_id: int
    version: int
    lines: list[ScriptLineOut]


class ScriptLineIn(BaseModel):
    """提交单场剧本的单行（来自 parse-single 预览结果，character 可空=舞台指示）。"""

    character: str | None = None
    text: str


class UpdateSceneScriptBody(BaseModel):
    """POST /scenes/{scene_id}/script 请求体：把选中场更新成一个新版本。"""

    raw_text: str  # 本次来源原文（OCR/粘贴），存版本 + 幂等比对用
    lines: list[ScriptLineIn]  # parse-single 预览确认后的逐行结果


class ScriptCommitOut(BaseModel):
    """选中场更新结果。skipped=True 表示内容与最新版相同、未新建版本。"""

    scene_id: int
    script_id: int
    version: int
    line_count: int
    skipped: bool


class ScriptDiffBody(BaseModel):
    """POST /scenes/{scene_id}/script/diff 请求体：新解析的逐行（照片 OCR / 文本），与该场最新版做增量对照。"""

    lines: list[ScriptLineIn]


class ScriptDiffRow(BaseModel):
    """一行增量对照。

    status：equal=未变（留旧）/ changed=改动（取新）/ added=新增（取新）/
    kept=旧有新无（保留旧，防 OCR 漏字漏行）。old/new 视状态可空。
    """

    status: Literal["equal", "changed", "added", "kept"]
    old: ScriptLineIn | None = None
    new: ScriptLineIn | None = None


class ScriptDiffOut(BaseModel):
    """增量对照结果。

    has_old=False → 该场无旧版，rows 全为 added、merged 即新行（前端可直接确认）。
    merged：落库用合并行（确认时作为 update_scene_script.lines 提交）。
    merged_raw_text：由 merged 重建的源文本（确认时作为 raw_text 提交），保证落库 raw_text↔lines
    一致——OCR 漏行触发 kept 时 merged 含旧行，不能再用 OCR 原文当 raw_text（否则幂等指纹/复算失真）。
    """

    has_old: bool
    rows: list[ScriptDiffRow]
    merged: list[ScriptLineIn]
    merged_raw_text: str


@router.get("/scenes/{scene_id}/script")
async def get_scene_script(
    scene_id: int,
    request: Request,
    _: None = Depends(require_admin),
) -> dict[str, ScriptOut | None]:
    """取指定场次最新剧本及行列表。

    无剧本或 scene 不存在 → {"script": null}（200，不 404）。
    行按 line_no 升序（dal.list_script_lines 已保证）。
    """
    dal = request.app.state.orchestrator.dal
    script_meta = dal.get_latest_script(scene_id)
    if script_meta is None:
        return {"script": None}
    script_id = script_meta["script_id"]
    version = script_meta["version"]
    raw_lines = dal.list_script_lines(script_id)
    lines = [ScriptLineOut(line_no=r["line_no"], character=r["character"], text=r["text"]) for r in raw_lines]
    return {"script": ScriptOut(script_id=script_id, version=version, lines=lines)}


@router.post("/scenes/{scene_id}/script")
async def update_scene_script(
    scene_id: int,
    body: UpdateSceneScriptBody,
    request: Request,
    _: None = Depends(require_admin),
) -> ScriptCommitOut:
    """把【选中场】的剧本更新成一个新版本（照片/文本增补的落库口）。

    版本追加语义（见 soundspeed_script_reupload_design）：永不删旧版/旧行，只 insert
    新版本（version 自增），读侧自动切到新版。幂等：raw_text 与该场最新版相同 →
    skipped=True、不新建版本（防重复点击刷版本）。scene 不存在 → 404；lines 空 → 422。
    """
    dal = request.app.state.orchestrator.dal
    if dal.get_scene_info(scene_id) is None:
        raise HTTPException(status_code=404, detail="场次不存在")
    if not body.lines:
        raise HTTPException(status_code=422, detail="lines 为空，无可更新内容")

    latest = dal.get_latest_script(scene_id)
    if latest is not None and latest.get("raw_text") == body.raw_text:
        # 内容无变化：不刷版本，回报最新版现状
        existing = dal.list_script_lines(latest["script_id"])
        return ScriptCommitOut(
            scene_id=scene_id,
            script_id=latest["script_id"],
            version=latest["version"],
            line_count=len(existing),
            skipped=True,
        )

    from backend.pipelines.sp_script import normalize_character

    # insert_script 取 MAX(version)+1，故新版本即 latest.version+1（无旧版则首版=1）。
    new_version = latest["version"] + 1 if latest is not None else 1
    script_id = dal.insert_script(scene_id, body.raw_text)
    for line_no, ln in enumerate(body.lines, start=1):
        dal.insert_script_line(script_id, line_no, normalize_character(ln.character), ln.text)
    return ScriptCommitOut(
        scene_id=scene_id,
        script_id=script_id,
        version=new_version,
        line_count=len(body.lines),
        skipped=False,
    )


def _script_line_key(line: ScriptLineIn) -> tuple[str, str]:
    """对齐用归一键：角色归一 + 台词去首尾空白。仅用于 difflib 匹配，不影响输出文本。"""
    from backend.pipelines.sp_script import normalize_character

    return (normalize_character(line.character) or "", (line.text or "").strip())


def _merge_script_lines(
    old: list[ScriptLineIn], new: list[ScriptLineIn]
) -> tuple[list[ScriptDiffRow], list[ScriptLineIn]]:
    """difflib 对齐旧↔新，产出 (rows 供前端对照, merged 落库行)。

    语义（增量增补，见 soundspeed_script_reupload_design）：
      equal   → 留旧（旧行原样进 merged）
      replace → 取新（这段确实改了；展示成 changed，old/new 逐个配对，多余一侧单列）
      insert  → 加新（新有旧无 → added）
      delete  → 保留旧（旧有新无 → kept；防 OCR 漏字/漏行/只识别半场把内容删没）
    """
    sm = difflib.SequenceMatcher(
        a=[_script_line_key(l) for l in old],
        b=[_script_line_key(l) for l in new],
        autojunk=False,
    )
    rows: list[ScriptDiffRow] = []
    merged: list[ScriptLineIn] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i1, i2):
                rows.append(ScriptDiffRow(status="equal", old=old[k], new=old[k]))
                merged.append(old[k])
        elif tag == "replace":
            ob, nb = old[i1:i2], new[j1:j2]
            for k in range(max(len(ob), len(nb))):
                rows.append(
                    ScriptDiffRow(
                        status="changed",
                        old=ob[k] if k < len(ob) else None,
                        new=nb[k] if k < len(nb) else None,
                    )
                )
            merged.extend(nb)
        elif tag == "insert":
            for k in range(j1, j2):
                rows.append(ScriptDiffRow(status="added", old=None, new=new[k]))
                merged.append(new[k])
        elif tag == "delete":
            for k in range(i1, i2):
                rows.append(ScriptDiffRow(status="kept", old=old[k], new=None))
                merged.append(old[k])
    return rows, merged


@router.post("/scenes/{scene_id}/script/diff")
async def diff_scene_script(
    scene_id: int,
    body: ScriptDiffBody,
    request: Request,
    _: None = Depends(require_admin),
) -> ScriptDiffOut:
    """把新解析的逐行与该场最新版做增量对照（不落库，仅预览）。

    用途：照片/文本更新前给用户看「哪些改了、哪些新增、哪些旧的会保留」，确认后把 merged
    提交到 POST /scenes/{scene_id}/script。OCR 可能漏字/漏行/只识别半场，故旧有新无的行
    默认【保留旧】(status=kept)，避免增补反把内容删没。无旧版 → has_old=False、全 added。
    scene 不存在 → 404。
    """
    from backend.core.script_import import _build_raw_text  # noqa: PLC0415

    dal = request.app.state.orchestrator.dal
    if dal.get_scene_info(scene_id) is None:
        raise HTTPException(status_code=404, detail="场次不存在")

    new_lines = list(body.lines)
    latest = dal.get_latest_script(scene_id)
    if latest is None:
        rows = [ScriptDiffRow(status="added", old=None, new=l) for l in new_lines]
        merged = new_lines
    else:
        old_lines = [
            ScriptLineIn(character=r["character"], text=r["text"])
            for r in dal.list_script_lines(latest["script_id"])
        ]
        rows, merged = _merge_script_lines(old_lines, new_lines)

    merged_raw_text = _build_raw_text([(l.character, l.text) for l in merged])
    return ScriptDiffOut(
        has_old=latest is not None,
        rows=rows,
        merged=merged,
        merged_raw_text=merged_raw_text,
    )


# ── Note 端点（4.C）────────────────────────────────────────────────────────────


class NoteCreateBody(BaseModel):
    """POST /notes 请求体。"""

    text: str
    ts: float | None = None
    # 前端生成的乐观 pending 去重键（crypto.randomUUID），原样回传到 note.processed。
    client_id: str | None = None
    # WS 连接标识：query 分支据此把答案广播到 qp.answer.{conn_id}（前端按前缀认领）。
    conn_id: str | None = None


class NoteOut(BaseModel):
    """单条 note 事件响应投影。"""

    event_id: int
    take_id: int
    scene_code: str | None
    take_number: int | None
    category: str
    content: str
    raw_text: str
    ts: float


class NoteListOut(BaseModel):
    """GET /takes/{take_id}/notes 响应。"""

    take_id: int
    notes_aggregated: str | None
    events: list[NoteOut]


@router.post("/notes", status_code=202)
async def create_note(
    body: NoteCreateBody,
    request: Request,
    _: None = Depends(require_admin),
) -> dict:
    """提交 note：解析 @category → fire-and-forget NP Pipeline → 返回 202。

    NP Pipeline 在后台通过 LLM 判断归属 take 并写库。
    """
    orchestrator = request.app.state.orchestrator
    ts = body.ts or time.time()

    # 1. 规则解析（只提取 @category，不定位 take）
    try:
        note = parse_note(body.text, ts)
    except NoteParseError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 入口调度器（块③）：query → QP fire-and-forget 广播；note/任何失败 → 现有 NP。
    # 仅当有 conn_id（query 答案要广播到 qp.answer.{conn_id}）且 LLM 就绪、且非 @显式类别时分类。
    # classify 有意留在 202 关键路径（route 须在 202 时知道 kind 才能告诉前端 query/note，
    # 决定要不要撤掉乐观 pending）；其延迟由前端乐观 pending 提前到 await 前藏掉，故后端保持简单。
    service = getattr(request.app.state, "llm_service", None)
    if service is not None and body.conn_id and not body.text.lstrip().startswith("@"):
        kind = await classify_memo(note.raw_text, service)
        if kind == "query":
            # client_id 透传进 qp.answer payload：前端队列据此把答案落到对应那条 qaItem
            #（乐观插的 note pending 同样按 client_id 在 postNote.then(kind==="query") 撤掉）。
            schedule_qp_broadcast(
                note.raw_text,
                body.conn_id,
                dal=orchestrator.dal,
                service=service,
                cm=request.app.state.connection_manager,
                client_id=body.client_id,
            )
            return {"status": "processing", "kind": "query"}

    # 2. fire-and-forget NP Pipeline
    try:
        orchestrator.run_np_async(
            raw_text=note.raw_text,
            parsed_category=note.category,
            ts=note.ts,
            client_id=body.client_id,
        )
    except RuntimeError:
        # 不在 event loop 中（如同步测试环境），fallback 到当前活跃 take。
        # 端点是 async def → 生产恒在 loop 内，此路不可达；若哪天被改成 def 触发，
        # 这里会绕过整条 NP（无 LLM 归类、无 take 消歧、无 note.processed WS），故吼一声。
        logger.warning(
            "create_note fallback 命中：无 event loop，绕过 NP 直接落当前活跃 take（仅应出现在同步测试）"
        )
        dal = request.app.state.orchestrator.dal
        session = request.app.state.orchestrator.session
        if session.take_active and session.take_id is not None:
            event_id = dal.insert_note(
                take_id=session.take_id,
                category=note.category,
                content=note.content,
                raw_text=note.raw_text,
                ts=note.ts,
            )
            return {
                "status": "ok",
                "event_id": event_id,
                "take_id": session.take_id,
                "category": note.category,
                "content": note.content,
            }
        raise HTTPException(status_code=409, detail="no active take and no event loop for NP Pipeline")

    return {
        "status": "processing",
        "category": note.category,
        "content": note.content,
    }


# 后端语音上限：48kHz/30s mono PCM16 ≈ 2.9MB，给到 10MB 安全冗余（前端另有 30s/2MB 限制，§3.2）。
_MAX_VOICE_BYTES = 10 * 1024 * 1024


@router.post("/notes/voice", status_code=202)
async def create_voice_note(
    request: Request,
    file: UploadFile = File(...),
    client_id: str = Form(...),
    ts: float | None = Form(None),
    conn_id: str | None = Form(None),
    _: None = Depends(require_admin),
) -> dict:
    """提交语音 note（4.K / C1）：浏览器麦 WAV 直传 → fire-and-forget → 返回 202。

    有 conn_id → 走 voice dispatch（hop A/B 两步走判 note/query，query 广播 qp.answer.{conn_id}）。
    无 conn_id → 原有 run_np_voice_async 路径（只归置 NP，不判 query）。

    与 POST /notes（文本）对称：均 202，结果经 WS（note.processed / note.failed）回灌。
    音频来源是前端浏览器麦（getUserMedia，#19），非后端现场录音。
    """
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="音频为空")
    if len(audio) > _MAX_VOICE_BYTES:
        raise HTTPException(status_code=400, detail="音频超限（>10MB）")

    orchestrator = request.app.state.orchestrator
    resolved_ts = ts if ts is not None else time.time()
    service = getattr(request.app.state, "llm_service", None)

    # 有 conn_id → 走 voice dispatch（判 note/query）
    if conn_id is not None and service is not None:
        # 构建 NPInput（含 current_take_id/take_context）供 note 分支委托 run_np_voice
        np_input = orchestrator._build_np_input("", "note", resolved_ts)
        # voice_runner 来自 orchestrator._deps（须有 llm_service 才绑定）
        voice_runner = getattr(orchestrator._deps, "voice_runner", None)
        cm = request.app.state.connection_manager

        # 问题 1：wrapper 协程先发 LLM_STATUS busy，再跑 dispatch
        # preamble 在协程内部执行（可能 await ensure_model_ready），不阻塞 202
        # done callback 统一发 idle（成功/失败/取消三条路径）
        async def _dispatch_with_status() -> dict:
            await orchestrator._emit_np_status_preamble(service)
            return await run_voice_dispatch(
                audio,
                conn_id=conn_id,
                ts=resolved_ts,
                client_id=client_id,
                dal=orchestrator.dal,
                service=service,
                cm=cm,
                scene_context="",  # 简化：不预取场次文本，hop A 系统内联说明已足
                np_input=np_input,
                voice_runner=voice_runner,
            )

        # fire-and-forget：不 await，不阻塞 202，对齐块③ schedule_qp_broadcast 模式。
        task = asyncio.create_task(_dispatch_with_status())
        _voice_dispatch_tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            _voice_dispatch_tasks.discard(t)
            # 问题 1：无论成功/失败/取消，发 idle（对齐 _np_done_callback 形态）
            orchestrator._np_done_callback(t, label="voice_dispatch")

        task.add_done_callback(_done)
        return {"status": "processing", "client_id": client_id, "kind": "dispatching"}

    # 无 conn_id → 原有 run_np_voice_async 路径
    try:
        orchestrator.run_np_voice_async(
            audio=audio,
            ts=resolved_ts,
            client_id=client_id,
        )
    except RuntimeError:
        # 不在 event loop 中（如同步测试环境）：语音必须经多模态推理，无直接落库 fallback。
        raise HTTPException(status_code=503, detail="语音 NP 需在 event loop 中运行")

    return {"status": "processing", "client_id": client_id}


@router.get("/takes/{take_id}/notes")
async def get_take_notes(
    take_id: int,
    request: Request,
    _: None = Depends(require_admin),
) -> NoteListOut:
    """返回指定 take 的 note 汇总 + 事件列表。"""
    dal = request.app.state.orchestrator.dal

    take = dal.get_take(take_id)
    if take is None:
        raise HTTPException(status_code=404, detail="take not found")

    events = dal.list_notes(take_id)

    # 查 scene_code + take_number
    scene_code: str | None = None
    if take:
        scenes = dal.list_scenes()
        for s in scenes:
            if s["scene_id"] == take.scene_id:
                scene_code = s.get("scene_code")
                break
    take_number: int | None = take.take_number if take else None

    events_out: list[NoteOut] = []
    for evt in events:
        payload: dict = evt.payload if isinstance(evt.payload, dict) else {}
        cat = payload.get("category", "note")
        ct = payload.get("content", "")
        raw = payload.get("raw_text", "")
        if not (isinstance(cat, str) and isinstance(ct, str) and isinstance(raw, str)):
            cat = str(cat) if cat else "note"
            ct = str(ct) if ct else ""
            raw = str(raw) if raw else ""
        events_out.append(
            NoteOut(
                event_id=evt.event_id,
                take_id=evt.take_id,
                scene_code=scene_code,
                take_number=take_number,
                category=cat,
                content=ct,
                raw_text=raw,
                ts=evt.ts,
            )
        )

    return NoteListOut(
        take_id=take_id,
        notes_aggregated=take.notes if take else None,
        events=events_out,
    )


# ── 2.C：建场端点 ────────────────────────────────────────────────────────────


class CreateSceneBody(BaseModel):
    """POST /scenes 请求体。"""

    scene_code: str
    description: str | None = None
    shoot_date: str | None = None
    int_ext: str | None = None
    time_of_day: str | None = None
    location: str | None = None


@router.post("/scenes")
async def create_scene(
    body: CreateSceneBody,
    request: Request,
    _: None = Depends(require_admin),
) -> dict:
    """建场（get-or-create）：新建或复用已有 scene_code，均返回 200。

    created=True 表示本次新建，False 表示复用。is_active 反映 DB 当前状态。
    """
    dal = request.app.state.orchestrator.dal
    scene_id, created = dal.get_or_create_scene(
        body.scene_code,
        description=body.description,
        shoot_date=body.shoot_date,
        int_ext=body.int_ext,
        time_of_day=body.time_of_day,
        location=body.location,
    )
    active_id = dal.get_active_scene_id()
    return {
        "scene_id": scene_id,
        "scene_code": body.scene_code,
        "created": created,
        "is_active": scene_id == active_id,
    }


# ── 2.C：激活场次端点 ─────────────────────────────────────────────────────────


@router.post("/scenes/{scene_id}/activate")
async def activate_scene(
    scene_id: int,
    request: Request,
    _: None = Depends(require_admin),
) -> dict:
    """激活指定场次。

    步骤：录制中检查 → 404 → set_active_scene → 刷新 session → publish SCENE_CHANGED。
    """
    orchestrator = request.app.state.orchestrator
    dal = orchestrator.dal
    session = orchestrator.session

    # 录制中禁止切场（全局状态，用 session.take_active）
    if session.take_active:
        raise HTTPException(
            status_code=409,
            detail={"error": "take_in_progress"},
        )

    # 查 scene 是否存在（用 list_scenes 找，顺便取 scene_code）
    scenes = dal.list_scenes()
    target = next((s for s in scenes if s["scene_id"] == scene_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="scene not found")

    # 写 DB + 刷新内存
    dal.set_active_scene(scene_id)
    session.activate_scene(scene_id)

    # publish WS 事件
    orchestrator.publish(
        SCENE_CHANGED,
        SceneChangedPayload(
            scene_id=scene_id,
            scene_code=target["scene_code"],
            is_active=True,
        ),
    )

    return {"scene_id": scene_id, "scene_code": target["scene_code"]}


# ── 2.C：PATCH /takes/{take_id} ──────────────────────────────────────────────


class PatchTakeBody(BaseModel):
    """PATCH /takes/{take_id} 请求体（所有字段可选）。"""

    status: Literal["pass", "ng", "keep", "tbd"] | None = None
    shot: str | None = None
    scene_id: int | None = None
    take_number: int | None = None
    notes: str | None = None


@router.patch("/takes/{take_id}")
async def patch_take(
    take_id: int,
    body: PatchTakeBody,
    request: Request,
    _: None = Depends(require_admin),
) -> TakeDTO:
    """部分更新 take 元数据。

    录制中（end_ts IS NULL）：禁改 scene_id/take_number→409；允许改 notes。
    冲突处理：TakeNumberConflictError→409；目标 scene 不存在→404；take 不存在→404。
    成功后 publish TAKE_CHANGED，返回更新后的 TakeDTO。
    """
    orchestrator = request.app.state.orchestrator
    dal = orchestrator.dal

    # take 存在性检查
    take = dal.get_take(take_id)
    if take is None:
        raise HTTPException(status_code=404, detail="take not found")

    # 录制中限制（行级判断：end_ts IS NULL）
    is_recording = take.end_ts is None
    if is_recording and (body.scene_id is not None or body.take_number is not None):
        raise HTTPException(
            status_code=409,
            detail={"error": "take_in_progress"},
        )

    # 先处理 status（走 set_take_status，写 manual.mark 事件）
    if body.status is not None:
        dal.set_take_status(take_id, body.status)

    # 再处理其余字段（走 update_take_meta）
    # 冲突处理改为后缀追加，不再抛 TakeNumberConflictError（不再 409）
    has_meta_update = any(
        v is not None for v in (body.shot, body.scene_id, body.take_number, body.notes)
    )
    if has_meta_update:
        try:
            dal.update_take_meta(
                take_id,
                shot=body.shot,
                scene_id=body.scene_id,
                take_number=body.take_number,
                notes=body.notes,
            )
        except ValueError:
            raise HTTPException(status_code=404, detail="target scene not found")

    # 重新取（update 可能改了字段）
    updated = dal.get_take(take_id)
    assert updated is not None  # take 存在性已确认

    # publish TAKE_CHANGED
    orchestrator.publish(
        TAKE_CHANGED,
        TakeChangedPayload(
            take_id=updated.take_id,
            scene_id=updated.scene_id,
            take_number=updated.take_number,
            status=updated.status,
            script_diff=updated.script_diff,
        ),
    )

    return TakeDTO.model_validate(updated, from_attributes=True)


# ── 2.C：DELETE /takes/{take_id}（软删）─────────────────────────────────────


@router.delete("/takes/{take_id}", status_code=204)
async def delete_take(
    take_id: int,
    request: Request,
    _: None = Depends(require_admin),
) -> None:
    """软删 take。录制中→409；不存在（含已软删）→404；成功→204。

    子表数据保留（不触发 CASCADE），可通过 restore 端点撤销。
    删除后 publish TAKE_DELETED。
    """
    orchestrator = request.app.state.orchestrator
    dal = orchestrator.dal

    # 存在性检查（get_take 排除软删行）
    take = dal.get_take(take_id)
    if take is None:
        raise HTTPException(status_code=404, detail="take not found")

    # 录制中禁删（行级判断）
    if take.end_ts is None:
        raise HTTPException(
            status_code=409,
            detail={"error": "take_in_progress"},
        )

    scene_id = take.scene_id
    dal.delete_take(take_id)

    orchestrator.publish(
        TAKE_DELETED,
        TakeDeletedPayload(take_id=take_id, scene_id=scene_id),
    )


# ── 2.C：POST /takes/{take_id}/restore ───────────────────────────────────────


@router.post("/takes/{take_id}/restore")
async def restore_take(
    take_id: int,
    request: Request,
    _: None = Depends(require_admin),
) -> TakeDTO:
    """撤销软删。

    仅对已软删（deleted_at IS NOT NULL）的 take 有效；
    未软删或不存在→404；成功→200 + 恢复后的 TakeDTO。
    """
    orchestrator = request.app.state.orchestrator
    dal = orchestrator.dal

    # 查含软删的 take
    take = dal.get_take_any(take_id)
    if take is None:
        raise HTTPException(status_code=404, detail="take not found")
    if take.deleted_at is None:
        raise HTTPException(status_code=404, detail="take not deleted")

    dal.restore_take(take_id)

    restored = dal.get_take(take_id)
    assert restored is not None  # restore 后应可见
    return TakeDTO.model_validate(restored, from_attributes=True)
