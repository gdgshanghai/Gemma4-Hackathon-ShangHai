"""
FastAPI 服务 —— 微信云函数 / 端侧前端调用的入口。

端点：
  POST /chat          一轮对话（默认端侧 Gemma 4 4B；多模态自动升云端）
  POST /privacy/erase 一键删除用户全部数据（被遗忘权）
  GET  /healthz       健康检查
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from src.config import ModelTier
from src.gemma.function_calling import run_turn
from src.privacy.data_governance import pseudonymize, erase_user

app = FastAPI(title="她健康·PCOS伴侣 / Gemma 4 后端", version="1.0")


class ChatRequest(BaseModel):
    openid: str                      # 入口即假名化，不入库
    message: str
    history: list[dict[str, Any]] = []
    vision_consent: bool = False     # 本次是否授权解析图片
    image_path: str | None = None
    tier: str | None = None          # 可显式指定 edge/cloud


class ChatResponse(BaseModel):
    reply: str
    escalated: bool
    tool_trace: list[dict[str, Any]]


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    user_id = pseudonymize(req.openid)
    context = {
        "user_id": user_id,
        "vision_consent": req.vision_consent,
        "image_path": req.image_path,
    }
    tier = ModelTier(req.tier) if req.tier else None
    out = run_turn(req.message, req.history, context, tier=tier)
    return ChatResponse(**out)


@app.post("/privacy/erase")
def erase(openid: str) -> dict[str, Any]:
    return erase_user(pseudonymize(openid))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
