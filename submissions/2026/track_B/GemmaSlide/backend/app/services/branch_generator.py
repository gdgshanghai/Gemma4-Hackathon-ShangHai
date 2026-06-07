from __future__ import annotations

import asyncio
import json
import logging
import re
import time

import httpx

from app.core.config import settings
from app.schemas.live import (
    BranchAction,
    BranchActionType,
    BranchNode,
    BranchTreeResponse,
)
from app.services.script_adapter import _prepare_slide_image

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
# Prompt
# ────────────────────────────────────────────────────────────

BRANCH_SYSTEM_PROMPT = """You are an expert presentation coach. You see a slide image and need to predict the different ways a speaker might present it.

Your task: Generate a BRANCH TREE for the CURRENT SLIDE ONLY — multiple possible paths the speaker might take through THIS slide. Do NOT generate branches for adjacent slides.

Each branch represents ONE thing the speaker might say (1-2 sentences), PLUS a visual action to perform on the CURRENT slide.

CRITICAL LANGUAGE RULE:
- Look at the text on the slide. ALL predicted_text AND teleprompter MUST be in the SAME LANGUAGE as the slide content.
- If the slide is in Chinese, generate Chinese. If English, generate English. If Japanese, generate Japanese. Etc.
- Do NOT translate — match the slide's language exactly.

OUTPUT FORMAT — return ONLY complete, valid JSON (no markdown, no code fences, no extra text).
Make sure the final character is a closing brace }:

{
  "branches": [
    {
      "branch_id": "b1",
      "predicted_text": "What the speaker might say for this point...",
      "action": {
        "type": "highlight",
        "bbox_1000": [ymin, xmin, ymax, xmax],
        "duration_ms": 3000
      },
      "teleprompter": "Short hint for teleprompter...",
      "next_branches": [
        {
          "branch_id": "b2",
          "predicted_text": "The NEXT thing they might say after b1...",
          "action": { "type": "none", "bbox_1000": [], "duration_ms": 0 },
          "teleprompter": "...",
          "next_branches": []
        }
      ]
    }
  ]
}

RULES:
1. Generate 3-4 TOP-LEVEL branches covering different ways to approach the CURRENT slide.
2. Each top-level branch should have 1-2 child branches (next_branches).
3. Each child branch should have 1 grandchild branch (keep it shallow, ~15 nodes total).
4. branch_id format: short, e.g. b1, b1_a, b1_a1.
5. predicted_text: What the speaker would ACTUALLY SAY (natural spoken language, 1-2 short sentences).
6. teleprompter: A very short hint for the speaker (≤10 words, can be same as predicted_text).
7. action.type: Pick from: highlight, circle, arrow, transition, none.
8. BBOX COORDINATES (CRITICAL — be precise):
   bbox_1000 uses 0-1000 normalized coordinates where [0,0] is top-left and [1000,1000] is bottom-right.
   Look CAREFULLY at the current slide image and estimate where each element actually sits:
   - Y-axis: 0=very top, 250=top quarter, 500=middle, 750=lower quarter, 1000=bottom.
   - X-axis: 0=left edge, 250=left quarter, 500=center, 750=right quarter, 1000=right edge.
   For each element you want to highlight, look at its position on the slide and estimate the
   bounding box coordinates. Be as precise as possible — the bbox should tightly enclose the element.
   For "transition" and "none" actions: bbox_1000 should be [].
9. Vary the action types across branches.
10. If a branch is the LAST branch in a path, its action.type should be "transition".
11. ADJACENT SLIDE AWARENESS (text context only): Prev/next slide TEXT is provided for narrative context.
    - Use prev slide text to understand what was already covered (don't repeat).
    - Use next slide text to prepare natural transitions.
    - ALL generated branches MUST be about the CURRENT slide's content and visuals.
    - bbox_1000 coordinates MUST reference elements on the CURRENT slide image ONLY.
12. Keep all text concise. Output MUST be COMPLETE valid JSON ending with }."""


