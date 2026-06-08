"""迁移执行器。

使用 PRAGMA user_version 跟踪已应用版本，幂等执行。
per-connection PRAGMA（foreign_keys / journal_mode / busy_timeout）
在 runner 自己的连接上各自初始化，不写入 .sql 文件。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.db.lifecycle import _configure_connection

MIGRATIONS_DIR = Path(__file__).parent

# 每个版本对应一个 .sql 文件
MIGRATION_FILES: dict[int, str] = {
    1: "v1_init.sql",
    2: "v2_scene_heading.sql",
    3: "v3_scene_take_soft_delete.sql",
    4: "v4_takes_shot_unique.sql",
    # 1.x（实时 ASR / speaker / diarization）的 schema 接在 2.x 的 v4 之后，
    # 避免与 2.x 的 v3/v4 版本号冲突。注意 take_transcript 必须排在 v4 重建 takes 之后。
    5: "v5_speakers.sql",
    6: "v6_take_transcript.sql",
    7: "v7_take_speakers.sql",
    8: "v8_app_settings.sql",
    9: "v9_status_rename.sql",
    # 本特性的 script_uploads 原排 v9，与 main 的 v9_status_rename 撞号，改号顺延为 v10。
    10: "v10_script_uploads.sql",
}


def apply_migrations(db_path: Path) -> None:
    """
    将数据库升级到最新 schema 版本。
    使用 PRAGMA user_version 记录已应用版本号。
    幂等：已应用的迁移不会重复执行。

    Args:
        db_path: SQLite 数据库文件路径。文件不存在时自动创建。
    """
    conn = sqlite3.connect(db_path)
    try:
        _configure_connection(conn)

        current_version: int = conn.execute("PRAGMA user_version;").fetchone()[0]

        for version in sorted(MIGRATION_FILES.keys()):
            if version <= current_version:
                continue  # 已应用，跳过
            sql_file = MIGRATIONS_DIR / MIGRATION_FILES[version]
            sql = sql_file.read_text(encoding="utf-8")
            conn.executescript(sql)  # executescript 自动 commit，且会设置 user_version
    finally:
        conn.close()
