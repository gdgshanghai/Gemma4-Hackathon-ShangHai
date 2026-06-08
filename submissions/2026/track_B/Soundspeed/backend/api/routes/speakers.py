"""说话人管理端点。

管理说话人台账（CRUD）及声纹 enrollment。

端点：
  GET    /api/v1/speakers              列出所有说话人
  POST   /api/v1/speakers              新建说话人（仅名字，未录声纹）
  GET    /api/v1/speakers/{id}         获取单个说话人
  PATCH  /api/v1/speakers/{id}         更新显示名
  DELETE /api/v1/speakers/{id}         删除说话人
  POST   /api/v1/speakers/{id}/enroll  上传音频样本，提取并存储声纹 embedding

Enrollment 音频格式：
  - WAV 文件（推荐）：multipart/form-data, field name = "file"
  - 原始 PCM int16：multipart/form-data, field name = "file"，需附带 ?sample_rate=16000
  建议时长 ≥15s 干净独白，短于 2s 拒绝请求。
  服务端自动重采样至 16kHz 单声道（如果必要）。

diarization_engine 从 request.app.state.diarization_engine 读取（可 None —— 无 HF token 时）。
"""
from __future__ import annotations

import asyncio
import wave
import io
import logging

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from backend.api.auth import require_admin
from backend.db.dal import DAL
from backend.diarization.enroll_recorder import (
    CaptureActiveError,
    EnrollBusyError,
    EnrollRecorder,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/speakers", tags=["speakers"])

SAMPLE_RATE = 16000
MIN_ENROLL_SECONDS = 2.0  # 最短录入时长；不足时返回 400
MIN_ENROLL_RMS = 30.0  # int16 RMS 静音阈值（≈ -60dBFS）；低于此判定现场麦没收到声音


# ── DTO ──────────────────────────────────────────────────────────────────────


class SpeakerOut(BaseModel):
    speaker_id: int
    display_name: str
    has_enrollment: bool
    sample_count: int
    scope_key: str | None = None
    created_at: float
    updated_at: float


class CreateSpeakerIn(BaseModel):
    display_name: str
    scope_key: str | None = None


class UpdateSpeakerIn(BaseModel):
    display_name: str


# ── helpers ──────────────────────────────────────────────────────────────────


def _dal(request: Request) -> DAL:
    return request.app.state.orchestrator.dal


def _enroll_recorder(request: Request) -> EnrollRecorder:
    rec = getattr(request.app.state, "enroll_recorder", None)
    if rec is None:
        raise HTTPException(status_code=503, detail="实时采集未启用，无法用现场麦录声纹")
    return rec


def _spk_to_out(d: dict) -> SpeakerOut:
    return SpeakerOut(
        speaker_id=d["speaker_id"],
        display_name=d["display_name"],
        has_enrollment=d.get("embedding") is not None,
        sample_count=d.get("sample_count", 0),
        scope_key=d.get("scope_key"),
        created_at=d["created_at"],
        updated_at=d["updated_at"],
    )


def _parse_audio_bytes(data: bytes, sample_rate: int) -> np.ndarray:
    """将上传的字节解析为 int16 16kHz 单声道 numpy 数组。

    支持 WAV 格式（自动检测）和原始 int16 PCM。
    如果 WAV 采样率 != 16kHz，尝试线性重采样（轻量级，仅整数倍比例）。
    如果非整数倍，抛出 ValueError 提示调用方先用客户端重采样。
    """
    # 检测 WAV 魔数 "RIFF"
    if len(data) >= 4 and data[:4] == b"RIFF":
        return _parse_wav(data)

    # 原始 PCM int16
    if len(data) % 2 != 0:
        raise ValueError("raw PCM 数据长度不是偶数字节（非 int16）")
    return np.frombuffer(data, dtype=np.int16).copy()


def _parse_wav(data: bytes) -> np.ndarray:
    """解析 WAV 文件，返回 int16 16kHz 单声道 numpy 数组。"""
    with wave.open(io.BytesIO(data)) as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sampwidth != 2:
        raise ValueError(f"WAV 采样位深必须为 16-bit（实际 {sampwidth * 8}-bit）")

    samples = np.frombuffer(raw, dtype=np.int16).copy()

    # 多声道 → 取首通道（mono）
    if n_channels > 1:
        samples = samples.reshape(-1, n_channels)[:, 0].copy()

    # 重采样至 16kHz（仅支持整数倍降采样）
    if framerate != SAMPLE_RATE:
        if framerate % SAMPLE_RATE == 0:
            factor = framerate // SAMPLE_RATE
            samples = samples[::factor]
        elif SAMPLE_RATE % framerate == 0:
            # 上采样（罕见，通常无需）
            factor = SAMPLE_RATE // framerate
            samples = np.repeat(samples, factor)
        else:
            raise ValueError(
                f"WAV 采样率 {framerate}Hz 无法简单重采样至 {SAMPLE_RATE}Hz，"
                f"请在客户端先转换为 16kHz 单声道 WAV"
            )

    return samples


def _rms_int16(pcm: np.ndarray) -> float:
    if len(pcm) == 0:
        return 0.0
    return float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))


