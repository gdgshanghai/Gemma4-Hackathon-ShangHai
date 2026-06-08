"""Diarization 包：take 结束后批量回填说话人标签。

公共接口：
  TakeAudioBuffer  — take 期间累积 ch1 PCM（内存，不落盘）
  DiarizationEngine — 包 pyannote.audio 4.0 批量分离说话人
  SpeakerRegistry  — 跨 take 声纹台账（cosine 匹配 → 全局编号/演员名）
  DiarizationBackfill — take.end 异步链：buffer→engine→registry→align→DAL→L2
"""
from backend.diarization.buffer import TakeAudioBuffer
from backend.diarization.engine import DiarizationEngine, SpeakerTurn
from backend.diarization.registry import SpeakerRegistry
from backend.diarization.backfill import DiarizationBackfill

__all__ = [
    "TakeAudioBuffer",
    "DiarizationEngine",
    "SpeakerTurn",
    "SpeakerRegistry",
    "DiarizationBackfill",
]
