"""语音转文字（STT），非 TTS。"""

from __future__ import annotations

import io
import logging
import math
import shutil
import subprocess
import tempfile
from array import array
from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel

from gemma_api.config import WHISPER_COMPUTE, WHISPER_DEVICE, WHISPER_MODEL

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_whisper() -> WhisperModel:
    logger.info("加载 Whisper 模型: %s (%s)", WHISPER_MODEL, WHISPER_DEVICE)
    return WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)


def transcribe_audio(data: bytes, filename: str = "audio.wav") -> str:
    suffix = Path(filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        path = f.name
    try:
        model = _get_whisper()
        segments, info = model.transcribe(path, language="zh", vad_filter=True)
        text = "".join(seg.text for seg in segments).strip()
        if not text:
            segments, info = model.transcribe(path, language="zh", vad_filter=False)
            text = "".join(seg.text for seg in segments).strip()
            logger.info("STT VAD 空结果后重试完成 lang=%s len=%d", info.language, len(text))
        else:
            logger.info("STT 完成 lang=%s len=%d", info.language, len(text))
        return text or "(未识别到有效语音内容)"
    finally:
        Path(path).unlink(missing_ok=True)


def inspect_audio_file(path: str) -> dict:
    """Return lightweight diagnostics for a received audio file."""
    p = Path(path)
    diag = {"path": str(p), "size_bytes": p.stat().st_size if p.exists() else 0}

    if shutil.which("ffprobe"):
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration:stream=codec_name,sample_rate,channels",
                    "-of",
                    "json",
                    str(p),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
            diag["ffprobe"] = json_loads_safe(result.stdout)
        except Exception as e:
            diag["ffprobe_error"] = str(e)

    if shutil.which("ffmpeg"):
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(p),
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-f",
                    "s16le",
                    "-",
                ],
                capture_output=True,
                timeout=20,
                check=True,
            )
            raw = result.stdout
            if raw:
                samples = array("h")
                samples.frombytes(raw)
                peak = max(abs(s) for s in samples) if samples else 0
                rms = math.sqrt(sum(s * s for s in samples) / len(samples)) if samples else 0.0
                diag["decoded_samples"] = len(samples)
                diag["duration_sec_est"] = round(len(samples) / 16000, 3)
                diag["peak"] = peak
                diag["rms"] = round(rms, 2)
                diag["rms_dbfs"] = round(20 * math.log10(max(rms, 1e-9) / 32768), 2)
                diag["likely_silent"] = peak < 200 or rms < 30
            else:
                diag["decoded_samples"] = 0
                diag["likely_silent"] = True
        except Exception as e:
            diag["ffmpeg_decode_error"] = str(e)

    return diag


def json_loads_safe(value: str) -> dict:
    import json

    try:
        return json.loads(value)
    except Exception:
        return {}
