from app.schemas.pptx import (
    BBoxEmu,
    BBoxNorm,
    BBoxPx,
    ShapeElement,
    SlideImage,
    SlideResult,
)
from app.services.metadata_sanitizer import MetadataSanitizer


def _shape(
    *,
    element_id: str,
    shape_type_name: str,
    text: str | None,
    x: float,
    y: float,
    w: float,
    h: float,
    name: str = "shape",
) -> ShapeElement:
    return ShapeElement(
        element_id=element_id,
        z_index=1,
        name=name,
        shape_type_code=1,
        shape_type_name=shape_type_name,
        is_group=False,
        has_text=bool(text),
        text=text,
        bbox_emu=BBoxEmu(x=0, y=0, width=0, height=0),
        bbox_norm=BBoxNorm(x=x, y=y, width=w, height=h),
        bbox_px=BBoxPx(x=0, y=0, width=0, height=0),
    )


def test_simplify_slide_filters_decorative_and_keeps_semantic() -> None:
    decorative_line = _shape(
        element_id="1.1",
        shape_type_name="LINE",
        text=None,
        x=0.1,
        y=0.1,
        w=0.05,
        h=0.001,
    )
    title = _shape(
        element_id="1.2",
        shape_type_name="TEXT_BOX",
        text="Quarterly results",
        x=0.05,
        y=0.05,
        w=0.9,
        h=0.1,
    )
    picture = _shape(
        element_id="1.3",
        shape_type_name="PICTURE",
        text=None,
        x=0.65,
        y=0.2,
        w=0.2,
        h=0.2,
        name="logo",
    )

    slide = SlideResult(
        slide_index=1,
        slide_width_emu=0,
        slide_height_emu=0,
        image=SlideImage(width_px=1920, height_px=1080, image_base64=None),
        elements=[decorative_line, title, picture],
    )

    simplified = MetadataSanitizer.simplify_slide(slide)
    ids = [item.element_id for item in simplified]

    assert "1.1" not in ids
    assert "1.2" in ids
    assert "1.3" in ids


def test_position_bucket_center_and_corner() -> None:
    center = _shape(
        element_id="1.1",
        shape_type_name="TEXT_BOX",
        text="Center",
        x=0.4,
        y=0.4,
        w=0.2,
        h=0.2,
    )
    top_left = _shape(
        element_id="1.2",
        shape_type_name="TEXT_BOX",
        text="Top left",
        x=0.01,
        y=0.01,
        w=0.1,
        h=0.1,
    )

    slide = SlideResult(
        slide_index=1,
        slide_width_emu=0,
        slide_height_emu=0,
        image=SlideImage(width_px=100, height_px=100, image_base64=None),
        elements=[center, top_left],
    )
    simplified = MetadataSanitizer.simplify_slide(slide)

    by_id = {item.element_id: item for item in simplified}
    assert by_id["1.1"].normalized_position == "center"
    assert by_id["1.2"].normalized_position == "top-left"
