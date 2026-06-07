from __future__ import annotations

import logging
from pathlib import Path

from fastapi import HTTPException, status
from pptx import Presentation

from app.core.config import settings
from app.schemas.pptx import ParsePptxResponse
from app.services.image_service import ImageService
from app.services.pptx_parser import parse_presentation

logger = logging.getLogger(__name__)


class PptxService:
    @staticmethod
    def parse_file(
        file_path: Path,
        include_images_base64: bool,
        flatten_groups: bool,
        element_types: set[str] | None,
    ) -> ParsePptxResponse:
        try:
            prs = Presentation(str(file_path))
            slide_count = len(prs.slides)
        except Exception as exc:
            logger.exception("Failed to read pptx file: %s", file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read pptx file: {exc}",
            ) from exc

        if slide_count > settings.max_slide_count:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Slide count exceeds max allowed: {settings.max_slide_count}",
            )

        output_dir = file_path.parent / "images"
        try:
            image_paths = ImageService.convert_pptx_to_images(file_path, output_dir)
            image_infos = ImageService.collect_image_infos(
                image_paths, include_images_base64
            )
        except Exception as exc:
            logger.exception("Failed to convert pptx to images for file: %s", file_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to convert pptx to images: {exc}",
            ) from exc

        try:
            slides, total_elements = parse_presentation(
                str(file_path),
                image_infos=image_infos,
                flatten_groups=flatten_groups,
                element_types=element_types,
            )
        except Exception as exc:
            logger.exception(
                "Failed to parse presentation contents for file: %s", file_path
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse presentation contents: {exc}",
            ) from exc

        return ParsePptxResponse(
            file_name=file_path.name,
            total_slides=len(slides),
            total_elements=total_elements,
            slides=slides,
            errors=[],
        )
