"""场记单 CSV 导出（feat/export）。

纯函数 + 行装配，FastAPI 路由（backend/api/routes/takes.py: GET /takes/export）调用。

设计要点：
  - FileName 列：port frontend-design 的 DEFAULT_FILENAME_FORMAT 默认约定（01_S1_T001）。
    后端只生成默认板式名；用户可配格式是尚未合并到 main 的纯前端 localStorage 偏好，
    不在此重复实现，避免两份 formatFileName 漂移。等其合并后由前端把格式参数传进来即可。
  - Lines 列：本 take 的 ch1 transcript 段文本（对白）拼接，ch2 备注不计入。
  - CSV：走标准库 csv 模块（正确转义逗号/引号/换行），utf-8-sig 落 BOM（Excel 中文不乱码），
    首行是非表格的「导出日期」行（有意，满足「文件最顶部加导出日期」），第二行才是表头。
"""
from __future__ import annotations

import codecs
import csv
import io
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.db.dal import DAL

# 表头固定（顺序即列序）。第二行写它，第一行留给导出日期。
CSV_HEADER = ["Scene", "Shot", "Take", "FileName", "Note", "Lines", "Mark"]

# status → Mark 列显示（对齐前端 STATUS_LABEL：大写英文）。
_MARK_LABELS = {"pass": "PASS", "ng": "NG", "keep": "KEEP", "tbd": "TBD"}

# Excel/Sheets 公式触发字符：以这些开头的单元格会被当公式执行（CSV 注入），导出前需中和。
_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class SegFormat:
    """单段命名格式：前缀 + 补零位数（对齐前端 filename-format.ts SegFormat）。pad=0 不补零。"""

    prefix: str
    pad: int


@dataclass(frozen=True)
class FileNameFormat:
    """板式文件名格式（对齐前端 FileNameFormat）。导出 FileName 列按此渲染，与 UI 显示一致。"""

    scene: SegFormat
    shot: SegFormat
    take: SegFormat
    sep: str


# 默认格式（01_S1_T001），与前端 DEFAULT_FILENAME_FORMAT 同值。
# 导出端点不传格式参数时用它，行为与「未接入用户格式」前一致。
DEFAULT_FILENAME_FORMAT = FileNameFormat(
    scene=SegFormat("", 2),
    shot=SegFormat("S", 0),
    take=SegFormat("T", 3),
    sep="_",
)


@dataclass
class ExportRow:
    """CSV 一条数据行（与 CSV_HEADER 一一对应）。"""

    scene: str
    shot: str
    take: str
    file_name: str
    note: str
    lines: str
    mark: str


def _digits_of(code: str) -> str:
    """从 scene_code（'Scene_1' / '3A' / '1'）抠首段数字；抠不到则原样返回（对齐前端 digitsOf）。"""
    m = re.search(r"\d+", code)
    return m.group(0) if m else code


def _pad(value: str, width: int) -> str:
    """左补零到 width 位（width=0 不补，对齐前端 padNum/padStart）。"""
    return value.zfill(width) if width > 0 else value


def take_filename(
    scene_code: str | None,
    shot: str | None,
    take_number: int | None,
    fmt: FileNameFormat = DEFAULT_FILENAME_FORMAT,
) -> str:
    """按 fmt 板式约定生成文件名。缺失段跳过，不留空分隔。

    与前端 formatFileName 同算法（逐段 prefix + padNum，scene 抠数字，sep 连接）：
    take 只用 take_number（不带冲突后缀），后缀只进 Take 列。
    """
    segs: list[str] = []
    if scene_code:
        segs.append(fmt.scene.prefix + _pad(_digits_of(scene_code), fmt.scene.pad))
    if shot:
        segs.append(fmt.shot.prefix + _pad(shot, fmt.shot.pad))
    if take_number is not None:
        segs.append(fmt.take.prefix + _pad(str(take_number), fmt.take.pad))
    return fmt.sep.join(segs)


def default_take_filename(scene_code: str | None, shot: str | None, take_number: int | None) -> str:
    """默认板式（01_S1_T001）文件名 —— take_filename(默认格式) 的薄封装。"""
    return take_filename(scene_code, shot, take_number, DEFAULT_FILENAME_FORMAT)


def _take_label(take_number: int, take_suffix: str) -> str:
    """Take 列显示：编号拼冲突后缀（对齐前端 formatTakeLabel，suffix='' → '3'，'+' → '3+'）。"""
    return f"{take_number}{take_suffix or ''}"


