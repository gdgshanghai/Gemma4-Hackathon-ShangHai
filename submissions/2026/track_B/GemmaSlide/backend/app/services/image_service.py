from __future__ import annotations

import base64
import inspect
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class SlideImageInfo:
    slide_index: int
    path: Path
    width_px: int
    height_px: int
    base64_data: str | None


class ImageService:
    @staticmethod
    def _slide_sort_key(path: Path) -> tuple[int, str]:
        digits = "".join(ch for ch in path.stem if ch.isdigit())
        if digits:
            return int(digits), path.name
        return 10**9, path.name

    @staticmethod
    def convert_pptx_to_images(pptx_path: Path, output_dir: Path) -> list[Path]:
        missing_tools = [
            tool for tool in ("soffice", "pdftoppm") if shutil.which(tool) is None
        ]
        if missing_tools:
            missing = ", ".join(missing_tools)
            raise RuntimeError(
                f"Missing required system tools: {missing}. Install LibreOffice and Poppler utils and ensure they are in PATH."
            )

        from pptxtoimages.tools import PPTXToImageConverter

        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            converter = PPTXToImageConverter(str(pptx_path), output_dir=str(output_dir))
        except TypeError:
            converter = PPTXToImageConverter(str(pptx_path))

        convert_params = inspect.signature(converter.convert).parameters
        if len(convert_params) == 0:
            image_paths = converter.convert()
        elif "output_dir" in convert_params:
            try:
                image_paths = converter.convert(
                    str(pptx_path), output_dir=str(output_dir)
                )
            except TypeError:
                image_paths = converter.convert(output_dir=str(output_dir))
        else:
            image_paths = converter.convert(str(pptx_path))

        return [Path(p) for p in image_paths]

    @staticmethod
    def collect_image_infos(
        image_paths: list[Path], include_base64: bool
    ) -> dict[int, SlideImageInfo]:
        image_infos: dict[int, SlideImageInfo] = {}
        for idx, img_path in enumerate(
            sorted(image_paths, key=ImageService._slide_sort_key), start=1
        ):
            with Image.open(img_path) as img:
                width_px, height_px = img.size

            base64_data = None
            if include_base64:
                raw = img_path.read_bytes()
                encoded = base64.b64encode(raw).decode("ascii")
                base64_data = f"data:image/png;base64,{encoded}"

            image_infos[idx] = SlideImageInfo(
                slide_index=idx,
                path=img_path,
                width_px=width_px,
                height_px=height_px,
                base64_data=base64_data,
            )

        return image_infos
