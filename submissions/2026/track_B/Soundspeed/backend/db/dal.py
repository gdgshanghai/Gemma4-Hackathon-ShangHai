"""数据访问层（DAL）。

所有数据库读写通过此类进行，不允许外部拼接 SQL。
构造时传入数据库文件路径，自动调用 apply_migrations 确保 schema 最新。
写操作使用 BEGIN IMMEDIATE 显式事务，避免 WAL 模式下隐式事务竞争。
JSON 字段在 DAL 内部透明处理：写入时 json.dumps，读取时 json.loads。
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.db.lifecycle import _configure_connection
from backend.db.migrations.runner import apply_migrations

# SQLite 3.39.4 不支持 unixepoch('now', 'subsec')，用 strftime 兼容写法
_NOW_TS_SQL = "CAST(strftime('%s', 'now') AS REAL)"

# vacate / restore / update_take_meta 里 '+' 后缀循环的最大迭代次数守卫（DeepSeek #3）
# 测试可 monkeypatch 成低值以验证超限异常
_MAX_SUFFIX_ITER = 1000

# _resolve_base_slot 的 exclude_take_id 哨兵：新 take 尚未 INSERT、无既有 take_id 可排除时传它。
# 任何真实 take_id ≥ 1（AUTOINCREMENT），故 -1 不会误排除任何行。
_NO_EXCLUDE_TAKE_ID = -1

# QP 场次编号归一：剥 Scene/场/Sc/S 前缀 + 分隔符，保留数字+后缀，统一大写。
# (?=\d) 前瞻：前缀只在其后（跨可选分隔符）紧跟数字时才剥，避免误剥 `sce3` 这类。
_SCENE_PREFIX_RE = re.compile(r"^(?:scene|场|sc|s)[\s_\-]*(?=\d)", re.IGNORECASE)
# 中文口语「第N场」归一：第一场/第1场/第72场/第十一场 → 阿拉伯数字。
_CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
_SCENE_ORDINAL_RE = re.compile(r"^第\s*([0-9一二三四五六七八九十]+)\s*场")


def _cn_numeral_to_arabic(s: str) -> str | None:
    """中文数字 1-99 → 阿拉伯字符串；纯阿拉伯原样返回；无法解析返回 None。

    覆盖电影场次常见区间：一→1，十→10，十一→11，二十→20，二十一→21，九十九→99。
    超 99（百/千）或含未知字符返回 None。
    """
    if s.isdigit():
        return s
    if "十" not in s:
        return str(_CN_DIGITS[s]) if s in _CN_DIGITS else None
    tens_part, _, ones_part = s.partition("十")
    if (tens_part and tens_part not in _CN_DIGITS) or (ones_part and ones_part not in _CN_DIGITS):
        return None
    tens = _CN_DIGITS.get(tens_part, 1) if tens_part else 1  # 「十X」→ 十位=1
    ones = _CN_DIGITS.get(ones_part, 0) if ones_part else 0  # 「X十」→ 个位=0
    return str(tens * 10 + ones)

# 万能笔 authorizer：只放行 SELECT 系动作，其余 DENY（挡 ATTACH/写/非 data_version PRAGMA）。
# FTS 影子表（_config/_idx/_data/_docsize）按设计可读：MATCH 内部需要 _config/_idx，
# 且影子表漏不出 script_lines 之外的剧本内容——模型本就能直接读 script_lines 拿全部台词。
# 真正边界：action 级（PRAGMA scoped + FUNCTION 整体放行除 load_extension）+ mode=ro +
#   单句守卫 + 行数封顶 + 超时。
# FUNCTION 放行范围：bm25/coalesce 等 FTS/标量函数均需放行，但 load_extension 在
#   authorizer 层独立 DENY（RCE 向量，纵深防御，不依赖 enable_load_extension 未调用）。
# Accepted risk：SELECT zeroblob/randomblob 大分配内存 DoS——单用户 demo、模型上下文受限、
#   风险有界，本期不堵。
_QP_ALLOWED_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_RECURSIVE,
    }
)


def normalize_scene_code(raw: str) -> str:
    """归一场次编号用于读侧匹配（spec §7.2）。

    trim → 中文口语「第N场」归一 → 剥前缀（Scene/场/Sc/S + 分隔符）→ 大写。
    例：'Scene_3A'→'3A'，'第一场'→'1'，'第72场'→'72'，'s72'→'72'，'场3'→'3'，'3'→'3'，''→''。
    读、写两侧都过一遍再精确比对，覆盖「同号不同前缀」的常见变体；
    剥不掉前缀的原样大写返回（不破坏纯中文/特殊编号）。
    前缀只在其后（跨可选分隔符）紧跟数字时才剥，避免误剥 `sce3` 这类。
    中文口语「第一场」「第72场」「第十一场」是 4B 真模型实测高频传法（e2e Task 11 发现）——
    normalize 在此收编，避免模型用口语场次号查不到而瞎答。中文数字仅支持 1-99（超 99 如
    「第百场」无法解析、落回前缀剥离/原样）。已知限制：「第3场A」会匹配到「场」即止、返回「3」、
    **截掉字母后缀 A**（与 Scene_3A→3A 不匹配）；带后缀场次建议用 Scene_3A 这类正式写法。
    """
    s = str(raw).strip()
    if not s:
        return ""
    m = _SCENE_ORDINAL_RE.match(s)
    if m:  # 「第一场」/「第1场」/「第72场」/「第十一场」→ 纯数字
        arabic = _cn_numeral_to_arabic(m.group(1))
        if arabic is not None:
            return arabic
        # 无法解析（如超 99）→ 落回下面前缀剥离/原样
    s = _SCENE_PREFIX_RE.sub("", s)
    return s.strip().upper()


# ── 数据类（read 方法的返回类型）────────────────────────────────────────────


@dataclass
class Take:
    take_id: int
    scene_id: int
    shot: str  # 镜次编号；'' 表示无镜（v4 NOT NULL DEFAULT ''）
    take_number: int
    take_suffix: str  # 冲突后缀，默认 ''，冲突时 '+' / '++' …（v3）
    start_ts: float
    end_ts: float | None
    status: str  # 'pass' | 'ng' | 'keep' | 'tbd'
    performer_issues: dict | list | None  # NP 解析输出，DAL 负责 json.loads；写入时也传 dict/list
    audio_quality: str | None
    script_diff: dict | None  # L2 输出，DAL 负责 json.loads；写入时也传 dict
    notes: str | None
    deleted_at: float | None  # 软删时间戳，NULL 表示未删除（v3）
    created_at: float
    updated_at: float
    # diarization 回填后的结构化转录（ASR + speaker 整合，v4），DAL 负责 json.loads
    structured_transcript: dict | None = None


@dataclass
class TranscriptSegment:
    segment_id: int
    take_id: int
    ch: int  # 1 或 2
    speaker: str | None
    text: str
    start_frame: int  # 毫秒（秒 × 1000 取整），字段名沿用历史命名
    end_frame: int    # 毫秒（秒 × 1000 取整），字段名沿用历史命名
    created_at: float


@dataclass
class ScriptLine:
    line_id: int
    script_id: int
    line_no: int
    character: str | None
    text: str
    created_at: float


@dataclass
class TakeEvent:
    event_id: int
    take_id: int
    event_type: str
    ts: float
    payload: dict[str, Any]
    created_at: float


# ── 自定义异常 ────────────────────────────────────────────────────────────────


class TakeNumberConflictError(Exception):
    """跨场移动时目标 (scene_id, take_number) 已被占用，无法自动解决冲突。

    上层路由应将此异常映射为 HTTP 409。
    """


# ── 内部辅助 ──────────────────────────────────────────────────────────────────


def _next_take_number(conn: sqlite3.Connection, scene_id: int, shot: str) -> int:
    """(scene_id, shot) 组内下一个可用 take_number（live MAX+1，软删号可复用）。

    事务内调用版本，直接用传入的 conn，不开新事务。
    空组返回 1。
    """
    row = conn.execute(
        "SELECT COALESCE(MAX(take_number), 0) + 1 AS next_num "
        "FROM takes WHERE scene_id = ? AND shot = ? AND deleted_at IS NULL;",
        (scene_id, shot),
    ).fetchone()
    return int(row["next_num"])


def _alloc_free_suffix(
    conn: sqlite3.Connection,
    scene_id: int,
    shot: str,
    take_number: int,
    exclude_take_id: int,
    start: str = "+",
) -> str:
    """在 (scene_id, shot, take_number) 下找一个空闲 take_suffix，从 start 开始顺位追加 '+'。

    取占用集合（软删 + live 均算占用），排除 exclude_take_id 自身。
    找到第一个不在占用集合中的 suffix 即返回。
    超 _MAX_SUFFIX_ITER 次迭代抛 RuntimeError（含「后缀循环超过 N 次」子串）。
    """
    taken_rows = conn.execute(
        "SELECT take_suffix FROM takes "
        "WHERE scene_id = ? AND shot = ? AND take_number = ? AND take_id != ?;",
        (scene_id, shot, take_number, exclude_take_id),
    ).fetchall()
    taken_suffixes = {r["take_suffix"] for r in taken_rows}

    new_suffix = start
    _iter = 0
    while new_suffix in taken_suffixes:
        _iter += 1
        if _iter >= _MAX_SUFFIX_ITER:
            raise RuntimeError(
                f"后缀循环超过 {_MAX_SUFFIX_ITER} 次，"
                f"scene_id={scene_id} shot={shot!r} take_number={take_number}"
            )
        new_suffix = new_suffix + "+"
    return new_suffix


def _row_to_take(row: sqlite3.Row) -> Take:
    performer_issues = row["performer_issues"]
    script_diff = row["script_diff"]
    keys = row.keys()
    structured = row["structured_transcript"] if "structured_transcript" in keys else None
    return Take(
        take_id=row["take_id"],
        scene_id=row["scene_id"],
        take_number=row["take_number"],
        take_suffix=row["take_suffix"],
        shot=row["shot"],
        start_ts=row["start_ts"],
        end_ts=row["end_ts"],
        status=row["status"],
        performer_issues=json.loads(performer_issues) if performer_issues else None,
        audio_quality=row["audio_quality"],
        script_diff=json.loads(script_diff) if script_diff else None,
        notes=row["notes"],
        deleted_at=row["deleted_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        structured_transcript=json.loads(structured) if structured else None,
    )


def _row_to_segment(row: sqlite3.Row) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=row["segment_id"],
        take_id=row["take_id"],
        ch=row["ch"],
        speaker=row["speaker"],
        text=row["text"],
        start_frame=row["start_frame"],
        end_frame=row["end_frame"],
        created_at=row["created_at"],
    )


def _row_to_event(row: sqlite3.Row) -> TakeEvent:
    return TakeEvent(
        event_id=row["event_id"],
        take_id=row["take_id"],
        event_type=row["event_type"],
        ts=row["ts"],
        payload=json.loads(row["payload"]),
        created_at=row["created_at"],
    )


def _row_to_script_line(row: sqlite3.Row) -> ScriptLine:
    return ScriptLine(
        line_id=row["line_id"],
        script_id=row["script_id"],
        line_no=row["line_no"],
        character=row["character"],
        text=row["text"],
        created_at=row["created_at"],
    )


# ── DAL 类 ──────────────────────────────────────────────────────────────────


class DAL:
    """
    数据访问层。所有数据库读写必须通过此类，不允许外部拼接 SQL。
    构造时传入数据库文件路径，自动应用迁移（调用 apply_migrations）。
    """

    def __init__(self, db_path: Path) -> None:
        """
        初始化 DAL，自动调用 apply_migrations 确保 schema 最新。
        每次 sqlite3.connect() 后必须立即执行以下 per-connection PRAGMA，
        否则外键约束不生效、WAL busy_timeout 不起效：
            PRAGMA foreign_keys = ON;
            PRAGMA journal_mode = WAL;
            PRAGMA busy_timeout = 5000;
        """
        apply_migrations(db_path)
        self._db_path = db_path  # QP 只读连接用（_readonly_conn），不复用共享 self._conn
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        _configure_connection(self._conn)

    # ── 内部事务 helper ───────────────────────────────────────────────────────

    @contextmanager
    def _write_tx(self) -> Iterator[sqlite3.Connection]:
        """写事务 context manager：BEGIN IMMEDIATE 显式加锁，避免 WAL 下隐式事务竞争。"""
        with self._conn:
            self._conn.execute("BEGIN IMMEDIATE;")
            yield self._conn

    # ── QP 只读路径（D-QP-12：临时 mode=ro 连接，不碰共享 self._conn）─────────────

    @contextmanager
    def _readonly_conn(self) -> Iterator[sqlite3.Connection]:
        """每次开一个临时 mode=ro 连接，用完 finally close。

        executor 在事件循环外（to_thread worker）跑，复用共享 self._conn 是跨线程
        并发隐患（D-QP-12）。所有 QP 读（场次目录/策展工具/万能笔）一律走本 helper。
        """
        conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        # 只设 busy_timeout。故意不调 _configure_connection / 不设 PRAGMA journal_mode=WAL——
        # 在 mode=ro 连接上执行 WAL 切换会抛 OperationalError: attempt to write a readonly
        # database（WAL 要写 -wal/-shm）。ro 连接读已落盘 WAL 内容无需切 journal_mode。
        conn.execute("PRAGMA busy_timeout = 5000;")
        try:
            yield conn
        finally:
            conn.close()

    def list_scenes_readonly(self) -> list[dict]:
        """QP 场次目录用：按创建序返回全部场次（只读连接）。

        只返 QP 场次目录所需最小列集合（scene_id/scene_code/location/int_ext/
        time_of_day/shoot_date），不是 list_scenes 的全列只读版。
        """
        with self._readonly_conn() as conn:
            rows = conn.execute(
                "SELECT scene_id, scene_code, location, int_ext, time_of_day, shoot_date "
                "FROM scenes ORDER BY created_at, scene_id;"
            ).fetchall()
        return [dict(r) for r in rows]

    def resolve_scene_id(self, scene_ref: str) -> int | None:
        """口语/变体场次引用 → 真实 scene_id：两侧 normalize 后精确匹配。

        找不到返回 None（调用方据此老实说没有，禁止模糊替换，spec §7.3）。
        数字不同 = 不同场，不跨号匹配（spec §7.5）。
        """
        target = normalize_scene_code(scene_ref)
        if not target:
            return None
        # 全表扫：场次量级 O(10¹)，不加 index 可接受，别误当遗漏优化去改。
        for s in self.list_scenes_readonly():
            if normalize_scene_code(s["scene_code"]) == target:
                return int(s["scene_id"])
        return None

    def count_takes(self, scene_id: int, status: str | None = None) -> int:
        """统计某场次的有效 take 数（软删过滤；可选 status 过滤）。

        scene 不存在或无 take 时返回 0（缺场由 executor 的 resolve_scene_id 先把关，Task 5）。
        """
        sql = "SELECT COUNT(*) AS n FROM takes WHERE scene_id = ? AND deleted_at IS NULL"
        params: tuple = (scene_id,)
        if status is not None:
            sql += " AND status = ?"
            params = (scene_id, status)
        with self._readonly_conn() as conn:
            row = conn.execute(sql + ";", params).fetchone()
        return int(row["n"])

    def get_scene_info(self, scene_id: int) -> dict | None:
        """返回场次信息 + 最新剧本的角色数。无此场次返回 None。"""
        with self._readonly_conn() as conn:
            row = conn.execute(
                "SELECT scene_id, scene_code, location, int_ext, time_of_day, shoot_date "
                "FROM scenes WHERE scene_id = ?;",
                (scene_id,),
            ).fetchone()
            if row is None:
                return None
            char_row = conn.execute(
                "SELECT COUNT(DISTINCT sl.character) AS n "
                "FROM script_lines sl "
                "WHERE sl.script_id = ("
                "  SELECT script_id FROM scripts WHERE scene_id = ? ORDER BY version DESC LIMIT 1"
                ") AND sl.character IS NOT NULL;",
                (scene_id,),
            ).fetchone()
        info = dict(row)
        info["character_count"] = int(char_row["n"])
        return info

    def list_characters(self, scene_id: int) -> list[str]:
        """返回场次最新版剧本里去重后的角色清单（舞台指示 character=NULL 不计）。

        scene 不存在或无剧本时返回 []（缺场由 executor 的 resolve_scene_id 先把关，Task 5）。
        多版本剧本时只取最新版（ORDER BY version DESC LIMIT 1），不 union 历史版本。
        """
        with self._readonly_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT sl.character AS c "
                "FROM script_lines sl "
                "WHERE sl.script_id = ("
                "  SELECT script_id FROM scripts WHERE scene_id = ? ORDER BY version DESC LIMIT 1"
                ") AND sl.character IS NOT NULL "
                "ORDER BY sl.character;",
                (scene_id,),
            ).fetchall()
        return [r["c"] for r in rows]

    def list_all_characters(self) -> list[str]:
        """返回整部戏（全场次最新版剧本）去重后的角色清单，按角色名排序。

        供声纹注册弹窗的"选角色"下拉用：演员一个角色横跨多场，故取全场次并集，
        而非单场（list_characters 是单场版）。每场只算最新版剧本（version 最大），
        不 union 历史版本。无任何剧本时返回 []。
        """
        with self._readonly_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT sl.character AS c "
                "FROM script_lines sl "
                "WHERE sl.script_id IN ("
                "  SELECT s1.script_id FROM scripts s1 "
                "  WHERE s1.version = ("
                "    SELECT MAX(s2.version) FROM scripts s2 WHERE s2.scene_id = s1.scene_id"
                "  )"
                ") AND sl.character IS NOT NULL "
                "ORDER BY sl.character;"
            ).fetchall()
        return [r["c"] for r in rows]

    def search_script_lines(self, query: str, scene_id: int | None = None) -> list[dict]:
        """FTS5 MATCH 检索台词（BM25 排序，只读连接）。返回 line_no/character/text dict 列表。"""
        base = (
            "SELECT sl.line_no AS line_no, sl.character AS character, sl.text AS text "
            "FROM script_lines_fts fts "
            "JOIN script_lines sl ON sl.line_id = fts.rowid "
        )
        with self._readonly_conn() as conn:
            if scene_id is not None:
                rows = conn.execute(
                    base
                    + "JOIN scripts s ON s.script_id = sl.script_id "
                    "WHERE fts.text MATCH ? AND s.scene_id = ? "
                    "ORDER BY bm25(script_lines_fts);",
                    (query, scene_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    base + "WHERE fts.text MATCH ? ORDER BY bm25(script_lines_fts);",
                    (query,),
                ).fetchall()
        return [dict(r) for r in rows]

    def query_readonly(
        self,
        sql: str,
        params: tuple = (),
        *,
        max_rows: int = 300,
        timeout_s: float = 3.0,
    ) -> dict:
        """万能笔：执行模型现写的只读 SQL（spec §6 安全墙）。

        安全边界（action 级，无表名 deny）：
        - PRAGMA 分支最先：只放行 FTS MATCH 内部所需的 data_version，其余 PRAGMA 一律 DENY。
        - FUNCTION 分支次之：整体放行（bm25 等 FTS/标量函数需要），但独立堵死 load_extension
          （RCE 向量；即便当前 _readonly_conn 未 enable_load_extension，也在 authorizer 层
          独立防御，防未来连接配置变动打开缺口）。
        - _QP_ALLOWED_ACTIONS（SELECT/READ/FUNCTION/RECURSIVE）放行其余，其余 DENY。
          这挡住了 ATTACH（SQLITE_ATTACH）、写（INSERT/UPDATE/DELETE）、临时表（CREATE）等。
        - FTS 影子表（_config/_idx/_data/_docsize）按设计可读：MATCH 内部需要 _config/_idx，
          且影子表漏不出 script_lines 之外信息（模型本就能直接读 script_lines）。
        - 额外防线：mode=ro 连接挡物理写；单句守卫（sqlite3.Warning）；行数封顶；超时 abort。
        - Accepted risk：SELECT zeroblob/randomblob 大分配内存 DoS——单用户 demo、上下文受限，
          本期不堵。
        错误不抛穿：包成 {"error": ...} 让循环下一跳自纠。
        成功返回 {"columns": [...], "rows": [...], "row_count": n, "truncated": bool}。
        """
        import time

        def _authorizer(
            action: int, arg1: object, arg2: object, db_name: object, trigger: object
        ) -> int:
            # PRAGMA 分支必须在 allowed-actions 检查之前（SQLITE_PRAGMA 不在 allowed 集合）。
            # 只放行 data_version（FTS MATCH 内部用来检测 DB 并发修改），其余 PRAGMA 全部 DENY。
            if action == sqlite3.SQLITE_PRAGMA:
                return sqlite3.SQLITE_OK if arg1 == "data_version" else sqlite3.SQLITE_DENY
            # FUNCTION 整体放行（bm25 等 FTS/标量函数需要），但独立堵死 load_extension——
            # 它是 RCE 向量；即便当前 _readonly_conn 未 enable_load_extension，也在
            # authorizer 层堵死，防未来连接配置变动打开缺口（纵深防御）。
            if action == sqlite3.SQLITE_FUNCTION:
                return sqlite3.SQLITE_DENY if arg2 == "load_extension" else sqlite3.SQLITE_OK
            if action in _QP_ALLOWED_ACTIONS:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        with self._readonly_conn() as conn:
            deadline = time.monotonic() + timeout_s
            conn.set_authorizer(_authorizer)
            conn.set_progress_handler(
                lambda: 1 if time.monotonic() > deadline else 0, 1000
            )
            try:
                cur = conn.execute(sql, params)
                fetched = cur.fetchmany(max_rows + 1)
                truncated = len(fetched) > max_rows
                fetched = fetched[:max_rows]
                columns = [d[0] for d in cur.description] if cur.description else []
                return {
                    "columns": columns,
                    "rows": [dict(r) for r in fetched],
                    "row_count": len(fetched),
                    "truncated": truncated,
                }
            except sqlite3.Warning as exc:
                return {"error": f"只能执行单条 SQL 语句：{exc}"}
            except sqlite3.OperationalError as exc:
                return {"error": f"查询失败或超时：{exc}"}
            except sqlite3.DatabaseError as exc:
                return {"error": f"数据库拒绝该查询（仅允许只读 SELECT）：{exc}"}
            finally:
                conn.set_authorizer(None)
                conn.set_progress_handler(None, 1000)

    # ── 资源管理 ──────────────────────────────────────────────────────────────

    def close(self) -> None:
        """关闭底层 sqlite 连接。"""
        self._conn.close()

    def __enter__(self) -> "DAL":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    # ── scenes ──────────────────────────────────────────────────────────────

    def create_scene(
        self,
        scene_code: str,
        description: str | None = None,
        shoot_date: str | None = None,
    ) -> int:
        """创建场次，返回 scene_id。"""
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO scenes (scene_code, description, shoot_date) VALUES (?, ?, ?);",
                (scene_code, description, shoot_date),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def set_active_scene(self, scene_id: int) -> None:
        """将指定 scene_id 设为活跃场次，清除其他场次的 is_active。"""
        with self._write_tx() as conn:
            conn.execute("UPDATE scenes SET is_active = 0;")
            conn.execute(
                "UPDATE scenes SET is_active = 1 WHERE scene_id = ?;", (scene_id,)
            )

    def get_active_scene_id(self) -> int | None:
        """返回当前活跃场次 ID，无则返回 None。"""
        row = self._conn.execute(
            "SELECT scene_id FROM scenes WHERE is_active = 1 LIMIT 1;"
        ).fetchone()
        return row["scene_id"] if row else None

    def list_scenes(self) -> list[dict]:
        """返回所有场次的基本信息列表（含 slugline 三列 + has_script）。

        has_script（0/1）：该场是否已有剧本版本（EXISTS 子查询，O(1) per row）。
        前端剧本面板据此跳过无剧本的空场（如 dev 种子的 Scene_1），不展示空占位。
        """
        rows = self._conn.execute(
            "SELECT s.scene_id, s.scene_code, s.description, s.shoot_date, s.is_active, "
            "s.created_at, s.int_ext, s.time_of_day, s.location, "
            "EXISTS(SELECT 1 FROM scripts sc WHERE sc.scene_id = s.scene_id) AS has_script "
            "FROM scenes s ORDER BY s.scene_id ASC;"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_scene_heading(
        self,
        scene_id: int,
        *,
        int_ext: str | None = None,
        time_of_day: str | None = None,
        location: str | None = None,
    ) -> None:
        """部分更新场次 slugline 字段。

        只写非 None 且非空白的字段（COALESCE 保留原值），避免把未传字段清空。
        None 或空白字符串（包括空串 "" 和纯空白 "   "）均视为「不更新该字段，保留原值」。
        三者全为 None 或空白时等同 no-op。
        """
        def _normalize(v: str | None) -> str | None:
            """空串/纯空白归一为 None，以便 COALESCE 保留原值。"""
            if v is None:
                return None
            return v if v.strip() else None

        with self._write_tx() as conn:
            conn.execute(
                "UPDATE scenes SET "
                "int_ext     = COALESCE(?, int_ext), "
                "time_of_day = COALESCE(?, time_of_day), "
                "location    = COALESCE(?, location) "
                "WHERE scene_id = ?;",
                (_normalize(int_ext), _normalize(time_of_day), _normalize(location), scene_id),
            )

    # ── takes ────────────────────────────────────────────────────────────────

    def _vacate_base_slot(
        self,
        conn: sqlite3.Connection,
        scene_id: int,
        shot: str,
        take_number: int,
    ) -> None:
        """若 (scene_id, shot, take_number, '') 被一条软删行占着，把该软删行的 suffix 顺位追加 '+'。

        规则：
          - 只处理软删行（deleted_at IS NOT NULL）占着 suffix='' 的情形。
          - 若 '' 未被软删行占（空闲或被 live 行占），no-op。
          - 找到后：在该 scene+shot+number 下循环找一个既不撞软删也不撞 live 的空 suffix，
            UPDATE 软删行的 take_suffix，让出 ''。

        注意：「vacate 软删占用者让位加 '+' 到 live」与「给被编辑 take 加后缀」是两路不对称逻辑：
        前者只动软删行；后者只动 live 的被编辑行，永不挪已有 live 占用者（DeepSeek #4 注）。

        调用时必须在写事务内（BEGIN IMMEDIATE 已持有），直接用传入 conn 操作，不开新事务。
        """
        occupant = conn.execute(
            "SELECT take_id, take_suffix FROM takes "
            "WHERE scene_id = ? AND shot = ? AND take_number = ? AND take_suffix = '' "
            "AND deleted_at IS NOT NULL;",
            (scene_id, shot, take_number),
        ).fetchone()
        if occupant is None:
            return  # no-op：'' 未被软删行占

        # 从 '+' 开始顺位找空闲 suffix（_alloc_free_suffix 含 MAX_ITER 守卫）
        new_suffix = _alloc_free_suffix(
            conn, scene_id, shot, take_number, exclude_take_id=occupant["take_id"]
        )
        conn.execute(
            "UPDATE takes SET take_suffix = ? WHERE take_id = ?;",
            (new_suffix, occupant["take_id"]),
        )

    def _resolve_base_slot(
        self,
        conn: sqlite3.Connection,
        target_scene: int,
        target_shot: str,
        target_number: int,
        exclude_take_id: int,
    ) -> tuple[str, str]:
        """查目标四元 (target_scene, target_shot, target_number, '') 的占用状态，返回 (target_suffix, conflict_resolution)。

        三态：
        - '' 未被占用 → ("", "none")
        - 被软删行占 → _vacate_base_slot 让出 '' → ("", "vacate")
        - 被 live 行占 → 被编辑 take 加后缀 → (suffix, "suffix")

        不对称规则（DeepSeek #4 注）：vacate 只动软删行；加后缀只动被编辑 take，live 占用者永不被挪。
        调用时必须在写事务内（BEGIN IMMEDIATE 已持有），直接用传入 conn 操作，不开新事务。
        """
        occupant_row = conn.execute(
            "SELECT take_id, deleted_at FROM takes "
            "WHERE scene_id = ? AND shot = ? AND take_number = ? AND take_suffix = '' "
            "AND take_id != ?;",
            (target_scene, target_shot, target_number, exclude_take_id),
        ).fetchone()

        if occupant_row is None:
            return ("", "none")
        if occupant_row["deleted_at"] is not None:
            self._vacate_base_slot(conn, target_scene, target_shot, target_number)
            return ("", "vacate")
        # live 行占用 → 被编辑 take 顺位加后缀（_alloc_free_suffix 含 MAX_ITER 守卫）
        suffix = _alloc_free_suffix(
            conn, target_scene, target_shot, target_number, exclude_take_id=exclude_take_id
        )
        return (suffix, "suffix")

    def start_take(
        self,
        scene_id: int,
        shot: str,
        start_ts: float,
        take_number: int | None = None,
    ) -> tuple[int, int]:
        """新建 take 行，返回 (take_id, take_number)。

        take_number 在 BEGIN IMMEDIATE 写事务内确定 + 解析号位冲突：
          1. 定号：take_number 为 None → (scene_id, shot) 组内 MAX(live)+1；显式传入 → 直接用
             （用户在底部 Take 弹窗手动指定的待录号）。
          2. _resolve_base_slot：解析 (scene_id, shot, take_number, '') 号位三态——空闲直接用 ''；
             被软删行占 → vacate 让位，新 take 仍落 ''；被 live 行占（手动往回退占已用号）→
             新 take 顺位加后缀（'+'/'++'…），live 占用者永不被挪。
          3. INSERT 新 take，落 (scene_id, shot, take_number, 解析得的 suffix)。

        自动号路径（take_number=None）行为不变：MAX+1 永不撞 live 行，故 _resolve_base_slot 恒返回
        ''（空闲或 vacate），等价于旧 _vacate_base_slot + 落 ''。
        原子性依赖单连接 + IMMEDIATE 事务：同一进程单连接下，步骤 1-3 不会被其他写入打断。
        shot='' 表示无镜编号（v4 约定，不报错）。（DeepSeek #1）
        """
        with self._write_tx() as conn:
            # 步骤 1：定号（自动 MAX+1 或用显式传入号）
            if take_number is None:
                take_number = _next_take_number(conn, scene_id, shot)
            # 步骤 2：解析号位冲突（新行尚未插入，不排除任何已有行）
            suffix, _resolution = self._resolve_base_slot(
                conn, scene_id, shot, take_number, exclude_take_id=_NO_EXCLUDE_TAKE_ID
            )
            # 步骤 3：插入新 take
            cur = conn.execute(
                "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) "
                "VALUES (?, ?, ?, ?, ?);",
                (scene_id, shot, take_number, suffix, start_ts),
            )
        return cur.lastrowid, take_number  # type: ignore[return-value]

    def end_take(
        self,
        take_id: int,
        end_ts: float,
        status: str | None = None,
        script_diff: dict | None = None,
        notes: str | None = None,
    ) -> None:
        """更新 take 结束时间，可选更新 status / L2 输出。

        status / script_diff / notes 走 preserve-on-None（COALESCE）：传 None 即保留库中原值，
        不清零。故 end_take 只负责标记结束 + 写入显式给的字段，不覆盖它没被给的列
        （status 是用户 Mark、script_diff 由 L2 单独写、notes 由 memo 写，各有其主，end_take 不碰）。
        script_diff 传 dict，DAL 内部 json.dumps 后存库；读取时 json.loads 还原。
        与 update_take_np_output 同构的 COALESCE 写法。
        """
        script_diff_json = json.dumps(script_diff) if script_diff is not None else None
        with self._write_tx() as conn:
            conn.execute(
                f"UPDATE takes SET end_ts = ?, "
                f"status = COALESCE(?, status), "
                f"script_diff = COALESCE(?, script_diff), "
                f"notes = COALESCE(?, notes), "
                f"updated_at = {_NOW_TS_SQL} "
                f"WHERE take_id = ?;",
                (end_ts, status, script_diff_json, notes, take_id),
            )

    def update_take_np_output(
        self,
        take_id: int,
        performer_issues: dict | list | None,
        audio_quality: str | None,
        status: str | None,
    ) -> None:
        """NP Pipeline 写入结构化字段，不覆盖 end_ts。

        performer_issues 传 dict/list，DAL 内部 json.dumps 后存库；
        读取时 _row_to_take 会 json.loads 还原。
        """
        performer_issues_json = (
            json.dumps(performer_issues) if performer_issues is not None else None
        )
        with self._write_tx() as conn:
            conn.execute(
                f"UPDATE takes SET performer_issues = ?, audio_quality = ?, "
                f"status = COALESCE(?, status), "
                f"updated_at = {_NOW_TS_SQL} "
                f"WHERE take_id = ?;",
                (performer_issues_json, audio_quality, status, take_id),
            )

    def update_take_structured_transcript(
        self,
        take_id: int,
        structured_transcript: dict | None,
    ) -> None:
        """写入 diarization 回填后的结构化转录（ASR + speaker 整合，v4）。

        传 dict，DAL 内部 json.dumps（ensure_ascii=False 保中文可读）后存库；
        读取时 _row_to_take 会 json.loads 还原。
        """
        payload = (
            json.dumps(structured_transcript, ensure_ascii=False)
            if structured_transcript is not None
            else None
        )
        with self._write_tx() as conn:
            conn.execute(
                f"UPDATE takes SET structured_transcript = ?, updated_at = {_NOW_TS_SQL} "
                f"WHERE take_id = ?;",
                (payload, take_id),
            )

    def get_take(self, take_id: int) -> Take | None:
        """按 take_id 获取单条 take，不存在或已软删返回 None。"""
        row = self._conn.execute(
            "SELECT * FROM takes WHERE take_id = ? AND deleted_at IS NULL;", (take_id,)
        ).fetchone()
        return _row_to_take(row) if row else None

    def get_take_any(self, take_id: int) -> Take | None:
        """按 take_id 获取单条 take（含软删行），不存在返回 None。供 restore 端点使用。"""
        row = self._conn.execute(
            "SELECT * FROM takes WHERE take_id = ?;", (take_id,)
        ).fetchone()
        return _row_to_take(row) if row else None

    def list_takes(self, scene_id: int | None = None) -> list[Take]:
        """返回 take 列表（排除软删行），可按 scene_id 过滤，按 take_number 升序。"""
        if scene_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM takes WHERE scene_id = ? AND deleted_at IS NULL ORDER BY take_number ASC;",
                (scene_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM takes WHERE deleted_at IS NULL ORDER BY take_number ASC;"
            ).fetchall()
        return [_row_to_take(r) for r in rows]

    # ── take_events ──────────────────────────────────────────────────────────

    def insert_take_event(
        self,
        take_id: int,
        event_type: str,
        payload: dict,
        ts: float,
    ) -> int:
        """写入 take 事件行，返回 event_id。"""
        payload_json = json.dumps(payload)
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO take_events (take_id, event_type, payload, ts) "
                "VALUES (?, ?, ?, ?);",
                (take_id, event_type, payload_json, ts),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def list_take_events(
        self,
        take_id: int,
        event_type: str | None = None,
    ) -> list[TakeEvent]:
        """返回某 take 的事件列表，可按 event_type 过滤，按 ts 升序。"""
        if event_type is not None:
            rows = self._conn.execute(
                "SELECT * FROM take_events WHERE take_id = ? AND event_type = ? "
                "ORDER BY ts ASC;",
                (take_id, event_type),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM take_events WHERE take_id = ? ORDER BY ts ASC;",
                (take_id,),
            ).fetchall()
        return [_row_to_event(r) for r in rows]

    # ── transcript_segments ──────────────────────────────────────────────────

    def insert_segment(
        self,
        take_id: int,
        ch: int,
        speaker: str | None,
        text: str,
        start_frame: int,
        end_frame: int,
    ) -> int:
        """写入一条转录片段，返回 segment_id。ch 必须为 1 或 2。

        start_frame / end_frame 单位为毫秒（秒 × 1000 取整），字段名沿用历史命名。
        """
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO transcript_segments "
                "(take_id, ch, speaker, text, start_frame, end_frame) "
                "VALUES (?, ?, ?, ?, ?, ?);",
                (take_id, ch, speaker, text, start_frame, end_frame),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def list_segments(
        self,
        take_id: int,
        ch: int | None = None,
        speaker: str | None = None,
    ) -> list[TranscriptSegment]:
        """
        返回某 take 的转录片段列表。
        ch=None 表示不过滤声道。
        """
        base = "SELECT * FROM transcript_segments WHERE take_id = ?"
        params: list[Any] = [take_id]
        if ch is not None:
            base += " AND ch = ?"
            params.append(ch)
        if speaker is not None:
            base += " AND speaker = ?"
            params.append(speaker)
        base += " ORDER BY start_frame ASC;"
        rows = self._conn.execute(base, params).fetchall()
        return [_row_to_segment(r) for r in rows]

    def list_ch1_texts_by_take(self) -> dict[int, list[str]]:
        """一趟取全部 ch1 转录文本，按 take_id 分组、组内按 start_frame 升序。

        供 CSV 导出装配「Lines」列用：一次查询替代 per-take list_segments，避免 N+1。
        只取 ch1（对白）；ch2 备注不计入导出 Lines 列。空表返回空 dict。
        """
        rows = self._conn.execute(
            "SELECT take_id, text FROM transcript_segments "
            "WHERE ch = 1 ORDER BY take_id ASC, start_frame ASC;"
        ).fetchall()
        out: dict[int, list[str]] = {}
        for r in rows:
            out.setdefault(r["take_id"], []).append(r["text"])
        return out

    def get_segment(self, segment_id: int) -> TranscriptSegment | None:
        """按 segment_id 获取单条片段，不存在返回 None。"""
        row = self._conn.execute(
            "SELECT * FROM transcript_segments WHERE segment_id = ?;",
            (segment_id,),
        ).fetchone()
        return _row_to_segment(row) if row else None

    def update_segment_speaker(self, segment_id: int, speaker: str | None) -> int:
        """改单条片段的 speaker，返回受影响行数（0 = segment 不存在）。

        归属（take 匹配）与 ch1 限制由 route 层先用 get_segment 校验，不进 WHERE。
        speaker=None 表示置「未知」（schema 允许 NULL）。
        """
        with self._write_tx() as conn:
            cur = conn.execute(
                "UPDATE transcript_segments SET speaker = ? WHERE segment_id = ?;",
                (speaker, segment_id),
            )
        return cur.rowcount

    # ── scripts ──────────────────────────────────────────────────────────────

    def insert_script(
        self,
        scene_id: int,
        raw_text: str,
        version: int | None = None,
    ) -> int:
        """
        插入剧本原文，返回 script_id。
        version=None 时自动取该场次最大版本 +1。
        """
        with self._write_tx() as conn:
            if version is None:
                row = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) AS max_v FROM scripts "
                    "WHERE scene_id = ?;",
                    (scene_id,),
                ).fetchone()
                version = row["max_v"] + 1
            cur = conn.execute(
                "INSERT INTO scripts (scene_id, raw_text, version) VALUES (?, ?, ?);",
                (scene_id, raw_text, version),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_latest_script(self, scene_id: int) -> dict | None:
        """返回场次最新版本剧本（script_id + raw_text），无则返回 None。"""
        row = self._conn.execute(
            "SELECT script_id, raw_text, version FROM scripts "
            "WHERE scene_id = ? ORDER BY version DESC LIMIT 1;",
            (scene_id,),
        ).fetchone()
        return dict(row) if row else None

    # ── script_uploads（上传/解析两段拆分，v9）─────────────────────────────────

    def insert_script_upload(self, filename: str, raw_text: str) -> int:
        """存一份待解析的原始剧本（status='uploaded'），返回 upload_id。不碰 LLM。"""
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO script_uploads (filename, raw_text, char_count, status) "
                "VALUES (?, ?, ?, 'uploaded');",
                (filename, raw_text, len(raw_text)),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_script_upload(self, upload_id: int) -> dict | None:
        """返回上传记录的元信息（不含 raw_text，避免大字段），无则 None。"""
        row = self._conn.execute(
            "SELECT upload_id, filename, char_count, status, detail, created_at, updated_at "
            "FROM script_uploads WHERE upload_id = ?;",
            (upload_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_script_upload_raw(self, upload_id: int) -> str | None:
        """返回上传记录的原始文本（解析步骤用），无则 None。"""
        row = self._conn.execute(
            "SELECT raw_text FROM script_uploads WHERE upload_id = ?;",
            (upload_id,),
        ).fetchone()
        return row["raw_text"] if row else None

    def list_script_uploads(self) -> list[dict]:
        """返回所有上传记录元信息，按 upload_id 倒序（最新在前）。"""
        rows = self._conn.execute(
            "SELECT upload_id, filename, char_count, status, detail, created_at, updated_at "
            "FROM script_uploads ORDER BY upload_id DESC;"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_script_upload_status(
        self, upload_id: int, status: str, detail: str | None = None
    ) -> None:
        """更新上传记录状态（uploaded/parsing/parsed/error），detail 传 None 则保留原值。"""
        with self._write_tx() as conn:
            conn.execute(
                f"UPDATE script_uploads SET status = ?, "
                f"detail = COALESCE(?, detail), updated_at = {_NOW_TS_SQL} "
                f"WHERE upload_id = ?;",
                (status, detail, upload_id),
            )

    def reset_stale_parsing_uploads(self) -> int:
        """把残留在 'parsing' 的上传标记为 error（启动时调用）。返回清理条数。

        解析任务在内存中（asyncio task），进程重启/崩溃后这些任务已不存在，
        但 DB 里的 'parsing' 状态会残留 → 前端无限转圈。启动时统一复位为中断。
        """
        with self._write_tx() as conn:
            cur = conn.execute(
                f"UPDATE script_uploads SET status = 'error', "
                f"detail = '解析中断（服务已重启），请重新解析', updated_at = {_NOW_TS_SQL} "
                f"WHERE status = 'parsing';"
            )
        return cur.rowcount

    # ── script_lines ─────────────────────────────────────────────────────────

    def insert_script_line(
        self,
        script_id: int,
        line_no: int,
        character: str | None,
        text: str,
    ) -> int:
        """插入一行台词，返回 line_id。FTS5 触发器自动同步。"""
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO script_lines (script_id, line_no, character, text) "
                "VALUES (?, ?, ?, ?);",
                (script_id, line_no, character, text),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def match_script_line(
        self,
        query: str,
        scene_id: int | None = None,
    ) -> list[ScriptLine]:
        """
        用 FTS5 MATCH 检索台词，返回匹配行列表（按 BM25 排序）。
        scene_id 不为 None 时限制在该场次剧本内。
        """
        if scene_id is not None:
            rows = self._conn.execute(
                "SELECT sl.line_id, sl.script_id, sl.line_no, sl.character, sl.text, sl.created_at "
                "FROM script_lines_fts fts "
                "JOIN script_lines sl ON sl.line_id = fts.rowid "
                "JOIN scripts s ON s.script_id = sl.script_id "
                "WHERE fts.text MATCH ? AND s.scene_id = ? "
                "ORDER BY bm25(script_lines_fts);",
                (query, scene_id),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT sl.line_id, sl.script_id, sl.line_no, sl.character, sl.text, sl.created_at "
                "FROM script_lines_fts fts "
                "JOIN script_lines sl ON sl.line_id = fts.rowid "
                "WHERE fts.text MATCH ? "
                "ORDER BY bm25(script_lines_fts);",
                (query,),
            ).fetchall()
        return [_row_to_script_line(r) for r in rows]

    # ── take_line_matches ────────────────────────────────────────────────────

    def insert_take_line_match(
        self,
        take_id: int,
        line_id: int,
        diff_type: str,
        payload: dict,
    ) -> int:
        """写入 take-剧本行比对结果，返回 match_id。"""
        payload_json = json.dumps(payload)
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO take_line_matches (take_id, line_id, diff_type, payload) "
                "VALUES (?, ?, ?, ?);",
                (take_id, line_id, diff_type, payload_json),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def list_take_line_matches(self, take_id: int) -> list[dict]:
        """返回某 take 的所有偏差记录，含 line_id + diff_type + payload。"""
        rows = self._conn.execute(
            "SELECT match_id, take_id, line_id, diff_type, payload, created_at "
            "FROM take_line_matches WHERE take_id = ? ORDER BY match_id ASC;",
            (take_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d["payload"])
            result.append(d)
        return result

    # ── active_observers ─────────────────────────────────────────────────────

    def upsert_observer(self, connection_id: str, name: str) -> None:
        """插入或更新观察者记录（INSERT OR REPLACE）。"""
        with self._write_tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO active_observers (connection_id, name) "
                "VALUES (?, ?);",
                (connection_id, name),
            )

    def remove_observer(self, connection_id: str) -> None:
        """删除观察者记录。"""
        with self._write_tx() as conn:
            conn.execute(
                "DELETE FROM active_observers WHERE connection_id = ?;",
                (connection_id,),
            )

    def list_observers(self) -> list[dict]:
        """返回当前所有在线观察者列表。"""
        rows = self._conn.execute(
            "SELECT connection_id, name, joined_at FROM active_observers ORDER BY joined_at ASC;"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── audit_log ─────────────────────────────────────────────────────────────

    def append_audit(
        self,
        actor: str,
        action: str,
        payload: dict,
    ) -> int:
        """追加一条审计日志，返回 log_id。"""
        payload_json = json.dumps(payload)
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO audit_log (actor, action, payload) VALUES (?, ?, ?);",
                (actor, action, payload_json),
            )
        return cur.lastrowid  # type: ignore[return-value]

    # ── L2 Pipeline 写入（1.H）──────────────────────────────────────────────────

    def update_take_l2_output(
        self,
        take_id: int,
        script_diff: dict | None,
    ) -> None:
        """L2 Pipeline 写入 script_diff 字段。

        dict 走 json.dumps，None 写 NULL。
        """
        script_diff_json = json.dumps(script_diff) if script_diff is not None else None
        with self._write_tx() as conn:
            conn.execute(
                f"UPDATE takes SET script_diff = ?, updated_at = {_NOW_TS_SQL} WHERE take_id = ?;",
                (script_diff_json, take_id),
            )

    def insert_take_line_matches(
        self,
        take_id: int,
        matches: list[dict],
    ) -> None:
        """批量写入 take_line_matches。

        过滤 line_no==-1 的 insertion（按 l2-pipeline §D5 决策）。
        matches 每项需含：line_no / line_id / diff_type / detail（可选）。
        line_id 为 FK to script_lines，caller 负责在传入前做 line_no → line_id 映射。
        """
        rows_to_insert = [m for m in matches if m.get("line_no") != -1]
        if not rows_to_insert:
            return
        with self._write_tx() as conn:
            for m in rows_to_insert:
                detail = m.get("detail")
                payload_json = json.dumps({"detail": detail}) if detail is not None else "{}"
                conn.execute(
                    "INSERT INTO take_line_matches (take_id, line_id, diff_type, payload) "
                    "VALUES (?, ?, ?, ?);",
                    (take_id, m["line_id"], m["diff_type"], payload_json),
                )

    def list_script_lines(self, script_id: int) -> list[dict]:
        """返回剧本行列表，含 line_no / line_id / character / text，按 line_no ASC。"""
        rows = self._conn.execute(
            "SELECT line_id, line_no, character, text FROM script_lines "
            "WHERE script_id = ? ORDER BY line_no ASC;",
            (script_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── notes (take_events + takes.notes 聚合) ───────────────────────────────

    def insert_note(
        self,
        take_id: int,
        category: str,
        content: str,
        raw_text: str,
        ts: float,
    ) -> int:
        """写入一条 note 事件（take_events），并原子更新 takes.notes 聚合。

        原子操作（同一事务）：
        1. INSERT INTO take_events (take_id, event_type, ts, payload)
           payload = {"category": category, "content": content, "raw_text": raw_text}
        2. 重建 takes.notes：SELECT 该 take 所有 manual.note 事件的 ts, category, content，
           按 ts 升序拼接为：
           [2026-06-12T14:30:01+00:00] @issue 开头有飞机声
           用 datetime.fromtimestamp(ts, timezone.utc).isoformat() 生成时间戳格式。
           如果 content 为空，则不追加内容文本（如 \"[ts] @pass\"）。
           拼接后 UPDATE takes SET notes=?, updated_at=... WHERE take_id=?。
        """
        payload = {"category": category, "content": content, "raw_text": raw_text}
        payload_json = json.dumps(payload)
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO take_events (take_id, event_type, ts, payload) "
                "VALUES (?, 'manual.note', ?, ?);",
                (take_id, ts, payload_json),
            )
            event_id = cur.lastrowid

            # 重建 takes.notes 聚合
            rows = conn.execute(
                "SELECT ts, payload FROM take_events "
                "WHERE take_id = ? AND event_type = 'manual.note' "
                "ORDER BY ts ASC;",
                (take_id,),
            ).fetchall()

            lines = []
            for r in rows:
                event_ts = r["ts"]
                p = json.loads(r["payload"])
                cat = p.get("category", "")
                cont = p.get("content", "")
                ts_str = datetime.fromtimestamp(event_ts, tz=timezone.utc).isoformat()
                if cont:
                    lines.append("[{}] @{} {}".format(ts_str, cat, cont))
                else:
                    lines.append("[{}] @{}".format(ts_str, cat))

            notes_text = "\n".join(lines) if lines else None
            conn.execute(
                f"UPDATE takes SET notes = ?, updated_at = {_NOW_TS_SQL} WHERE take_id = ?;",
                (notes_text, take_id),
            )
        return event_id  # type: ignore[return-value]

    def list_notes(
        self,
        take_id: int,
        category: str | None = None,
    ) -> list[TakeEvent]:
        """按 take_id 列出 note 事件（event_type='manual.note'）。

        可选按 category 过滤，按 ts 升序返回。
        """
        if category is not None:
            rows = self._conn.execute(
                "SELECT * FROM take_events "
                "WHERE take_id = ? AND event_type = 'manual.note' "
                "AND json_extract(payload, '$.category') = ? "
                "ORDER BY ts ASC;",
                (take_id, category),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM take_events "
                "WHERE take_id = ? AND event_type = 'manual.note' "
                "ORDER BY ts ASC;",
                (take_id,),
            ).fetchall()
        return [_row_to_event(r) for r in rows]
    # ── speakers 台账（v5 migration）────────────────────────────────────────────

    def insert_speaker(
        self,
        display_name: str,
        embedding_blob: bytes | None = None,
        sample_count: int = 1,
        scope_key: str | None = None,
    ) -> int:
        """新增说话人记录，返回 speaker_id。"""
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO speakers (display_name, embedding, sample_count, scope_key) "
                "VALUES (?, ?, ?, ?);",
                (display_name, embedding_blob, sample_count, scope_key),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def list_speakers(self, scope_key: str | None = None) -> list[dict]:
        """返回台账中所有说话人。embedding 字段反序列化为 numpy 数组（可 None）。"""
        import numpy as np

        if scope_key is not None:
            rows = self._conn.execute(
                "SELECT speaker_id, display_name, embedding, sample_count, scope_key, "
                "created_at, updated_at "
                "FROM speakers WHERE scope_key = ? OR scope_key IS NULL ORDER BY speaker_id ASC;",
                (scope_key,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT speaker_id, display_name, embedding, sample_count, scope_key, "
                "created_at, updated_at "
                "FROM speakers ORDER BY speaker_id ASC;"
            ).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            blob = d.get("embedding")
            if blob is not None:
                try:
                    d["embedding"] = np.frombuffer(blob, dtype=np.float32)
                except Exception:
                    d["embedding"] = None
            result.append(d)
        return result

    def get_speaker(self, speaker_id: int) -> dict | None:
        """按 speaker_id 获取单条说话人记录（embedding 反序列化为 numpy 数组）。"""
        import numpy as np

        row = self._conn.execute(
            "SELECT speaker_id, display_name, embedding, sample_count, scope_key, "
            "created_at, updated_at FROM speakers WHERE speaker_id = ?;",
            (speaker_id,),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        blob = d.get("embedding")
        if blob is not None:
            try:
                d["embedding"] = np.frombuffer(blob, dtype=np.float32)
            except Exception:
                d["embedding"] = None
        return d

    def update_speaker_name(self, speaker_id: int, display_name: str) -> None:
        """更新说话人显示名（演员姓名绑定）。"""
        with self._write_tx() as conn:
            conn.execute(
                f"UPDATE speakers SET display_name = ?, updated_at = {_NOW_TS_SQL} "
                f"WHERE speaker_id = ?;",
                (display_name, speaker_id),
            )

    def update_speaker_embedding(
        self,
        speaker_id: int,
        embedding_blob: bytes,
        sample_count: int = 1,
    ) -> None:
        """更新说话人声纹 embedding（enrollment 后调用）。"""
        with self._write_tx() as conn:
            conn.execute(
                f"UPDATE speakers SET embedding = ?, sample_count = ?, "
                f"updated_at = {_NOW_TS_SQL} WHERE speaker_id = ?;",
                (embedding_blob, sample_count, speaker_id),
            )

    def delete_speaker(self, speaker_id: int) -> None:
        """删除说话人记录。"""
        with self._write_tx() as conn:
            conn.execute("DELETE FROM speakers WHERE speaker_id = ?;", (speaker_id,))

    # ── take ↔ 演员关联（v7）─────────────────────────────────────────────────────

    def set_take_speakers(self, take_id: int, speaker_ids: list[int]) -> None:
        """覆盖式设置某 take 的在场演员列表（先清后插）。空列表 = 清空。"""
        with self._write_tx() as conn:
            conn.execute("DELETE FROM take_speakers WHERE take_id = ?;", (take_id,))
            conn.executemany(
                "INSERT OR IGNORE INTO take_speakers (take_id, speaker_id) VALUES (?, ?);",
                [(take_id, sid) for sid in speaker_ids],
            )

    def list_take_speakers(self, take_id: int) -> list[dict]:
        """返回某 take 挂的已注册演员（join speakers，embedding 反序列化为 numpy）。"""
        import numpy as np

        rows = self._conn.execute(
            "SELECT s.speaker_id, s.display_name, s.embedding, s.sample_count, "
            "s.scope_key, s.created_at, s.updated_at "
            "FROM take_speakers ts JOIN speakers s ON s.speaker_id = ts.speaker_id "
            "WHERE ts.take_id = ? ORDER BY s.speaker_id ASC;",
            (take_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            blob = d.get("embedding")
            if blob is not None:
                try:
                    d["embedding"] = np.frombuffer(blob, dtype=np.float32)
                except Exception:
                    d["embedding"] = None
            result.append(d)
        return result

    # ── diarization 回填 ────────────────────────────────────────────────────────

    def bulk_update_segment_speaker(self, seg_speaker_map: dict[int, str]) -> None:
        """批量更新 transcript_segments.speaker 字段。

        seg_speaker_map: {segment_id: global_display_name}
        """
        if not seg_speaker_map:
            return
        with self._write_tx() as conn:
            for segment_id, speaker_name in seg_speaker_map.items():
                conn.execute(
                    "UPDATE transcript_segments SET speaker = ? WHERE segment_id = ?;",
                    (speaker_name, segment_id),
                )

    # ── 2.B 新增方法 ─────────────────────────────────────────────────────────

    def set_take_status(self, take_id: int, status: str) -> None:
        """更新 take 的 status，并在 take_events 写一条 manual.mark 事件。

        status 必须是 'pass' / 'ng' / 'keep' / 'tbd' 之一，否则抛 ValueError。
        单事务内完成：UPDATE takes + INSERT take_events（inline，不调 insert_take_event 避免嵌套事务）。
        """
        _VALID_STATUSES = {"pass", "ng", "keep", "tbd"}
        if status not in _VALID_STATUSES:
            raise ValueError(
                f"非法 status 值 {status!r}，必须是 {sorted(_VALID_STATUSES)} 之一"
            )
        payload_json = json.dumps({"status": status})
        with self._write_tx() as conn:
            conn.execute(
                f"UPDATE takes SET status = ?, updated_at = {_NOW_TS_SQL} WHERE take_id = ?;",
                (status, take_id),
            )
            conn.execute(
                f"INSERT INTO take_events (take_id, event_type, ts, payload) "
                f"VALUES (?, 'manual.mark', {_NOW_TS_SQL}, ?);",
                (take_id, payload_json),
            )

    def update_take_meta(
        self,
        take_id: int,
        *,
        shot: str | None = None,
        scene_id: int | None = None,
        take_number: int | None = None,
        notes: str | None = None,
    ) -> None:
        """部分更新 take 元数据，处理 UNIQUE(scene_id, shot, take_number, take_suffix) 冲突。在单个事务内完成。

        字段语义：
        - shot：None 表示不改；'' 是合法值（清空 shot 标注）；非 None 表示改 shot。
        - notes：None 表示不改，空串 "" 是合法值（清空备注）。
        - scene_id：目标场次 ID，None 表示不改（保持当前场）。目标 scene 不存在时抛 ValueError。
        - take_number：目标编号，None 表示不改或由冲突算法自动计算。

        冲突处理（spec §16 四元 key）：
        - 情形 A：仅改 scene_id（无 take_number）→ 追加为目标 (scene, target_shot) 组 live MAX+1。
        - 情形 B/C/D：改 take_number 或 shot（含跨场）→ 若目标四元 (scene,shot,number,'') 被占用
          （含软删行），按规则处理：软删占用者 → vacate 让出 ''；live 占用者 → 被编辑 take 加后缀。
          （DeepSeek #4 注：两路不对称：vacate 只动软删行，加后缀只动被编辑 take，live 占用者永不被挪）

        成功后写一条 take_events（event_type='manual.edit'），payload 含 changed_fields 列表
        和 conflict_resolution（'append' / 'suffix' / 'none'）。

        status 字段不在本方法，走 set_take_status。
        """
        # 取当前 take 快照（事务外读，仅用于后续判断）
        row = self._conn.execute(
            "SELECT scene_id, take_number, shot FROM takes WHERE take_id = ? AND deleted_at IS NULL;",
            (take_id,),
        ).fetchone()
        if row is None:
            return

        cur_scene: int = row["scene_id"]
        cur_number: int = row["take_number"]
        cur_shot: str = row["shot"]  # v4 后 NOT NULL

        # 确定目标 scene 和 shot
        target_scene = scene_id if scene_id is not None else cur_scene
        target_shot = shot if shot is not None else cur_shot  # None 用 cur；'' 是合法的空 shot
        is_cross_scene = (scene_id is not None) and (scene_id != cur_scene)
        is_shot_change = (shot is not None) and (shot != cur_shot)

        with self._write_tx() as conn:
            # 涉及 scene_id 变更，先校验目标 scene 存在
            if scene_id is not None:
                exists = conn.execute(
                    "SELECT 1 FROM scenes WHERE scene_id = ?;", (scene_id,)
                ).fetchone()
                if not exists:
                    raise ValueError(f"目标 scene_id={scene_id} 不存在")

            # 计算目标编号及冲突解决方式
            conflict_resolution = "none"
            target_number: int
            target_suffix: str = ""

            if take_number is None:
                if is_cross_scene:
                    # 情形 A：移场，追加到目标 (scene, target_shot) 组 live MAX+1（软删号可复用）
                    target_number = _next_take_number(conn, target_scene, target_shot)
                    conflict_resolution = "append"
                    # 若目标四元 (target_scene, target_shot, target_number, '') 被软删行占着，先让出 ''
                    self._vacate_base_slot(conn, target_scene, target_shot, target_number)
                elif is_shot_change:
                    # 决策 3：仅改 shot（同场），保留 take_number，落到目标 (scene, target_shot, number, '')
                    target_number = cur_number
                    target_suffix, res = self._resolve_base_slot(
                        conn, target_scene, target_shot, target_number, exclude_take_id=take_id
                    )
                    if res == "suffix":
                        conflict_resolution = res
                else:
                    # 无 take_number，无跨场，无 shot 变更 → 不改编号
                    target_number = cur_number
            else:
                target_number = take_number
                if target_number != cur_number or is_cross_scene or is_shot_change:
                    # 检查目标四元 (scene, target_shot, number, '') 是否被占用（排除自己）
                    # 不对称规则（DeepSeek #4）：
                    #   - 占用者是软删 → vacate 让出 ''，被编辑 take 落干净 ''
                    #   - 占用者是 live → 被编辑 take 顺位加后缀（live 行永不被挪）
                    target_suffix, res = self._resolve_base_slot(
                        conn, target_scene, target_shot, target_number, exclude_take_id=take_id
                    )
                    if res == "suffix":
                        conflict_resolution = res

            # 汇总需要更新的字段
            set_clauses: list[str] = []
            params: list[Any] = []

            if scene_id is not None:
                set_clauses.append("scene_id = ?")
                params.append(target_scene)
            if target_number != cur_number or conflict_resolution == "suffix" or is_shot_change:
                set_clauses.append("take_number = ?")
                params.append(target_number)
                set_clauses.append("take_suffix = ?")
                params.append(target_suffix)
            elif take_number is not None and target_number == cur_number and not is_cross_scene and not is_shot_change:
                # 同场改号但号未变（目标与当前相同），suffix 也不变，无需写 take_number/take_suffix
                pass
            if shot is not None:
                set_clauses.append("shot = ?")
                params.append(target_shot)
            if notes is not None:
                set_clauses.append("notes = ?")
                params.append(notes)

            # 记录本次改动的业务字段（供 take_events payload）
            changed_fields: list[str] = []
            if scene_id is not None:
                changed_fields.append("scene_id")
            if target_number != cur_number:
                changed_fields.append("take_number")
            if is_cross_scene and take_number is None:
                changed_fields.append("take_number")  # append 也改了编号
            if target_suffix:
                changed_fields.append("take_suffix")
            if shot is not None:
                changed_fields.append("shot")
            if notes is not None:
                changed_fields.append("notes")

            if set_clauses:
                set_clauses.append(f"updated_at = {_NOW_TS_SQL}")
                params.append(take_id)
                conn.execute(
                    f"UPDATE takes SET {', '.join(set_clauses)} WHERE take_id = ?;",
                    params,
                )

            # 写 take_events（manual.edit），inline 不调 insert_take_event
            event_payload_json = json.dumps(
                {
                    "changed_fields": changed_fields,
                    "conflict_resolution": conflict_resolution,
                    "final_suffix": target_suffix,
                }
            )
            conn.execute(
                f"INSERT INTO take_events (take_id, event_type, ts, payload) "
                f"VALUES (?, 'manual.edit', {_NOW_TS_SQL}, ?);",
                (take_id, event_payload_json),
            )

    def next_take_number(self, scene_id: int, shot: str) -> int:
        """返回 (scene_id, shot) 组内下一个可用 take_number（live MAX+1，软删号可复用）。

        复用语义：以当前 live（deleted_at IS NULL）行中最大 take_number 为基准，
        返回 MAX(live)+1。软删行不占号位，删掉最新 take 后下次可拿回同一号。
        空组返回 1。shot='' 表示无镜组（v4 约定）。

        注意：此方法用于外部读取「当前组下一号」供 UI 展示（决策 4），
        start_take 内部在写事务里重新原子计算，不直接用此值写库。
        """
        return _next_take_number(self._conn, scene_id, shot)

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
        """返回 (scene_id, created)。created=True 表示本次新建，False 表示复用已有行。

        行为：先 SELECT，命中返回 (id, False)（忽略余参数，不更新已有行）；
        未命中 INSERT 返回 (id, True)；INSERT 撞唯一索引时兜底重 SELECT。
        """
        # 先查
        row = self._conn.execute(
            "SELECT scene_id FROM scenes WHERE scene_code = ?;",
            (scene_code,),
        ).fetchone()
        if row is not None:
            return int(row["scene_id"]), False

        # 未命中，尝试 INSERT
        try:
            with self._write_tx() as conn:
                cur = conn.execute(
                    "INSERT INTO scenes (scene_code, description, shoot_date, int_ext, time_of_day, location) "
                    "VALUES (?, ?, ?, ?, ?, ?);",
                    (scene_code, description, shoot_date, int_ext, time_of_day, location),
                )
            return int(cur.lastrowid), True  # type: ignore[arg-type]
        except sqlite3.IntegrityError:
            # 并发下 INSERT 撞唯一索引，兜底重 SELECT
            row = self._conn.execute(
                "SELECT scene_id FROM scenes WHERE scene_code = ?;",
                (scene_code,),
            ).fetchone()
            return int(row["scene_id"]), False  # type: ignore[index]

    def delete_take(self, take_id: int) -> None:
        """软删 take：设置 deleted_at 时间戳，子表数据保留（不触发 CASCADE）。

        执行顺序（单事务）：SELECT 快照 → INSERT audit_log → UPDATE deleted_at。
        take 不存在时静默 no-op。
        """
        with self._write_tx() as conn:
            snapshot = conn.execute(
                "SELECT take_id, scene_id, take_number, status, shot, notes, "
                "start_ts, end_ts FROM takes WHERE take_id = ?;",
                (take_id,),
            ).fetchone()
            if snapshot is None:
                return

            audit_payload = json.dumps(
                {
                    "take_id": snapshot["take_id"],
                    "scene_id": snapshot["scene_id"],
                    "take_number": snapshot["take_number"],
                    "status": snapshot["status"],
                    "shot": snapshot["shot"],
                    "notes": snapshot["notes"],
                    "start_ts": snapshot["start_ts"],
                    "end_ts": snapshot["end_ts"],
                }
            )
            conn.execute(
                f"INSERT INTO audit_log (actor, action, payload, ts) "
                f"VALUES ('user', 'take.delete', ?, {_NOW_TS_SQL});",
                (audit_payload,),
            )
            conn.execute(
                f"UPDATE takes SET deleted_at = {_NOW_TS_SQL} WHERE take_id = ?;",
                (take_id,),
            )

    def reset_all(self) -> None:
        """单事务内清空全部业务表（dev 专用）。

        按「子表先于父表」顺序 DELETE，遵循外键约束（PRAGMA foreign_keys ON）：
          take_line_matches / take_events / transcript_segments
            → takes → script_lines → scripts → scenes
            → audit_log → active_observers（无 FK，顺序任意）

        FTS5 影子表（script_lines_fts*）靠 script_lines 上的 BEFORE DELETE 触发器同步，
        DELETE FROM script_lines 会逐行触发 FTS 删除，影子表随之清空。
        方法只做清空，不负责重新播种（播种在端点层）。
        """
        with self._write_tx() as conn:
            conn.execute("DELETE FROM take_line_matches;")
            conn.execute("DELETE FROM take_events;")
            conn.execute("DELETE FROM transcript_segments;")
            conn.execute("DELETE FROM takes;")
            conn.execute("DELETE FROM script_lines;")
            conn.execute("DELETE FROM scripts;")
            conn.execute("DELETE FROM scenes;")
            conn.execute("DELETE FROM audit_log;")
            conn.execute("DELETE FROM active_observers;")

    def restore_take(self, take_id: int) -> None:
        """撤销软删：清除 deleted_at，在 audit_log 写 take.restore。

        take 不存在时静默 no-op。

        兜底逻辑（DeepSeek #2）：正常路径下软删行在被复用（start_take）时已被 _vacate_base_slot
        挪到 '+'，restore 后落回其当前 suffix 不撞 live 行。
        但若极端情况下 (scene, shot, number, suffix) 与 live 行冲突，则顺位追加 '+'
        直到找到空闲 suffix，更新后再清 deleted_at，防止抛 500。

        ⚠ 注（schema 限制）：当前 UNIQUE(scene_id, shot, take_number, take_suffix) 包含软删行，
        因此被 restore 的 (tuple) 在库中必然唯一，live_conflict 在正常路径下不可达，
        fallback + MAX_ITER 属防御性死码。若未来改成 partial unique（仅 live 行），fallback 会生效。
        """
        with self._write_tx() as conn:
            # 取被恢复行的快照（含软删行）
            snap = conn.execute(
                "SELECT scene_id, shot, take_number, take_suffix FROM takes WHERE take_id = ?;",
                (take_id,),
            ).fetchone()
            if snap is None:
                return  # 不存在，no-op

            scene_id = snap["scene_id"]
            shot = snap["shot"]
            take_number = snap["take_number"]
            current_suffix = snap["take_suffix"]

            # 检查 (scene, shot, number, current_suffix) 是否与 live 行冲突（排除自己）
            # 只检查 live 行：UNIQUE 约束仅在 (live) 行间有意义（SQLite 中软删行也受约束）
            live_conflict = conn.execute(
                "SELECT take_id FROM takes "
                "WHERE scene_id = ? AND shot = ? AND take_number = ? AND take_suffix = ? "
                "AND take_id != ? AND deleted_at IS NULL;",
                (scene_id, shot, take_number, current_suffix, take_id),
            ).fetchone()

            if live_conflict is not None:
                # 兜底：顺位找空闲 suffix（_alloc_free_suffix 含 MAX_ITER 守卫）
                # start=current_suffix+"+"：从当前 suffix 顺位追加，占用集合含软删行（DeepSeek #2）
                new_suffix = _alloc_free_suffix(
                    conn, scene_id, shot, take_number,
                    exclude_take_id=take_id,
                    start=current_suffix + "+",
                )
                conn.execute(
                    "UPDATE takes SET take_suffix = ? WHERE take_id = ?;",
                    (new_suffix, take_id),
                )

            conn.execute(
                "UPDATE takes SET deleted_at = NULL WHERE take_id = ?;",
                (take_id,),
            )
            audit_payload = json.dumps({"take_id": take_id})
            conn.execute(
                f"INSERT INTO audit_log (actor, action, payload, ts) "
                f"VALUES ('user', 'take.restore', ?, {_NOW_TS_SQL});",
                (audit_payload,),
            )

    # ── app_settings KV（v8）──────────────────────────────────────────────────

    def get_setting(self, key: str) -> str | None:
        """读取应用级 KV 设置。key 不存在返回 None。"""
        row = self._conn.execute(
            "SELECT value FROM app_settings WHERE key = ?;",
            (key,),
        ).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        """写入（UPSERT）应用级 KV 设置。"""
        with self._write_tx() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value;",
                (key, value),
            )
