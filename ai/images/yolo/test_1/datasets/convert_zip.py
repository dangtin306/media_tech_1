"""Build the shared media_tech_yolo release package.

The output is written beside this script as ``media_tech_yolo.zip`` and has
one stable top-level folder containing the model and every dataset folder.
"""

import argparse
import hashlib
import json
import os
import urllib.parse
import urllib.request
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


def github_request(
    url: str,
    token: str,
    method: str = "GET",
    body: bytes | None = None,
    content_type: str = "application/vnd.github+json",
) -> bytes:
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
            "User-Agent": "media-tech-yolo-release",
        },
    )
    with urllib.request.urlopen(request) as response:
        return response.read()


def upload_release(output: Path) -> None:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "Thieu GITHUB_TOKEN. Dat token trong bien moi truong, sau do chay lai --upload-release."
        )

    repository = os.getenv("GITHUB_REPO", "dangtin306/media_tech_1")
    release_tag = os.getenv("GITHUB_RELEASE_TAG", "media_tech_yolo")
    api_root = f"https://api.github.com/repos/{repository}"
    release = json.loads(
        github_request(f"{api_root}/releases/tags/{release_tag}", token)
    )

    asset_names = {output.name, f"{output.stem}.sha256"}
    for asset in release.get("assets", []):
        if asset["name"] in asset_names:
            github_request(
                f"{api_root}/releases/assets/{asset['id']}", token, method="DELETE"
            )

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name(f"{output.stem}.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    upload_url = release["upload_url"].split("{", 1)[0]
    for asset_path, content_type in (
        (output, "application/zip"),
        (checksum, "text/plain"),
    ):
        query = urllib.parse.urlencode({"name": asset_path.name})
        github_request(
            f"{upload_url}?{query}",
            token,
            method="POST",
            body=asset_path.read_bytes(),
            content_type=content_type,
        )
    print(f"Release updated: {repository}@{release_tag}")
    print(f"Uploaded: {output.name}, {checksum.name}")


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
    parser.add_argument(
        "--upload-release",
        action="store_true",
        help="Tu dong ghi de asset trong GitHub Release media_tech_yolo.",
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
    if args.upload_release:
        upload_release(output)


if __name__ == "__main__":
    main()
