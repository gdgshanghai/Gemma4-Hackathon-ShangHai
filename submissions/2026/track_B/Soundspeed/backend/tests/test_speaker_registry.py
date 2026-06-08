"""SpeakerRegistry 单测（重构后）：scoped 匹配本 take 演员 + 匿名说话人N。

无状态、无 DB：candidates（本 take 挂的注册演员）由调用方传入；未命中 → per-take 说话人N。
"""
from __future__ import annotations

import numpy as np

from backend.diarization.registry import SpeakerRegistry, _cosine_similarity


def _emb(*vals: float) -> np.ndarray:
    return np.array(vals, dtype=np.float32)


def _actor(name: str, emb: np.ndarray | None) -> dict:
    return {"speaker_id": 1, "display_name": name, "embedding": emb}


# ── cosine 防御 ──────────────────────────────────────────────────────────────────


def test_cosine_same_direction_is_one():
    assert _cosine_similarity(_emb(1, 0, 0), _emb(5, 0, 0)) == 1.0


def test_cosine_orthogonal_is_zero():
    assert _cosine_similarity(_emb(1, 0), _emb(0, 1)) == 0.0


def test_cosine_dim_mismatch_returns_zero_not_crash():
    assert _cosine_similarity(_emb(1, 0, 0), _emb(1, 0)) == 0.0


# ── resolve：匹配本 take 演员 ──────────────────────────────────────────────────────


def test_no_candidates_all_anonymous():
    reg = SpeakerRegistry()
    out = reg.resolve({"SPEAKER_00": _emb(1, 0), "SPEAKER_01": _emb(0, 1)}, candidates=[])
    assert set(out.values()) == {"说话人1", "说话人2"}


def test_none_candidates_all_anonymous():
    reg = SpeakerRegistry()
    out = reg.resolve({"SPEAKER_00": _emb(1, 0)})  # candidates 默认 None
    assert out == {"SPEAKER_00": "说话人1"}


def test_matches_attached_actor():
    reg = SpeakerRegistry()
    cands = [_actor("张三", _emb(1, 0, 0))]
    out = reg.resolve({"SPEAKER_00": _emb(3, 0, 0)}, candidates=cands)  # 同向 cos=1
    assert out == {"SPEAKER_00": "张三"}


def test_unmatched_cluster_falls_back_to_anonymous():
    reg = SpeakerRegistry()
    cands = [_actor("张三", _emb(1, 0, 0))]
    # 一个命中张三，一个正交（不命中）→ 匿名说话人1
    out = reg.resolve(
        {"SPEAKER_00": _emb(1, 0, 0), "SPEAKER_01": _emb(0, 1, 0)},
        candidates=cands,
    )
    assert out["SPEAKER_00"] == "张三"
    assert out["SPEAKER_01"] == "说话人1"


def test_below_threshold_is_anonymous():
    reg = SpeakerRegistry(threshold=0.99)
    cands = [_actor("张三", _emb(1, 1, 0))]
    out = reg.resolve({"SPEAKER_00": _emb(1, 0, 0)}, candidates=cands)  # cos≈0.707<0.99
    assert out == {"SPEAKER_00": "说话人1"}


def test_candidate_without_embedding_ignored():
    reg = SpeakerRegistry()
    cands = [_actor("没录声纹的", None)]
    out = reg.resolve({"SPEAKER_00": _emb(1, 0)}, candidates=cands)
    assert out == {"SPEAKER_00": "说话人1"}


def test_none_embedding_cluster_is_anonymous():
    reg = SpeakerRegistry()
    cands = [_actor("张三", _emb(1, 0))]
    out = reg.resolve({"SPEAKER_00": None}, candidates=cands)
    assert out == {"SPEAKER_00": "说话人1"}


def test_two_clusters_match_same_actor():
    reg = SpeakerRegistry()
    cands = [_actor("张三", _emb(1, 0, 0))]
    out = reg.resolve(
        {"SPEAKER_00": _emb(2, 0, 0), "SPEAKER_01": _emb(5, 0, 0)},
        candidates=cands,
    )
    assert out == {"SPEAKER_00": "张三", "SPEAKER_01": "张三"}
