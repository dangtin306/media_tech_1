"""Run the cobasoc_1 YOLO model on one random dataset image."""

import argparse
import os
import random
from pathlib import Path

import torch
from ultralytics import YOLO


PROJECT_DIR = Path(__file__).resolve().parent
DATASET_DIR = PROJECT_DIR / "datasets" / "cobasoc_1"
OUTPUT_DIR = PROJECT_DIR / "runs" / "test_2"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path.resolve()
    return None


def find_model() -> Path:
    configured = os.getenv("YOLO_MODEL")
    candidates = [
        Path(configured).expanduser() if configured else Path(),
        PROJECT_DIR / "runs" / "cobasoc_1" / "weights" / "best.pt",
        Path("/root/model/yolo26n.pt"),
        Path(r"D:\hustmedia\python\yolo26n.pt"),
    ]
    model = first_existing([path for path in candidates if str(path) != "."])
    if model is None:
        raise FileNotFoundError(
            "Khong tim thay model cobasoc_1. Dat YOLO_MODEL toi file best.pt."
        )
    return model


def find_random_source() -> Path:
    configured = os.getenv("YOLO_SOURCE")
    if configured:
        source = Path(configured).expanduser()
        if source.is_file():
            return source.resolve()
        raise FileNotFoundError(f"Khong tim thay YOLO_SOURCE: {source}")

    # Prefer the held-out test split, then validation, then training images.
    image_files: list[Path] = []
    for split in ("test", "valid", "val", "train"):
        split_dir = DATASET_DIR / split / "images"
        if split_dir.is_dir():
            image_files.extend(
                path for path in split_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS
            )
        if image_files:
            break

    if not image_files:
        raise FileNotFoundError(
            "Khong tim thay anh trong datasets/cobasoc_1. Dat YOLO_SOURCE toi mot anh."
        )

    seed = os.getenv("YOLO_SEED")
    chooser = random.Random(int(seed)) if seed else random.Random()
    return chooser.choice(image_files).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--show", action="store_true", help="Mo cua so anh (can giao dien).")
    args = parser.parse_args()

    if args.model:
        os.environ["YOLO_MODEL"] = str(args.model)
    if args.source:
        os.environ["YOLO_SOURCE"] = str(args.source)

    model_path = find_model()
    source_path = find_random_source()
    requested_device = os.getenv("YOLO_DEVICE", "auto").lower()
    device = (
        "cuda:0" if requested_device == "auto" and torch.cuda.is_available()
        else "cpu" if requested_device == "auto" else requested_device
    )
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("YOLO_DEVICE yeu cau CUDA nhung PyTorch khong thay GPU")

    print(f"Model: {model_path}")
    print(f"Random source: {source_path}")
    print(f"Device: {device}")
    print(f"Output: {OUTPUT_DIR}")

    model = YOLO(str(model_path))
    model.predict(
        source=str(source_path),
        conf=args.conf,
        device=device,
        save=True,
        show=args.show,
        project=str(OUTPUT_DIR.parent),
        name=OUTPUT_DIR.name,
        exist_ok=True,
    )
    print(f"Done: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
