from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


MEDIA_TECH_ROOT = Path(__file__).resolve().parents[3]
OPENCLAW_SOURCE = MEDIA_TECH_ROOT / "server" / "openclaw" / "app"
DOCKERFILE = OPENCLAW_SOURCE / "Dockerfile"
DEFAULT_TAG = "openclaw_win:latest"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the official OpenClaw Docker image from the tested source."
    )
    parser.add_argument(
        "--tag",
        default=DEFAULT_TAG,
        help=f"Docker image tag (default: {DEFAULT_TAG})",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push the image after a successful local build.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Build without using cached Docker layers.",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Always pull newer base images.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if shutil.which("docker") is None:
        print("[error] docker was not found in PATH", file=sys.stderr)
        return 1
    if not OPENCLAW_SOURCE.is_dir():
        print(f"[error] OpenClaw source not found: {OPENCLAW_SOURCE}", file=sys.stderr)
        return 1
    if not DOCKERFILE.is_file():
        print(f"[error] Dockerfile not found: {DOCKERFILE}", file=sys.stderr)
        return 1

    command = [
        "docker",
        "build",
        "--progress=plain",
        "--platform=linux/amd64",
        "-f",
        str(DOCKERFILE),
        "-t",
        args.tag,
    ]
    if args.no_cache:
        command.append("--no-cache")
    if args.pull:
        command.append("--pull")
    command.append(str(OPENCLAW_SOURCE))

    print(f"[build] source: {OPENCLAW_SOURCE}", flush=True)
    print(f"[build] dockerfile: {DOCKERFILE}", flush=True)
    print(f"[build] image: {args.tag}", flush=True)
    result = subprocess.run(command, cwd=OPENCLAW_SOURCE)
    if result.returncode != 0:
        print(f"[error] docker build failed with code {result.returncode}", file=sys.stderr)
        return result.returncode

    if args.push:
        print(f"[push] uploading {args.tag}", flush=True)
        push = subprocess.run(["docker", "push", args.tag])
        if push.returncode != 0:
            print("[error] docker push failed", file=sys.stderr)
            return push.returncode

    print(f"[ok] image built: {args.tag}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
