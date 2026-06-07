from app.schemas.pptx import BBoxEmu, BBoxNorm, BBoxPx


def clamp_norm(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def emu_to_norm(bbox: BBoxEmu, slide_width_emu: int, slide_height_emu: int) -> BBoxNorm:
    if slide_width_emu <= 0 or slide_height_emu <= 0:
        return BBoxNorm(x=0.0, y=0.0, width=0.0, height=0.0)

    return BBoxNorm(
        x=clamp_norm(bbox.x / slide_width_emu),
        y=clamp_norm(bbox.y / slide_height_emu),
        width=clamp_norm(bbox.width / slide_width_emu),
        height=clamp_norm(bbox.height / slide_height_emu),
    )


def emu_to_px(
    bbox: BBoxEmu,
    slide_width_emu: int,
    slide_height_emu: int,
    image_width_px: int,
    image_height_px: int,
) -> BBoxPx:
    if slide_width_emu <= 0 or slide_height_emu <= 0:
        return BBoxPx(x=0, y=0, width=0, height=0)

    x = round(bbox.x / slide_width_emu * image_width_px)
    y = round(bbox.y / slide_height_emu * image_height_px)
    w = round(bbox.width / slide_width_emu * image_width_px)
    h = round(bbox.height / slide_height_emu * image_height_px)

    return BBoxPx(x=max(0, x), y=max(0, y), width=max(0, w), height=max(0, h))
