from pathlib import Path

# 项目根目录为当前文件所在目录，便于上传 GitHub 后在其他机器运行。
BASE_DIR = Path(__file__).resolve().parent

# 数据集相关目录
DATASET_DIR = BASE_DIR / "dataset"
DATASET_IMAGES_DIR = DATASET_DIR / "images"
DATASET_LABELS_DIR = DATASET_DIR / "labels"
PUBLIC_DATA_DIR = BASE_DIR / "public_data"

# 输入输出目录
INPUTS_DIR = BASE_DIR / "inputs"
OUTPUTS_DIR = BASE_DIR / "outputs"
RUNS_DIR = OUTPUTS_DIR / "runs"
EXPORT_DIR = OUTPUTS_DIR / "export"
METRICS_DIR = OUTPUTS_DIR / "metrics"
PREDICT_IMAGE_DIR = OUTPUTS_DIR / "predict_images"
PREDICT_VIDEO_DIR = OUTPUTS_DIR / "predict_videos"
WEIGHTS_DIR = BASE_DIR / "weights"

# 数据集划分
SPLITS = ("train", "val", "test")

# 类别配置：按你的新需求改成单类别摔倒检测
CLASS_NAMES = ["fall"]
CLASS_ID = 0

# 训练参数
# 使用官方预训练权重微调，比从 yolov8n.yaml 从零训练更适合当前小数据集。
MODEL_NAME = str(WEIGHTS_DIR / "yolov8n.pt")
TRAIN_RUN_NAME = "train_fall_pretrained"
EPOCHS = 100
IMG_SIZE = 640
GPU_BATCH_SIZE = 8
CPU_BATCH_SIZE = 4
CONF_THRES = 0.45
IOU_THRES = 0.45
WORKERS = 0

# 视频行为确认参数：连续多帧检测到 fall 才提示报警
FALL_CONFIRM_FRAMES = 5

# 推理输入
DEFAULT_IMAGE_PATH = INPUTS_DIR / "test.jpg"
DEFAULT_VIDEO_PATH = INPUTS_DIR / "test.mp4"
WEBCAM_INDEX = 0
WINDOW_NAME = "Fall Detection YOLOv8"

# Conda 环境
CONDA_BAT = Path(r"E:\Anaconda\condabin\conda.bat")
ENV_NAME = "yolov8"

# 可接受的图片和视频格式
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}

# 将公开数据中的摔倒相关类别合并成单类 fall
POSITIVE_CLASS_KEYWORDS = {
    "fall",
    "fallen",
    "falling",
    "fall detected",
}

# 不纳入摔倒单类的数据类别
NEGATIVE_CLASS_KEYWORDS = {
    "no fall",
    "nofall",
    "normal",
    "standing",
    "stand",
    "sitting",
    "sit",
    "walking",
    "walk",
    "bending",
    "bend",
    "sleeping",
    "sleep",
    "crouching",
    "crouch",
}


def ensure_directories():
    """创建项目运行所需的全部目录。"""
    for split in SPLITS:
        (DATASET_IMAGES_DIR / split).mkdir(parents=True, exist_ok=True)
        (DATASET_LABELS_DIR / split).mkdir(parents=True, exist_ok=True)

    for folder in (
        PUBLIC_DATA_DIR,
        INPUTS_DIR,
        OUTPUTS_DIR,
        RUNS_DIR,
        EXPORT_DIR,
        METRICS_DIR,
        PREDICT_IMAGE_DIR,
        PREDICT_VIDEO_DIR,
        WEIGHTS_DIR,
    ):
        folder.mkdir(parents=True, exist_ok=True)


def get_data_yaml_path() -> Path:
    return DATASET_DIR / "data.yaml"


def get_best_model_path() -> Path:
    return WEIGHTS_DIR / "best.pt"


def get_last_model_path() -> Path:
    return WEIGHTS_DIR / "last.pt"


def get_exported_onnx_path() -> Path:
    return EXPORT_DIR / "best.onnx"
