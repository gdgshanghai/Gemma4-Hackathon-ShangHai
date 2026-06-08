from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RequestType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"


class TextSummarizeRequest(BaseModel):
    """示例: POST /api/v1/text/summarize"""
    prompt: str = Field(
        ...,
        description="总结任务说明，例如：用三条要点总结以下内容",
        examples=["请用中文三条要点总结以下内容，并标注关键数据。"],
    )
    text: str = Field(
        ...,
        description="待总结的原文",
        examples=[
            "苹果公司 2024 财年第四季度营收 949.3 亿美元，同比增长 6%。"
            "iPhone 收入 462.2 亿美元。服务业务收入 249.7 亿美元，创历史新高。"
        ],
    )
    enable_search: bool = Field(
        True,
        description="允许模型在知识不足时调用 web_search",
    )
    include_thinking: bool = Field(
        False,
        description="为 true 时，将 Gemma4 <|channel>thought 思考过程写入 meta.thinking 供调试",
    )
    stream: bool = Field(
        False,
        description="为 true 时返回 SSE 流（text/event-stream），可实时看到状态与回答 token",
    )


class AudioSummarizeRequest(BaseModel):
    """multipart 表单；由 gemma4-e4b-mm 原生处理音频（非 Whisper）"""
    prompt: str = "请转写并总结这段语音的核心内容。"
    enable_search: bool = True


class ImageAnalyzeRequest(BaseModel):
    """multipart 表单字段说明（见 /api/v1/examples）"""
    prompt: str = "请识别并描述图片中的主要内容，必要时说明不确定之处。"
    enable_search: bool = True


class ToolCallInfo(BaseModel):
    name: str
    arguments: dict[str, Any]
    result_preview: Optional[str] = None


class AnalyzeResponse(BaseModel):
    request_type: RequestType
    model: str
    answer: str
    transcript: Optional[str] = None
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    used_search: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)
