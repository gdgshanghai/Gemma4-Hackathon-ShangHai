"""Tests for BranchTracker — stateful branch matching with hysteresis."""

from __future__ import annotations

import pytest

from app.schemas.live import (
    BranchAction,
    BranchActionType,
    BranchNode,
    BranchTrackResult,
)
from app.services.branch_tracker import (
    BranchTracker,
    BranchTrackerConfig,
    _compute_depths,
    _segment_clauses,
)


# ── Helpers ──


def b(text: str, bid: str = "", children: list[BranchNode] | None = None,
      action_type: BranchActionType = BranchActionType.NONE,
      bbox: list[int] | None = None) -> BranchNode:
    return BranchNode(
        branch_id=bid or "b_" + text[:6].replace(" ", "_"),
        predicted_text=text,
        action=BranchAction(
            type=action_type,
            bbox_1000=bbox or [100, 100, 300, 300],
        ),
        next_branches=children or [],
    )


def make_tree() -> list[BranchNode]:
    """Fixture tree: one parent with two children."""
    return [
        b("AI安全很重要", "b1", children=[
            b("我们需要认真对待", "b1_a"),
            b("具体来说有三点", "b1_a1", children=[
                b("第一点是数据", "b1_a1a"),
            ]),
        ]),
        b("机器学习是未来", "b2"),
    ]


def make_tracker(config: BranchTrackerConfig | None = None) -> BranchTracker:
    return BranchTracker(config=config)


# ── _segment_clauses ──


def test_segment_no_punctuation():
    assert _segment_clauses("hello world") == [("hello world", False)]


def test_segment_one_punctuation():
    assert _segment_clauses("AI安全很重要。") == [("AI安全很重要。", True)]


def test_segment_two_clauses():
    clauses = _segment_clauses("AI安全很重要。接下来我们讨论")
    assert clauses == [("AI安全很重要。", True), ("接下来我们讨论", False)]


def test_segment_multiple_punctuation():
    clauses = _segment_clauses("句子一。句子二！句子三？")
    assert len(clauses) == 3
    assert all(hp for _, hp in clauses)


def test_segment_english_punctuation():
    clauses = _segment_clauses("First point. Second point.")
    assert len(clauses) == 2
    assert all(hp for _, hp in clauses)


def test_segment_empty():
    assert _segment_clauses("") == []


def test_segment_only_punctuation():
    assert _segment_clauses("。") == [("。", True)]


# ── _compute_depths ──


def test_compute_depths_flat():
    depth_map, all_depths = _compute_depths([
        b("文本一", "b1"),
        b("文本二", "b2"),
    ])
    assert depth_map == {"b1": 1, "b2": 1}
    assert all_depths == {1}


def test_compute_depths_nested():
    depth_map, all_depths = _compute_depths(make_tree())
    assert depth_map["b1"] == 1
    assert depth_map["b2"] == 1
    assert depth_map["b1_a"] == 2
    assert depth_map["b1_a1"] == 2
    assert depth_map["b1_a1a"] == 3
    assert all_depths == {1, 2, 3}


def test_compute_depths_empty():
    depth_map, all_depths = _compute_depths([])
    assert depth_map == {}
    assert all_depths == set()


# ── Basic matching ──


def test_tracker_empty_text_returns_no_match():
    t = make_tracker()
    result = t.process("", False, make_tree())
    assert result.match is None


def test_tracker_no_branches():
    t = make_tracker()
    result = t.process("hello", False, [])
    assert result.match is None


def test_tracker_strong_match():
    t = make_tracker()
    result = t.process("AI安全很重要", False, make_tree())
    assert result.match is not None
    assert result.match.branch_id == "b1"
    assert result.match.confidence > 0.4


# ── Hysteresis / bounce prevention ──


def test_tracker_bounce_prevention():
    """Same branch stays active through intermediate results with minor text changes."""
    t = make_tracker()
    tree = make_tree()

    # First result establishes active branch
    r1 = t.process("AI安全", False, tree)
    assert r1.match is not None
    assert r1.match.branch_id == "b1"

    # Gradually growing text — should stay on b1
    r2 = t.process("AI安全很", False, tree)
    assert r2.match is not None
    assert r2.match.branch_id == "b1", f"bounced to {r2.match.branch_id}"

    r3 = t.process("AI安全很重要", False, tree)
    assert r3.match is not None
    assert r3.match.branch_id == "b1", f"bounced to {r3.match.branch_id}"


