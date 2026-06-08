from fastapi import APIRouter, File, Form, UploadFile

from gemma_api.config import OLLAMA_MODEL
from gemma_api.schemas import AnalyzeResponse, RequestType
from gemma_api.services import agent

router = APIRouter(prefix="/image", tags=["image"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_image(
    prompt: str = Form(
        default="请识别并描述图片中的主要内容、文字与场景。",
        description="图像分析任务说明",
    ),
    enable_search: bool = Form(default=True),
    file: UploadFile = File(..., description="图片文件 jpg/png/webp 等"),
) -> AnalyzeResponse:
    data = await file.read()
    answer, tools, used, meta = await agent.process_image(
        prompt, data, enable_search=enable_search
    )
    return AnalyzeResponse(
        request_type=RequestType.IMAGE,
        model=OLLAMA_MODEL,
        answer=answer,
        tool_calls=tools,
        used_search=used,
        meta={**meta, "filename": file.filename, "bytes": len(data)},
    )
