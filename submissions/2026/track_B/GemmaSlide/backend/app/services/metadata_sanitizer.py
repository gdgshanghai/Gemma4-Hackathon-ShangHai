from __future__ import annotations

from app.core.config import settings
from app.schemas.pptx import AiReadyElement, ShapeElement, SlideResult


class MetadataSanitizer:
    _decorative_types = {
        "LINE",
        "CONNECTOR",
        "FREEFORM",
        "BACKGROUND",
    }
    _semantic_types = {
        "PICTURE",
        "TABLE",
        "CHART",
        "TEXT_BOX",
        "PLACEHOLDER",
    }

    @staticmethod
    def _position_bucket(element: ShapeElement) -> str:
        center_x = element.bbox_norm.x + (element.bbox_norm.width / 2.0)
        center_y = element.bbox_norm.y + (element.bbox_norm.height / 2.0)

        col = (
            "left" if center_x < 1 / 3 else ("right" if center_x > 2 / 3 else "center")
        )
        row = (
            "top" if center_y < 1 / 3 else ("bottom" if center_y > 2 / 3 else "center")
        )

        if row == "center" and col == "center":
            return "center"
        return f"{row}-{col}"

    @staticmethod
    def _content_for(element: ShapeElement) -> str:
        if element.text and element.text.strip():
            return element.text.strip()

        if element.shape_type_name == "PICTURE":
            return f"Image '{element.name}'"
        if element.shape_type_name == "TABLE":
            rows = element.table_rows or 0
            cols = element.table_cols or 0
            return f"Table ({rows}x{cols})"
        if element.shape_type_name == "CHART" or element.has_chart:
            return f"Chart '{element.name}'"

        return element.name

    @classmethod
    def _is_decorative(cls, element: ShapeElement) -> bool:
        area = element.bbox_norm.width * element.bbox_norm.height
        has_text = bool(element.text and element.text.strip())
        typ = element.shape_type_name.upper()

        if not has_text and typ in cls._decorative_types:
            return True

        if (
            not has_text
            and area < settings.decorative_min_area_norm
            and typ not in cls._semantic_types
        ):
            return True

        # Typical slide background rectangle.
        if not has_text and typ == "AUTO_SHAPE" and area > 0.85:
            return True

        return False

    @classmethod
    def simplify_slide(cls, slide: SlideResult) -> list[AiReadyElement]:
        simplified: list[AiReadyElement] = []
        for element in slide.elements:
            if cls._is_decorative(element):
                continue

            simplified.append(
                AiReadyElement(
                    element_id=element.element_id,
                    type=element.shape_type_name,
                    content=cls._content_for(element),
                    normalized_position=cls._position_bucket(element),
                    bbox_px=element.bbox_px,
                )
            )
        return simplified