async def _finalize_enrollment(
    dal: DAL, engine, speaker_id: int, pcm: np.ndarray
) -> SpeakerOut:
    """enroll 共用尾巴：静音守卫 → 时长守卫 → 提 embedding → 存库 → SpeakerOut。

    upload 端点与现场麦 stop 端点共用，保证两条路径一致。
    """
    if _rms_int16(pcm) < MIN_ENROLL_RMS:
        raise HTTPException(
            status_code=400,
            detail="音频能量过低，几乎听不到声音（检查麦克风是否静音 / 是否对准）",
        )
    duration_s = len(pcm) / SAMPLE_RATE
    if duration_s < MIN_ENROLL_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"音频时长 {duration_s:.1f}s 太短（最短 {MIN_ENROLL_SECONDS}s）",
        )

    loop = asyncio.get_running_loop()
    try:
        embedding = await loop.run_in_executor(None, engine.extract_embedding, pcm)
    except Exception as exc:
        logger.exception("enrollment 提取 embedding 失败 speaker_id=%d", speaker_id)
        raise HTTPException(status_code=500, detail=f"embedding 提取失败: {exc}")

    if embedding is None:
        raise HTTPException(status_code=500, detail="embedding 模型未能返回结果")

    dal.update_speaker_embedding(
        speaker_id=speaker_id,
        embedding_blob=embedding.astype(np.float32).tobytes(),
        sample_count=1,
    )
    logger.info(
        "说话人 %d 声纹已录入（时长=%.1fs, 维度=%d）",
        speaker_id, duration_s, embedding.shape[0],
    )
    return _spk_to_out(dal.get_speaker(speaker_id))  # type: ignore[arg-type]


# ── 端点 ──────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[SpeakerOut])
async def list_speakers(
    request: Request,
    scope_key: str | None = Query(default=None),
    _: str = Depends(require_admin),
):
    """列出所有说话人（含是否已录入声纹）。"""
    dal = _dal(request)
    rows = dal.list_speakers(scope_key=scope_key)
    return [_spk_to_out(r) for r in rows]


@router.post("", response_model=SpeakerOut, status_code=201)
async def create_speaker(
    body: CreateSpeakerIn,
    request: Request,
    _: str = Depends(require_admin),
):
    """新建说话人（仅登记名字，尚未录入声纹）。"""
    dal = _dal(request)
    sid = dal.insert_speaker(
        display_name=body.display_name,
        scope_key=body.scope_key,
        sample_count=0,  # 尚未 enroll：0 个声纹样本（enroll 后置 1）
    )
    row = dal.get_speaker(sid)
    if row is None:
        raise HTTPException(status_code=500, detail="创建后找不到记录")
    return _spk_to_out(row)


@router.get("/{speaker_id}", response_model=SpeakerOut)
async def get_speaker(
    speaker_id: int,
    request: Request,
    _: str = Depends(require_admin),
):
    dal = _dal(request)
    row = dal.get_speaker(speaker_id)
    if row is None:
        raise HTTPException(status_code=404, detail="说话人不存在")
    return _spk_to_out(row)


@router.patch("/{speaker_id}", response_model=SpeakerOut)
async def update_speaker(
    speaker_id: int,
    body: UpdateSpeakerIn,
    request: Request,
    _: str = Depends(require_admin),
):
    """更新说话人显示名（演员姓名绑定）。"""
    dal = _dal(request)
    if dal.get_speaker(speaker_id) is None:
        raise HTTPException(status_code=404, detail="说话人不存在")
    dal.update_speaker_name(speaker_id, body.display_name)
    return _spk_to_out(dal.get_speaker(speaker_id))  # type: ignore[arg-type]


