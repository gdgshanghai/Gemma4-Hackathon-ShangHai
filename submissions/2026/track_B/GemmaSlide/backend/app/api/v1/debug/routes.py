from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile

from app.schemas.pptx import ParsePptxResponse
from app.services.file_service import FileService
from app.services.pptx_service import PptxService

router = APIRouter(prefix="/debug", tags=["debug"])


@router.post("/pptx/parse", response_model=ParsePptxResponse)
async def parse_pptx(
    file: UploadFile = File(...),
    include_images_base64: bool = Query(default=True),
    flatten_groups: bool = Query(default=True),
    element_types: Annotated[list[str] | None, Query()] = None,
) -> ParsePptxResponse:
    request_id, file_path = await FileService.save_upload(file)
    try:
        filters = {
            item.strip().lower() for item in (element_types or []) if item.strip()
        }
        return PptxService.parse_file(
            file_path=file_path,
            include_images_base64=include_images_base64,
            flatten_groups=flatten_groups,
            element_types=(filters if filters else None),
        )
    finally:
        FileService.cleanup_request_dir(request_id)
