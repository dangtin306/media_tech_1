"""Train YOLO26n on the cobasoc_1 dataset."""

import os
import platform
from pathlib import Path

import torch
from ultralytics import YOLO


PROJECT_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = Path("/root/model/yolo_package/media_tech_yolo")


def first_file(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path.resolve()
    return None


def find_dataset() -> Path:
    configured = os.getenv("YOLO_DATA")
    candidates = [
        Path(configured).expanduser() if configured else Path(),
        PROJECT_DIR / "datasets" / "cobasoc_1" / "data.yaml",
        PACKAGE_DIR / "datasets" / "cobasoc_1" / "data.yaml",
    ]
    dataset = first_file([path for path in candidates if str(path) != "."])
    if dataset is None:
        raise FileNotFoundError(
            "Khong tim thay cobasoc_1/data.yaml. Dat YOLO_DATA toi file dataset."
        )
    return dataset


def find_model() -> Path:
    configured = os.getenv("YOLO_MODEL")
    candidates = [
        Path(configured).expanduser() if configured else Path(),
        PROJECT_DIR.parent / "yolo26n" / "yolo26n.pt",
        PACKAGE_DIR / "model" / "yolo26n.pt",
    ]
    model = first_file([path for path in candidates if str(path) != "."])
    if model is None:
        raise FileNotFoundError(
            "Khong tim thay yolo26n.pt. Dat YOLO_MODEL toi file model."
        )
    return model


DATASET_YAML = find_dataset()
MODEL_PATH = find_model()
RUNS_DIR = Path(os.getenv("YOLO_RUNS", str(PROJECT_DIR / "runs"))).expanduser().resolve()


def main() -> None:
    requested_device = os.getenv("YOLO_DEVICE", "auto").lower()
    device = (
        "cuda:0" if requested_device == "auto" and torch.cuda.is_available()
        else "cpu" if requested_device == "auto" else requested_device
    )
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("YOLO_DEVICE yeu cau CUDA nhung PyTorch khong thay GPU")

    epochs = int(os.getenv("YOLO_EPOCHS", "100"))
    imgsz = int(os.getenv("YOLO_IMGSZ", "640"))
    batch_value = os.getenv("YOLO_BATCH", "auto").lower()
    batch = (-1 if device.startswith("cuda") else 2) if batch_value == "auto" else int(batch_value)
    default_workers = 0 if platform.system() == "Windows" else min(8, os.cpu_count() or 1)
    workers = int(os.getenv("YOLO_WORKERS", str(default_workers)))

    print(f"Training device: {device}")
    print(f"Dataset: {DATASET_YAML}")
    print(f"Model: {MODEL_PATH}")
    print(f"epochs={epochs}, imgsz={imgsz}, batch={batch}, workers={workers}")

    model = YOLO(str(MODEL_PATH))
    model.train(
        data=str(DATASET_YAML),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        workers=workers,
        project=str(RUNS_DIR),
        name=os.getenv("YOLO_NAME", "cobasoc_1"),
        exist_ok=True,
    )


if __name__ == "__main__":
    main()
