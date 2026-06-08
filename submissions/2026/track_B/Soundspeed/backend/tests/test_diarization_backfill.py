"""DiarizationBackfill 全链 + 结构化转录（切片 3）。

- build_structured_transcript 纯组装
- DAL.update_take_structured_transcript ↔ get_take 往返
- DiarizationBackfill.run 全链（假 engine/registry/dal，真实 buffer）
- 跳过路径（engine=None / 短音频）仍触发 L2、不写结构化
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from backend.diarization.backfill import (
    DiarizationBackfill,
    build_structured_transcript,
)
from backend.diarization.buffer import TakeAudioBuffer
from backend.diarization.engine import SpeakerTurn
from backend.db.dal import DAL


# ── build_structured_transcript（纯） ───────────────────────────────────────────


def _seg(segment_id, speaker, text, start_ms, end_ms, ch=1):
    return SimpleNamespace(
        segment_id=segment_id, ch=ch, speaker=speaker,
        text=text, start_frame=start_ms, end_frame=end_ms,
    )


def test_build_structured_transcript_shape():
    segs = [
        _seg(1, "说话人1", "你好", 0, 2000),
        _seg(2, "说话人2", "走吧", 2000, 4000),
    ]
    out = build_structured_transcript(segs)
    assert out == {
        "version": 1,
        "ch1": [
            {"speaker": "说话人1", "text": "你好", "start_ms": 0, "end_ms": 2000},
            {"speaker": "说话人2", "text": "走吧", "start_ms": 2000, "end_ms": 4000},
        ],
    }


def test_build_structured_transcript_empty():
    assert build_structured_transcript([]) == {"version": 1, "ch1": []}


# ── DAL 往返 ─────────────────────────────────────────────────────────────────────


def test_dal_take_speakers_roundtrip(tmp_dal: DAL):
    scene_id = tmp_dal.create_scene("S")
    take_id, _ = tmp_dal.start_take(scene_id, shot="", start_ts=0.0, take_number=1)
    s1 = tmp_dal.insert_speaker("张三", embedding_blob=np.ones(4, dtype=np.float32).tobytes())
    s2 = tmp_dal.insert_speaker("李四")  # 无声纹

    tmp_dal.set_take_speakers(take_id, [s1, s2])
    rows = tmp_dal.list_take_speakers(take_id)
    assert {r["display_name"] for r in rows} == {"张三", "李四"}
    zhang = next(r for r in rows if r["display_name"] == "张三")
    assert zhang["embedding"].tolist() == [1, 1, 1, 1]  # 反序列化为 numpy
    li = next(r for r in rows if r["display_name"] == "李四")
    assert li["embedding"] is None

    # 覆盖式更新（先清后插）
    tmp_dal.set_take_speakers(take_id, [s2])
    assert [r["speaker_id"] for r in tmp_dal.list_take_speakers(take_id)] == [s2]
    # 空列表清空
    tmp_dal.set_take_speakers(take_id, [])
    assert tmp_dal.list_take_speakers(take_id) == []


def test_dal_structured_transcript_roundtrip(tmp_dal: DAL):
    scene_id = tmp_dal.create_scene("S")
    take_id, _ = tmp_dal.start_take(scene_id, shot="", start_ts=0.0, take_number=1)
    assert tmp_dal.get_take(take_id).structured_transcript is None

    doc = {"version": 1, "ch1": [{"speaker": "说话人1", "text": "嗨", "start_ms": 0, "end_ms": 500}]}
    tmp_dal.update_take_structured_transcript(take_id, doc)
    assert tmp_dal.get_take(take_id).structured_transcript == doc


# ── 全链 ─────────────────────────────────────────────────────────────────────────


class _FakeDal:
    """有状态的 ch1 segment 台账：bulk_update 改 speaker，list_segments 反映最新。"""

    def __init__(self, segments, take_speakers=None):
        self._segs = segments
        self.structured = None
        self.bulk_calls: list[dict] = []
        self.take_speakers = take_speakers or []

    def list_segments(self, take_id, ch=None):
        return [s for s in self._segs if ch is None or s.ch == ch]

    def bulk_update_segment_speaker(self, m):
        self.bulk_calls.append(dict(m))
        for s in self._segs:
            if s.segment_id in m:
                s.speaker = m[s.segment_id]

    def update_take_structured_transcript(self, take_id, structured):
        self.structured = structured

    def list_take_speakers(self, take_id):
        return list(self.take_speakers)


class _FakeEngine:
    def __init__(self, turns):
        self._turns = turns
        self.seen_num_speakers = "unset"

    def diarize(self, pcm, *, num_speakers=None):
        self.seen_num_speakers = num_speakers
        return self._turns


class _FakeRegistry:
    def __init__(self, mapping):
        self._m = mapping
        self.seen_candidates = None

    def resolve(self, avg_embeddings, candidates=None):
        self.seen_candidates = candidates
        return dict(self._m)


@pytest.mark.asyncio
async def test_run_full_chain_writes_speakers_structured_and_triggers_l2():
    segs = [
        _seg(1, None, "你好", 0, 2000),
        _seg(2, None, "走吧", 2000, 4000),
    ]
    dal = _FakeDal(segs)
    buf = TakeAudioBuffer()
    buf.append(np.zeros(16000 * 5, dtype=np.int16), start_frame=0)  # 5s，audio_start_s=0

    turns = [
        SpeakerTurn(0.0, 2.0, "SPEAKER_00", embedding=np.array([1, 0], dtype=np.float32)),
        SpeakerTurn(2.0, 4.0, "SPEAKER_01", embedding=np.array([0, 1], dtype=np.float32)),
    ]
    engine = _FakeEngine(turns)
    registry = _FakeRegistry({"SPEAKER_00": "说话人1", "SPEAKER_01": "说话人2"})

    published: list[tuple] = []
    l2_calls: list[tuple] = []

    async def _l2(tid, sid, tn):
        l2_calls.append((tid, sid, tn))

    backfill = DiarizationBackfill(
        dal=dal, buffer=buf, engine=engine, registry=registry,
        publish=lambda topic, payload: published.append((topic, payload)),
        l2_trigger=_l2,
    )

    await backfill.run(take_id=10, scene_id=2, take_number=3)

    # backfill 把本 take 挂的演员（candidates）传给了 resolve
    assert registry.seen_candidates == []  # 本测试未挂演员
    assert engine.seen_num_speakers is None  # 未挂演员 → 不给人数先验，pyannote 自动判定
    # speaker 回填
    assert dal.bulk_calls == [{1: "说话人1", 2: "说话人2"}]
    assert segs[0].speaker == "说话人1" and segs[1].speaker == "说话人2"
    # 结构化转录写入（带回填后的 speaker）
    assert dal.structured == {
        "version": 1,
        "ch1": [
            {"speaker": "说话人1", "text": "你好", "start_ms": 0, "end_ms": 2000},
            {"speaker": "说话人2", "text": "走吧", "start_ms": 2000, "end_ms": 4000},
        ],
    }
    # 先发 take.processing(diarizing)，回填后发 take.segments.updated
    topics = [t for t, _ in published]
    assert "take.processing" in topics
    proc = next(p for t, p in published if t == "take.processing")
    assert proc.phase == "diarizing"
    assert "take.segments.updated" in topics
    seg_evt = next(p for t, p in published if t == "take.segments.updated")
    assert seg_evt.take_id == 10 and seg_evt.scene_id == 2
    # buffer 已释放
    assert buf.sample_count == 0
    # L2 gate 在回填后触发
    assert l2_calls == [(10, 2, 3)]


@pytest.mark.asyncio
async def test_run_passes_selected_actor_count_as_num_speakers():
    """本 take 选了 N 个演员 → diarize 收到 num_speakers=N（修「选了2人却只分出1人」）。"""
    segs = [_seg(1, None, "你好", 0, 2000), _seg(2, None, "走吧", 2000, 4000)]
    dal = _FakeDal(
        segs,
        take_speakers=[
            {"speaker_id": 1, "display_name": "顾朗", "embedding": None},
            {"speaker_id": 2, "display_name": "夏雨", "embedding": None},
        ],
    )
    buf = TakeAudioBuffer()
    buf.append(np.zeros(16000 * 5, dtype=np.int16), start_frame=0)
    engine = _FakeEngine([SpeakerTurn(0.0, 2.0, "SPEAKER_00"), SpeakerTurn(2.0, 4.0, "SPEAKER_01")])
    backfill = DiarizationBackfill(
        dal=dal, buffer=buf, engine=engine,
        registry=_FakeRegistry({"SPEAKER_00": "说话人1", "SPEAKER_01": "说话人2"}),
        publish=lambda t, p: None, l2_trigger=None,
    )

    await backfill.run(take_id=10, scene_id=2, take_number=1)

    assert engine.seen_num_speakers == 2  # 选了 2 个演员 → 人数先验=2


@pytest.mark.asyncio
async def test_run_engine_none_skips_backfill_but_triggers_l2():
    dal = _FakeDal([_seg(1, None, "x", 0, 1000)])
    buf = TakeAudioBuffer()
    buf.append(np.zeros(16000 * 2, dtype=np.int16), start_frame=0)
    l2_calls: list[tuple] = []

    async def _l2(tid, sid, tn):
        l2_calls.append((tid, sid, tn))

    backfill = DiarizationBackfill(
        dal=dal, buffer=buf, engine=None, registry=None,
        publish=lambda t, p: None, l2_trigger=_l2,
    )
    await backfill.run(take_id=1, scene_id=1, take_number=1)

    assert dal.bulk_calls == []
    assert dal.structured is None
    assert l2_calls == [(1, 1, 1)]   # 仍触发 L2
    assert buf.sample_count == 0     # 仍释放内存


@pytest.mark.asyncio
async def test_run_short_audio_skips_but_triggers_l2():
    dal = _FakeDal([_seg(1, None, "x", 0, 500)])
    buf = TakeAudioBuffer()
    buf.append(np.zeros(8000, dtype=np.int16), start_frame=0)  # 0.5s < 1s
    l2_calls: list[tuple] = []

    async def _l2(tid, sid, tn):
        l2_calls.append((tid, sid, tn))

    backfill = DiarizationBackfill(
        dal=dal, buffer=buf, engine=_FakeEngine([]), registry=_FakeRegistry({}),
        publish=lambda t, p: None, l2_trigger=_l2,
    )
    await backfill.run(take_id=1, scene_id=1, take_number=1)

    assert dal.structured is None
    assert l2_calls == [(1, 1, 1)]
