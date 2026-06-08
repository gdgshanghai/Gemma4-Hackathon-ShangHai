"""ASR 运行配置端点：读当前语言/模型 + 切换转录语言。

GET  /api/v1/asr           当前 language / model（+ UI 可选语言列表）
POST /api/v1/asr/language  切换转录语言（即时生效，无需重载模型）

状态存在 app.state.live_asr（LiveAsrSession）。未启用实时 ASR 时
GET 返回 enabled=False，POST 返回 409。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.api.auth import require_admin

router = APIRouter(prefix="/api/v1", tags=["asr"])

# UI 下拉提供的语言（whisper 实际支持 99 种；auto=自动检测）
_UI_LANGUAGES = ["zh", "en", "auto"]


@router.get("/asr")
async def get_asr(
    request: Request,
    _: None = Depends(require_admin),
) -> dict[str, object]:
    """当前转录语言 + 模型大小（未启用实时 ASR 时 enabled=False）。"""
    session = getattr(request.app.state, "live_asr", None)
    if session is None:
        return {"enabled": False, "language": None, "model": None, "languages": _UI_LANGUAGES}
    return {
        "enabled": True,
        "language": session.language,
        "model": session.model_size,
        "languages": _UI_LANGUAGES,
    }


class LanguageBody(BaseModel):
    language: str


@router.post("/asr/language")
async def set_language(
    body: LanguageBody,
    request: Request,
    _: None = Depends(require_admin),
) -> dict[str, object]:
    """切换转录语言。未启用实时 ASR → 409；空语言 → 422。"""
    session = getattr(request.app.state, "live_asr", None)
    if session is None:
        raise HTTPException(status_code=409, detail="live ASR not enabled")
    lang = body.language.strip()
    if not lang:
        raise HTTPException(status_code=422, detail="language required")
    session.set_language(lang)
    return {"status": "ok", "language": lang}
