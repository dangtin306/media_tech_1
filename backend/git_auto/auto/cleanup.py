from __future__ import annotations

import os
from pathlib import Path


IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
IGNORED_FILES = {".DS_Store"}


def clean_repo(repo: Path) -> None:
    for path in repo.rglob("*"):
        if not path.exists():
            continue
        if ".git" in path.parts:
            continue
        if path.is_dir():
            if path.name in IGNORED_DIRS:
                _remove_dir(path)
            continue
        if path.suffix == ".pyc" or path.name in IGNORED_FILES:
            path.unlink(missing_ok=True)


def _remove_dir(path: Path) -> None:
    for root, dirs, files in os.walk(path, topdown=False):
        root_path = Path(root)
        for filename in files:
            (root_path / filename).unlink(missing_ok=True)
        for dirname in dirs:
            (root_path / dirname).rmdir()
    path.rmdir()
