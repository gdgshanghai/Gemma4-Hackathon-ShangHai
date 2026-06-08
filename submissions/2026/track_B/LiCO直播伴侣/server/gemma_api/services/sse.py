"""Server-Sent Events 编码。"""

from __future__ import annotations

import json
from typing import Any


def sse_line(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
