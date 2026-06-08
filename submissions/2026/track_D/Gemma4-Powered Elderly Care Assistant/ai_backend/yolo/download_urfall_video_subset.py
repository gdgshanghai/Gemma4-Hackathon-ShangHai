import argparse
import csv
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BASE_DIR / "inputs"
DEFAULT_MANIFEST = BASE_DIR / "video_validation" / "urfall_full_manifest.csv"
BASE_URL = "https://fenix.ur.edu.pl/~mkepski/ds/data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the 100 directly published UR Fall RGB MP4 videos."
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Download again even if the local file size matches the remote size.",
    )
    return parser.parse_args()


def build_items() -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []

    for index in range(1, 31):
        for camera in ("cam0", "cam1"):
            file_name = f"urfall_fall_{index:02d}_{camera}.mp4"
            remote_name = f"fall-{index:02d}-{camera}.mp4"
            items.append(
                {
                    "id": f"urfall_fall_{index:02d}_{camera}",
                    "label": "fall",
                    "camera": camera,
                    "file_name": file_name,
                    "url": f"{BASE_URL}/{remote_name}",
                }
            )

    for index in range(1, 41):
        file_name = f"urfall_adl_{index:02d}_cam0.mp4"
        remote_name = f"adl-{index:02d}-cam0.mp4"
        items.append(
            {
                "id": f"urfall_adl_{index:02d}_cam0",
                "label": "no_fall",
                "camera": "cam0",
                "file_name": file_name,
                "url": f"{BASE_URL}/{remote_name}",
            }
        )

    return items


def remote_size(url: str, timeout: int) -> Optional[int]:
    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = response.headers.get("Content-Length")
        return int(value) if value else None


def download_one(
    item: Dict[str, str],
    output_dir: Path,
    retries: int,
    timeout: int,
    force: bool,
) -> Dict[str, str]:
    output_path = output_dir / item["file_name"]
    url = item["url"]
    expected_size = None

    for attempt in range(1, retries + 1):
        try:
            expected_size = remote_size(url, timeout)
            if (
                not force
                and expected_size is not None
                and output_path.exists()
                and output_path.stat().st_size == expected_size
            ):
                return {**item, "status": "skipped", "path": str(output_path)}

            with urllib.request.urlopen(url, timeout=timeout) as response:
                payload = response.read()
            output_path.write_bytes(payload)

            if expected_size is not None and output_path.stat().st_size != expected_size:
                raise RuntimeError(
                    f"incomplete download: {output_path.stat().st_size} != {expected_size}"
                )
            return {**item, "status": "downloaded", "path": str(output_path)}
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            if attempt >= retries:
                return {
                    **item,
                    "status": "failed",
                    "path": str(output_path),
                    "error": str(exc),
                }
            time.sleep(attempt)

    return {**item, "status": "failed", "path": str(output_path), "error": "unknown"}


def video_metadata(path: Path) -> Dict[str, float]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return {"frames": 0, "fps": 0.0, "width": 0, "height": 0}
        return {
            "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "fps": round(float(cap.get(cv2.CAP_PROP_FPS)), 3),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        }
    finally:
        cap.release()


def write_manifest(items: List[Dict[str, str]], output_dir: Path, manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "split",
        "label",
        "camera",
        "source_path",
        "source_url",
        "frames",
        "fps",
        "width",
        "height",
        "bytes",
    ]

    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            path = output_dir / item["file_name"]
            metadata = video_metadata(path) if path.exists() else {}
            writer.writerow(
                {
                    "id": item["id"],
                    "split": "validation",
                    "label": item["label"],
                    "camera": item["camera"],
                    "source_path": f"inputs/{item['file_name']}",
                    "source_url": item["url"],
                    "frames": metadata.get("frames", 0),
                    "fps": metadata.get("fps", 0.0),
                    "width": metadata.get("width", 0),
                    "height": metadata.get("height", 0),
                    "bytes": path.stat().st_size if path.exists() else 0,
                }
            )


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    manifest_path = Path(args.manifest).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    items = build_items()
    results: List[Dict[str, str]] = []
    workers = max(1, args.workers)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                download_one,
                item,
                output_dir,
                args.retries,
                args.timeout,
                args.force,
            )
            for item in items
        ]
        for index, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            print(f"[{index:03d}/{len(items)}] {result['status']}: {result['file_name']}")

    successful = [item for item in items if (output_dir / item["file_name"]).exists()]
    write_manifest(successful, output_dir, manifest_path)

    failed = [item for item in results if item["status"] == "failed"]
    print(f"manifest: {manifest_path}")
    print(f"videos_present: {len(successful)}")
    print(f"failed: {len(failed)}")
    for item in failed:
        print(f"failed_item: {item['file_name']} {item.get('error', '')}")


if __name__ == "__main__":
    main()
