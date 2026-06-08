"""Note-parsing pipeline: turn raw user text into a structured NoteStruct."""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches an optional scene-code + take-number prefix: "<scene> <digits> "
_SCENE_TAKE_RE = re.compile(r"^([A-Za-z0-9_-]+) (\d+)\b\s*")

# Matches an optional @-category prefix: "@<lowercase> "
_CATEGORY_RE = re.compile(r"^@([a-z]+)\b\s*")

# Valid category values
_VALID_CATEGORIES = frozenset({"pass", "ng", "keep", "issue", "note"})

# Maximum content length
_MAX_CONTENT_LENGTH = 2000


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NoteParseError(Exception):
    """Note 解析错误，携带用户可视化错误消息。"""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class NoteStruct:
    raw_text: str
    scene_code: str | None
    take_number: int | None
    category: str  # 默认 "note"
    content: str  # 可为空串
    ts: float


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse_note(raw_text: str, ts: float) -> NoteStruct:
    """Parse *raw_text* into a :class:`NoteStruct`.

    1. Extract optional ``<scene_code> <take_number>`` prefix.
    2. Extract optional ``@category`` prefix from the remainder.
    3. The rest (stripped) becomes the content.
    """
    remaining = raw_text

    # --- scene_code + take_number ------------------------------------------
    scene_code: str | None = None
    take_number: int | None = None

    m = _SCENE_TAKE_RE.match(remaining)
    if m:
        scene_code = m.group(1)
        take_number = int(m.group(2))
        remaining = remaining[m.end() :]

    # --- category -----------------------------------------------------------
    category: str = "note"

    m = _CATEGORY_RE.match(remaining)
    if m:
        category = m.group(1)
        remaining = remaining[m.end() :]

    # --- content ------------------------------------------------------------
    content = remaining.strip()

    # --- validation ---------------------------------------------------------
    if category not in _VALID_CATEGORIES:
        raise NoteParseError(
            f"未知类别: {category}，合法值: pass, ng, keep, issue, note"
        )

    if len(content) > _MAX_CONTENT_LENGTH:
        raise NoteParseError("内容过长")

    return NoteStruct(
        raw_text=raw_text,
        scene_code=scene_code,
        take_number=take_number,
        category=category,
        content=content,
        ts=ts,
    )
