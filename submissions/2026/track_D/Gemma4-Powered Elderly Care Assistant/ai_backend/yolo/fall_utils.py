import re
import shutil
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from project_config import (
    BASE_DIR,
    CLASS_NAMES,
    CPU_BATCH_SIZE,
    DATASET_IMAGES_DIR,
    DATASET_LABELS_DIR,
    DEFAULT_IMAGE_PATH,
    DEFAULT_VIDEO_PATH,
    EXPORT_DIR,
    GPU_BATCH_SIZE,
    IMAGE_SUFFIXES,
    SPLITS,
    VIDEO_SUFFIXES,
    WEIGHTS_DIR,
)


def to_posix(path: Path) -> str:
    """将路径转换为 Ultralytics/YAML 更稳妥的字符串形式。"""
    return str(path).replace("\\", "/")


def detect_device():
    """自动识别设备；有 NVIDIA GPU 时优先使用 0。"""
    try:
        import torch

        return 0 if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def get_batch_size(device) -> int:
    """根据设备类型自动设置较稳妥的 batch。"""
    return GPU_BATCH_SIZE if device != "cpu" else CPU_BATCH_SIZE


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def list_images(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES])


def list_videos(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES])


def count_images_in_split(split: str) -> int:
    return len(list_images(DATASET_IMAGES_DIR / split))


def find_default_image() -> Optional[Path]:
    if DEFAULT_IMAGE_PATH.exists():
        return DEFAULT_IMAGE_PATH
    images = list_images(DEFAULT_IMAGE_PATH.parent)
    return images[0] if images else None


def find_default_video() -> Optional[Path]:
    if DEFAULT_VIDEO_PATH.exists():
        return DEFAULT_VIDEO_PATH
    videos = list_videos(DEFAULT_VIDEO_PATH.parent)
    return videos[0] if videos else None


def normalize_name(name: str) -> str:
    """统一类别名称，方便把多个公开数据映射成 fall 单类。"""
    return re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()


def resolve_names(names) -> List[str]:
    """兼容 data.yaml 中 names 为列表或字典两种写法。"""
    if isinstance(names, dict):
        ordered = []
        for key in sorted(names, key=lambda item: int(item)):
            ordered.append(str(names[key]))
        return ordered
    if isinstance(names, (list, tuple)):
        return [str(item) for item in names]
    return []


def ensure_dataset_not_empty():
    """训练前检查 train/val 是否至少有图片。"""
    train_count = count_images_in_split("train")
    val_count = count_images_in_split("val")
    if train_count == 0:
        raise RuntimeError(
            "训练集为空：请先把图片放到 E:\\traumatology\\dataset\\images\\train，"
            "并准备对应标签，或者运行 merge_public_datasets.py 合并公开数据。"
        )
    if val_count == 0:
        raise RuntimeError(
            "验证集为空：请先把图片放到 E:\\traumatology\\dataset\\images\\val，"
            "并准备对应标签，或者运行 merge_public_datasets.py 合并公开数据。"
        )


def dataset_summary_text() -> str:
    lines = ["当前数据集统计："]
    for split in SPLITS:
        lines.append(
            f"- {split}: 图片 {count_images_in_split(split)} 张，标签目录 {DATASET_LABELS_DIR / split}"
        )
    lines.append(f"- 类别: {CLASS_NAMES}")
    return "\n".join(lines)


def get_latest_run_weight(weight_name: str = "best.pt") -> Optional[Path]:
    candidates = sorted(BASE_DIR.glob(f"outputs/runs/**/weights/{weight_name}"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def locate_model(weight_name: str = "best.pt") -> Path:
    fixed_path = WEIGHTS_DIR / weight_name
    if fixed_path.exists():
        return fixed_path
    latest_path = get_latest_run_weight(weight_name)
    if latest_path and latest_path.exists():
        return latest_path
    raise FileNotFoundError(
        f"未找到模型文件 {weight_name}。请先运行 train_yolov8.py 完成训练。"
    )


def copy_weight_if_exists(source: Path, target: Path):
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def export_best_to_onnx(best_model_path: Path, img_size: int):
    """导出 ONNX，便于后续部署或跨环境推理。"""
    from ultralytics import YOLO

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(best_model_path))
    export_result = model.export(format="onnx", imgsz=img_size, opset=12, simplify=False)

    if export_result:
        exported_path = Path(export_result)
        final_path = EXPORT_DIR / "best.onnx"
        if exported_path.exists() and exported_path.resolve() != final_path.resolve():
            shutil.copy2(exported_path, final_path)
        return final_path
    return None


def make_unique_stem(dataset_name: str, split: str, image_path: Path, index: int) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", dataset_name).strip("_") or "dataset"
    safe_stem = re.sub(r"[^a-zA-Z0-9_]+", "_", image_path.stem).strip("_") or "image"
    return f"{safe_name}_{split}_{index:06d}_{safe_stem}"


def build_yolo_data_yaml_text(dataset_root: Path) -> str:
    dataset_root_text = to_posix(dataset_root)
    return "\n".join(
        [
            f"path: {dataset_root_text}",
            f"train: {dataset_root_text}/images/train",
            f"val: {dataset_root_text}/images/val",
            f"test: {dataset_root_text}/images/test",
            "names:",
            "  0: fall",
            "",
        ]
    )


def create_empty_label_for_image(image_path: Path, label_dir: Path):
    label_dir.mkdir(parents=True, exist_ok=True)
    label_path = label_dir / f"{image_path.stem}.txt"
    if not label_path.exists():
        label_path.write_text("", encoding="utf-8")


def create_empty_labels_for_existing_images():
    """给已有图片补齐空标签，便于后续手工标注或做负样本。"""
    for split in SPLITS:
        image_dir = DATASET_IMAGES_DIR / split
        label_dir = DATASET_LABELS_DIR / split
        for image_path in list_images(image_dir):
            create_empty_label_for_image(image_path, label_dir)


def iter_label_lines(label_path: Path) -> Iterable[str]:
    if not label_path.exists():
        return []
    return label_path.read_text(encoding="utf-8").splitlines()


def run_with_error_message(entry_func):
    """统一入口异常输出，避免新手看到大段 Python 回溯。"""
    try:
        entry_func()
    except KeyboardInterrupt:
        print("你已手动中断脚本执行。")
        sys.exit(1)
    except Exception as exc:
        print(f"运行失败：{exc}")
        sys.exit(1)
