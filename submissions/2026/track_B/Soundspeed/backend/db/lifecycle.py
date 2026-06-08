"""应用生命周期钩子。

此模块提供服务启动/关闭时对 volatile 状态的显式清理操作。
DAL 构造本身不调用这里的函数——只有 FastAPI startup hook 在服务启动时显式调用一次。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def _configure_connection(conn: sqlite3.Connection) -> None:
    """统一设置每个 sqlite3 连接的必备 PRAGMA。

    所有打开连接的地方（DAL 构造、apply_migrations、purge_volatile_tables）
    都必须调用此函数，避免 PRAGMA 散落造成不一致（如 WAL/busy_timeout 漏设）。
    """
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")


def purge_volatile_tables(db_path: Path) -> None:
    """清空跨重启不保留的 volatile 表。

    当前清空 active_observers（WebSocket 连接状态，重启后全部失效）。
    未来如有其他 volatile 表，在此函数中追加。

    此函数由 FastAPI startup hook 显式调用一次，DAL 构造不调。
    """
    conn = sqlite3.connect(db_path)
    try:
        _configure_connection(conn)
        conn.execute("DELETE FROM active_observers;")
        conn.commit()
    finally:
        conn.close()