def build_export_rows(
    dal: DAL,
    fmt: FileNameFormat = DEFAULT_FILENAME_FORMAT,
    ts_from: float | None = None,
    ts_to: float | None = None,
) -> list[ExportRow]:
    """从 DAL 装配导出行（一趟 join takes+scenes + 一趟 ch1 段，不 N+1）。

    排序：scene_code → shot → take_number → take_suffix。软删行已被 list_takes 排除。
    fmt 控制 FileName 列板式（默认 DEFAULT_FILENAME_FORMAT，与 UI 显示一致）。
    ts_from/ts_to 给定时按 take 开录时间 start_ts 过滤，半开区间 [ts_from, ts_to)
    （用于「导出今天」；省略即全部）。
    """
    scene_codes = {s["scene_id"]: s["scene_code"] for s in dal.list_scenes()}
    lines_by_take = dal.list_ch1_texts_by_take()

    rows: list[ExportRow] = []
    for t in dal.list_takes(None):
        if ts_from is not None and t.start_ts < ts_from:
            continue
        if ts_to is not None and t.start_ts >= ts_to:
            continue
        scene_code = scene_codes.get(t.scene_id, f"#{t.scene_id}")
        rows.append(
            ExportRow(
                scene=scene_code,
                shot=t.shot,
                take=_take_label(t.take_number, t.take_suffix),
                file_name=take_filename(scene_code, t.shot, t.take_number, fmt),
                note=t.notes or "",
                # Lines：本 take 的 ch1 段（对白）按 start_frame 升序拼接；ch2 备注不计入。
                lines="\n".join(lines_by_take.get(t.take_id, [])),
                mark=_MARK_LABELS.get(t.status, t.status.upper()),
            )
        )
    rows.sort(
        key=lambda r: (_natural_sort_key(r.scene), _natural_sort_key(r.shot), _take_sort_key(r.take))
    )
    return rows


def _take_sort_key(take_label: str) -> tuple[int, str]:
    """把 Take 列（'3' / '3+'）拆成 (数字, 后缀) 排序键，让 3 排在 3+ 前、10 排在 9 后。"""
    m = re.match(r"(\d+)(.*)", take_label)
    if m:
        return int(m.group(1)), m.group(2)
    return 0, take_label


def _natural_sort_key(value: str) -> tuple[int, int, str]:
    """数字感知排序键：抠首个数字段按数值排，无数字编号排其后按字典序。

    让 Scene_2 排在 Scene_10 前、shot '2' 排在 '10' 前（裸字符串排序会反，因 '10' < '2'）。
    纯字母/无数字编号落到第二组，组内稳定字典序。
    """
    m = re.search(r"\d+", value)
    if m:
        return (0, int(m.group(0)), value)
    return (1, 0, value)


def _sanitize_cell(value: str) -> str:
    """中和 CSV 公式注入：以公式触发字符开头的格前缀单引号（OWASP 标准缓解）。

    note/lines 是用户自由文本，Excel 是导出明确目标（带 BOM）。以 = + - @ 开头的内容会被
    Excel/Sheets 当公式执行（=HYPERLINK / DDE 命令）。前缀 ' 让 Excel 视为纯文本。
    """
    if value and value.startswith(_CSV_INJECTION_PREFIXES):
        return "'" + value
    return value


def rows_to_csv(rows: list[ExportRow], export_date: str) -> bytes:
    """把导出行序列化为 CSV 字节（utf-8-sig BOM；首行导出日期，次行表头）。

    首行是单格非表格行「导出日期：YYYY-MM-DD」（有意，满足「文件最顶部加导出日期」），
    第二行才是固定表头。走 csv 模块，逗号/引号/换行自动转义；utf-8-sig 落 BOM 让 Excel
    正确识别中文。
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([f"导出日期：{export_date}"])
    writer.writerow(CSV_HEADER)
    for r in rows:
        # 用户自由文本（note/lines）防 CSV 公式注入；系统生成列一并过，便宜且无副作用。
        writer.writerow(
            [
                _sanitize_cell(c)
                for c in (r.scene, r.shot, r.take, r.file_name, r.note, r.lines, r.mark)
            ]
        )
    return codecs.BOM_UTF8 + buf.getvalue().encode("utf-8")
