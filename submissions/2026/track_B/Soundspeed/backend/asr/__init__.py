"""ASR 层：实时语音转文字（whisper.cpp via pywhispercpp）。

Phase 1 只含实时段级转录（whisper_runner）；diarization / enrollment / 角色匹配
是 take.end 后的批量阶段（Phase 2，按 2026-06-02-realtime-diarization-voicenote-design）。
"""
from backend.asr.config import DEFAULT_ASR_MODEL, ASRConfig
from backend.asr.whisper_runner import WhisperRunner

__all__ = ["DEFAULT_ASR_MODEL", "ASRConfig", "WhisperRunner"]
