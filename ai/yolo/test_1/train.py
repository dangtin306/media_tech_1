from pathlib import Path

import torch
from ultralytics import YOLO


PROJECT_DIR = Path(__file__).resolve().parent
DATASET_YAML = PROJECT_DIR / "data.yaml"
MODEL_PATH = PROJECT_DIR.parent / "yolo26n" / "yolo26n.pt"


def main() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy model: {MODEL_PATH}")

    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"Training device: {device}")
    print(f"Dataset: {DATASET_YAML}")

    model = YOLO(str(MODEL_PATH))
    model.train(
        data=str(DATASET_YAML),
        epochs=100,
        imgsz=640,
        batch=8,
        device=device,
        project=str(PROJECT_DIR / "runs"),
        name="vietnam_flag",
        exist_ok=True,
    )


if __name__ == "__main__":
    main()