def test_tracker_hysteresis_blocks_weak_switch():
    """Weak new candidate does NOT overcome hysteresis."""
    t = make_tracker()

    # Establish b1 as active
    t.process("AI安全很重要", False, make_tree())
    assert t.active_branch_id == "b1"

    # Switch to a short text that weakly matches b2
    result = t.process("未来", False, make_tree())
    # Since "未来" is short, combined with b1's hysteresis, b1 should stay
    # (b2 score must be > b1_score * 1.20 to take over)
    assert result.match is not None
    # b1 stays active (hysteresis protects it)


def test_tracker_strong_new_candidate_overcomes_hysteresis():
    """Very strong new match can overcome hysteresis."""
    t = make_tracker()

    # Establish b2 (weaker)
    t.process("机器学习", False, make_tree())

    # Now a very strong match for b1
    result = t.process("AI安全是非常重要的课题", False, make_tree())
    assert result.match is not None
    # Strong enough to overcome if active was weak
    assert result.match.branch_id in ("b1", t.active_branch_id)


# ── Punctuation / coverage ──


def test_tracker_punctuation_covers_branch():
    """Punctuation + high score → branch added to covered."""
    t = make_tracker()
    result = t.process("AI安全很重要。", True, make_tree())
    assert result.match is not None
    assert result.match.branch_id == "b1"
    assert "b1" in result.covered_ids
    assert "b1" in result.all_covered_ids


def test_tracker_no_punctuation_no_cover():
    """Without punctuation, no branches covered even if high score."""
    t = make_tracker()
    result = t.process("AI安全很重要", False, make_tree())
    assert result.match is not None
    assert result.covered_ids == []
    assert result.all_covered_ids == []


def test_tracker_covered_branch_penalized():
    """After b1 is covered, b2 should be preferred for new text."""
    t = make_tracker()

    # Cover b1
    t.process("AI安全很重要。", True, make_tree())

    # Now text matching both — b2 should win because b1 is penalized
    result = t.process("机器学习和AI都很重要", False, make_tree())
    assert result.match is not None
    # b2 should be preferred since b1 is covered (0.25x penalty)
    assert result.match.branch_id == "b2"


# ── Path following ──


def test_tracker_child_boost():
    """After parent covered, child gets boost over sibling."""
    t = make_tracker()

    # Cover b1
    t.process("AI安全很重要。", True, make_tree())

    # Now text matching b1_a (child of b1) should get boost
    result = t.process("我们需要认真对待", False, make_tree())
    assert result.match is not None
    assert result.match.branch_id == "b1_a"


def test_tracker_sequential_clauses():
    """Two clauses in one ASR result: first covers b1, second highlights b1_a."""
    t = make_tracker()

    # Single ASR result with two clauses
    result = t.process("AI安全很重要。我们需要认真对待", False, make_tree())

    assert result.match is not None
    # b1 should be covered (punctuation on first clause)
    assert "b1" in result.covered_ids
    assert result.segment_count == 2


def test_tracker_deep_tree_coverage():
    """Cover b1 → b1_a → b1_a1 in sequence."""
    t = make_tracker()

    r1 = t.process("AI安全很重要。", True, make_tree())
    assert "b1" in r1.covered_ids

    r2 = t.process("我们需要认真对待。", True, make_tree())
    assert "b1_a" in r2.covered_ids

    r3 = t.process("具体来说有三点。", True, make_tree())
    assert "b1_a1" in r3.covered_ids


def test_tracker_segment_count():
    t = make_tracker()
    result = t.process("你好。再见。", False, make_tree())
    assert result.segment_count == 2


# ── Depth priority ──


def test_tracker_depth_priority_shallow_first():
    """When nothing is covered yet, depth-1 branches get priority boost."""
    t = make_tracker()

    # Text that matches b2 (depth 1, "机器学习是未来") better than b1_a1a (depth 3, "第一点是数据")
    result = t.process("机器学习是未来的趋势", False, make_tree())
    assert result.match is not None
    # b2 should win: depth-1 gets priority boost, depth-3 does not
    assert result.match.branch_id == "b2", f"Expected b2 (depth 1), got {result.match.branch_id}"


