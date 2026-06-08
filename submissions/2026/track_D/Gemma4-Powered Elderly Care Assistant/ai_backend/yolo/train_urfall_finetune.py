import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA = BASE_DIR / "dataset_urfall_frames" / "data.yaml"
DEFAULT_WEIGHTS = BASE_DIR / "weights" / "best.pt"
DEFAULT_OUTPUT_DIR = BASE_DIR / "outputs" / "runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune the fall detector with UR Fall extracted frames."
    )
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--name", default="train_urfall_finetune")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--device", default=None)
    parser.add_argument("--copy-best", action="store_true")
    return parser.parse_args()


def detect_device():
    try:
        import torch

        return 0 if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def main() -> None:
    args = parse_args()
    data_path = Path(args.data).resolve()
    weights_path = Path(args.weights).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not data_path.exists():
        raise FileNotFoundError(f"data.yaml not found: {data_path}")
    if not weights_path.exists():
        raise FileNotFoundError(f"weights not found: {weights_path}")

    device = args.device if args.device is not None else detect_device()
    model = YOLO(str(weights_path))
    result = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        device=device,
        project=str(output_dir),
        name=args.name,
        exist_ok=True,
    )

    run_dir = Path(getattr(result, "save_dir", output_dir / args.name))
    best_path = run_dir / "weights" / "best.pt"
    print(f"run_dir: {run_dir}")
    print(f"best_path: {best_path}")

    if args.copy_best and best_path.exists():
        target = BASE_DIR / "weights" / "best_urfall_finetuned.pt"
        shutil.copy2(best_path, target)
        print(f"copied_best: {target}")


if __name__ == "__main__":
    main()
