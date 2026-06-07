from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
import time

from PIL import Image
from pydantic import BaseModel

from app.schemas.live import ScriptSuggestion
from app.services.llm_factory import build_live_chat_model

logger = logging.getLogger(__name__)

# ——————————————————————————————————————————————
# Image preprocessing
# ——————————————————————————————————————————————

def _prepare_slide_image(image_base64: str, max_size: int = 1024) -> str | None:
    """Resize slide PNG to JPEG, longest side ≤ max_size, return as data-URI string."""
    try:
        # Strip data URI prefix if present (e.g. "data:image/png;base64,...")
        if image_base64.startswith("data:"):
            image_base64 = image_base64.split(",", 1)[1]
        raw = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(raw))
        w, h = img.size
        if max(w, h) <= max_size:
            return _to_data_uri(img)
        scale = max_size / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception:
        logger.warning("Failed to resize slide image", exc_info=True)
        return None


def _to_data_uri(img: Image.Image) -> str:
    """Convert image to JPEG data-URI for smaller payload than PNG."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"


# ——————————————————————————————————————————————
# Model & Adapter
# ——————————————————————————————————————————————

class _AdapterOutput(BaseModel):
    next_suggestion: str = ""
    transition_ready: bool = False


class ScriptAdapter:
    """Calls a multimodal LLM to adapt the presentation script based on the
    user's live speech and the current slide screenshot."""

    SYSTEM_PROMPT = (
        "You are an expert live presentation co-pilot. "
        "You see the current slide as an image and hear what the speaker is saying. "
        "Your job is to give the speaker a natural 1-2 sentence suggestion for what to say NEXT.\n\n"
        "Context you receive:\n"
        "- Slide image (what the audience sees right now)\n"
        "- User's actual speech so far (ASR transcript)\n"
        "- Previous slide summary (may be empty on the first slide)\n\n"
        "Your task:\n"
        "1. Look at the slide — understand its topic, structure, charts, bullet points.\n"
        "2. Compare what the user already said with what the slide covers.\n"
        "3. Generate 1-2 sentences for what they should say NEXT to move the presentation forward.\n"
        "4. If the user has covered all key points on this slide, set transition_ready: true.\n\n"
        "Rules:\n"
        "- Match the user's speaking style and language. Don't force them back to a rigid script.\n"
        "- Keep suggestions natural and conversational — like a friend whispering in their ear.\n"
        "- If the user just introduced the slide topic, suggest the first key point.\n"
        "- If they're mid-way, suggest the next logical point.\n"
        "- If they've covered everything, summarize briefly and set transition_ready: true.\n"
        "- Return ONLY valid JSON: {\"next_suggestion\": \"...\", \"transition_ready\": true/false}\n"
        "- No markdown, no code fences, no <thought> tags, no extra characters."
    )

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._last_call_time = 0.0

    async def adapt(
        self,
        user_speech: str,
        previous_summary: str,
        slide_image_base64: str | None = None,
    ) -> ScriptSuggestion | None:
        """Generate a suggestion. Debounces: skips if called within 2s of last call."""
        async with self._lock:
            now = time.monotonic()
            if now - self._last_call_time < 2.0:
                logger.debug("ScriptAdapter debounced (last call %.1fs ago)", now - self._last_call_time)
                return None
            self._last_call_time = now

        return await asyncio.wait_for(
            self._call_llm(user_speech, previous_summary, slide_image_base64),
            timeout=15.0,
        )

    async def _call_llm(
        self,
        user_speech: str,
        previous_summary: str,
        slide_image_base64: str | None,
    ) -> ScriptSuggestion | None:
        from langchain_core.messages import HumanMessage, SystemMessage

        image_uri = _prepare_slide_image(slide_image_base64) if slide_image_base64 else None

        # Build multimodal user message
        user_content: list[dict] = []
        if image_uri:
            user_content.append({"type": "image_url", "image_url": {"url": image_uri}})
        user_content.append({
            "type": "text",
            "text": (
                f"User's actual speech so far:\n{user_speech}\n\n"
                f"Previous slide summary:\n{previous_summary or '(first slide — no previous summary)'}"
            ),
        })

        chat_model = build_live_chat_model()
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        t0 = time.monotonic()
        response = await asyncio.to_thread(chat_model.invoke, messages)
        elapsed = time.monotonic() - t0
        logger.info("ScriptAdapter LLM call completed in %.2fs", elapsed)

        raw = response.content if hasattr(response, "content") else str(response)
        text = str(raw).strip()
        logger.debug("ScriptAdapter raw LLM response: %s", repr(text[:500]))

        text = _clean_llm_output(text)
        logger.debug("ScriptAdapter cleaned text: %s", repr(text[:300]))

        parsed = _parse_json_output(text)
        return ScriptSuggestion(
            next_suggestion=parsed.next_suggestion,
            transition_ready=parsed.transition_ready,
        )


# ——————————————————————————————————————————————
# Output cleaning helpers
# ——————————————————————————————————————————————

def _clean_llm_output(text: str) -> str:
    """Strip Gemma thinking blocks and markdown fences from LLM output."""
    text = re.sub(r"<thought>.*?</thought>\s*", "", text, flags=re.DOTALL)
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    return text


def _parse_json_output(text: str) -> _AdapterOutput:
    """Parse adapter JSON, with a fallback that extracts the first {...} object."""
    try:
        return _AdapterOutput.model_validate_json(text)
    except Exception:
        match = re.search(r"\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]*\}", text)
        if match:
            logger.debug("ScriptAdapter fallback JSON extraction: %r", match.group()[:200])
            return _AdapterOutput.model_validate_json(match.group())
        raise
