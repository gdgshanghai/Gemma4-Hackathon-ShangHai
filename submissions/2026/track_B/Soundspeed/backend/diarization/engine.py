"""DiarizationEngine：包 pyannote.audio 4.0 批量说话人分离。

输入：int16 16kHz 单声道 numpy 数组（内存，不接收文件路径）。
输出：list[SpeakerTurn]，含 start_s / end_s / label / embedding。

懒加载：首次调用 diarize() 时才从 HuggingFace 下载模型权重。
CUDA 可用时自动移至 GPU（RTX 3060 Ti 推荐）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000  # 固定 16kHz


@dataclass
class SpeakerTurn:
    """一段说话人区间，含局部标签和（可选）embedding 质心。"""

    start_s: float
    end_s: float
    label: str          # pyannote 局部标签，如 "SPEAKER_00"
    embedding: np.ndarray | None = field(default=None, repr=False)


class DiarizationEngine:
    """pyannote.audio 4.0 批量说话人分离引擎（懒加载）。

    hf_token：HuggingFace access token，用于访问 gated 模型。
    model_id：diarization pipeline 模型 ID（默认 pyannote/speaker-diarization-community-1，pyannote.audio 4.0 原生）。

    声纹 embedding 统一用 pipeline 自带的 community-1（实测产出 256 维，pipeline 内部用
    resnet34 embedder）：diarize 取 per-speaker centroid，enroll（extract_embedding）取主
    说话人 centroid——两条路径走同一 pipeline、同一 output.speaker_embeddings，故同空间、
    同维度，才能跨 take / 与注册演员比对。
    """

    def __init__(
        self,
        hf_token: str,
        model_id: str = "pyannote/speaker-diarization-community-1",
        cache_dir: str | None = None,
        *,
        pipeline: Any = None,
        device: Any = None,
    ) -> None:
        self._hf_token = hf_token
        self._model_id = model_id
        self._cache_dir = cache_dir  # HuggingFace 模型缓存目录（None → 默认 ~/.cache/huggingface）
        # pipeline / device 默认 None，首次用时懒加载真实模型；
        # 测试可注入假 pipeline 绕过加载（_ensure_loaded 见到非 None pipeline 即短路）。
        self._pipeline: Any = pipeline
        self._device: Any = device

    def _ensure_loaded(self) -> None:
        if self._pipeline is not None:
            return
        import os

        import torch
        from pyannote.audio import Pipeline

        logger.info("加载 pyannote diarization pipeline: %s", self._model_id)
        self._pipeline = Pipeline.from_pretrained(
            self._model_id,
            token=self._hf_token,
            cache_dir=self._cache_dir,
        )

        # 设备选择：默认 auto（有 CUDA 用 CUDA）；SOUNDSPEED_DIARIZATION_DEVICE=cpu 可强制 CPU。
        # 8GB 显存上 whisper + pyannote 同跑易 OOM（CUBLAS_ALLOC_FAILED），此时可切 CPU。
        pref = os.environ.get("SOUNDSPEED_DIARIZATION_DEVICE", "auto").lower()
        if torch.cuda.is_available() and pref != "cpu":
            self._device = torch.device("cuda")
            self._pipeline.to(self._device)
            logger.info("pyannote pipeline 已移至 CUDA")
        else:
            self._device = torch.device("cpu")
            reason = "SOUNDSPEED_DIARIZATION_DEVICE=cpu" if pref == "cpu" else "CUDA 不可用"
            logger.warning("pyannote 将在 CPU 运行（%s，速度较慢）", reason)

    @staticmethod
    def _free_cuda_cache() -> None:
        """推理前释放 torch 的 CUDA 缓存，缓解与 whisper 共享 8GB 显存时的碎片化 OOM。"""
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def diarize(
        self, pcm_int16: np.ndarray, *, num_speakers: int | None = None
    ) -> list[SpeakerTurn]:
        """对整段 int16 16kHz 单声道 PCM 进行说话人分离。

        返回 SpeakerTurn 列表，按时间升序排列。
        若 pcm_int16 太短（< 1 秒），返回空列表。

        num_speakers：说话人数先验（来自本 take 选定的参演演员数）。给定（≥1）时作为
            pyannote 的 num_speakers 约束，避免单麦/相似音色下自动聚类把多人塌成一人
            （用户选了 2 人却只分出 1 人的根因修复）。None → 自动判定（旧行为）。
        """
        if len(pcm_int16) < SAMPLE_RATE:  # < 1 秒
            logger.debug("音频太短 (%d 样本 < 1s)，跳过 diarization", len(pcm_int16))
            return []

        self._ensure_loaded()

        import torch

        # int16 → float32 [-1, 1]
        audio_float = pcm_int16.astype(np.float32) / 32768.0
        waveform = torch.from_numpy(audio_float).unsqueeze(0)  # (1, samples)

        self._free_cuda_cache()
        pipeline_kwargs: dict[str, int] = {}
        if num_speakers is not None and num_speakers >= 1:
            pipeline_kwargs["num_speakers"] = num_speakers
            logger.info("diarization 用人数先验 num_speakers=%d（来自本 take 选定演员）", num_speakers)
        output = self._pipeline(
            {"waveform": waveform, "sample_rate": SAMPLE_RATE}, **pipeline_kwargs
        )

        # pyannote.audio 4.0：community-1 返回 DiarizeOutput(speaker_diarization=Annotation,
        # speaker_embeddings=(n_spk, dim) 按 labels() 顺序)。3.x 直接返回 Annotation（无
        # speaker_diarization 属性）→ getattr 回退到 output 自身。
        annotation = getattr(output, "speaker_diarization", output)
        turns = self._turns_from_diarization(annotation)

        # 每说话人 embedding（跨 take 声纹比对）：用 4.0 pipeline 直接产出的 centroids
        # （community-1，实测 256 维）。enroll 走同一 pipeline 同一属性，故同空间可比。
        # pipeline 没给（无活跃说话人 / OracleClustering）时 embedding 留 None，registry 直接顺位新号。
        speaker_embeddings = getattr(output, "speaker_embeddings", None)
        if speaker_embeddings is not None and len(speaker_embeddings) > 0:
            turns = self._attach_pipeline_embeddings(turns, annotation, speaker_embeddings)

        logger.debug("diarization 完成：%d 个 turn，涉及 %d 个 speaker", len(turns), len({t.label for t in turns}))
        return turns

    @staticmethod
    def _attach_pipeline_embeddings(
        turns: list[SpeakerTurn],
        annotation: Any,
        speaker_embeddings: np.ndarray,
    ) -> list[SpeakerTurn]:
        """用 pipeline 直接产出的 per-speaker embedding 回填到 turns。

        speaker_embeddings 形状 (n_speakers, dim)，按 annotation.labels() 顺序排列
        （pyannote 4.0 DiarizeOutput 契约）。
        """
        labels = list(annotation.labels())
        label_emb = {
            lbl: speaker_embeddings[i]
            for i, lbl in enumerate(labels)
            if i < len(speaker_embeddings)
        }
        return [
            SpeakerTurn(
                start_s=t.start_s, end_s=t.end_s, label=t.label,
                embedding=label_emb.get(t.label),
            )
            for t in turns
        ]

    @staticmethod
    def _turns_from_diarization(diarization: Any) -> list[SpeakerTurn]:
        """把 pyannote diarization annotation 转成 SpeakerTurn 列表（纯映射，无 torch）。

        diarization 须支持 itertracks(yield_label=True) → (segment, _, label)，
        segment 有 .start / .end（秒）。抽出此处便于单测（注入假 annotation）。
        """
        return [
            SpeakerTurn(start_s=segment.start, end_s=segment.end, label=label)
            for segment, _, label in diarization.itertracks(yield_label=True)
        ]

    def extract_embedding(self, pcm_int16: np.ndarray) -> "np.ndarray | None":
        """从一段音频提取声纹 embedding（用于 enrollment），与 diarize 同空间（community-1，实测 256 维）。

        做法：把音频喂进 diarization pipeline，取**说话时长最长的说话人**的 centroid。
        enroll 应是单人干净独白（建议 ≥15s）；若检测到多说话人，取主说话人并告警。
        失败 / 无有效说话人 → None。
        """
        if len(pcm_int16) < SAMPLE_RATE:  # < 1s
            logger.warning("enrollment 音频太短 (%d 样本 < 1s)", len(pcm_int16))
            return None

        self._ensure_loaded()
        import torch

        if len(pcm_int16) < SAMPLE_RATE * 2:
            logger.warning(
                "enrollment 音频仅 %.1fs，声纹质量可能较差（建议 ≥15s）",
                len(pcm_int16) / SAMPLE_RATE,
            )

        audio_float = pcm_int16.astype(np.float32) / 32768.0
        waveform = torch.from_numpy(audio_float).unsqueeze(0)
        self._free_cuda_cache()
        try:
            output = self._pipeline({"waveform": waveform, "sample_rate": SAMPLE_RATE})
        except Exception:
            logger.warning("enrollment: pipeline 推理失败", exc_info=True)
            return None

        annotation = getattr(output, "speaker_diarization", output)
        embeddings = getattr(output, "speaker_embeddings", None)
        emb = self._dominant_embedding(annotation, embeddings)
        if emb is None:
            logger.warning("enrollment: pipeline 未产出有效说话人 embedding")
        return emb

    @staticmethod
    def _dominant_embedding(
        annotation: Any,
        speaker_embeddings: "np.ndarray | None",
    ) -> "np.ndarray | None":
        """取说话时长最长说话人的 centroid（按 annotation.labels() 顺序索引 embeddings）。

        纯逻辑（无 torch），便于单测。无 embedding / 无说话人 → None。
        """
        if speaker_embeddings is None or len(speaker_embeddings) == 0:
            return None
        labels = list(annotation.labels())
        if not labels:
            return None
        dominant = max(labels, key=lambda lbl: annotation.label_duration(lbl))
        idx = labels.index(dominant)
        if idx >= len(speaker_embeddings):
            return None
        if len(labels) > 1:
            logger.warning(
                "enrollment 检测到 %d 个说话人，取主说话人 %s（建议用单人干净独白）",
                len(labels), dominant,
            )
        return np.array(speaker_embeddings[idx], dtype=np.float32).ravel()