# ────────────────────────────────────────────────────────────
# Generator
# ────────────────────────────────────────────────────────────

class BranchGenerator:
    """Generates a 3-level branch tree for a slide using a multimodal LLM.

    The LLM sees the slide image and predicts multiple paths the speaker
    might take, each with an associated visual action (highlight/circle/etc).
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def generate(
        self,
        slide_image_base64: str,
        slide_index: int = 0,
        total_slides: int = 1,
        max_depth: int = 3,
        prev_slide_text: str | None = None,
        next_slide_text: str | None = None,
    ) -> BranchTreeResponse:
        """Generate a branch tree for the given slide image.

        Adjacent slide text (prev/next) is passed to the LLM as
        narrative context without sending extra images.
        """
        t0 = time.monotonic()

        image_uri = _prepare_slide_image(slide_image_base64)
        if not image_uri:
            return BranchTreeResponse(
                slide_index=slide_index,
                total_slides=total_slides,
                error="Failed to prepare slide image",
            )

        try:
            branches = await self._call_llm_with_retry(
                image_uri, slide_index, total_slides,
                prev_slide_text=prev_slide_text,
                next_slide_text=next_slide_text,
                max_retries=2,
            )

            # Trim depth if requested
            if max_depth < 3:
                branches = _trim_depth(branches, max_depth)

            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.info(
                "BranchGenerator: slide %d → %d top-level branches in %.0fms",
                slide_index,
                len(branches),
                elapsed_ms,
            )
            return BranchTreeResponse(
                slide_index=slide_index,
                total_slides=total_slides,
                branches=branches,
                generation_time_ms=round(elapsed_ms, 1),
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.exception("BranchGenerator failed for slide %d", slide_index)
            return BranchTreeResponse(
                slide_index=slide_index,
                total_slides=total_slides,
                generation_time_ms=round(elapsed_ms, 1),
                error=str(exc),
            )

    async def _call_llm_with_retry(
        self,
        image_uri: str,
        slide_index: int,
        total_slides: int,
        prev_slide_text: str | None = None,
        next_slide_text: str | None = None,
        max_retries: int = 2,
    ) -> list[BranchNode]:
        """Call LLM with retries on JSON parse failures.

        On retry, appends a correction hint to the user prompt asking
        the LLM to fix its JSON formatting.
        """
        last_error: str | None = None
        for attempt in range(max_retries + 1):
            try:
                return await self._call_llm(
                    image_uri, slide_index, total_slides,
                    prev_slide_text=prev_slide_text,
                    next_slide_text=next_slide_text,
                    retry_hint=(
                        f"Your previous output was NOT valid JSON. Error: {last_error}. "
                        "Please respond with ONLY valid JSON — no trailing commas, "
                        "no unquoted keys, no markdown fences, no extra text."
                    )
                    if last_error else None,
                )
            except (json.JSONDecodeError, ValueError) as e:
                last_error = str(e)
                if attempt < max_retries:
                    logger.warning(
                        "BranchGenerator slide %d JSON parse error (attempt %d/%d): %s. Retrying...",
                        slide_index,
                        attempt + 1,
                        max_retries,
                        last_error,
                    )
                else:
                    logger.error(
                        "BranchGenerator slide %d JSON parse failed after %d retries: %s",
                        slide_index,
                        max_retries,
                        last_error,
                    )
                    raise

        # Unreachable — kept for type checker
        raise RuntimeError("_call_llm_with_retry: unexpected fallthrough")

    async def _call_llm(
        self,
        image_uri: str,
        slide_index: int,
        total_slides: int,
        prev_slide_text: str | None = None,
        next_slide_text: str | None = None,
        retry_hint: str | None = None,
    ) -> list[BranchNode]:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        # Build text instruction with adjacent slide text context
        text_parts: list[str] = [
            f"Slide {slide_index + 1} of {total_slides}.",
        ]

        if prev_slide_text:
            text_parts.append(
                f"PREVIOUS SLIDE CONTENT (already covered by speaker):\n{prev_slide_text}"
            )

        if next_slide_text:
            text_parts.append(
                f"NEXT SLIDE CONTENT (upcoming, for transition prep):\n{next_slide_text}"
            )

        text_parts.append(
            "Generate a branch tree for the CURRENT slide ONLY (slide "
            f"{slide_index + 1}). The image below IS the current slide."
        )

        if retry_hint:
            text_parts.append(f"\n⚠️ CORRECTION NEEDED: {retry_hint}")

        user_content: list[dict] = [
            {"type": "image_url", "image_url": {"url": image_uri}},
            {"type": "text", "text": "\n\n".join(text_parts)},
        ]

        # Build a dedicated ChatOpenAI for branch generation.
        # Uses BRANCH_LLM_* settings which default to the main (Google) LLM.
        kwargs: dict = {
            "model": settings.branch_llm_model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.branch_llm_max_tokens,
        }
        if settings.branch_llm_endpoint:
            kwargs["base_url"] = settings.branch_llm_endpoint
        if settings.branch_llm_api_key:
            kwargs["api_key"] = settings.branch_llm_api_key
            kwargs["openai_api_key"] = settings.branch_llm_api_key
        if settings.branch_llm_request_timeout > 0:
            kwargs["http_client"] = httpx.Client(timeout=settings.branch_llm_request_timeout)

        chat_model = ChatOpenAI(**kwargs)
        messages = [
            SystemMessage(content=BRANCH_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        # Diagnostic: log call info
        has_prev = bool(prev_slide_text)
        has_next = bool(next_slide_text)
        logger.info(
            "BranchGenerator calling LLM (model=%s, endpoint=%s, max_tokens=%d, prev_text=%s, next_text=%s)",
            settings.branch_llm_model,
            settings.branch_llm_endpoint,
            settings.branch_llm_max_tokens,
            has_prev,
            has_next,
        )

        t0 = time.monotonic()
        response = await asyncio.to_thread(chat_model.invoke, messages)
        elapsed = time.monotonic() - t0
        logger.info("BranchGenerator LLM call completed in %.2fs", elapsed)

        # Diagnostic: dump response structure to find where the content lives
        logger.info(
            "BranchGenerator response type=%s, has_attrs=%s",
            type(response).__name__,
            [a for a in dir(response) if not a.startswith("_")],
        )

        # Try multiple ways to get content
        raw = ""
        if hasattr(response, "content") and response.content:
            raw = str(response.content)
        elif hasattr(response, "text") and response.text:
            raw = str(response.text)
        elif isinstance(response, dict):
            raw = response.get("content", "") or response.get("text", "") or json.dumps(response)
        else:
            # Last resort: dump everything
            raw_repr = repr(response)
            logger.error(
                "BranchGenerator: cannot extract text from response! repr=%s",
                raw_repr[:2000],
            )
            raise ValueError(
                f"Unexpected LLM response type: {type(response).__name__}. "
                f"repr={raw_repr[:300]}"
            )

        text = raw.strip()
        logger.info("BranchGenerator raw LLM response (len=%d, first 1200 chars): %s", len(text), repr(text[:1200]))

        # Truncation guard: if the raw text starts with { but has no closing }, the model hit its token limit
        if text.startswith("{") and not text.rstrip().endswith("}"):
            logger.error(
                "BranchGenerator: JSON appears truncated (starts with '{' but no closing '}', "
                "len=%d). Try increasing BRANCH_LLM_MAX_TOKENS.",
                len(text),
            )
            raise ValueError(
                f"LLM output truncated ({len(text)} chars). "
                "The branch tree JSON was cut off — increase BRANCH_LLM_MAX_TOKENS or reduce tree size."
            )

        # Clean and parse JSON
        cleaned = _clean_json(text)
        logger.info("BranchGenerator cleaned text (len=%d, first 400 chars): %s", len(cleaned), repr(cleaned[:400]))

        if not cleaned or not cleaned.strip():
            logger.error("BranchGenerator: cleaned text is empty! raw=%r", raw[:500])
            raise ValueError("LLM returned empty response after cleaning")

        data = json.loads(cleaned)

        branches_raw = data.get("branches", [])
        return [_parse_branch_node(b) for b in branches_raw]


# ────────────────────────────────────────────────────────────
# Parsing helpers
# ────────────────────────────────────────────────────────────

def _clean_json(text: str) -> str:
    """Extract JSON from potentially messy LLM output.

    Handles:
    - Markdown code fences (```json ... ```)
    - Gemma `<thought>...</thought>` tags
    - Text before/after the JSON object
    - Multiple JSON blocks (takes the largest one)
    """
    if not text or not text.strip():
        return ""

    # Strategy 1: Strip <thought>...</thought> blocks (Gemma common pattern)
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Strategy 2: Remove markdown code fences
    text = re.sub(r"```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```", "", text)

    # Strategy 3: Find ALL {...} blocks, pick the largest one (most likely the JSON we want)
    candidates: list[tuple[int, int]] = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                candidates.append((start, i + 1))
                start = -1

    if not candidates:
        # No braces found at all
        logger.warning("_clean_json: no JSON object found in text (len=%d)", len(text))
        return text.strip()

    # Pick the largest block
    best = max(candidates, key=lambda pair: pair[1] - pair[0])
    result = text[best[0] : best[1]].strip()

    # Strategy 4: Try to fix trailing garbage (e.g. extra text after the last })
    # Already handled by picking the longest balanced block

    return _fix_json_quirks(result)


def _fix_json_quirks(text: str) -> str:
    """Fix common LLM JSON formatting mistakes.

    - Trailing comma before }, ], or at end of line
    - Unquoted keys (e.g. {key: "value"} → {"key": "value"})
    """
    if not text:
        return text

    # Remove trailing commas before } or ]
    text = re.sub(r",(\s*[}\]])", r"\1", text)

    # Remove trailing comma at end of line (before newline + } or ])
    text = re.sub(r",(\s*\n\s*[}\]])", r"\1", text)

    return text


def _parse_branch_node(raw: dict) -> BranchNode:
    """Recursively parse a branch node from raw dict, with validation."""
    action_raw = raw.get("action", {})
    action_type_str = action_raw.get("type", "none")
    try:
        action_type = BranchActionType(action_type_str)
    except ValueError:
        logger.warning("Unknown action type %r, defaulting to none", action_type_str)
        action_type = BranchActionType.NONE

    action = BranchAction(
        type=action_type,
        bbox_1000=action_raw.get("bbox_1000", []),
        duration_ms=action_raw.get("duration_ms", 3000),
    )

    next_raw = raw.get("next_branches", [])
    next_branches = [_parse_branch_node(n) for n in next_raw]

    return BranchNode(
        branch_id=raw.get("branch_id", ""),
        predicted_text=raw.get("predicted_text", ""),
        action=action,
        teleprompter=raw.get("teleprompter", raw.get("predicted_text", "")),
        next_branches=next_branches,
    )


def _trim_depth(branches: list[BranchNode], max_depth: int) -> list[BranchNode]:
    """Trim the branch tree to a given depth (1 = top-level only, 2 = + children, 3 = full)."""
    if max_depth <= 1:
        return [
            BranchNode(
                branch_id=b.branch_id,
                predicted_text=b.predicted_text,
                action=b.action,
                teleprompter=b.teleprompter,
                next_branches=[],
            )
            for b in branches
        ]
    return [
        BranchNode(
            branch_id=b.branch_id,
            predicted_text=b.predicted_text,
            action=b.action,
            teleprompter=b.teleprompter,
            next_branches=_trim_depth(b.next_branches, max_depth - 1),
        )
        for b in branches
    ]
