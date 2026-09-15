"""Build the shared media_tech_yolo release package.

The output is written beside this script as ``media_tech_yolo.zip`` and has
one stable top-level folder containing the model and every dataset folder.
"""

import argparse
import os
import zipfile
from pathlib import Path


DATASETS_DIR = Path(__file__).resolve().parent
YOLO_DIR = DATASETS_DIR.parent.parent
DEFAULT_OUTPUT = DATASETS_DIR / "media_tech_yolo.zip"


def find_model(configured: str | None) -> Path:
    candidates = [
        Path(configured).expanduser() if configured else Path(),
        YOLO_DIR / "yolo26n" / "yolo26n.pt",
        YOLO_DIR / "yolo26n.pt",
        Path.cwd() / "yolo26n.pt",
    ]
    # Common Windows workspace location; harmless on other platforms.
    if len(DATASETS_DIR.parents) > 7:
        candidates.append(DATASETS_DIR.parents[7] / "yolo26n.pt")

    for candidate in candidates:
        if str(candidate) != "." and candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "Khong tim thay yolo26n.pt. Truyen --model hoac dat YOLO_MODEL toi file model."
    )


def find_datasets() -> list[Path]:
    datasets = sorted(
        (
            folder
            for folder in DATASETS_DIR.iterdir()
            if folder.is_dir()
            and not folder.name.startswith(".")
            and (folder / "data.yaml").is_file()
        ),
        key=lambda folder: folder.name.lower(),
    )
    if not datasets:
        raise FileNotFoundError(
            "Khong tim thay dataset nao. Moi dataset phai co data.yaml."
        )
    return datasets


def add_file(archive: zipfile.ZipFile, source: Path, archive_path: Path) -> None:
    archive.write(source, archive_path.as_posix())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(os.getenv("YOLO_MODEL", "")) or None,
        help="Duong dan yolo26n.pt; mac dinh tu dong tim model.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="File ZIP dau ra; mac dinh datasets/media_tech_yolo.zip.",
    )
    args = parser.parse_args()

    model = find_model(str(args.model) if args.model else None)
    datasets = find_datasets()
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    with zipfile.ZipFile(
        output, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        add_file(archive, model, Path("media_tech_yolo/model") / model.name)
        for dataset in datasets:
            for source in dataset.rglob("*"):
                if (
                    source.is_file()
                    and "__pycache__" not in source.parts
                    and source.suffix.lower() not in {".py", ".zip"}
                ):
                    relative = source.relative_to(DATASETS_DIR)
                    add_file(archive, source, Path("media_tech_yolo/datasets") / relative)

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"Model: {model}")
    print("Datasets: " + ", ".join(dataset.name for dataset in datasets))
    print(f"Created: {output}")
    print(f"Size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
