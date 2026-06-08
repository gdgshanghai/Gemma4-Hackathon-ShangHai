"""将上传音频规范为 Gemma4 E4B-mm 友好的 16kHz mono WAV。"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def normalize_audio(audio_bytes: bytes, filename: str = "audio.wav") -> tuple[bytes, str]:
    """
    经 ffmpeg 转为 16kHz 单声道 PCM WAV。
    纯音调/空文件可能仍无法被模型识别为语音，需真实人声或 TTS。
    """
    if not audio_bytes or len(audio_bytes) < 256:
        raise ValueError("音频文件过小或为空")

    suffix = Path(filename or "audio.wav").suffix or ".wav"
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        src = td_path / f"in{suffix}"
        dst = td_path / "out.wav"
        src.write_bytes(audio_bytes)
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not dst.exists():
            logger.warning("ffmpeg 转码失败，使用原始字节: %s", proc.stderr[-400:])
            return audio_bytes, "wav" if suffix.lower() == ".wav" else suffix.lstrip(".")
        return dst.read_bytes(), "wav"
