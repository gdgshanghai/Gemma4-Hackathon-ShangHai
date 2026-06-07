"""Stateful branch tracker with hysteresis, punctuation-clause processing,
and path-following boosts.

Design doc: docs/branch-tracker-v2-design.md
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from app.schemas.live import BranchActionType, BranchMatchResult, BranchNode, BranchTrackResult

logger = logging.getLogger(__name__)

# ── Punctuation regex ──
# Split on Chinese/English sentence-ending punctuation, keeping delimiter
# attached to the preceding clause.
_CLAUSE_SPLIT = re.compile(r"([。！？.!?\n]+)")


@dataclass
class BranchTrackerConfig:
    """Tunable parameters for the branch tracker."""

    # Thresholds
    coverage_threshold: float = 0.30
    min_confidence: float = 0.10

    # Weight multipliers
    coverage_penalty: float = 0.25  # Already-covered branches get this multiplier
    child_path_boost: float = 1.20  # Direct children of the last active_path entry
    same_path_boost: float = 1.05  # Same branch as last active_path entry
    sibling_path_penalty: float = 0.85  # Siblings of the last active_path entry

    # Hysteresis
    stickiness_boost: float = 1.15  # Boost for the currently active branch
    hysteresis_margin: float = 1.20  # New candidate must beat active × this

    # Depth priority: when no branch at shallower depths is covered yet,
    # branches at the shallowest uncovered depth get this boost.
    depth_priority_boost: float = 1.25

    # Buffer
    max_trailing_chars: int = 120


# ── Helpers (re-exported from branch_matcher to keep it self-contained) ──


def _flatten_branches(nodes: list[BranchNode]) -> list[BranchNode]:
    """BFS flatten the branch tree into a flat list."""
    result: list[BranchNode] = []
    stack = list(nodes)
    while stack:
        node = stack.pop(0)
        result.append(node)
        stack.extend(node.next_branches)
    return result


def _char_bigrams(s: str) -> set[str]:
    """Split text into character bigrams.

    Works equally well for CJK (你好世界 → {你好, 好世, 世界}) and
    space-separated languages (hello → {he, el, ll, lo}).
    """
    if len(s) >= 2:
        return {s[i:i + 2] for i in range(len(s) - 1)}
    return {s} if s else set()


def _similarity(a: str, b: str) -> float:
    """Prefix-aware similarity with character-bigram tokenization.

    Key insight: when a speaker says the first few characters of a branch,
    we MUST match quickly so visual cues appear early — not wait until the
    entire sentence is spoken.

    Three components:
      1. full_sim  — bigram-Jaccard + SequenceMatcher on full texts
      2. prefix_sim — same metrics on a prefix window of predicted_text (~2× asr length)
      3. prefix_char_ratio — consecutive matching chars from position 0
    """
    import difflib
    import re as _re

    _punct = _re.compile('[，。！？、；：""''「」『』【】（）《》…—,!?;:\'()\\[\\]-]')
    a_clean = _punct.sub("", a.lower()).strip()
    b_clean = _punct.sub("", b.lower()).strip()

    if not a_clean or not b_clean:
        return 0.0

    a_bigrams = _char_bigrams(a_clean)
    b_bigrams = _char_bigrams(b_clean)

    # 1. Full-text similarity
    if a_bigrams and b_bigrams:
        jaccard = len(a_bigrams & b_bigrams) / len(a_bigrams | b_bigrams)
    else:
        jaccard = 0.0
    seq_ratio = difflib.SequenceMatcher(None, a_clean, b_clean).ratio()
    full_sim = 0.5 * jaccard + 0.5 * seq_ratio

    # 2. Prefix-window similarity
    window_len = min(len(b_clean), max(len(a_clean) * 2, 8))
    prefix = b_clean[:window_len]

    p_bigrams = _char_bigrams(prefix)
    if a_bigrams and p_bigrams:
        p_jaccard = len(a_bigrams & p_bigrams) / len(a_bigrams | p_bigrams)
    else:
        p_jaccard = 0.0
    p_seq = difflib.SequenceMatcher(None, a_clean, prefix).ratio()
    prefix_sim = 0.5 * p_jaccard + 0.5 * p_seq

    # 3. Direct prefix character match
    match_len = 0
    for ca, cb in zip(a_clean, b_clean):
        if ca == cb:
            match_len += 1
        else:
            break
    prefix_char_ratio = match_len / max(len(a_clean), 1)

    return 0.3 * full_sim + 0.35 * prefix_sim + 0.35 * prefix_char_ratio


def _build_child_map(branches: list[BranchNode]) -> dict[str, set[str]]:
    """Build a parent_id → set of immediate child_ids mapping from a branch tree."""
    child_map: dict[str, set[str]] = {}
    for node in _flatten_branches(branches):
        for child in node.next_branches:
            child_map.setdefault(node.branch_id, set()).add(child.branch_id)
    return child_map


def _compute_depths(nodes: list[BranchNode]) -> tuple[dict[str, int], set[int]]:
    """Compute depth (1-based) for every branch in the tree.

    Returns (branch_id → depth, set of all depths present).
    """
    depth_map: dict[str, int] = {}
    all_depths: set[int] = set()

    def walk(children: list[BranchNode], depth: int) -> None:
        for node in children:
            depth_map[node.branch_id] = depth
            all_depths.add(depth)
            walk(node.next_branches, depth + 1)

    walk(nodes, 1)
    return depth_map, all_depths


def _segment_clauses(text: str) -> list[tuple[str, bool]]:
    """Split text into clauses, each annotated with whether it ends in punctuation.

    Returns list of (clause_text, has_punctuation).
    """
    parts = _CLAUSE_SPLIT.split(text)
    clauses: list[tuple[str, bool]] = []

    i = 0
    while i < len(parts):
        chunk = parts[i]
        if _CLAUSE_SPLIT.fullmatch(chunk):
            # This is a delimiter — attach to the PREVIOUS clause
            if clauses:
                prev_text, _ = clauses.pop()
                clauses.append((prev_text + chunk, True))
            else:
                # Delimiter at start of text — treat as its own clause
                clauses.append((chunk, True))
            i += 1
        else:
            stripped = chunk.strip()
            if stripped:
                clauses.append((chunk, False))
            i += 1

    return clauses


def _build_branch_map(branches: list[BranchNode]) -> dict[str, BranchNode]:
    """Build a flat id→node lookup from a branch tree."""
    return {n.branch_id: n for n in _flatten_branches(branches)}


class BranchTracker:
    """Per-slide stateful tracker that matches ASR text against precomputed branches.

    Responsibilities:
      - Prevent visual bounce via hysteresis
      - Treat punctuation as commit points (cover branches)
      - Boost child branches when parent is covered (path following)
      - Process multi-clause ASR results sequentially
    """

    def __init__(self, config: BranchTrackerConfig | None = None):
        self.config = config or BranchTrackerConfig()
        self._reset()

    def _reset(self) -> None:
        self.covered_branches: set[str] = set()
        self.active_branch_id: str | None = None
        self.active_score: float = 0.0
        self.active_path: list[str] = []  # e.g. ["b1", "b1_a"]
        self.trailing_buffer: str = ""

    # ── Public API ──

    def process(
        self,
        asr_text: str,
        is_sentence_end: bool,
        branches: list[BranchNode],
    ) -> BranchTrackResult:
        """Process one ASR result through the tracker.

        Args:
            asr_text: Raw ASR text (intermediate or sentence_end).
            is_sentence_end: Whether ASR considers this a complete sentence.
            branches: Current slide's branch tree.

        Returns:
            BranchTrackResult with match, covered_ids, and segment info.
        """
        t0 = time.monotonic()

        if not branches:
            return BranchTrackResult(
                match=None,
                covered_ids=[],
                all_covered_ids=sorted(self.covered_branches),
                segment_count=0,
            )

        branch_map = _build_branch_map(branches)
        child_map = _build_child_map(branches)
        depth_map, all_depths = _compute_depths(branches)
        covered_depths = {depth_map[bid] for bid in self.covered_branches if bid in depth_map}

        # Step 1: Concatenate trailing buffer + asr_text
        full_text = (self.trailing_buffer + " " + asr_text).strip()
        if not full_text:
            return BranchTrackResult(
                match=self._current_match_result(branch_map),
                covered_ids=[],
                all_covered_ids=sorted(self.covered_branches),
                segment_count=0,
            )

        # Step 2: Segment into clauses
        clauses = _segment_clauses(full_text)

        # Step 3: Process each clause in order
        newly_covered: list[str] = []
        best_active: tuple[str, float] | None = None
        segment_count = len(clauses)

        for i, (clause_text, has_punct) in enumerate(clauses):
            if not clause_text.strip():
                continue

            scored = self._score_all_branches(
                clause_text.strip(), branch_map, child_map, depth_map, covered_depths, all_depths
            )

            if not scored:
                continue

            best_id, best_score = scored[0]

            # Raw similarity (unboosted) for fair hysteresis comparison
            raw_best = _similarity(clause_text.strip(), branch_map[best_id].predicted_text)

            # Step 3c: Cover branch if punctuation + high confidence
            if has_punct and best_score >= self.config.coverage_threshold:
                if best_id not in self.covered_branches:
                    self.covered_branches.add(best_id)
                    newly_covered.append(best_id)
                    self._update_active_path(best_id, child_map)
                    logger.debug(
                        "BranchTracker: covered %s (score=%.3f, punct=True)",
                        best_id,
                        best_score,
                    )

            # Step 3d: Last clause determines active branch
            is_last = i == len(clauses) - 1
            if is_last:
                # Use raw similarity for hysteresis — apples-to-apples comparison
                resolved_id, resolved_score = self._apply_hysteresis(
                    (best_id, raw_best), branch_map
                )
                best_active = (resolved_id, resolved_score)

        # Update active state
        if best_active is not None:
            self.active_branch_id = best_active[0]
            self.active_score = best_active[1]

        # Step 4: Update trailing buffer
        if clauses and not clauses[-1][1]:
            # Last clause has no punctuation — keep as trailing buffer
            last_text = clauses[-1][0].strip()
            # Only buffer if it's the last clause and didn't produce a strong match
            if best_active is None or self.active_score < self.config.coverage_threshold:
                self.trailing_buffer = last_text
            else:
                self.trailing_buffer = ""
        else:
            self.trailing_buffer = ""

        # Force-flush if buffer too long
        if len(self.trailing_buffer) > self.config.max_trailing_chars:
            logger.debug("BranchTracker: flushing trailing buffer (%d chars)", len(self.trailing_buffer))
            self.trailing_buffer = ""

        elapsed_ms = (time.monotonic() - t0) * 1000

        match = self._current_match_result(
            branch_map, child_map, depth_map, covered_depths, all_depths, elapsed_ms
        )
        return BranchTrackResult(
            match=match,
            covered_ids=newly_covered,
            all_covered_ids=sorted(self.covered_branches),
            segment_count=segment_count,
        )

    def reset(self) -> None:
        """Reset all state (called on slide change or session stop)."""
        self._reset()

    # ── Internal methods ──

    def _score_all_branches(
        self,
        text: str,
        branch_map: dict[str, BranchNode],
        child_map: dict[str, set[str]],
        depth_map: dict[str, int],
        covered_depths: set[int],
        all_depths: set[int],
    ) -> list[tuple[str, float]]:
        """Compute weighted scores for all branches, sorted descending."""
        results: list[tuple[str, float]] = []
        for bid, node in branch_map.items():
            if not node.predicted_text.strip():
                continue
            raw = _similarity(text, node.predicted_text)
            weighted = raw * self._compute_multiplier(
                bid, branch_map, child_map, depth_map, covered_depths, all_depths
            )
            results.append((bid, round(weighted, 4)))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _compute_multiplier(
        self,
        branch_id: str,
        branch_map: dict[str, BranchNode],
        child_map: dict[str, set[str]],
        depth_map: dict[str, int],
        covered_depths: set[int],
        all_depths: set[int],
    ) -> float:
        """Compute the combined weight multiplier for a branch."""
        m = 1.0

        # Coverage penalty
        if branch_id in self.covered_branches:
            m *= self.config.coverage_penalty

        # Depth priority: boost branches at the shallowest uncovered depth.
        # Cross-branch jumping within the same depth is allowed; this only
        # prevents jumping to deeper levels before shallower ones are covered.
        branch_depth = depth_map.get(branch_id)
        if branch_depth is not None and all_depths:
            # Find the minimum depth that has NOT been covered yet
            uncovered = all_depths - covered_depths
            if uncovered and branch_depth == min(uncovered):
                m *= self.config.depth_priority_boost

        # Path boost (based on actual tree structure from child_map)
        if self.active_path:
            last = self.active_path[-1]
            if branch_id == last:
                m *= self.config.same_path_boost
            elif branch_id in child_map.get(last, set()):
                # Direct child of last active_path entry
                m *= self.config.child_path_boost
            else:
                # Check if sibling of last (share same parent)
                for parent_id, children in child_map.items():
                    if last in children and branch_id in children:
                        m *= self.config.sibling_path_penalty
                        break

        # Stickiness boost
        if branch_id == self.active_branch_id:
            m *= self.config.stickiness_boost

        return m

    def _apply_hysteresis(
        self,
        candidate: tuple[str, float],
        branch_map: dict[str, BranchNode],
    ) -> tuple[str, float]:
        """Apply hysteresis: only switch active branch if new candidate is
        significantly better, OR current active is already weak/covered."""
        new_id, new_score = candidate

        # No current active → accept only if above min_confidence
        if self.active_branch_id is None:
            if new_score >= self.config.min_confidence:
                return candidate
            return (new_id, 0.0)

        # Compute effective score: if active is covered, it's much weaker
        eff_active = self.active_score
        if self.active_branch_id in self.covered_branches:
            eff_active *= self.config.coverage_penalty

        # Current active is weak → disable hysteresis
        if eff_active < self.config.coverage_threshold:
            if new_score >= self.config.min_confidence:
                return candidate
            return (self.active_branch_id, self.active_score)

        # Current is strong: require hysteresis margin on effective score
        if new_score > eff_active * self.config.hysteresis_margin:
            return candidate

        # Return same branch with updated score
        if new_id == self.active_branch_id:
            return candidate

        # Keep current active (unchanged score)
        return (self.active_branch_id, self.active_score)

    def _update_active_path(
        self, covered_branch_id: str, child_map: dict[str, set[str]]
    ) -> None:
        """Update active_path when a branch is covered.

        Append if covered_branch is a direct child of the last path entry.
        Otherwise, start a new path (speaker jumped to a different topic).
        """
        if not self.active_path:
            self.active_path = [covered_branch_id]
            return

        last = self.active_path[-1]
        if covered_branch_id in child_map.get(last, set()):
            # Natural depth-first progression
            self.active_path.append(covered_branch_id)
        else:
            # Speaker jumped — start new path
            self.active_path = [covered_branch_id]

    def _current_match_result(
        self,
        branch_map: dict[str, BranchNode],
        child_map: dict[str, set[str]] | None = None,
        depth_map: dict[str, int] | None = None,
        covered_depths: set[int] | None = None,
        all_depths: set[int] | None = None,
        elapsed_ms: float = 0.0,
    ) -> BranchMatchResult | None:
        """Build a BranchMatchResult for the current active branch.
        Returns None if no active branch or confidence is below minimum.

        display_confidence = raw_active_score × current multipliers,
        for a fair representation of the tracker's effective score.
        """
        if self.active_branch_id is None:
            return None
        if self.active_score < self.config.min_confidence:
            return None
        node = branch_map.get(self.active_branch_id)
        if node is None:
            return None

        # Compute display confidence from raw score × current multipliers
        display_confidence = self.active_score
        if child_map is not None and depth_map is not None and covered_depths is not None and all_depths is not None:
            display_confidence *= self._compute_multiplier(
                self.active_branch_id, branch_map, child_map, depth_map, covered_depths, all_depths
            )
        display_confidence = round(display_confidence, 4)
        return BranchMatchResult(
            branch_id=node.branch_id,
            predicted_text=node.predicted_text,
            action=node.action,
            teleprompter=node.teleprompter,
            confidence=display_confidence,
            elapsed_ms=round(elapsed_ms, 1),
            candidates_scanned=len(branch_map),
            is_covered=self.active_branch_id in self.covered_branches,
        )
