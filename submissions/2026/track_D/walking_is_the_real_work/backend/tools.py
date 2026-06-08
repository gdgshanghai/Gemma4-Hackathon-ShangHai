"""Local tool implementations the model calls into.

Privacy stance (Track D, Social Good): inference stays in the local
deployment. Raw photos and exact GPS are not retained by application
storage or sent to a third-party inference API.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


ARCHIVE_DB = Path(__file__).parent / "archive.db"

# Pre-seeded list of Shanghai districts on the heritage protection roll.
# Real deployments would query the city open-data portal; for the demo we
# embed a small offline registry to keep the function-call loop self-contained.
HERITAGE_REGISTRY = {
    "巨鹿路":  {"listed": True,  "tier": "上海第二批历史风貌保护道路", "specimens_so_far": 14},
    "武康路":  {"listed": True,  "tier": "上海第一批历史风貌保护道路", "specimens_so_far": 38},
    "愚园路":  {"listed": True,  "tier": "上海第二批历史风貌保护道路", "specimens_so_far": 22},
    "南京西路": {"listed": True, "tier": "近代商业风貌区",            "specimens_so_far": 9},
}


def _init_db() -> None:
    with sqlite3.connect(ARCHIVE_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS specimens (
                no       TEXT PRIMARY KEY,
                title    TEXT,
                line     TEXT,
                palette  TEXT,
                place    TEXT,
                listed   INTEGER,
                created  TEXT
            )
        """)


def lookup_district_archive(place: str, geo: str | None = None) -> dict[str, Any]:
    for road, meta in HERITAGE_REGISTRY.items():
        if road in place:
            return {**meta, "matched_road": road}
    return {"listed": False, "tier": None, "specimens_so_far": 0, "matched_road": None}


def save_specimen(*, title: str, line: str, palette: list, place: str,
                  in_archive: bool = False) -> dict[str, Any]:
    _init_db()
    with sqlite3.connect(ARCHIVE_DB) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM specimens")
        n = cur.fetchone()[0]
        no = f"No. {(243 + n + 1):04d}"
        conn.execute(
            "INSERT INTO specimens VALUES (?,?,?,?,?,?,?)",
            (no, title, line, json.dumps(palette, ensure_ascii=False),
             place, int(in_archive), datetime.utcnow().isoformat()),
        )
    return {"specimen_no": no, "title": title, "line": line}


# Dispatcher used by gemma_client during the function-calling loop.
TOOL_DISPATCH = {
    "lookup_district_archive": lambda args: lookup_district_archive(**args),
    "save_specimen":           lambda args: save_specimen(**args),
}


def handle(name: str, arguments: dict) -> Any:
    fn = TOOL_DISPATCH.get(name)
    if fn is None:
        return {"error": f"unknown tool: {name}"}
    return fn(arguments)
