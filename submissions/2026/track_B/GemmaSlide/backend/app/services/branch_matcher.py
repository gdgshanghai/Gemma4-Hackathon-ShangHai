"""Match ASR text to the closest predicted branch using text similarity."""

from __future__ import annotations

import difflib
import logging
import re
import time

from app.schemas.live import BranchMatchResult, BranchNode

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.15

# Punctuation stripped before comparison to avoid "你好。" vs "你好" mismatches
_PUNCT_RE = re.compile('[，。！？、；：""''「」『』【】（）《》…—,!?;:\'()\\[\\]-]')


def _char_bigrams(s: str) -> set[str]:
    """Split text into character bigrams.

    Works equally well for CJK (你好世界 → {你好, 好世, 世界}) and
    space-separated languages (hello → {he, el, ll, lo}).
    Single-character strings return the char itself as a token.
    """
    if len(s) >= 2:
        return {s[i:i + 2] for i in range(len(s) - 1)}
    return {s} if s else set()


def _similarity(a: str, b: str) -> float:
    """Prefix-aware similarity with character-bigram tokenization.

    Key insight: when a speaker says the first few characters of a branch
    (e.g. "大家好，欢迎来到今天的"), we MUST match quickly so visual cues
    appear early — not wait until the entire sentence is spoken.

    Three components blended together:
      1. full_sim  — standard bigram-Jaccard + SequenceMatcher on full texts
      2. prefix_sim — same metrics but on a prefix window of predicted_text
         (≈ 2× length of asr_text). This ensures early partial utterances
         match well against long branch texts.
      3. prefix_char_ratio — simple ratio of consecutive matching chars
         from position 0. Gives direct credit for exact prefix matches.
    """
    a_clean = _PUNCT_RE.sub("", a.lower()).strip()
    b_clean = _PUNCT_RE.sub("", b.lower()).strip()

    if not a_clean or not b_clean:
        return 0.0

    a_bigrams = _char_bigrams(a_clean)
    b_bigrams = _char_bigrams(b_clean)

    # ── 1. Full-text similarity ──
    if a_bigrams and b_bigrams:
        jaccard = len(a_bigrams & b_bigrams) / len(a_bigrams | b_bigrams)
    else:
        jaccard = 0.0
    seq_ratio = difflib.SequenceMatcher(None, a_clean, b_clean).ratio()
    full_sim = 0.5 * jaccard + 0.5 * seq_ratio

    # ── 2. Prefix-window similarity ──
    window_len = min(len(b_clean), max(len(a_clean) * 2, 8))
    prefix = b_clean[:window_len]

    p_bigrams = _char_bigrams(prefix)
    if a_bigrams and p_bigrams:
        p_jaccard = len(a_bigrams & p_bigrams) / len(a_bigrams | p_bigrams)
    else:
        p_jaccard = 0.0
    p_seq = difflib.SequenceMatcher(None, a_clean, prefix).ratio()
    prefix_sim = 0.5 * p_jaccard + 0.5 * p_seq

    # ── 3. Direct prefix character match ──
    match_len = 0
    for ca, cb in zip(a_clean, b_clean):
        if ca == cb:
            match_len += 1
        else:
            break
    prefix_char_ratio = match_len / max(len(a_clean), 1)

    return 0.3 * full_sim + 0.35 * prefix_sim + 0.35 * prefix_char_ratio


def _flatten_branches(nodes: list[BranchNode]) -> list[BranchNode]:
    """BFS flatten the branch tree into a flat list."""
    result: list[BranchNode] = []
    stack = list(nodes)
    while stack:
        node = stack.pop(0)
        result.append(node)
        stack.extend(node.next_branches)
    return result


def match_branch(
    asr_text: str,
    branches: list[BranchNode],
    min_confidence: float = MIN_CONFIDENCE,
) -> BranchMatchResult | None:
    """Find the best-matching branch for the given ASR text.

    Returns None if no branch meets the minimum confidence threshold.
    """
    if not asr_text.strip() or not branches:
        return None

    t0 = time.monotonic()
    candidates = _flatten_branches(branches)

    best_node: BranchNode | None = None
    best_score = 0.0

    for node in candidates:
        if not node.predicted_text.strip():
            continue
        score = _similarity(asr_text, node.predicted_text)
        if score > best_score:
            best_score = score
            best_node = node

    elapsed_ms = (time.monotonic() - t0) * 1000

    if best_node is None or best_score < min_confidence:
        logger.debug(
            "BranchMatcher: no match for %r (best_score=%.3f, scanned=%d, %.1fms)",
            asr_text[:80],
            best_score,
            len(candidates),
            elapsed_ms,
        )
        return None

    logger.info(
        "BranchMatcher: matched %r → branch %s (score=%.3f, scanned=%d, %.1fms)",
        asr_text[:80],
        best_node.branch_id,
        best_score,
        len(candidates),
        elapsed_ms,
    )

    return BranchMatchResult(
        branch_id=best_node.branch_id,
        predicted_text=best_node.predicted_text,
        action=best_node.action,
        teleprompter=best_node.teleprompter,
        confidence=round(best_score, 4),
        elapsed_ms=round(elapsed_ms, 1),
        candidates_scanned=len(candidates),
    )