@router.delete("/{speaker_id}", status_code=204)
async def delete_speaker(
    speaker_id: int,
    request: Request,
    _: str = Depends(require_admin),
):
    dal = _dal(request)
    if dal.get_speaker(speaker_id) is None:
        raise HTTPException(status_code=404, detail="说话人不存在")
    dal.delete_speaker(speaker_id)


@router.post("/{speaker_id}/enroll", response_model=SpeakerOut)
async def enroll_speaker(
    speaker_id: int,
    request: Request,
    file: UploadFile = File(..., description="WAV 或原始 int16 PCM（16kHz 单声道）"),
    sample_rate: int = Query(default=16000, description="仅 raw PCM 时有效；WAV 自动读取"),
    _: str = Depends(require_admin),
):
    """录入说话人声纹样本。

    上传 ≥2s（建议 ≥15s）干净独白音频，后台提取 wespeaker embedding 并存储到台账。
    enrollment 成功后，diarization 回填时该说话人将被自动识别并标记名字。

    音频格式：
    - 推荐：WAV 16kHz 单声道 16-bit（浏览器 MediaRecorder 默认可导出）
    - 兼容：原始 int16 PCM bytes（需 ?sample_rate=16000）
    """
    dal = _dal(request)
    if dal.get_speaker(speaker_id) is None:
        raise HTTPException(status_code=404, detail="说话人不存在")

    engine = getattr(request.app.state, "diarization_engine", None)
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="diarization 引擎未启用（未设置 SOUNDSPEED_HF_TOKEN）",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        pcm = _parse_audio_bytes(data, sample_rate)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return await _finalize_enrollment(dal, engine, speaker_id, pcm)


@router.post("/{speaker_id}/enroll/start", status_code=202)
async def enroll_start(
    speaker_id: int,
    request: Request,
    _: str = Depends(require_admin),
):
    """开始用后端现场麦录声纹（与 Capture 同设备）。"""
    dal = _dal(request)
    if dal.get_speaker(speaker_id) is None:
        raise HTTPException(status_code=404, detail="说话人不存在")
    engine = getattr(request.app.state, "diarization_engine", None)
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="diarization 引擎未启用（未设置 SOUNDSPEED_HF_TOKEN）",
        )
    rec = _enroll_recorder(request)
    # 注意：录音器是单例、不绑定 speaker_id —— start 与 stop 必须配对到同一个 speaker
    # （前端用 per-open 的 keyed 弹窗保证），否则 stop 会把这段音频提取的声纹写到另一个演员名下。
    try:
        rec.start()
    except CaptureActiveError:
        raise HTTPException(status_code=409, detail="正在 Capture，无法同时用现场麦录声纹")
    except EnrollBusyError:
        raise HTTPException(status_code=409, detail="已有一段声纹录音在进行")
    return {"status": "recording", "speaker_id": speaker_id}


@router.post("/{speaker_id}/enroll/stop", response_model=SpeakerOut)
async def enroll_stop(
    speaker_id: int,
    request: Request,
    _: str = Depends(require_admin),
):
    """停止现场麦录音，提声纹存库。无论成败都先 stop 释放设备。"""
    rec = _enroll_recorder(request)
    pcm = rec.stop()  # 总是先释放设备
    dal = _dal(request)
    if dal.get_speaker(speaker_id) is None:
        raise HTTPException(status_code=404, detail="说话人不存在")
    engine = getattr(request.app.state, "diarization_engine", None)
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="diarization 引擎未启用（未设置 SOUNDSPEED_HF_TOKEN）",
        )
    return await _finalize_enrollment(dal, engine, speaker_id, pcm)


@router.post("/{speaker_id}/enroll/cancel", status_code=204)
async def enroll_cancel(
    speaker_id: int,
    request: Request,
    _: str = Depends(require_admin),
):
    """放弃现场麦录音并释放设备（弹窗关闭 / 出错时）。"""
    rec = getattr(request.app.state, "enroll_recorder", None)
    if rec is not None:
        rec.abort()
