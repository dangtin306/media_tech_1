"""Publish media_tech_ai code and media_tech_yolo package in one command."""

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[2]
PACKAGE_SCRIPT = (
    REPO_DIR / "ai" / "images" / "yolo" / "test_1" / "datasets" / "convert_zip.py"
)
CONFIG_PATH = Path(__file__).with_name("config.json")
YOLO_CODE_FILES = [
    "ai/images/yolo/test_1/README.md",
    "ai/images/yolo/test_1/data.yaml",
    "ai/images/yolo/test_1/datasets/convert_zip.py",
    "ai/images/yolo/test_1/test_1.py",
    "ai/images/yolo/test_1/train_1.py",
    "ai/images/yolo/test_1/train_2.py",
]


def _looks_like_token(value: object) -> bool:
    if not isinstance(value, str):
        return False
    value = value.strip()
    return value.startswith(("github_pat_", "ghp_")) and len(value) > 20


def get_github_token() -> str:
    """Read GitHub token from env first, then the local config file."""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        return token

    if CONFIG_PATH.is_file():
        with CONFIG_PATH.open(encoding="utf-8") as handle:
            config = json.load(handle)

        # Current config stores the PAT in github_token_env. Also support
        # clearer key names so the publisher remains backwards compatible.
        for key in ("github_token", "token", "github_pat", "GITHUB_TOKEN", "github_token_env"):
            value = config.get(key)
            if _looks_like_token(value):
                return value.strip()

        # Or github_token_env may contain the name of an environment variable.
        env_name = config.get("github_token_env")
        if isinstance(env_name, str):
            token = os.getenv(env_name.strip(), "").strip()
            if token:
                return token

    raise RuntimeError(
        "Khong tim thay GitHub token. Dat GITHUB_TOKEN hoac token trong "
        f"{CONFIG_PATH.name}."
    )


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    print("$", " ".join(command))
    subprocess.run(command, cwd=REPO_DIR, check=True, env=env)


def publish_package() -> None:
    command = [sys.executable, str(PACKAGE_SCRIPT), "--upload-release"]
    env = os.environ.copy()
    env["GITHUB_TOKEN"] = get_github_token()
    run(command, env=env)


def publish_repo() -> None:
    run(
        [
            "git",
            "add",
            "git_auto/github/up_to_github.py",
            "server/ubuntu/yolo",
        ]
        + ["-f", *YOLO_CODE_FILES]
    )
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
