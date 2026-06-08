"""3.C Script Import 单元测试（两阶段 preview/confirm 重构版）。

覆盖 plan_import（preview，只读分类）：
  P1  新场（scene_code 不在映射）→ 无重复
  P2  命中有脚本场 → 重复，original/incoming 内容正确
  P3  命中无脚本场 → 无重复（首次导入）
  P4  无号场 append-only 永不重复
  P5  单场 current_scene 多场合并成一个版本（merged lines + line_no 连续）
  P6  全空场跳过（不计入计划）
  P7  无 active scene → NoActiveSceneError
  P8  conflicts 的 original 带 raw_text + lines（来自 get_latest_script + list_script_lines）
  P9  单场 current_scene 有脚本 → conflict（original=当前场，incoming=合并内容）

覆盖 apply_import（写阶段，含 FakeDAL 和真 DAL）：
  A1  整批无重复 → 全写（decisions=None）
  A2  replace → 写新版本
  A3  skip → 不写
  A4  单场 current_scene 写（真 in-memory DAL）
  A5  版本自增（真 DAL）

真 in-memory DAL（preview）：
  R1  真 DAL plan_import：分类新场/命中有脚本/命中无脚本（list_scenes + get_latest_script 均在 main）
  R2  真 DAL plan_import：单场 current_scene 有脚本 → conflict，original 内容正确
  R3  真 DAL apply_import 单场写（版本自增、line_no 连续、raw_text 格式）

注：
  - plan_import 零 2.x 依赖（不调 get_or_create_scene），所有分类路径可用真 DAL 验。
  - apply_import 中的 get_or_create_scene 仍是 2.x 方法（multi_scene 路径），
    apply 多场路径用 FakeDAL 验协调逻辑，单场路径用真 DAL 验写行为。
    2.x 合 main 后 apply 多场可用真 DAL 重跑。
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterator

import pytest

from backend.core.script_import import (
    ImportPlan,
    NoActiveSceneError,
    _clean_lines,
    apply_import,
    import_single_scene,
    plan_import,
)
from backend.db.dal import DAL
from backend.pipelines.sp_script import ParsedLine, ParsedScene, Slugline


# ---------------------------------------------------------------------------
# Fake DAL（用于 apply_import 的 multi_scene 路径）
# ---------------------------------------------------------------------------


class FakeWriteDAL:
    """测试用假 DAL，实现完整的 ScriptImportWriteDAL Protocol。

    支持 get_or_create_scene（apply 多场路径）。
    """

    def __init__(self, active_scene_id: int | None = None) -> None:
        self._active_scene_id = active_scene_id

        # scene_code → scene_id
        self._scenes: dict[str, int] = {}
        self._next_scene_id = 100

        # script records: list of (scene_id, raw_text, version)
        self.scripts: list[tuple[int, str, int]] = []
        # scene_id → current max version
        self._scene_versions: dict[int, int] = {}
        self._next_script_id = 1000

        # (script_id, line_no, character, text)
        self.lines: list[tuple[int, int, str | None, str]] = []

    def get_active_scene_id(self) -> int | None:
        return self._active_scene_id

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
        if scene_code in self._scenes:
            return self._scenes[scene_code], False
        new_id = self._next_scene_id
        self._next_scene_id += 1
        self._scenes[scene_code] = new_id
        return new_id, True

    def insert_script(
        self,
        scene_id: int,
        raw_text: str,
        version: int | None = None,
    ) -> int:
        if version is None:
            version = self._scene_versions.get(scene_id, 0) + 1
        self._scene_versions[scene_id] = version
        script_id = self._next_script_id
        self._next_script_id += 1
        self.scripts.append((scene_id, raw_text, version))
        return script_id

    def insert_script_line(
        self,
        script_id: int,
        line_no: int,
        character: str | None,
        text: str,
    ) -> int:
        self.lines.append((script_id, line_no, character, text))
        return len(self.lines)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _scene(
    scene_code: str | None = None,
    lines: list[tuple[str | None, str]] | None = None,
    int_ext: str | None = None,
    time_of_day: str | None = None,
    location: str | None = None,
) -> ParsedScene:
    """快速构建 ParsedScene。lines 是 (character, text) 元组列表。"""
    parsed_lines = [ParsedLine(character=c, text=t) for c, t in (lines or [])]
    return ParsedScene(
        scene_code=scene_code,
        slugline=Slugline(int_ext=int_ext, time_of_day=time_of_day, location=location),
        lines=parsed_lines,
    )


# ---------------------------------------------------------------------------
# 真 in-memory DAL fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dal(tmp_path: pathlib.Path) -> Iterator[DAL]:
    """每个测试一个临时文件 sqlite DAL（不用 :memory:，DAL 双连接不兼容）。"""
    d = DAL(tmp_path / "test_si.db")
    try:
        yield d
    finally:
        d.close()


# ---------------------------------------------------------------------------
# P1  新场（scene_code 不在映射）→ 无重复
# ---------------------------------------------------------------------------


def test_plan_new_scene_no_conflict() -> None:
    """P1 桩：实质测试在 test_plan_new_scene_no_conflict_fake 和 R1 节。"""
    # plan_import 用只读 DAL（FakeReadDAL），见下方同名 _fake 测试和 R1 节真 DAL 测试。
    pass


# ---------------------------------------------------------------------------
# FakeReadDAL：只读 DAL，供 plan_import 分类路径测试
# ---------------------------------------------------------------------------


class FakeReadDAL:
    """只实现 plan_import 所需的只读方法 + apply 写方法（完整 Protocol）。

    list_scenes() 返回 {scene_code: scene_id} 的场列表（dict list）。
    get_latest_script(scene_id) 返回 script dict 或 None。
    list_script_lines(script_id) 返回 line dict 列表。
    """

    def __init__(
        self,
        active_scene_id: int | None = None,
        scenes: dict[str, int] | None = None,
        scripts: dict[int, dict | None] | None = None,
        script_lines: dict[int, list[dict]] | None = None,
    ) -> None:
        self._active_scene_id = active_scene_id
        # scene_code → scene_id
        self._scene_map: dict[str, int] = scenes or {}
        # scene_id → script dict (script_id, raw_text, version) or None
        self._scripts: dict[int, dict | None] = scripts or {}
        # script_id → list of line dicts
        self._lines: dict[int, list[dict]] = script_lines or {}

        # 写方法（apply）
        self._scene_versions: dict[int, int] = {}
        self._next_script_id = 5000
        self.written_scripts: list[tuple[int, str, int]] = []
        self.written_lines: list[tuple[int, int, str | None, str]] = []
        self._next_scene_id = 200
        self._created_scenes: dict[str, int] = dict(self._scene_map)

    def get_active_scene_id(self) -> int | None:
        return self._active_scene_id

    def list_scenes(self) -> list[dict]:
        return [{"scene_id": v, "scene_code": k} for k, v in self._scene_map.items()]

    def get_latest_script(self, scene_id: int) -> dict | None:
        return self._scripts.get(scene_id)

    def list_script_lines(self, script_id: int) -> list[dict]:
        return self._lines.get(script_id, [])

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
        if scene_code in self._created_scenes:
            return self._created_scenes[scene_code], False
        new_id = self._next_scene_id
        self._next_scene_id += 1
        self._created_scenes[scene_code] = new_id
        return new_id, True

    def insert_script(
        self,
        scene_id: int,
        raw_text: str,
        version: int | None = None,
    ) -> int:
        if version is None:
            version = self._scene_versions.get(scene_id, 0) + 1
        self._scene_versions[scene_id] = version
        script_id = self._next_script_id
        self._next_script_id += 1
        self.written_scripts.append((scene_id, raw_text, version))
        return script_id

    def insert_script_line(
        self,
        script_id: int,
        line_no: int,
        character: str | None,
        text: str,
    ) -> int:
        self.written_lines.append((script_id, line_no, character, text))
        return len(self.written_lines)


# ---------------------------------------------------------------------------
# P1  新场（scene_code 不在映射）→ 无重复
# ---------------------------------------------------------------------------


def test_plan_new_scene_no_conflict_fake() -> None:
    """multi_scene，scene_code 不在映射 → 无重复，conflicts 空，new_scenes 有内容。"""
    dal = FakeReadDAL(
        scenes={},   # 空映射
        scripts={},
    )
    scenes = [_scene(scene_code="3", lines=[("张三", "你好")])]
    plan = plan_import(scenes, target="multi_scene", batch_id="b1", dal=dal)

    assert isinstance(plan, ImportPlan)
    assert len(plan.conflicts) == 0
    assert len(plan.new_scenes) == 1
    assert plan.new_scenes[0]["scene_code"] == "3"


# ---------------------------------------------------------------------------
# P2  命中有脚本场 → 重复
# ---------------------------------------------------------------------------


def test_plan_existing_scene_with_script_is_conflict() -> None:
    """scene_code 在映射且该场有脚本 → 重复（conflict）。"""
    dal = FakeReadDAL(
        scenes={"3": 10},  # scene_code "3" → scene_id 10
        scripts={10: {"script_id": 99, "raw_text": "张三：旧台词", "version": 1}},
        script_lines={99: [{"line_id": 1, "line_no": 1, "character": "张三", "text": "旧台词"}]},
    )
    scenes = [_scene(scene_code="3", lines=[("张三", "新台词")])]
    plan = plan_import(scenes, target="multi_scene", batch_id="b1", dal=dal)

    assert len(plan.conflicts) == 1
    assert len(plan.new_scenes) == 0
    conflict = plan.conflicts[0]
    assert conflict["scene_id"] == 10
    assert conflict["scene_code"] == "3"


# ---------------------------------------------------------------------------
# P3  命中无脚本场 → 无重复（首次导入）
# ---------------------------------------------------------------------------


def test_plan_existing_scene_no_script_no_conflict() -> None:
    """scene_code 在映射但该场无脚本（首次导入）→ 无重复。"""
    dal = FakeReadDAL(
        scenes={"5": 20},  # 有场
        scripts={20: None},  # 但无脚本
    )
    scenes = [_scene(scene_code="5", lines=[("李四", "首次台词")])]
    plan = plan_import(scenes, target="multi_scene", batch_id="b1", dal=dal)

    assert len(plan.conflicts) == 0
    assert len(plan.new_scenes) == 1
    assert plan.new_scenes[0]["scene_id"] == 20
    assert plan.new_scenes[0]["scene_code"] == "5"


# ---------------------------------------------------------------------------
# P4  无号场 append-only 永不重复
# ---------------------------------------------------------------------------


def test_plan_no_code_append_only() -> None:
    """scene_code=None → 合成 code 唯一，必不在映射 → 永远是新场（无重复）。"""
    dal = FakeReadDAL(
        scenes={"3": 10},  # 已有其他场，不影响无号场
    )
    scenes = [
        _scene(scene_code=None, lines=[("张三", "第一场")]),
        _scene(scene_code=None, lines=[("李四", "第二场")]),
    ]
    plan = plan_import(scenes, target="multi_scene", batch_id="batch-42", dal=dal)

    assert len(plan.conflicts) == 0
    assert len(plan.new_scenes) == 2
    # 合成 code 应带 batch_id 前缀
    codes = [s["scene_code"] for s in plan.new_scenes]
    assert all("batch-42" in code for code in codes)


# ---------------------------------------------------------------------------
# P5  单场 current_scene 多场合并成一个版本
# ---------------------------------------------------------------------------


def test_plan_current_scene_merges_multi_scenes() -> None:
    """target=current_scene，传多场 → 合并成一个版本，new_scenes 长度 1，
    合并后 lines 顺序拼接，line_no 跨场连续。"""
    dal = FakeReadDAL(
        active_scene_id=1,
        scripts={1: None},  # 当前场无脚本 → 无重复
    )
    scenes = [
        _scene(lines=[("张三", "第一场A"), ("张三", "第一场B")]),
        _scene(lines=[("李四", "第二场A")]),
    ]
    plan = plan_import(scenes, target="current_scene", batch_id="b1", dal=dal)

    assert len(plan.conflicts) == 0
    assert len(plan.new_scenes) == 1
    merged = plan.new_scenes[0]
    assert merged["scene_id"] == 1
    # 合并后共 3 行
    assert len(merged["lines"]) == 3
    assert merged["lines"][0] == (None, "张三", "第一场A")
    assert merged["lines"][1] == (None, "张三", "第一场B")
    assert merged["lines"][2] == (None, "李四", "第二场A")


# ---------------------------------------------------------------------------
# P6  全空场跳过（清洗后无有效行）
# ---------------------------------------------------------------------------


def test_plan_skips_empty_scene() -> None:
    """清洗后无有效行的场整场跳过，不计入 new_scenes 也不计入 conflicts。"""
    dal = FakeReadDAL(
        scenes={},
    )
    scenes = [
        _scene(scene_code="3", lines=[("张三", "")]),   # 空 text → 整场空
        _scene(scene_code="4", lines=[("李四", "有效台词")]),
    ]
    plan = plan_import(scenes, target="multi_scene", batch_id="b1", dal=dal)

    # 场 "3" 被跳过，只有场 "4"
    assert len(plan.new_scenes) == 1
    assert plan.new_scenes[0]["scene_code"] == "4"
    assert len(plan.conflicts) == 0


# ---------------------------------------------------------------------------
# P7  无 active scene → NoActiveSceneError
# ---------------------------------------------------------------------------


def test_plan_no_active_scene_raises() -> None:
    """target=current_scene 但无 active scene → 抛 NoActiveSceneError。"""
    dal = FakeReadDAL(active_scene_id=None)
    scenes = [_scene(lines=[("张三", "台词")])]

    with pytest.raises(NoActiveSceneError):
        plan_import(scenes, target="current_scene", batch_id="b1", dal=dal)


# ---------------------------------------------------------------------------
# P8  conflicts 的 original 带 raw_text + lines
# ---------------------------------------------------------------------------


def test_plan_conflict_original_content() -> None:
    """conflict 的 original 包含 raw_text 和 lines（来自 get_latest_script + list_script_lines）。"""
    dal = FakeReadDAL(
        scenes={"7": 30},
        scripts={30: {"script_id": 77, "raw_text": "张三：旧台词\n李四：旧回复", "version": 2}},
        script_lines={77: [
            {"line_id": 1, "line_no": 1, "character": "张三", "text": "旧台词"},
            {"line_id": 2, "line_no": 2, "character": "李四", "text": "旧回复"},
        ]},
    )
    scenes = [_scene(scene_code="7", lines=[("张三", "新台词")])]
    plan = plan_import(scenes, target="multi_scene", batch_id="b1", dal=dal)

    conflict = plan.conflicts[0]
    original = conflict["original"]
    assert original["raw_text"] == "张三：旧台词\n李四：旧回复"
    assert len(original["lines"]) == 2
    assert original["lines"][0]["character"] == "张三"
    assert original["lines"][0]["text"] == "旧台词"

    # incoming 是清洗后的新内容
    incoming = conflict["incoming"]
    assert "张三" in incoming["raw_text"]
    assert len(incoming["lines"]) == 1


# ---------------------------------------------------------------------------
# P9  单场 current_scene 有脚本 → conflict
# ---------------------------------------------------------------------------


def test_plan_current_scene_with_script_is_conflict() -> None:
    """target=current_scene，当前场已有脚本 → conflict（original=当前场，incoming=合并内容）。"""
    dal = FakeReadDAL(
        active_scene_id=5,
        scripts={5: {"script_id": 55, "raw_text": "张三：旧版", "version": 1}},
        script_lines={55: [
            {"line_id": 1, "line_no": 1, "character": "张三", "text": "旧版"},
        ]},
    )
    scenes = [_scene(lines=[("张三", "新版内容")])]
    plan = plan_import(scenes, target="current_scene", batch_id="b1", dal=dal)

    assert len(plan.conflicts) == 1
    assert len(plan.new_scenes) == 0
    conflict = plan.conflicts[0]
    assert conflict["scene_id"] == 5
    assert conflict["original"]["raw_text"] == "张三：旧版"
    assert "新版内容" in conflict["incoming"]["raw_text"]


# ---------------------------------------------------------------------------
# A1  整批无重复 → decisions=None 直接全写
# ---------------------------------------------------------------------------


def test_apply_no_conflicts_writes_all() -> None:
    """整批无重复（plan.conflicts 空），decisions=None → 全写。"""
    dal = FakeReadDAL(scenes={})
    scenes = [
        _scene(scene_code="1", lines=[("张三", "台词A")]),
        _scene(scene_code="2", lines=[("李四", "台词B")]),
    ]
    plan = plan_import(scenes, target="multi_scene", batch_id="b1", dal=dal)
    assert len(plan.conflicts) == 0

    results = apply_import(plan, decisions=None, dal=dal)

    assert len(results) == 2
    assert len(dal.written_scripts) == 2


# ---------------------------------------------------------------------------
# A2  replace → 写新版本
# ---------------------------------------------------------------------------


def test_apply_replace_writes_new_version() -> None:
    """decisions 中 replace → 写该场新版本。"""
    dal = FakeReadDAL(
        scenes={"7": 30},
        scripts={30: {"script_id": 77, "raw_text": "旧版", "version": 1}},
        script_lines={77: [{"line_id": 1, "line_no": 1, "character": "张三", "text": "旧版"}]},
    )
    scenes = [_scene(scene_code="7", lines=[("张三", "新版")])]
    plan = plan_import(scenes, target="multi_scene", batch_id="b1", dal=dal)
    assert len(plan.conflicts) == 1

    decisions = {30: "replace"}
    results = apply_import(plan, decisions=decisions, dal=dal)

    assert len(results) == 1
    assert len(dal.written_scripts) == 1
    _, raw_text, _ = dal.written_scripts[0]
    assert "新版" in raw_text


# ---------------------------------------------------------------------------
# A3  skip → 不写
# ---------------------------------------------------------------------------


def test_apply_skip_does_not_write() -> None:
    """decisions 中 skip → 不写该场。"""
    dal = FakeReadDAL(
        scenes={"7": 30},
        scripts={30: {"script_id": 77, "raw_text": "旧版", "version": 1}},
        script_lines={77: [{"line_id": 1, "line_no": 1, "character": "张三", "text": "旧版"}]},
    )
    scenes = [_scene(scene_code="7", lines=[("张三", "新版")])]
    plan = plan_import(scenes, target="multi_scene", batch_id="b1", dal=dal)

    decisions = {30: "skip"}
    results = apply_import(plan, decisions=decisions, dal=dal)

    assert len(results) == 0
    assert len(dal.written_scripts) == 0


# ---------------------------------------------------------------------------
# A4/A5  真 DAL 单场：写、版本自增（plan + apply 联合）
# ---------------------------------------------------------------------------


def test_real_dal_single_scene_write(tmp_dal: DAL) -> None:
    """真 DAL，target=current_scene，无脚本 → plan 无冲突 → apply 写成功，版本=1。"""
    scene_id = tmp_dal.create_scene("SC_REAL")
    tmp_dal.set_active_scene(scene_id)

    scenes = [
        _scene(lines=[
            ("张三", "你好"),
            ("李四", ""),          # 空 text，应被过滤
            (None, "（停顿）"),
            ("", "空 character 归 None"),
        ])
    ]

    plan = plan_import(
        scenes,
        target="current_scene",
        batch_id="b1",
        dal=tmp_dal,
    )
    assert len(plan.conflicts) == 0
    assert len(plan.new_scenes) == 1

    results = apply_import(
        plan,
        decisions=None,
        dal=tmp_dal,  # type: ignore[arg-type]
    )
    assert len(results) == 1

    # 验证写库结果
    script = tmp_dal.get_latest_script(scene_id)
    assert script is not None
    assert script["version"] == 1

    expected_raw = "张三：你好\n（停顿）\n空 character 归 None"
    assert script["raw_text"] == expected_raw

    lines = tmp_dal.list_script_lines(script["script_id"])
    assert len(lines) == 3
    assert [ln["line_no"] for ln in lines] == [1, 2, 3]
    assert lines[0]["character"] == "张三"
    assert lines[1]["character"] is None
    assert lines[2]["character"] is None


def test_real_dal_single_scene_version_increments(tmp_dal: DAL) -> None:
    """真 DAL，第二次 plan+apply → 版本自增到 2。"""
    scene_id = tmp_dal.create_scene("SC_REAL2")
    tmp_dal.set_active_scene(scene_id)

    scenes1 = [_scene(lines=[("张三", "第一版")])]
    plan1 = plan_import(
        scenes1, target="current_scene", batch_id="b1", dal=tmp_dal
    )
    apply_import(plan1, decisions=None, dal=tmp_dal)  # type: ignore[arg-type]

    scenes2 = [_scene(lines=[("张三", "第二版")])]
    # 第二次：当前场已有脚本 → conflict
    plan2 = plan_import(
        scenes2, target="current_scene", batch_id="b2", dal=tmp_dal
    )
    assert len(plan2.conflicts) == 1

    # replace 决策
    conflict_scene_id = plan2.conflicts[0]["scene_id"]
    results = apply_import(
        plan2,
        decisions={conflict_scene_id: "replace"},
        dal=tmp_dal,  # type: ignore[arg-type]
    )
    assert len(results) == 1

    script = tmp_dal.get_latest_script(scene_id)
    assert script is not None
    assert script["version"] == 2
    assert "第二版" in script["raw_text"]


# ---------------------------------------------------------------------------
# R1  真 DAL plan_import：分类新场/命中有脚本/命中无脚本
# ---------------------------------------------------------------------------


def test_real_dal_plan_new_scene(tmp_dal: DAL) -> None:
    """真 DAL plan_import：scene_code 不在库 → 新场（无重复）。"""
    scenes = [_scene(scene_code="NEW_3", lines=[("张三", "你好")])]
    plan = plan_import(
        scenes, target="multi_scene", batch_id="b1", dal=tmp_dal
    )
    assert len(plan.conflicts) == 0
    assert len(plan.new_scenes) == 1
    assert plan.new_scenes[0]["scene_code"] == "NEW_3"


def test_real_dal_plan_existing_with_script_conflict(tmp_dal: DAL) -> None:
    """真 DAL plan_import：scene_code 在库且有脚本 → conflict。"""
    # 先建场并写一条脚本
    scene_id = tmp_dal.create_scene("EXIST_5")
    script_id = tmp_dal.insert_script(scene_id, "张三：老版本")
    tmp_dal.insert_script_line(script_id, 1, "张三", "老版本")

    scenes = [_scene(scene_code="EXIST_5", lines=[("张三", "新版本")])]
    plan = plan_import(
        scenes, target="multi_scene", batch_id="b1", dal=tmp_dal
    )
    assert len(plan.conflicts) == 1
    conflict = plan.conflicts[0]
    assert conflict["scene_id"] == scene_id
    assert conflict["scene_code"] == "EXIST_5"
    assert conflict["original"]["raw_text"] == "张三：老版本"
    assert conflict["original"]["lines"][0]["text"] == "老版本"


def test_real_dal_plan_existing_no_script_no_conflict(tmp_dal: DAL) -> None:
    """真 DAL plan_import：scene_code 在库但无脚本 → 无重复（首次导入）。"""
    scene_id = tmp_dal.create_scene("EXIST_NO_SCRIPT")
    # 不写脚本

    scenes = [_scene(scene_code="EXIST_NO_SCRIPT", lines=[("张三", "首次台词")])]
    plan = plan_import(
        scenes, target="multi_scene", batch_id="b1", dal=tmp_dal
    )
    assert len(plan.conflicts) == 0
    assert len(plan.new_scenes) == 1
    assert plan.new_scenes[0]["scene_id"] == scene_id


# ---------------------------------------------------------------------------
# R2  真 DAL：单场 current_scene 有脚本 → conflict，original 内容正确
# ---------------------------------------------------------------------------


def test_real_dal_plan_current_scene_conflict(tmp_dal: DAL) -> None:
    """真 DAL：current_scene 已有脚本 → conflict，original 内容来自库。"""
    scene_id = tmp_dal.create_scene("SC_CONFLICT")
    tmp_dal.set_active_scene(scene_id)
    script_id = tmp_dal.insert_script(scene_id, "张三：旧内容")
    tmp_dal.insert_script_line(script_id, 1, "张三", "旧内容")

    scenes = [_scene(lines=[("张三", "新内容")])]
    plan = plan_import(
        scenes, target="current_scene", batch_id="b1", dal=tmp_dal
    )
    assert len(plan.conflicts) == 1
    assert plan.conflicts[0]["original"]["raw_text"] == "张三：旧内容"
    assert plan.conflicts[0]["incoming"]["raw_text"] == "张三：新内容"


# ---------------------------------------------------------------------------
# H1（DeepSeek review）行清洗：纯空白 character 归一为 None
# ---------------------------------------------------------------------------


def test_clean_lines_blank_character_to_none() -> None:
    """H1：纯空白 character（LLM 抖动输出 '   '）归一为 None，不透传当角色名。"""
    scene = _scene(lines=[("   ", "舞台指示文本"), ("罗湘", "台词"), ("", "另一指示")])
    assert _clean_lines(scene) == [
        (None, "舞台指示文本"),
        ("罗湘", "台词"),
        (None, "另一指示"),
    ]


# ---------------------------------------------------------------------------
# R4  真 DAL apply multi_scene（rebase 2.x→main 后解锁，main 才有 get_or_create_scene）
# 价值在跨连接 read-after-write：DAL 读/写分连接（fixture 用文件不用 :memory:），
# 故断言一律经 DAL 读连接 read-back（list_scenes / get_latest_script），不信 apply 返回值。
# ---------------------------------------------------------------------------


def test_real_dal_apply_multi_scene_creates_new_scenes(tmp_dal: DAL) -> None:
    """真 DAL，multi_scene 多新场：apply 经 get_or_create_scene 建场，
    read-back 经 DAL 读连接确认 INSERT 已 commit 且对读连接可见。"""
    scenes = [
        _scene(scene_code="10", lines=[("张三", "十场台词")], int_ext="INT"),
        _scene(scene_code="11", lines=[("李四", "十一场台词")]),
    ]
    plan = plan_import(scenes, target="multi_scene", batch_id="b1", dal=tmp_dal)
    assert len(plan.conflicts) == 0
    assert len(plan.new_scenes) == 2

    results = apply_import(plan, decisions=None, dal=tmp_dal)  # type: ignore[arg-type]
    assert len(results) == 2

    # read-back：经 DAL 读连接（非 apply 返回值）确认建场已 commit 可见
    codes = {s["scene_code"] for s in tmp_dal.list_scenes()}
    assert {"10", "11"} <= codes

    for scene_id, _script_id in results:
        script = tmp_dal.get_latest_script(scene_id)
        assert script is not None
        assert script["version"] == 1
        assert len(tmp_dal.list_script_lines(script["script_id"])) == 1


def test_real_dal_apply_multi_scene_conflict_replace(tmp_dal: DAL) -> None:
    """真 DAL，multi_scene：命中有脚本场 conflict + replace → 版本自增；同批新场照建。"""
    existing_id = tmp_dal.create_scene("20")
    tmp_dal.insert_script(existing_id, "张三：旧版本")

    scenes = [
        _scene(scene_code="20", lines=[("张三", "新版本")]),   # conflict
        _scene(scene_code="21", lines=[("王五", "新场")]),      # new
    ]
    plan = plan_import(scenes, target="multi_scene", batch_id="b1", dal=tmp_dal)
    assert len(plan.conflicts) == 1
    assert len(plan.new_scenes) == 1

    conflict_id = plan.conflicts[0]["scene_id"]
    results = apply_import(
        plan, decisions={conflict_id: "replace"}, dal=tmp_dal  # type: ignore[arg-type]
    )
    assert len(results) == 2

    # conflict 场版本自增到 2，内容为新版本（read-back）
    script20 = tmp_dal.get_latest_script(existing_id)
    assert script20 is not None
    assert script20["version"] == 2
    assert "新版本" in script20["raw_text"]

    # 新场 21 建好，版本 1
    code_to_id = {s["scene_code"]: s["scene_id"] for s in tmp_dal.list_scenes()}
    assert "21" in code_to_id
    script21 = tmp_dal.get_latest_script(code_to_id["21"])
    assert script21 is not None
    assert script21["version"] == 1


def test_real_dal_apply_multi_scene_duplicate_code_within_batch(tmp_dal: DAL) -> None:
    """真 DAL，同批两个相同 scene_code（=3.B 跨块孤儿：一场被切成两 ParsedScene）。
    apply 调 get_or_create_scene 两次——第二次须 SELECT 命中写连接刚 INSERT 的行
    （跨连接 read-after-write）；若 DAL 双连接隔离，第二次会另建一场，此测试即报警。

    当前行为（§5.1 best-effort）：归并到同一场，产生两个 script 版本，
    get_latest_script 返回后者。multi_scene target 不像 current_scene 那样合并同 code，
    跨块孤儿前半段会被后半段顶成旧版本——合并留待 plan 层（见 memory 待办）。
    """
    scenes = [
        _scene(scene_code="30", lines=[("张三", "前半段")]),
        _scene(scene_code="30", lines=[("张三", "后半段")]),
    ]
    plan = plan_import(scenes, target="multi_scene", batch_id="b1", dal=tmp_dal)
    # plan 阶段不合并：库里无 "30"，scene_map 循环内不更新，两条都进 new_scenes
    assert len(plan.new_scenes) == 2

    results = apply_import(plan, decisions=None, dal=tmp_dal)  # type: ignore[arg-type]
    assert len(results) == 2

    # 跨连接 read-after-write：同一 scene_code 只建一个场
    matching = [s for s in tmp_dal.list_scenes() if s["scene_code"] == "30"]
    assert len(matching) == 1
    scene_id = matching[0]["scene_id"]
    assert results[0][0] == results[1][0] == scene_id

    # 两次 apply 落到同场 → 两个版本，latest=后半段
    script = tmp_dal.get_latest_script(scene_id)
    assert script is not None
    assert script["version"] == 2
    assert "后半段" in script["raw_text"]


# ---------------------------------------------------------------------------
# 更新全本（on_conflict="version"）：命中已有场追加新版本 / 同内容幂等
# ---------------------------------------------------------------------------


def test_import_single_scene_default_skips_on_conflict(tmp_dal: DAL) -> None:
    """默认 on_conflict='skip'：命中已有且已有脚本的场 → 返回 None，不刷版本（回归）。"""
    s = _scene("1", [("夏雨", "你来了。")])
    r1 = import_single_scene(s, target="multi_scene", synthetic_code="x", dal=tmp_dal)
    assert r1 is not None
    r2 = import_single_scene(s, target="multi_scene", synthetic_code="x", dal=tmp_dal)
    assert r2 is None  # 默认跳过
    assert tmp_dal.get_latest_script(r1["scene_id"])["version"] == 1


def test_import_single_scene_version_appends_on_change(tmp_dal: DAL) -> None:
    """on_conflict='version'：命中已有场且内容变了 → 同场追加新版本。"""
    r1 = import_single_scene(
        _scene("1", [("夏雨", "你来了。")]), target="multi_scene", synthetic_code="x", dal=tmp_dal
    )
    r2 = import_single_scene(
        _scene("1", [("夏雨", "你来晚了。")]),
        target="multi_scene", synthetic_code="x", dal=tmp_dal, on_conflict="version",
    )
    assert r2 is not None
    assert r2["scene_id"] == r1["scene_id"]  # 同场
    assert tmp_dal.get_latest_script(r1["scene_id"])["version"] == 2  # 追加新版本


def test_import_single_scene_version_idempotent_same_content(tmp_dal: DAL) -> None:
    """on_conflict='version' 但 raw_text 与最新版相同 → 幂等跳过，不刷版本。"""
    s = _scene("1", [("夏雨", "你来了。")])
    r1 = import_single_scene(s, target="multi_scene", synthetic_code="x", dal=tmp_dal)
    r2 = import_single_scene(
        s, target="multi_scene", synthetic_code="x", dal=tmp_dal, on_conflict="version"
    )
    assert r2 is None  # 内容无变化
    assert tmp_dal.get_latest_script(r1["scene_id"])["version"] == 1
