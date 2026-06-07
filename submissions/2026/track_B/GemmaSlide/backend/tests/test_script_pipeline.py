from app.schemas.pptx import (
    BBoxEmu,
    BBoxNorm,
    BBoxPx,
    CueActionType,
    CueTiming,
    ParsePptxResponse,
    ShapeElement,
    SlideImage,
    SlideResult,
)
from app.services.script_pipeline import ScriptPipelineService, _LlmSlideScript


class _FakeStructuredModel:
    def __init__(self, outputs):
        self._outputs = outputs
        self._index = 0

    def invoke(self, _messages):
        output = self._outputs[self._index]
        self._index += 1
        if isinstance(output, Exception):
            raise output
        return output


class _FakeChatModel:
    def __init__(self, outputs):
        self._outputs = outputs

    def with_structured_output(self, _schema):
        return _FakeStructuredModel(self._outputs)


def _shape(element_id: str, bbox_x: int) -> ShapeElement:
    return ShapeElement(
        element_id=element_id,
        z_index=1,
        name=element_id,
        shape_type_code=1,
        shape_type_name="TEXT_BOX",
        is_group=False,
        has_text=True,
        text="content",
        bbox_emu=BBoxEmu(x=0, y=0, width=0, height=0),
        bbox_norm=BBoxNorm(x=0.0, y=0.0, width=0.1, height=0.1),
        bbox_px=BBoxPx(x=bbox_x, y=20, width=30, height=40),
    )


def test_generate_script_converts_bbox_from_1000_scale(monkeypatch) -> None:
    slide_1 = SlideResult(
        slide_index=1,
        slide_width_emu=100,
        slide_height_emu=100,
        image=SlideImage(width_px=1000, height_px=500, image_base64="img-1"),
        elements=[_shape("1.1", 100)],
    )
    parsed = ParsePptxResponse(
        file_name="deck.pptx",
        total_slides=1,
        total_elements=1,
        slides=[slide_1],
    )

    fake_outputs = [
        _LlmSlideScript(
            narrative_segments=[
                {
                    "text": "First slide line",
                    "visual_cue": {
                        "action_type": CueActionType.HIGHLIGHT,
                        "box": [500, 500, 700, 700],
                        "timing": CueTiming.MIDDLE,
                    },
                }
            ],
            summary="slide one",
        ),
    ]

    monkeypatch.setattr(
        "app.services.script_pipeline.build_chat_model",
        lambda _llm_model: _FakeChatModel(fake_outputs),
    )

    result = ScriptPipelineService.generate_presentation_script(parsed)

    first_segment = result.slides[0].narrative_segments[0]

    assert first_segment.visual_cue.action_type == CueActionType.HIGHLIGHT
    assert first_segment.visual_cue.bbox_px is not None
    assert first_segment.visual_cue.bbox_px.x == 500
    assert first_segment.visual_cue.bbox_px.y == 250
    assert first_segment.visual_cue.bbox_px.width == 200
    assert first_segment.visual_cue.bbox_px.height == 100


def test_generate_script_keeps_null_bbox_when_none(monkeypatch) -> None:
    slide = SlideResult(
        slide_index=1,
        slide_width_emu=100,
        slide_height_emu=100,
        image=SlideImage(width_px=1000, height_px=500, image_base64="img-1"),
        elements=[_shape("1.1", 100)],
    )
    parsed = ParsePptxResponse(
        file_name="deck.pptx",
        total_slides=1,
        total_elements=1,
        slides=[slide],
    )

    fake_outputs = [
        _LlmSlideScript(
            narrative_segments=[
                {
                    "text": "Point at word",
                    "visual_cue": {
                        "action_type": CueActionType.CIRCLE,
                        "box": None,
                        "timing": CueTiming.MIDDLE,
                    },
                }
            ],
            summary="slide one",
        )
    ]

    monkeypatch.setattr(
        "app.services.script_pipeline.build_chat_model",
        lambda _llm_model: _FakeChatModel(fake_outputs),
    )

    result = ScriptPipelineService.generate_presentation_script(parsed)
    segment = result.slides[0].narrative_segments[0]

    assert segment.visual_cue.action_type == CueActionType.CIRCLE
    assert segment.visual_cue.bbox_px is None


def test_metadata_sanitizer_reference_contains_element_bbox() -> None:
    refs = ScriptPipelineService._build_user_content(
        image_base64="data:image/png;base64,abc",
        previous_context="",
    )

    assert refs[0]["type"] == "text"
    assert "normalized 0-1000 coordinates" in refs[0]["text"]
    assert "[ymin, xmin, ymax, xmax]" in refs[0]["text"]


def test_generate_script_retries_invalid_json_then_succeeds(monkeypatch) -> None:
    slide = SlideResult(
        slide_index=1,
        slide_width_emu=100,
        slide_height_emu=100,
        image=SlideImage(width_px=1000, height_px=500, image_base64="img-1"),
        elements=[_shape("1.1", 100)],
    )
    parsed = ParsePptxResponse(
        file_name="deck.pptx",
        total_slides=1,
        total_elements=1,
        slides=[slide],
    )

    fake_outputs = [
        RuntimeError(
            "1 validation error for _LlmSlideScript: Invalid JSON: trailing characters"
        ),
        _LlmSlideScript(
            narrative_segments=[
                {
                    "text": "Retry success",
                    "visual_cue": {
                        "action_type": CueActionType.HIGHLIGHT,
                        "box": [100, 100, 200, 200],
                        "timing": CueTiming.MIDDLE,
                    },
                }
            ],
            summary="ok",
        ),
    ]

    monkeypatch.setattr(
        "app.services.script_pipeline.build_chat_model",
        lambda _llm_model: _FakeChatModel(fake_outputs),
    )

    result = ScriptPipelineService.generate_presentation_script(parsed)
    segment = result.slides[0].narrative_segments[0]
    assert segment.text == "Retry success"
    assert segment.visual_cue.bbox_px is not None
    assert segment.visual_cue.bbox_px.x == 100
