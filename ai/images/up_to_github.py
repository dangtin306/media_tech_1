"""Publish media_tech_ai code and media_tech_yolo package in one command."""

import os
import subprocess
import sys
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[2]
PACKAGE_SCRIPT = (
    REPO_DIR / "ai" / "images" / "yolo" / "test_1" / "datasets" / "convert_zip.py"
)
MODEL_DEFAULT = Path(r"D:\hustmedia\python\yolo26n.pt")


def run(command: list[str]) -> None:
    print("$", " ".join(command))
    subprocess.run(command, cwd=REPO_DIR, check=True)


def publish_package() -> None:
    model = Path(os.getenv("YOLO_MODEL", str(MODEL_DEFAULT)))
    command = [sys.executable, str(PACKAGE_SCRIPT), "--model", str(model), "--upload-release"]
    if not os.getenv("GITHUB_TOKEN"):
        raise RuntimeError(
            "Thieu GITHUB_TOKEN. Dat token trong terminal de upload Release tu dong."
        )
    run(command)


def publish_repo() -> None:
    run(["git", "add", "ai/images/up_to_github.py", "ai/images/yolo/test_1", "server/ubuntu/yolo"])
    changed = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=REPO_DIR
    ).returncode
    if changed:
        run(["git", "commit", "-m", "Update YOLO code and release workflow"])
    else:
        print("Repo code khong co thay doi moi.")
    run(["git", "push", "origin", "main"])


def main() -> None:
    publish_repo()
    publish_package()
    print("Da xong: ZIP da upload vao Release va code da push len repo.")
    print("Ubuntu: git pull, sau do tai lai media_tech_yolo.zip theo guide_data.md.")


if __name__ == "__main__":
    main()
