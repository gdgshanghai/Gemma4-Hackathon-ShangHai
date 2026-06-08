from fastapi import APIRouter, File, Form, UploadFile

from gemma_api.config import OLLAMA_AUDIO_MODEL, WHISPER_FALLBACK
from gemma_api.schemas import AnalyzeResponse, RequestType
from gemma_api.services import agent, stt
from gemma_api.services.audio_prep import normalize_audio

router = APIRouter(prefix="/audio", tags=["audio"])


def _audio_format(filename: str) -> str:
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    return ext if ext in ("wav", "mp3", "m4a", "webm", "ogg", "flac") else "wav"


@router.post("/summarize", response_model=AnalyzeResponse)
async def summarize_audio(
    prompt: str = Form(
        default="请转写这段语音，并用中文总结核心内容。",
        description="总结任务说明",
    ),
    enable_search: bool = Form(default=True),
    file: UploadFile = File(..., description="音频文件"),
) -> AnalyzeResponse:
    data = await file.read()
    fmt = _audio_format(file.filename or "audio.wav")
    try:
        data, fmt = normalize_audio(data, file.filename or "audio.wav")
    except ValueError:
        raise
    except Exception:
        pass  # 无 ffmpeg 或转码失败时沿用原始格式

    try:
        answer, tools, used, meta = await agent.process_audio_native(
            prompt, data, audio_format=fmt, enable_search=enable_search
        )
        transcript = None
        if "转写：" in answer:
            parts = answer.split("总结：", 1)
            transcript = parts[0].replace("转写：", "").strip()
        return AnalyzeResponse(
            request_type=RequestType.AUDIO,
            model=OLLAMA_AUDIO_MODEL,
            answer=answer,
            transcript=transcript,
            tool_calls=tools,
            used_search=used,
            meta=meta,
        )
    except Exception as e:
        if not WHISPER_FALLBACK:
            raise
        transcript = stt.transcribe_audio(data, filename=file.filename or "audio.wav")
        answer, tools, used, meta = await agent.process_audio_transcript(
            prompt, transcript, enable_search=enable_search
        )
        meta["fallback"] = "whisper_stt"
        meta["native_error"] = str(e)
        return AnalyzeResponse(
            request_type=RequestType.AUDIO,
            model=OLLAMA_AUDIO_MODEL,
            answer=answer,
            transcript=transcript,
            meta=meta,
            tool_calls=tools,
            used_search=used,
        )
