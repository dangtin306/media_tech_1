from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cleanup import clean_repo
from git_ops import capture, current_branch, git_root, has_changes, remote_url, run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto clean, stage, commit, and push a git repo to origin."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Path to the git repository. Defaults to current directory.",
    )
    parser.add_argument(
        "-m",
        "--message",
        default="auto push",
        help="Commit message to use when there are changes.",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Branch to push. Defaults to the current branch.",
    )
    args = parser.parse_args()

    repo = git_root(args.repo)
    print(f"Repo: {repo}")

    clean_repo(repo)

    run(["git", "add", "."], repo)

    if has_changes(repo):
        run(["git", "commit", "-m", args.message], repo)
    else:
        print("No changes to commit.")

    branch = args.branch or current_branch(repo)
    print(f"Remote: {remote_url(repo)}")
    print(f"Branch: {branch}")

    run(["git", "push", "-u", "origin", branch], repo)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
