"""Train YOLO26n on the cobasoc_1 dataset."""

import os
import platform
from pathlib import Path

import torch
from ultralytics import YOLO


PROJECT_DIR = Path(__file__).resolve().parent


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


def resolve_dataset_yaml(dataset: Path, output_dir: Path) -> Path:
    """Create a portable YAML with absolute image paths for Ultralytics."""
    import yaml

    config = yaml.safe_load(dataset.read_text(encoding="utf-8")) or {}
    dataset_root = dataset.parent.resolve()
    for key in ("train", "val", "test"):
        value = config.get(key)
        if isinstance(value, str) and not Path(value).expanduser().is_absolute():
            config[key] = str((dataset_root / value).resolve())
    config["path"] = str(dataset_root)
    resolved = output_dir / ".cobasoc_1_resolved.yaml"
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return resolved


DATASET_YAML = find_dataset()
MODEL_PATH = find_model()
DEFAULT_RUNS_DIR = (
    Path("/root/model/images/yolo")
    if os.name != "nt"
    else PROJECT_DIR / "runs"
)
RUNS_DIR = Path(os.getenv("YOLO_RUNS", str(DEFAULT_RUNS_DIR))).expanduser().resolve()


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
    resolved_dataset = resolve_dataset_yaml(DATASET_YAML, RUNS_DIR)
    print(f"Dataset: {DATASET_YAML}")
    print(f"Resolved dataset: {resolved_dataset}")
    print(f"Model: {MODEL_PATH}")
    print(f"epochs={epochs}, imgsz={imgsz}, batch={batch}, workers={workers}")

    model = YOLO(str(MODEL_PATH))
    model.train(
        data=str(resolved_dataset),
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
