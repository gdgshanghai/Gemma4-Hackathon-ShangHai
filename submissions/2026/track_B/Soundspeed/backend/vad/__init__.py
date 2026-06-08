"""Voice Activity Layer：AudioChunk 流 → 每声道端点切段 → SpeechSegment。

audio-input-layer 的直接下游、ASRService 的直接上游。
详见 docs/specs/2026-06-02-voice-activity-layer.md。
"""
from backend.vad.models import SpeechSegment, VadConfig
from backend.vad.segmenter import ChannelVADSegmenter

__all__ = ["SpeechSegment", "VadConfig", "ChannelVADSegmenter"]
