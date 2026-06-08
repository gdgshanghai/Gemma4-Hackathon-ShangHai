"""3.D：剧本导入端点（上传 → 解析 → 分场 → 入库）。

端点（spec §7）：
  POST /api/v1/scripts/upload          上传文件主入口（multipart）。
  POST /api/v1/scripts/import/confirm  重复场确认替换（阶段 2）。

数据流（上传）：
  file bytes
    → script_extract.extract_text          （3.F，按扩展名提取纯文本）
    → sp_script.run_sp_parse               （3.B，Gemma 分块分场 → ParsedScene[]）
    → script_import.plan_import            （3.C 阶段 1，只读分类，零写）
    → 无重复 → apply_import 直接入库 → {status:"imported"}
       有重复 → 不写 → {status:"needs_confirmation", plan, conflicts}

依赖注入（沿用 takes.py 模式）：
  dal         = request.app.state.orchestrator.dal
  llm_service = request.app.state.llm_service
  鉴权        = Depends(require_admin)

target 取值（spec §6）：
  multi_scene   （默认，上传整本）：解析器自动分场，按 scene_code 建/匹配场。
  current_scene （粘贴到当前场）：所有场 lines 合并成 active scene 的一个新版本。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import time
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from backend.api.auth import require_admin
from backend.core.script_extract import (
    SUPPORTED_EXTENSIONS,
    ExtractError,
    UnsupportedFormatError,
    extract_text,
)
from backend.core.script_import import (
    ImportPlan,
    NoActiveSceneError,
    apply_import,
    import_single_scene,
    plan_import,
)
from backend.pipelines.sp_script import (
    SPParseError,
    parse_scene_block,
    parse_scene_block_fc,
    split_for_parse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scripts", tags=["scripts"])

# 上传体量上限（10 MB）：剧本纯文本/文档远小于此，挡住误传大文件。
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


# ── 响应/请求模型 ────────────────────────────────────────────────────────────


class ImportedSceneOut(BaseModel):
    """单个已入库场次的结果投影（供前端展示「创建成了什么」）。"""

    scene_id: int
    script_id: int
    scene_code: str | None
    int_ext: str | None
    time_of_day: str | None
    location: str | None
    line_count: int
    lines: list[dict]  # [{line_no, character, text}]


class ConflictOut(BaseModel):
    """重复场冲突项（前端做左右 diff）。"""

    scene_id: int
    scene_code: str | None
    original: dict  # {raw_text, lines}
    incoming: dict  # {raw_text, lines}


class UploadResult(BaseModel):
    """upload / confirm 统一响应。

    status="imported"           → scenes 填充，conflicts/plan 为空。
    status="needs_confirmation" → conflicts + plan 填充，scenes 为空。
    """

    status: Literal["imported", "needs_confirmation"]
    scenes: list[ImportedSceneOut] = []
    conflicts: list[ConflictOut] = []
    plan: dict | None = None  # needs_confirmation 时回传，confirm 原样带回


class ScriptUploadInfo(BaseModel):
    """一条上传记录的元信息（不含 raw_text）。"""

    upload_id: int
    filename: str
    char_count: int
    status: str  # uploaded | parsing | parsed | error
    detail: str | None = None
    created_at: float
    updated_at: float


class UploadSavedResult(BaseModel):
    """/upload 响应：只表示「已存入 DB」，不含解析结果。"""

    upload_id: int
    filename: str
    char_count: int
    status: str  # "uploaded"


class SceneDecision(BaseModel):
    scene_id: int
    action: Literal["replace", "skip"]


class ConfirmBody(BaseModel):
    plan: dict  # upload 阶段返回的 plan（原样回传，解析只发生一次）
    decisions: list[SceneDecision] = []


class ParseSingleBody(BaseModel):
    text: str  # 单场剧本文本（可含场头行）


class ParsedLineOut(BaseModel):
    character: str | None  # 对白角色名；描述/动作行为 None
    text: str


class ParseSingleResult(BaseModel):
    """单场原生 FC 解析结果（不入库，仅返回结构化内容供预览/确认）。

    raw_text：解析所依据的源文本（文本入口=用户粘贴原文；照片入口=视觉 OCR 转写文本）。
    提交（update_scene_script）以它作为该版本的 raw_text，统一两种入口的落库与幂等比对。
    """

    scene_code: str | None
    int_ext: str | None
    time_of_day: str | None
    location: str | None
    lines: list[ParsedLineOut]
    raw_text: str


# ── 内部辅助 ─────────────────────────────────────────────────────────────────


def _build_imported_scenes(results: list[tuple[int, int]], dal) -> list[ImportedSceneOut]:
    """根据 apply_import 返回的 (scene_id, script_id)，回读 DB 构造展示结果。

    回读而非用 plan：保证返回的是真正落库的内容（含 DB 分配的 line_no）。
    """
    scene_meta = {s["scene_id"]: s for s in dal.list_scenes()}
    out: list[ImportedSceneOut] = []
    for scene_id, script_id in results:
        meta = scene_meta.get(scene_id, {})
        lines = dal.list_script_lines(script_id)
        out.append(
            ImportedSceneOut(
                scene_id=scene_id,
                script_id=script_id,
                scene_code=meta.get("scene_code"),
                int_ext=meta.get("int_ext"),
                time_of_day=meta.get("time_of_day"),
                location=meta.get("location"),
                line_count=len(lines),
                lines=[
                    {
                        "line_no": ln["line_no"],
                        "character": ln["character"],
                        "text": ln["text"],
                    }
                    for ln in lines
                ],
            )
        )
    return out


def _plan_to_dict(plan: ImportPlan) -> dict:
    """ImportPlan → JSON 可序列化 dict（confirm 原样回传，解析只发生一次）。"""
    return {
        "target": plan.target,
        "new_scenes": plan.new_scenes,
        "conflicts": plan.conflicts,
    }


def _plan_from_dict(data: dict) -> ImportPlan:
    """confirm body 的 plan dict → ImportPlan（JSON 把 tuple 转成 list，apply 解包兼容）。"""
    return ImportPlan(
        target=data.get("target", "multi_scene"),
        new_scenes=data.get("new_scenes", []),
        conflicts=data.get("conflicts", []),
    )


# ── 端点 ─────────────────────────────────────────────────────────────────────


@router.post("/upload", response_model=UploadSavedResult)
async def upload_script(
    request: Request,
    file: UploadFile = File(...),
    _: None = Depends(require_admin),
) -> UploadSavedResult:
    """阶段 1（上传）：提取文本 + 存入 DB。**不碰 Gemma**，秒回、永不超时。

    解析分场是独立的一步（POST /uploads/{id}/parse），见 spec：上传≠解析。
    """
    dal = request.app.state.orchestrator.dal

    # 读字节 + 体量保护
    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(413, "文件过大（上限 10 MB）")

    # 提取纯文本（3.F）
    filename = file.filename or "未命名"
    try:
        raw_text = extract_text(filename, data)
    except UnsupportedFormatError as exc:
        raise HTTPException(
            415, f"{exc}（支持：{', '.join(sorted(SUPPORTED_EXTENSIONS))}）"
        ) from exc
    except ExtractError as exc:
        raise HTTPException(422, str(exc)) from exc

    if not raw_text.strip():
        raise HTTPException(422, "文件无文本内容")

    upload_id = dal.insert_script_upload(filename, raw_text)
    logger.info("剧本上传：%s 提取 %d 字，已存 upload_id=%d", filename, len(raw_text), upload_id)
    return UploadSavedResult(
        upload_id=upload_id,
        filename=filename,
        char_count=len(raw_text),
        status="uploaded",
    )


@router.get("/uploads", response_model=list[ScriptUploadInfo])
async def list_uploads(
    request: Request,
    _: None = Depends(require_admin),
) -> list[ScriptUploadInfo]:
    """列出所有上传记录（含解析状态），最新在前。"""
    dal = request.app.state.orchestrator.dal
    return [ScriptUploadInfo(**u) for u in dal.list_script_uploads()]


def _block_fingerprint(block: str) -> str:
    """无号场的稳定合成 code 指纹：对源文本块（去空白）取 sha1 前 12 位。

    源块由 split_for_parse 从 raw_text 确定性切出（不经 LLM），故同一原文重传 →
    同一指纹 → get_or_create_scene 复用既有场，无号场不再每次重传都建重复场
    （旧实现用随机 batch_id，每次解析都不同 → 累积重复，见 soundspeed_script_reupload_design）。
    去空白抗换行/缩进抖动；不同内容 → 不同指纹，自然区分同次多无号场。
    """
    norm = "".join(block.split())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


async def run_parse_job(
    dal,
    llm_service,
    upload_id: int,
    raw_text: str,
    target: Literal["multi_scene", "current_scene"],
    on_conflict: Literal["skip", "version"] = "skip",
) -> None:
    """后台解析任务：瞬时切场 → 逐场 Gemma 结构化 → 每场即时入库（前端实时刷出）。

    进度写进 script_uploads.detail（"解析中 i/N 场…"）；逐场失败只跳过该场、不中断整本；
    全程异常兜底为 error（不抛给调用方）。
    multi_scene：逐场增量入库（import_single_scene，全局合成 code 保证无号场唯一）。
    current_scene：合并成一版需全量 → plan_import 批量。
    """
    try:
        blocks = split_for_parse(raw_text)
        total = len(blocks)
        if total == 0:
            dal.update_script_upload_status(upload_id, "error", "清洗后无有效内容")
            return

        if target == "current_scene":
            await _run_parse_batch(dal, llm_service, upload_id, blocks, total)
            return

        # multi_scene：逐场解析 → 逐场入库。无号场的合成 code 用源块内容指纹（稳定），
        # 同一原文重传 → 同场复用、不再建重复场（旧实现用随机 batch_id 每次都新建）。
        imported = skipped = 0
        for i, block in enumerate(blocks, 1):
            dal.update_script_upload_status(upload_id, "parsing", f"解析中 {i}/{total} 场…")
            t0 = time.monotonic()
            try:
                scenes = await parse_scene_block(block, llm_service, timeout=180.0)
            except (SPParseError, TimeoutError) as exc:
                logger.warning("场块 %d/%d 解析失败（跳过）：%s", i, total, exc)
                continue
            logger.info(
                "场块 %d/%d 解析耗时 %.1fs（输入 %d 字，得 %d 场）",
                i, total, time.monotonic() - t0, len(block), len(scenes),
            )
            block_fp = _block_fingerprint(block)
            for j, scene in enumerate(scenes):
                # 一块通常一场；偶发多场用 :j 区分，仍随源块内容稳定
                synth = f"import:{block_fp}" if j == 0 else f"import:{block_fp}:{j}"
                res = import_single_scene(
                    scene,
                    target="multi_scene",
                    synthetic_code=synth,
                    dal=dal,
                    on_conflict=on_conflict,
                )
                if res is None:
                    skipped += 1
                else:
                    imported += 1

        if imported == 0 and skipped == 0:
            dal.update_script_upload_status(upload_id, "error", "未解析出任何场次")
            return
        detail = f"已导入 {imported} 场" + (f"，{skipped} 场跳过" if skipped else "")
        dal.update_script_upload_status(upload_id, "parsed", detail)
        logger.info("剧本解析完成 upload_id=%d：%s", upload_id, detail)
    except NoActiveSceneError:
        dal.update_script_upload_status(upload_id, "error", "无活跃场次，无法导入到当前场")
    except Exception as exc:  # 兜底：后台任务异常不得静默丢失
        logger.exception("解析任务异常 upload_id=%d", upload_id)
        dal.update_script_upload_status(upload_id, "error", f"解析异常：{exc}")


async def _run_parse_batch(dal, llm_service, upload_id, blocks, total) -> None:
    """current_scene 路径：解析全部场（带进度）后 plan_import 批量合并入库。"""
    scenes = []
    for i, block in enumerate(blocks, 1):
        dal.update_script_upload_status(upload_id, "parsing", f"解析中 {i}/{total} 场…")
        try:
            scenes.extend(await parse_scene_block(block, llm_service, timeout=180.0))
        except (SPParseError, TimeoutError) as exc:
            logger.warning("场块 %d/%d 解析失败（跳过）：%s", i, total, exc)
    if not scenes:
        dal.update_script_upload_status(upload_id, "error", "未解析出任何场次")
        return
    batch_id = uuid.uuid4().hex[:8]
    plan = plan_import(scenes, target="current_scene", batch_id=batch_id, dal=dal)
    new_only = ImportPlan(target=plan.target, new_scenes=plan.new_scenes, conflicts=[])
    results = apply_import(new_only, decisions=None, dal=dal)
    skipped = len(plan.conflicts)
    detail = f"已导入 {len(results)} 场" + (f"，{skipped} 场跳过" if skipped else "")
    dal.update_script_upload_status(upload_id, "parsed", detail)


@router.post("/uploads/{upload_id}/parse", response_model=ScriptUploadInfo)
async def parse_upload(
    request: Request,
    upload_id: int,
    target: Literal["multi_scene", "current_scene"] = "multi_scene",
    on_conflict: Literal["skip", "version"] = "skip",
    _: None = Depends(require_admin),
) -> ScriptUploadInfo:
    """阶段 2（解析）：启动后台解析任务，立即返回（status=parsing）。

    解析与上传解耦、且不阻塞请求：后台逐场处理并更新进度，前端轮询 GET /uploads 展示。
    on_conflict=version（multi_scene 更新全本）：命中已有场追加新版本（内容无变化则幂等跳过）；
    默认 skip 保持首次导入语义（命中已有场跳过不替换）。
    """
    dal = request.app.state.orchestrator.dal
    llm_service = request.app.state.llm_service
    if llm_service is None:
        raise HTTPException(503, "LLM 服务未启用，无法解析剧本")

    info = dal.get_script_upload(upload_id)
    if info is None:
        raise HTTPException(404, "上传记录不存在")
    raw_text = dal.get_script_upload_raw(upload_id)
    if not raw_text:
        raise HTTPException(422, "上传记录无文本内容")

    # 切场瞬时完成 → 立刻拿到总数 N，置 parsing 进度起点
    blocks = split_for_parse(raw_text)
    if not blocks:
        dal.update_script_upload_status(upload_id, "error", "清洗后无有效内容")
        raise HTTPException(422, "清洗后无有效剧本内容（全为空行/噪声）")
    dal.update_script_upload_status(upload_id, "parsing", f"解析中 0/{len(blocks)} 场…")

    # 后台跑解析（保留 task 引用防 GC，完成后自动移除）
    tasks: set = getattr(request.app.state, "parse_tasks", None)
    if tasks is None:
        tasks = set()
        request.app.state.parse_tasks = tasks
    task = asyncio.create_task(
        run_parse_job(dal, llm_service, upload_id, raw_text, target, on_conflict)
    )
    tasks.add(task)
    task.add_done_callback(tasks.discard)

    logger.info("剧本解析：upload_id=%d 启动后台任务（%d 场块）", upload_id, len(blocks))
    return ScriptUploadInfo(**dal.get_script_upload(upload_id))


@router.post("/import/confirm", response_model=UploadResult)
async def confirm_import(
    request: Request,
    body: ConfirmBody,
    _: None = Depends(require_admin),
) -> UploadResult:
    """阶段 2：按用户对每个重复场的 replace/skip 决策写库。"""
    dal = request.app.state.orchestrator.dal
    plan = _plan_from_dict(body.plan)
    decisions = {d.scene_id: d.action for d in body.decisions}

    results = apply_import(plan, decisions=decisions, dal=dal)
    return UploadResult(
        status="imported",
        scenes=_build_imported_scenes(results, dal),
    )


@router.post("/parse-single", response_model=ParseSingleResult)
async def parse_single(
    request: Request,
    body: ParseSingleBody,
    _: None = Depends(require_admin),
) -> ParseSingleResult:
    """单场解析（Gemma 原生 function calling）：一段剧本文本 → 结构化一场，**不入库**。

    走 report_parsed_lines 工具（forced tool_choice），输出结构由 grammar 物理保证。
    是「照片增补 / 更新对话框」单场路径的基础，也是黑客松原生 FC 的展示点；
    整本批量导入仍走 POST /uploads/{id}/parse（快路径，不上 FC）。
    """
    llm_service = request.app.state.llm_service
    if llm_service is None:
        raise HTTPException(503, "LLM 服务未启用，无法解析剧本")

    text = body.text.strip()
    if not text:
        raise HTTPException(422, "文本为空")

    scenes = await parse_scene_block_fc(text, llm_service, timeout=180.0)
    return _scene_to_parse_result(scenes[0], raw_text=text)


# ── 照片 → 剧本（3.x 多模态）──────────────────────────────────────────────────

# 单次最多张数：一场剧本通常几页、每页文本不多；上限挡住误传整本相册（每张还各受 _MAX_UPLOAD_BYTES 限）。
_MAX_IMAGES = 5
# 扩展名 → MIME 兜底（浏览器一般给 content_type；缺失时按后缀猜，最后退 jpeg）。
_IMAGE_MIME = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "gif": "image/gif", "bmp": "image/bmp",
}


def _dedup_parsed_lines(lines: list[ParsedLineOut]) -> list[ParsedLineOut]:
    """折叠连续完全相同的解析行（character+text 都同）——OCR/解析 loop 的最后一道兜底。"""
    out: list[ParsedLineOut] = []
    for ln in lines:
        if out and out[-1].character == ln.character and out[-1].text.strip() == ln.text.strip():
            continue
        out.append(ln)
    return out


def _scene_to_parse_result(scene, raw_text: str, *, dedup: bool = False) -> ParseSingleResult:
    """ParsedScene → ParseSingleResult（parse_single 与 parse_images 共用投影）。

    dedup=True（仅照片路径）：折叠连续完全相同的解析行，兜底 OCR/解析 loop。文本粘贴路径
    （parse_single）保持 dedup=False，不吞用户原文里合法的连续重复台词。
    """
    lines = [ParsedLineOut(character=ln.character, text=ln.text) for ln in scene.lines]
    if dedup:
        lines = _dedup_parsed_lines(lines)
    return ParseSingleResult(
        scene_code=scene.scene_code,
        int_ext=scene.slugline.int_ext,
        time_of_day=scene.slugline.time_of_day,
        location=scene.slugline.location,
        lines=lines,
        raw_text=raw_text,
    )


def _img_data_uri(data: bytes, content_type: str | None, filename: str) -> str:
    """图片字节 → data URI（多模态 messages 的 image_url content 用）。"""
    mime = content_type
    if not mime or not mime.startswith("image/"):
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mime = _IMAGE_MIME.get(ext, "image/jpeg")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


# 回合/特殊标记：模型越界续写时会吐出这些；遇到即视为正文结束，截断其后所有内容。
_SPECIAL_MARKERS = ("<|turn", "<end_of_turn>", "<start_of_turn>", "<eos>", "<|im_end|>", "<bos>")


def _strip_special_tokens(text: str) -> str:
    """截掉模型越过回合边界后吐出的特殊标记及其之后的全部内容（<|turn|> / <|turn>model 等）。

    OCR 内容本身通常正确，"重复"多是模型不在回合结束处停、继续吐 <|turn|> 再乱写/重写。
    与生成期的 stop 双保险：stop 让模型早停，这里清掉万一漏网的残留标记 + 越界续写。
    """
    cut = len(text)
    for m in _SPECIAL_MARKERS:
        i = text.find(m)
        if i != -1:
            cut = min(cut, i)
    return text[:cut]


def _dedup_repeated_lines(text: str) -> str:
    """折叠 OCR 的循环重复行（小模型通病）。两道：

    1. **连续完全相同行 → 折成一条（不限长度）**：根治「上笑。」这类短词连吐 N 遍的 degenerate
       loop（连续重复绝不可能是合法内容）。代价：丢掉极罕见的合法连续重复行（可接受）。
    2. 近窗（前 3 条长行）内重复 → 丢：拦近距块循环 A B A B；长度≥4 才入窗，护非连续的合法短句
       （「好。」「嗯。」等隔行重复仍保留）。
    """
    out: list[str] = []
    recent: list[str] = []  # 最近 3 条已保留的长行（去空白）
    for ln in text.splitlines():
        s = ln.strip()
        if s:
            if out and out[-1].strip() == s:  # 连续相同（任意长度）
                continue
            if len(s) >= 4 and s in recent:  # 近窗块循环
                continue
        out.append(ln)
        if s and len(s) >= 4:
            recent.append(s)
            if len(recent) > 3:
                recent.pop(0)
    return "\n".join(out)


async def _ocr_images_to_text(llm_service, image_data_uris: list[str]) -> str:
    """视觉 OCR：逐页（每次单图）转写后拼接（无 tools，走多模态 handler）。

    逐页单图而非一次喂多图：根治小模型一次看多图时整段循环重复（用户实测 3 图大量重复）；
    每页输出也被 max_tokens 封顶，单页跑飞不拖垮整次。按上传顺序拼接成全文。
    """
    from backend.llm.config import TASK_CONFIG  # noqa: PLC0415

    system = TASK_CONFIG["script_vision_ocr"]["system"]
    pages: list[str] = []
    for uri in image_data_uris:
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "把这张剧本照片逐字转写成纯文本。"},
                    {"type": "image_url", "image_url": {"url": uri}},
                ],
            },
        ]
        # 视觉 OCR：1120 image token + n_batch 大，CPU 上偏慢，单页 timeout 放宽到 180s。
        page = await llm_service.infer(messages, task_type="script_vision_ocr", timeout=180.0)
        # 先切掉越界续写的特殊标记及其后内容，再折叠残留重复行。
        page = _dedup_repeated_lines(_strip_special_tokens(page)).strip()
        if page:
            pages.append(page)
    return "\n".join(pages)


def _extract_target_scene_text(ocr_text: str, scene_code: str | None) -> str:
    """从多页 OCR 全文里只取目标场（scene_code）的内容，丢相邻场（上一场尾 / 下一场头）。

    用 split_scenes_by_slugline 按场头切：有显式场号时它本就丢弃首个场号前的前言（=第一页开头
    上一场的尾巴），再按 scene_code 选中目标场那块（丢掉末页的下一场）。场号归一复用读侧
    canonical 的 normalize_scene_code（剥 Scene/场/Sc/S 前缀 + 中文序数），与库内匹配口径一致
    （比纯 alnum 折叠强：SCENE 3A / 3A 都归一为 3A 而能匹配）。
    无 scene_code / 切不出多块 / 匹配不到 → 原样返回（宁可多带、不丢内容；OCR 没认出场头时的兜底）。
    """
    if not scene_code:
        return ocr_text
    from backend.db.dal import normalize_scene_code  # noqa: PLC0415
    from backend.pipelines.sp_script import (  # noqa: PLC0415
        _split_scene_header,
        split_scenes_by_slugline,
    )

    blocks = split_scenes_by_slugline(ocr_text)
    if len(blocks) <= 1:
        return ocr_text
    want = normalize_scene_code(scene_code)
    for b in blocks:
        code, _slug, _body = _split_scene_header(b)
        if code and normalize_scene_code(code) == want:
            return b
    return ocr_text


@router.post("/parse-images", response_model=ParseSingleResult)
async def parse_images(
    request: Request,
    files: list[UploadFile] = File(...),
    scene_code: str | None = Form(None),
    _: None = Depends(require_admin),
) -> ParseSingleResult:
    """照片 → 单场剧本：视觉 OCR 逐字转写 → parse_scene_block 结构化一场，**不入库**。

    与 parse-single 同形状返回（含 raw_text=OCR 文本），前端复用同一预览/提交流（SceneUpdateDialog）。
    解析用**无 grammar** 的 parse_scene_block（非 parse_scene_block_fc）：照片多页 OCR 文本偏长，
    grammar 强制 FC 在 Gemma 上慢约 5.6×，长文本会超 180s（实测 3 页超时）；本场只需更新内容、
    不要求结构严格，故走快路径。需多模态模型：SOUNDSPEED_LLM_TEXT_ONLY=1 / mmproj 未加载 → 503。
    """
    llm_service = request.app.state.llm_service
    if llm_service is None:
        raise HTTPException(503, "LLM 服务未启用，无法解析剧本")

    # 视觉可用性预检：text_only / mmproj 缺失 → 明确指引（去掉 TEXT_ONLY 重启）。
    from backend.llm.service import _text_only, resolve_mmproj_path  # noqa: PLC0415

    if _text_only() or resolve_mmproj_path(download=False) is None:
        raise HTTPException(
            503, "视觉模型未启用（mmproj 未加载）。请去掉 SOUNDSPEED_LLM_TEXT_ONLY=1 后重启后端。"
        )

    if not files:
        raise HTTPException(422, "未上传任何图片")
    if len(files) > _MAX_IMAGES:
        raise HTTPException(413, f"图片过多（上限 {_MAX_IMAGES} 张）")

    uris: list[str] = []
    for f in files:
        data = await f.read()
        if not data:
            continue
        if len(data) > _MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"图片过大（单张上限 10 MB）：{f.filename or '未命名'}")
        uris.append(_img_data_uri(data, f.content_type, f.filename or ""))
    if not uris:
        raise HTTPException(422, "图片为空")

    ocr_text = await _ocr_images_to_text(llm_service, uris)
    if not ocr_text.strip():
        raise HTTPException(422, "未能从照片识别出文本")

    # 只取目标场：丢掉首页开头上一场的尾、末页下一场的头（按场头切 + scene_code 选中那块）。
    scene_text = _extract_target_scene_text(ocr_text, scene_code)
    if not scene_text.strip():
        raise HTTPException(422, "未能从照片识别出本场内容")

    # 无 grammar 快解析（照片 OCR 文本偏长，grammar FC 会超时）；返回 [一个 ParsedScene]。
    scenes = await parse_scene_block(scene_text, llm_service, timeout=180.0)
    # dedup=True：照片路径才折叠连续重复行（OCR loop 兜底）；文本路径不折叠。
    return _scene_to_parse_result(scenes[0], raw_text=scene_text, dedup=True)
