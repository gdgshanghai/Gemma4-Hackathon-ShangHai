"""3.C：剧本入库协调模块（ticket 3.C）—— preview/confirm 两阶段版。

公共 API：
  ScriptImportReadDAL   只读 DAL Protocol（plan_import 用，零 2.x 依赖）。
  ScriptImportWriteDAL  写 DAL Protocol（apply_import 用，含 get_or_create_scene）。
  NoActiveSceneError    单场路径无 active scene 时抛出的领域异常。
  ImportPlan            preview 阶段产出的结构化计划（dataclass）。
  plan_import           阶段 1：只读分类，返回 ImportPlan。
  apply_import          阶段 2：按 decisions 写库。

设计依据：
  docs/specs/2026-06-03-script-import-sp-pipeline.md §5.1 + §0 分叉 1

两阶段概述（§5.1）：
  plan_import  —— 行清洗 + 跳过全空场 + 只读分类（list_scenes / get_latest_script）。
               绝不调 get_or_create_scene，保证零写、零 2.x 依赖。
               target=current_scene 时把所有场 lines 合并成一个 merged 版本。
  apply_import —— 唯一调 get_or_create_scene 的地方；
               按 decisions（replace/skip）决定重复场是否写；
               无重复场全写；整批无重复时 decisions=None 合法。

Protocol 拆分理由：
  plan_import 的 dal 只需只读方法（全在 main DAL），
  类型层面验证「preview 零 2.x 依赖」——真 DAL 结构满足 ScriptImportReadDAL，
  preview 路径测试无需 # type: ignore。
  apply_import 的 dal 需要 get_or_create_scene（2.x 方法），
  multi_scene apply 路径等 2.x 合 main 后真 DAL 才结构满足 ScriptImportWriteDAL。

batch_id 注入：
  合成 scene_code（import:<batch_id>:<n>）所需的 batch_id 由调用方传入，
  保证 append-only 测试可复现。合成序号 n 使用原始迭代序号（跳过空场后剩余
  场的序号），保证唯一性。

疑点（留 Lead 拍板）：
  1. decisions 中缺失的 scene_id 默认 skip（保守，不覆盖好版本）。
  2. 合成 code 序号 n 用清洗后序号（0,1,2...），不含被跳过的空场。
  3. ScriptImportReadDAL / ScriptImportWriteDAL 分拆方案已采用，
     如 Lead 认为 Protocol 太多可合并回单个，apply 侧加 # type: ignore。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from backend.pipelines.sp_script import ParsedScene


# ---------------------------------------------------------------------------
# 领域异常
# ---------------------------------------------------------------------------


class NoActiveSceneError(Exception):
    """单场路径无 active scene 时抛出，调用方（3.D 端点）转 422。"""


# ---------------------------------------------------------------------------
# 只读 DAL Protocol（plan_import 用）
# ---------------------------------------------------------------------------


@runtime_checkable
class ScriptImportReadDAL(Protocol):
    """plan_import 所需的只读 DAL surface。

    全部方法均已在 main 的真 DAL 实现，零 2.x 依赖。
    """

    def get_active_scene_id(self) -> int | None:
        """返回当前活跃场次 ID，无则返回 None。"""
        ...

    def list_scenes(self) -> list[dict]:
        """返回所有场次列表，每个 dict 含 scene_id / scene_code 等。"""
        ...

    def get_latest_script(self, scene_id: int) -> dict | None:
        """返回该场次最新版本剧本（含 script_id/raw_text/version），无则 None。"""
        ...

    def list_script_lines(self, script_id: int) -> list[dict]:
        """返回剧本行列表（含 line_no/line_id/character/text），按 line_no ASC。"""
        ...


# ---------------------------------------------------------------------------
# 写 DAL Protocol（apply_import 用，含 get_or_create_scene）
# ---------------------------------------------------------------------------


@runtime_checkable
class ScriptImportWriteDAL(Protocol):
    """apply_import 所需的写 DAL surface。

    get_or_create_scene 是 2.x 方法，multi_scene apply 路径依赖 2.x 合 main。
    single_scene apply 路径只用 get_active_scene_id / insert_script / insert_script_line，
    均在 main，单场路径真 DAL 测试今天可运行（带 # type: ignore[arg-type]）。
    """

    def get_active_scene_id(self) -> int | None: ...

    def get_or_create_scene(
        self,
        scene_code: str,
        *,
        description: str | None = None,
        shoot_date: str | None = None,
        int_ext: str | None = None,
        time_of_day: str | None = None,
        location: str | None = None,
    ) -> tuple[int, bool]:
        """按 scene_code 查找或建场。

        命中 → (existing_id, False)，忽略其余参数，不更新已有行。
        未命中 → INSERT → (new_id, True)。
        并发 IntegrityError 兜底重 SELECT → (id, False)。
        """
        ...

    def insert_script(
        self,
        scene_id: int,
        raw_text: str,
        version: int | None = None,
    ) -> int:
        """插入剧本原文，version=None 时自动取该场 MAX+1，返回 script_id。"""
        ...

    def insert_script_line(
        self,
        script_id: int,
        line_no: int,
        character: str | None,
        text: str,
    ) -> int:
        """插入一行台词，返回 line_id。"""
        ...


# ---------------------------------------------------------------------------
# ImportPlan 结构
# ---------------------------------------------------------------------------


@dataclass
class ImportPlan:
    """plan_import 返回的结构化计划，带到 apply_import 作唯一写入指令。

    Fields:
        target:      "current_scene" | "multi_scene"，apply 据此分支。
        new_scenes:  无重复场列表，每个 dict 含：
                       scene_id (int | None)  — 已有场 ID（命中无脚本场）或 None（全新场）
                       scene_code (str | None) — multi_scene 的目标 code
                       lines (list[tuple])     — 清洗后行，(line_no_placeholder, character, text)
                                                  line_no_placeholder = None（apply 时从 1 分配）
                       raw_text (str)          — 拼接好的 raw_text
                       slugline (dict)         — int_ext/time_of_day/location（建场用）
        conflicts:   重复场列表，每个 dict 含：
                       scene_id (int)
                       scene_code (str | None)
                       original (dict)         — {raw_text: str, lines: list[dict]}
                       incoming (dict)         — {raw_text: str, lines: list[tuple]}
    """

    target: Literal["current_scene", "multi_scene"]
    new_scenes: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _clean_lines(
    scene: "ParsedScene",
) -> list[tuple[str | None, str]]:
    """行清洗（spec §5 步骤 4）。

    - 过滤 text.strip() 为空的行。
    - character 空串归一为 None（舞台指示）。
    返回 (character, text) 元组列表。
    """
    return [
        (None if (ln.character or "").strip() == "" else ln.character, ln.text)
        for ln in scene.lines
        if ln.text.strip()
    ]


def _build_raw_text(valid_lines: list[tuple[str | None, str]]) -> str:
    """按 spec §5 口径拼接 raw_text（对齐 debug.py:139）。

    有 character → "character：text"，无（舞台指示）→ 直出 text，换行分隔。
    """
    return "\n".join(
        f"{character}：{text}" if character else text
        for character, text in valid_lines
    )


def _lines_to_plan_tuples(
    valid_lines: list[tuple[str | None, str]],
) -> list[tuple[None, str | None, str]]:
    """把 (character, text) 转为 plan 内的 (None, character, text)。

    第一个 None 是 line_no 占位（apply 时从 1 连续分配）。
    """
    return [(None, c, t) for c, t in valid_lines]


# ---------------------------------------------------------------------------
# 阶段 1：plan_import（preview，只读，零写）
# ---------------------------------------------------------------------------


def plan_import(
    scenes: "list[ParsedScene]",
    *,
    target: Literal["current_scene", "multi_scene"],
    batch_id: str,
    dal: ScriptImportReadDAL,
) -> ImportPlan:
    """Preview 阶段：行清洗 + 只读分类，返回 ImportPlan。

    Args:
        scenes:   解析器（3.B）输出的场列表。
        target:   "current_scene" 走单场路径，其余走多场路径。
        batch_id: 批次标识，用于合成无号场的 scene_code（保证可复现）。
        dal:      实现 ScriptImportReadDAL 的 DAL（只读方法全在 main）。

    Returns:
        ImportPlan：含 new_scenes（待写内容）和 conflicts（重复场）。

    Raises:
        NoActiveSceneError: target="current_scene" 但无 active scene。

    保证：
        - 绝不调 get_or_create_scene（零写承诺）。
        - 清洗判空在定 scene_id 之前（spec §5 步骤 5）。
        - current_scene 路径合并所有场 lines 成一个版本。

    调用方（3.D 端点）注意：返回的 plan 若 new_scenes 与 conflicts 均空
    （全空场被跳过 / 输入无有效行）= 全空信号，端点应返回 422、不再调 apply_import
    （spec §5 步骤 5）。
    """
    plan = ImportPlan(target=target)
    is_single = target == "current_scene"

    if is_single:
        # 单场路径：合并所有场 lines 成一个 merged 版本
        active_scene_id = dal.get_active_scene_id()
        if active_scene_id is None:
            raise NoActiveSceneError("no active scene")

        # 合并清洗：跨场顺序 flatten
        merged_lines: list[tuple[str | None, str]] = []
        for scene in scenes:
            merged_lines.extend(_clean_lines(scene))

        if not merged_lines:
            # 全批合并后空：返回空 plan（3.D 端点 422）
            return plan

        raw_text = _build_raw_text(merged_lines)
        existing_script = dal.get_latest_script(active_scene_id)

        if existing_script is not None:
            # 有脚本 → conflict
            original_lines = dal.list_script_lines(existing_script["script_id"])
            plan.conflicts.append({
                "scene_id": active_scene_id,
                "scene_code": None,  # single 路径无 scene_code
                "original": {
                    "raw_text": existing_script["raw_text"],
                    "lines": original_lines,
                },
                "incoming": {
                    "raw_text": raw_text,
                    "lines": _lines_to_plan_tuples(merged_lines),
                },
            })
        else:
            # 无脚本 → 新场（首次）
            plan.new_scenes.append({
                "scene_id": active_scene_id,
                "scene_code": None,
                "lines": _lines_to_plan_tuples(merged_lines),
                "raw_text": raw_text,
                "slugline": {"int_ext": None, "time_of_day": None, "location": None},
            })

        return plan

    # 多场路径：建 {scene_code: scene_id} 映射
    scene_map: dict[str, int] = {
        s["scene_code"]: s["scene_id"]
        for s in dal.list_scenes()
        if s.get("scene_code") is not None
    }

    synthetic_n = 0  # 无号场合成序号（跳过空场后的计数）
    for scene in scenes:
        # 行清洗（在定 scene_id 之前）
        valid_lines = _clean_lines(scene)
        if not valid_lines:
            # 步骤 5：全空场整场跳过
            continue

        raw_text = _build_raw_text(valid_lines)

        # 定 scene_code
        if scene.scene_code is not None:
            code = scene.scene_code
        else:
            code = f"import:{batch_id}:{synthetic_n}"
            synthetic_n += 1

        slugline = {
            "int_ext": scene.slugline.int_ext,
            "time_of_day": scene.slugline.time_of_day,
            "location": scene.slugline.location,
        }

        if code in scene_map:
            # 命中已有场
            existing_scene_id = scene_map[code]
            existing_script = dal.get_latest_script(existing_scene_id)
            if existing_script is not None:
                # 有脚本 → conflict
                original_lines = dal.list_script_lines(existing_script["script_id"])
                plan.conflicts.append({
                    "scene_id": existing_scene_id,
                    "scene_code": code,
                    "original": {
                        "raw_text": existing_script["raw_text"],
                        "lines": original_lines,
                    },
                    "incoming": {
                        "raw_text": raw_text,
                        "lines": _lines_to_plan_tuples(valid_lines),
                    },
                })
            else:
                # 命中但无脚本 → 新场（首次导入）
                plan.new_scenes.append({
                    "scene_id": existing_scene_id,
                    "scene_code": code,
                    "lines": _lines_to_plan_tuples(valid_lines),
                    "raw_text": raw_text,
                    "slugline": slugline,
                })
        else:
            # 不在映射（新场 or 无号合成 code）
            plan.new_scenes.append({
                "scene_id": None,  # apply 时由 get_or_create_scene 建
                "scene_code": code,
                "lines": _lines_to_plan_tuples(valid_lines),
                "raw_text": raw_text,
                "slugline": slugline,
            })

    return plan


# ---------------------------------------------------------------------------
# 阶段 2：apply_import（写，唯一调 get_or_create_scene 的地方）
# ---------------------------------------------------------------------------


def _write_scene(dal: ScriptImportWriteDAL, scene_id: int, entry: dict) -> tuple[int, int]:
    """把 plan entry（raw_text + lines）写入 script + script_lines，返回 (scene_id, script_id)。"""
    raw_text: str = entry["raw_text"]
    plan_lines: list[tuple] = entry["lines"]  # (None, character, text)

    script_id = dal.insert_script(scene_id, raw_text)
    for line_no, (_, character, text) in enumerate(plan_lines, start=1):
        dal.insert_script_line(script_id, line_no, character, text)
    return scene_id, script_id


def apply_import(
    plan: ImportPlan,
    *,
    decisions: dict[int, str] | None,
    dal: ScriptImportWriteDAL,
) -> list[tuple[int, int]]:
    """Confirm 阶段：按 decisions 写库，返回 (scene_id, script_id) 列表。

    Args:
        plan:      plan_import 返回的 ImportPlan。
        decisions: 每个重复场的决策，key=scene_id，value="replace"|"skip"。
                   plan.conflicts 为空时 decisions=None 合法（整批无重复直接写）。
                   有 conflict 但某 scene_id 不在 decisions 中 → 默认 skip（保守）。
        dal:       实现 ScriptImportWriteDAL 的 DAL。

    Returns:
        每个实际写入的场 (scene_id, script_id) 列表（跳过的场不计入）。

    设计：
        - new_scenes 全写（无条件）。
        - conflicts 按 decisions 决定：replace 写、skip 跳过、缺失默认 skip。
        - single_scene 路径 apply 不走 get_or_create_scene：
          使用 plan 中的 scene_id（来自 get_active_scene_id snapshot）直接写。
        - multi_scene 路径：new_scenes.scene_id 为 None 时调 get_or_create_scene 建场；
          scene_id 非 None（命中无脚本的已有场）直接使用。
        - 解析只发生一次（§5.1 硬约束）：plan 带完整 cleaned lines，apply 直接写。

    ⚠ TOCTOU（spec §5.1 单用户低风险）：single_scene 用 plan 的 active scene snapshot
      直接写，preview→confirm 之间若 active scene 被切换（多用户/后台）会写到旧场。本 core
      不防；3.D confirm 端点应重校验 get_active_scene_id() 与 plan 一致、不一致返 409。
      multi_scene conflict 的 scene_code 必非 None（单场 conflict code=None 被 is_single 隔离）。
    """
    decisions = decisions or {}
    results: list[tuple[int, int]] = []

    is_single = plan.target == "current_scene"

    # 写无重复场
    for entry in plan.new_scenes:
        if is_single:
            # single 路径：scene_id 已在 plan 中（get_active_scene_id snapshot）
            assert entry["scene_id"] is not None
            scene_id: int = entry["scene_id"]
        else:
            # multi 路径：scene_id 为 None 时建场，非 None 时直接用
            if entry["scene_id"] is None:
                slugline = entry.get("slugline", {})
                scene_id, _ = dal.get_or_create_scene(
                    entry["scene_code"],
                    int_ext=slugline.get("int_ext"),
                    time_of_day=slugline.get("time_of_day"),
                    location=slugline.get("location"),
                )
            else:
                scene_id = entry["scene_id"]

        results.append(_write_scene(dal, scene_id, entry))

    return _apply_conflicts(plan, decisions, dal, is_single, results)


def import_single_scene(
    scene: "ParsedScene",
    *,
    target: Literal["current_scene", "multi_scene"],
    synthetic_code: str,
    dal: ScriptImportWriteDAL,
    active_scene_id: int | None = None,
    on_conflict: Literal["skip", "version"] = "skip",
) -> dict | None:
    """逐场增量入库（异步解析的每场即时落库用）。

    清洗该场行；空场返回 None（跳过）。多场路径按 scene_code（无号用 synthetic_code）
    get_or_create_scene；命中既有且已有脚本 → 重复场，返回 None（本期跳过不替换）。
    单场路径写入 active_scene_id（注意：多次调用会各起新版本，current_scene 的
    「多场合并成一版」语义不适用增量，调用方对 current_scene 应走 plan_import 批量）。

    Returns:
        {scene_id, script_id, scene_code} 或 None（空场/重复跳过）。

    Raises:
        NoActiveSceneError: target=current_scene 但 active_scene_id 为 None。
    """
    valid_lines = _clean_lines(scene)
    if not valid_lines:
        return None  # 空场跳过（spec §5 步骤 5）

    raw_text = _build_raw_text(valid_lines)

    if target == "current_scene":
        if active_scene_id is None:
            raise NoActiveSceneError("no active scene")
        scene_id = active_scene_id
        scene_code: str | None = None
    else:
        scene_code = scene.scene_code or synthetic_code
        scene_id, created = dal.get_or_create_scene(
            scene_code,
            int_ext=scene.slugline.int_ext,
            time_of_day=scene.slugline.time_of_day,
            location=scene.slugline.location,
        )
        if not created:
            existing = dal.get_latest_script(scene_id)
            if existing is not None:
                if on_conflict == "skip":
                    return None  # 重复场：跳过不替换（默认）
                # on_conflict="version"（更新全本）：raw_text 没变则幂等跳过、不刷版本；
                # 变了则 fall through 追加新版本（旧版保留）。
                if existing.get("raw_text") == raw_text:
                    return None

    script_id = dal.insert_script(scene_id, raw_text)
    for line_no, (character, text) in enumerate(valid_lines, start=1):
        dal.insert_script_line(script_id, line_no, character, text)
    return {"scene_id": scene_id, "script_id": script_id, "scene_code": scene_code}


def _apply_conflicts(plan, decisions, dal, is_single, results):
    """apply_import 的重复场写入分支（按 decisions：replace 写 / skip 跳过）。"""
    # 写重复场（按 decisions）
    for conflict in plan.conflicts:
        conflict_scene_id: int = conflict["scene_id"]
        action = decisions.get(conflict_scene_id, "skip")  # 缺失默认 skip

        if action != "replace":
            continue

        if is_single:
            # single 路径：直接用 scene_id（snapshot）
            scene_id = conflict_scene_id
        else:
            # multi 路径：调 get_or_create_scene 确认场存在（兜并发）
            scene_id, _ = dal.get_or_create_scene(
                conflict["scene_code"],
            )

        # 写 incoming 内容（新版本）
        results.append(_write_scene(dal, scene_id, conflict["incoming"]))

    return results
