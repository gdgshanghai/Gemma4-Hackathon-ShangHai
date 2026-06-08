"""FastAPI entrypoint for the City Color Archive backend.

Endpoints
    POST /api/extract_palette       multipart image  -> 4 hex+zh swatches
    POST /api/inscribe              palette + place  -> title + line via Gemma
                                                        native function calls
    GET  /api/archive_stats         district stats for the masthead
    GET  /healthz                   liveness probe

The frontend (frontend/walking-app.html) is served from /static for the
single-container Docker deploy.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import tools
from .gemma_client import get_client


FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app = FastAPI(
    title="City Color Archive · Gemma 4 Backend",
    description="散步采集城市色彩,Gemma 4 4B 多模态 + 原生函数调用",
    version="1.0.0",
)

class Swatch(BaseModel):
    hex: str
    zh: str


class InscribeRequest(BaseModel):
    palette: list[Swatch]
    place: str
    geo: str = ""


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "stub": os.environ.get("GEMMA_STUB", "0") == "1"}


@app.post("/api/extract_palette")
async def extract_palette(image: UploadFile = File(...)) -> dict:
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="image must be jpeg/png/webp")
    raw = await image.read()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="image > 8MB")

    palette = get_client().extract_palette(raw)
    # Privacy: the application never retains the raw image after this request.
    return {"palette": palette}


@app.post("/api/inscribe")
def inscribe(req: InscribeRequest) -> dict:
    palette = [s.dict() for s in req.palette]
    result = get_client().inscribe_with_tools(
        palette=palette,
        place=req.place,
        geo=req.geo,
        tool_handler=tools.handle,
    )
    return result


@app.get("/api/archive_stats")
def archive_stats() -> dict:
    return {"districts": tools.HERITAGE_REGISTRY}


# Mount the static frontend last so /api/* still resolves first.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
