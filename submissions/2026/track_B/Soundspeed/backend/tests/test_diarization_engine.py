"""DiarizationEngine 单测（切片 2）：短音频短路 / turn 映射 / 注入短路加载。

不触碰真实 pyannote / torch：长度守卫在加载前返回；映射用纯 helper + 假 annotation；
注入 pipeline 使 _ensure_loaded 短路。真实模型质量留 [手动测试] smoke。
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from backend.diarization.engine import DiarizationEngine, SpeakerTurn


def test_short_audio_returns_empty_without_loading():
    eng = DiarizationEngine(hf_token="x")
    out = eng.diarize(np.zeros(8000, dtype=np.int16))  # 0.5s < 1s 守卫
    assert out == []
    assert eng._pipeline is None  # 未触发加载


def test_turns_from_diarization_maps_segments():
    class _FakeDia:
        def itertracks(self, yield_label=True):
            yield SimpleNamespace(start=0.0, end=1.5), None, "SPEAKER_00"
            yield SimpleNamespace(start=2.0, end=3.25), None, "SPEAKER_01"

    turns = DiarizationEngine._turns_from_diarization(_FakeDia())
    assert all(isinstance(t, SpeakerTurn) for t in turns)
    assert [(t.start_s, t.end_s, t.label) for t in turns] == [
        (0.0, 1.5, "SPEAKER_00"),
        (2.0, 3.25, "SPEAKER_01"),
    ]


def test_turns_from_empty_diarization():
    class _Empty:
        def itertracks(self, yield_label=True):
            return iter(())

    assert DiarizationEngine._turns_from_diarization(_Empty()) == []


def test_diarize_passes_num_speakers_to_pipeline():
    """num_speakers 先验透传到 pyannote pipeline；默认（None）不带该约束。"""
    calls: dict = {}

    class _FakePipe:
        def __call__(self, data, num_speakers=None):
            calls["num_speakers"] = num_speakers
            return SimpleNamespace(
                speaker_diarization=SimpleNamespace(
                    itertracks=lambda yield_label=True: iter(
                        [(SimpleNamespace(start=0.0, end=1.0), None, "SPEAKER_00")]
                    )
                ),
                speaker_embeddings=None,
            )

    eng = DiarizationEngine(hf_token="x", pipeline=_FakePipe())
    pcm = np.zeros(16000 * 2, dtype=np.int16)  # 2s ≥ 1s 守卫

    eng.diarize(pcm, num_speakers=2)
    assert calls["num_speakers"] == 2  # 选了 2 人 → 约束 pyannote 分 2 个
    eng.diarize(pcm)
    assert calls["num_speakers"] is None  # 默认不约束（自动判定）


def test_attach_pipeline_embeddings_maps_by_label_order():
    """pyannote 4.0：speaker_embeddings 按 annotation.labels() 顺序，按 label 回填到 turns。"""
    class _Ann:
        def labels(self):
            return ["SPEAKER_00", "SPEAKER_01"]

    turns = [
        SpeakerTurn(0.0, 1.0, "SPEAKER_01"),
        SpeakerTurn(1.0, 2.0, "SPEAKER_00"),
        SpeakerTurn(2.0, 3.0, "SPEAKER_01"),
    ]
    emb = np.array([[1, 0], [0, 1]], dtype=np.float32)  # idx0→SPEAKER_00, idx1→SPEAKER_01
    out = DiarizationEngine._attach_pipeline_embeddings(turns, _Ann(), emb)
    # SPEAKER_01 → emb[1]=[0,1]，SPEAKER_00 → emb[0]=[1,0]
    assert out[0].embedding.tolist() == [0, 1]
    assert out[1].embedding.tolist() == [1, 0]
    assert out[2].embedding.tolist() == [0, 1]


def test_dominant_embedding_picks_longest_speaker():
    """enroll：取说话时长最长说话人的 centroid（按 labels() 顺序索引）。"""
    class _Ann:
        def labels(self):
            return ["SPEAKER_00", "SPEAKER_01"]

        def label_duration(self, lbl):
            return {"SPEAKER_00": 2.0, "SPEAKER_01": 9.0}[lbl]  # 01 最长

    emb = np.array([[1, 0], [0, 1]], dtype=np.float32)
    out = DiarizationEngine._dominant_embedding(_Ann(), emb)
    assert out.tolist() == [0, 1]  # SPEAKER_01 → emb[1]


def test_dominant_embedding_none_when_no_embeddings():
    class _Ann:
        def labels(self):
            return ["SPEAKER_00"]

        def label_duration(self, lbl):
            return 1.0

    assert DiarizationEngine._dominant_embedding(_Ann(), None) is None
    assert DiarizationEngine._dominant_embedding(_Ann(), np.zeros((0, 2), dtype=np.float32)) is None


def test_injected_pipeline_skips_load():
    sentinel = object()
    eng = DiarizationEngine(hf_token="x", pipeline=sentinel)
    eng._ensure_loaded()  # 有注入 pipeline → 直接 return，不导入/下载
    assert eng._pipeline is sentinel
