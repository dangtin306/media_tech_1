"""Run YOLO inference on one image and save the annotated result.

The script is cross-platform. It prefers a trained ``best.pt`` in ``runs``;
set ``YOLO_MODEL`` and ``YOLO_SOURCE`` when using another model or image.
"""

import argparse
import os
from pathlib import Path

import torch
from ultralytics import YOLO


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "runs" / "test"


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path.resolve()
    return None


def find_model() -> Path:
    configured = os.getenv("YOLO_MODEL")
    candidates = [
        Path(configured).expanduser() if configured else Path(),
        PROJECT_DIR / "runs" / "vietnam_flag" / "weights" / "best.pt",
        PROJECT_DIR / "runs" / "guide_new_ubuntu_test" / "weights" / "best.pt",
        PROJECT_DIR / "runs" / "guide_fresh_test" / "weights" / "best.pt",
        Path("/root/model/yolo_package/media_tech_yolo/model/yolo26n.pt"),
    ]
    model = first_existing([path for path in candidates if str(path) != "."])
    if model is None:
        raise FileNotFoundError(
            "Khong tim thay model. Hay dat YOLO_MODEL toi file best.pt hoac yolo26n.pt."
        )
    return model


def find_source() -> Path:
    configured = os.getenv("YOLO_SOURCE")
    candidates = [
        Path(configured).expanduser() if configured else Path(),
        PROJECT_DIR / "test.jpg",
        PROJECT_DIR / "test.png",
    ]
    source = first_existing([path for path in candidates if str(path) != "."])
    if source is None:
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        for root in (PROJECT_DIR / "datasets", PROJECT_DIR / "roboflow_downloaded"):
            if root.is_dir():
                source = next(
                    (p.resolve() for p in root.rglob("*") if p.suffix.lower() in image_extensions),
                    None,
                )
                if source is not None:
                    break
    if source is None:
        raise FileNotFoundError(
            "Khong tim thay anh. Dat YOLO_SOURCE toi anh can test, vi du test.jpg."
        )
    return source


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
    source_path = find_source()
    requested_device = os.getenv("YOLO_DEVICE", "auto").lower()
    device = "cuda:0" if requested_device == "auto" and torch.cuda.is_available() else "cpu" if requested_device == "auto" else requested_device

    print(f"Model: {model_path}")
    print(f"Source: {source_path}")
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
