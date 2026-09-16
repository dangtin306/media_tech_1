import os
import platform
from pathlib import Path

import torch
from ultralytics import YOLO


PROJECT_DIR = Path(__file__).resolve().parent


def env_path(name: str, default: Path) -> Path:
    return Path(os.getenv(name, str(default))).expanduser().resolve()


def first_file(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path.resolve()
    return None


def find_dataset() -> Path:
    configured = os.getenv("YOLO_DATA")
    local_dataset_dir = PROJECT_DIR / "datasets" / "vietnam_flag"
    if configured:
        candidates = [Path(configured).expanduser()]
    elif (
        (local_dataset_dir / "train" / "images").is_dir()
        and (local_dataset_dir / "valid" / "images").is_dir()
    ):
        candidates = [PROJECT_DIR / "data.yaml"]
    else:
        candidates = [PROJECT_DIR / "datasets" / "vietnam_flag" / "data.yaml"]
    dataset = first_file([path for path in candidates if str(path) != "."])
    if dataset is None:
        raise FileNotFoundError(
            "Khong tim thay data.yaml. Dat YOLO_DATA toi file data.yaml cua dataset."
        )
    return dataset


def find_model() -> Path:
    configured = os.getenv("YOLO_MODEL")
    candidates = [
        Path(configured).expanduser() if configured else Path(),
        Path("/root/model/images/yolo/main/yolo26n.pt"),
        Path(r"D:\hustmedia\python\yolo26n.pt"),
        PROJECT_DIR.parent / "yolo26n" / "yolo26n.pt",
    ]
    model = first_file([path for path in candidates if str(path) != "."])
    if model is None:
        raise FileNotFoundError(
            "Khong tim thay yolo26n.pt. Dat YOLO_MODEL toi file model."
        )
    return model


DATASET_YAML = find_dataset()
MODEL_PATH = find_model()
DEFAULT_RUNS_DIR = (
    Path("/root/model/images/yolo")
    if os.name != "nt"
    else PROJECT_DIR / "runs"
)
RUNS_DIR = env_path("YOLO_RUNS", DEFAULT_RUNS_DIR)


def main() -> None:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Không tìm thấy model: {MODEL_PATH}")
    if not DATASET_YAML.is_file():
        raise FileNotFoundError(f"Không tìm thấy dataset YAML: {DATASET_YAML}")

    requested_device = os.getenv("YOLO_DEVICE", "auto").lower()
    device = (
        "cuda:0" if requested_device == "auto" and torch.cuda.is_available()
        else "cpu" if requested_device == "auto" else requested_device
    )
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("YOLO_DEVICE yêu cầu CUDA nhưng PyTorch không thấy GPU")

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
        name=os.getenv("YOLO_NAME", "vietnam_flag"),
        exist_ok=True,
    )


if __name__ == "__main__":
    main()