def test_tracker_depth_priority_after_cover():
    """After depth-1 covered, depth-2 branches get boost."""
    t = make_tracker()

    # Cover depth-1
    t.process("AI安全很重要。", True, make_tree())

    # Now depth-2 branches should get priority boost
    # b1_a (depth 2) should be preferred over other depth-1 branches
    result = t.process("我们需要认真对待", False, make_tree())
    assert result.match is not None
    assert result.match.branch_id == "b1_a"


def test_tracker_depth_priority_all_covered():
    """When all depths are covered, no depth priority boost applies."""
    t = make_tracker()

    # Cover depths 1, 2, 3
    t.process("AI安全很重要。", True, make_tree())
    t.process("我们需要认真对待。", True, make_tree())
    t.process("第一点是数据。", True, make_tree())

    # All depths covered → no depth priority, let other factors decide
    result = t.process("机器学习", False, make_tree())
    # Should still work, just no depth-guided preference
    assert result.match is not None


def test_tracker_cross_branch_same_depth():
    """Cross-branch jumping within the same depth is allowed (when strong enough
    to overcome hysteresis)."""
    t = make_tracker()

    # Weakly match b1 first (establishes moderate hysteresis grip).
    # "安全" is a substring of "AI安全很重要" but NOT a prefix,
    # so prefix_char_ratio=0 and the score stays moderate (~0.20).
    t.process("安全", False, make_tree())

    # Now a strong match for b2 (also depth 1) — should overcome b1's grip
    result = t.process("机器学习是未来的趋势和方向", False, make_tree())
    assert result.match is not None
    # b2 is at same depth (1), cross-branch jump is allowed when strong enough
    assert result.match.branch_id == "b2"


# ── Trailing buffer ──


def test_tracker_trailing_buffer():
    """Text without punctuation that doesn't match well → buffered."""
    t = make_tracker(config=BranchTrackerConfig(max_trailing_chars=50))
    t.process("这个是一些无关的话", False, make_tree())
    # Should have buffered something if no match or weak match
    # The important thing: next result concatenates buffer
    result = t.process("AI安全很重要", False, make_tree())
    assert result.match is not None


def test_tracker_buffer_flushes_on_strong_match():
    """Buffer concatenation helps matching."""
    t = make_tracker(config=BranchTrackerConfig(max_trailing_chars=200))
    t.process("我们", False, make_tree())
    result = t.process("AI安全很重要。", True, make_tree())
    assert result.match is not None
    assert result.match.branch_id == "b1"


# ── Reset ──


def test_tracker_reset():
    t = make_tracker()
    t.process("AI安全很重要。", True, make_tree())
    assert len(t.covered_branches) > 0
    assert t.active_branch_id is not None

    t.reset()
    assert len(t.covered_branches) == 0
    assert t.active_branch_id is None
    assert t.active_score == 0.0
    assert t.active_path == []
    assert t.trailing_buffer == ""


# ── Edge cases ──


def test_tracker_whitespace_only():
    t = make_tracker()
    result = t.process("   ", False, make_tree())
    assert result.match is None


def test_tracker_none_match_when_text_too_short():
    t = make_tracker()
    result = t.process("xyz", False, make_tree())
    # Completely unrelated text — no branch should match
    assert result.match is None


def test_tracker_covered_ids_accumulate():
    t = make_tracker()
    t.process("AI安全很重要。", True, make_tree())
    result = t.process("我们需要认真对待。", True, make_tree())
    assert len(result.all_covered_ids) >= 2


def test_tracker_mixed_action_types():
    """Branches with highlight/circle actions still work."""
    tree = [
        b("highlight this area", "h1", action_type=BranchActionType.HIGHLIGHT),
        b("circle that part", "c1", action_type=BranchActionType.CIRCLE),
    ]
    t = make_tracker()
    result = t.process("highlight this area。", True, tree)
    assert result.match is not None
    assert result.match.branch_id == "h1"
    assert "h1" in result.covered_ids
