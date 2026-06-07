from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


class FileService:
    @staticmethod
    async def save_upload(file: UploadFile) -> tuple[str, Path]:
        file_name = file.filename or "uploaded.pptx"
        if not file_name.lower().endswith(".pptx"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .pptx files are supported.",
            )

        request_id = str(uuid4())
        request_dir = settings.temp_root / request_id
        request_dir.mkdir(parents=True, exist_ok=True)

        file_path = request_dir / file_name
        size_limit = settings.max_upload_size_mb * 1024 * 1024
        total_size = 0

        try:
            with file_path.open("wb") as f:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > size_limit:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File exceeds max size {settings.max_upload_size_mb}MB.",
                        )
                    f.write(chunk)
        except Exception:
            shutil.rmtree(request_dir, ignore_errors=True)
            raise

        return request_id, file_path

    @staticmethod
    def cleanup_request_dir(request_id: str) -> None:
        request_dir = settings.temp_root / request_id
        if request_dir.exists():
            shutil.rmtree(request_dir, ignore_errors=True)
