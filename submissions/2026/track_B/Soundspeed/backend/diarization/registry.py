"""SpeakerRegistry：把本 take diarization 的 local cluster 映射到说话人名。

匹配范围 = 本 take 挂的已注册演员（candidates，调用方从 DAL.list_take_speakers 传入）：
  - 命中（cosine 相似度 ≥ threshold）→ 该演员的 display_name
  - 未命中 / 本 take 没挂演员 → per-take 匿名 "说话人N"（仅本 take 标签，**不持久化**）

无状态、无 DB 依赖：注册演员台账只通过 speakers 路由（设置面板）维护，diarization
不再往里自动插匿名说话人。embedding 必须与 diarize 同空间（community-1，实测 256 维）。
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

# cosine 相似度阈值：>= 此值视为同一说话人。真机需按实际 embedding 标定（D2 [手动测试]）。
_DEFAULT_THRESHOLD = 0.5


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """两个向量的 cosine 相似度。维度不一致 / 全零 → 0.0（不匹配，绝不抛异常）。"""
    if a.shape != b.shape:
        return 0.0
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class SpeakerRegistry:
    """无状态映射器：local cluster embedding → 演员名 / 匿名说话人N。

    threshold：cosine 相似度阈值，>= 此值视为命中某注册演员（默认 0.5）。
    """

    def __init__(self, threshold: float = _DEFAULT_THRESHOLD) -> None:
        self._threshold = threshold

    def resolve(
        self,
        local_embeddings: dict[str, np.ndarray | None],
        candidates: list[dict] | None = None,
    ) -> dict[str, str]:
        """把本 take 的 {local_label: embedding} 映射到 {local_label: 显示名}。

        candidates: 本 take 挂的已注册演员 dict 列表（含 display_name + embedding）。
        命中演员 → 演员名；未命中 / candidates 为空 → 顺位匿名 "说话人N"（per-take，不入库）。
        """
        matchable = [c for c in (candidates or []) if c.get("embedding") is not None]

        mapping: dict[str, str] = {}
        anon = 0
        for local_label, embedding in local_embeddings.items():
            name = self._match(embedding, matchable)
            if name is None:
                anon += 1
                name = f"说话人{anon}"
                logger.debug("local %s → 匿名 %s", local_label, name)
            else:
                logger.debug("local %s → 注册演员 %s", local_label, name)
            mapping[local_label] = name
        return mapping

    def _match(
        self,
        embedding: np.ndarray | None,
        candidates: list[dict],
    ) -> str | None:
        """在 candidates 里找 cosine 最近的演员，超过阈值返回其 display_name，否则 None。"""
        if embedding is None or not candidates:
            return None

        best_sim = -1.0
        best_name: str | None = None
        for c in candidates:
            stored = c.get("embedding")
            if stored is None:
                continue
            sim = _cosine_similarity(embedding, stored)
            if sim > best_sim:
                best_sim = sim
                best_name = c["display_name"]

        if best_sim >= self._threshold:
            return best_name
        return None
