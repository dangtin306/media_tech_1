from __future__ import annotations

import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    print(f"> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def capture(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git_root(start: Path) -> Path:
    current = start.resolve()
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            raise SystemExit(f"Not a git repository: {start}")
        current = current.parent


def current_branch(repo: Path) -> str:
    branch = capture(["git", "branch", "--show-current"], repo)
    if not branch:
        raise SystemExit("Could not determine current branch.")
    return branch


def remote_url(repo: Path, remote_name: str = "origin") -> str:
    return capture(["git", "remote", "get-url", remote_name], repo)


def has_changes(repo: Path) -> bool:
    status = capture(["git", "status", "--porcelain"], repo)
    return bool(status)

