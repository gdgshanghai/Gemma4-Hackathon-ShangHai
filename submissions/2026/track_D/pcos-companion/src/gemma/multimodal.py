"""
多模态：用 Gemma 4 26B MoE（vision）解析化验单 / B 超报告图片。

隐私约束（赛道 D 核心）：
  - 仅在用户【显式授权】后调用（前端勾选「同意本次解析这张图」）。
  - 图片只在内存中以 base64 传入自托管的云端 Gemma，不落盘、不入库；
    解析完成即丢弃，仅把【脱敏后的结构化指标】写回档案。
  - 整个链路不经任何第三方模型 API。
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from src.config import ModelTier
from src.gemma.client import GemmaClient
from src.tools.registry import register

_VISION_INSTRUCTION = (
    "你是医学化验单结构化助手。请只抽取图片中可见的指标，输出 JSON，"
    "字段：items（name/value/unit/reference 列表）、impression（B 超印象，如有）。"
    "不要给出任何诊断或解读，只做客观抽取。无法识别的留空。"
)


def _encode_image(image_path: str) -> str:
    raw = Path(image_path).read_bytes()
    return base64.b64encode(raw).decode("ascii")


def parse_lab_report(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    # 鉴权：必须有本次显式授权
    if not context.get("vision_consent"):
        return {"tool": "parse_lab_report", "status": "denied",
                "message": "解析化验单需要你先授权，我们不会在未经同意时读取图片。"}

    image_path = context.get("image_path")
    if not image_path:
        return {"tool": "parse_lab_report", "status": "no_image"}

    client = GemmaClient(tier=ModelTier.CLOUD)  # 多模态走云端 26B MoE
    b64 = _encode_image(image_path)
    messages = [
        {"role": "system", "content": _VISION_INSTRUCTION},
        {"role": "user", "content": [
            {"type": "text", "text": "请抽取这张化验单/报告的指标。"},
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]},
    ]
    try:
        resp = client.chat(messages)
        text = GemmaClient.extract_text(resp)
        structured = _safe_json(text)
    finally:
        client.close()
        b64 = ""  # 立即清除内存中的图片数据

    # 仅写回脱敏的结构化指标，原图不留存
    from src.privacy.data_governance import write_profile_event
    write_profile_event(context["user_id"],
                        {"kind": "lab_report", "structured": structured})
    return {"tool": "parse_lab_report", "status": "ok", "structured": structured,
            "note": "原图未保存，仅记录结构化指标；解读请以医生为准。"}


def _safe_json(text: str) -> dict[str, Any]:
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"items": [], "impression": "", "raw": text[:500]}


register("parse_lab_report", parse_lab_report)
