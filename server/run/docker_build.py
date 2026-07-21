from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = PROJECT_ROOT / "server" / "docker" / "Dockerfile"
ADAPTER_SOURCE = Path(r"D:\huggingface\hub\Qwen\Qwen3.5-4B_vn_1\adapter")
ADAPTER_STAGE = PROJECT_ROOT / "server" / "docker" / "adapter"
DEFAULT_TAG = "media-tech-qwen:latest"
DEFAULT_HUB_TAG = "hustmedia/media-tech-qwen:latest"
DEFAULT_VHDX = Path(
    r"D:\hustmedia\application\Docker\DockerDesktopWSL\disk\docker_data.vhdx"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Media Tech Qwen Docker image."
    )
    parser.add_argument(
        "--tag",
        default=DEFAULT_HUB_TAG,
        help=f"Docker image tag (default: {DEFAULT_HUB_TAG})",
    )
    parser.add_argument(
        "--push",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Push the image to its registry tag after a successful build (default: enabled).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Build without using cached Docker layers.",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Always pull the latest base image.",
    )
    parser.add_argument(
        "--cleanup-cache",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Remove unused BuildKit cache after the build (default: enabled).",
    )
    parser.add_argument(
        "--compact-vhdx",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Compact Docker's VHDX after the build (default: enabled).",
    )
    return parser.parse_args()


def cleanup_cache() -> bool:
    print("[cleanup] removing unused BuildKit cache", flush=True)
    result = subprocess.run(["docker", "builder", "prune", "-af"])
    return result.returncode == 0


def compact_vhdx() -> bool:
    if not DEFAULT_VHDX.is_file():
        print(f"[error] Docker VHDX not found: {DEFAULT_VHDX}", file=sys.stderr)
        return False

    if shutil.which("wsl") is None:
        print("[error] wsl was not found in PATH", file=sys.stderr)
        return False

    print("[compact] stopping Docker Desktop", flush=True)
    stop = subprocess.run(["docker", "desktop", "stop"])
    if stop.returncode != 0:
        print("[error] could not stop Docker Desktop", file=sys.stderr)
        return False

    subprocess.run(["wsl", "--shutdown"], check=False)
    optimize = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "if (Get-Command Optimize-VHD -ErrorAction SilentlyContinue) { "
            f"Optimize-VHD -Path '{DEFAULT_VHDX}' -Mode Full "
            "} else { exit 127 }",
        ]
    )
    compact = optimize
    if optimize.returncode == 127:
        print("[compact] Optimize-VHD unavailable; using diskpart", flush=True)
        script = (
            'select vdisk file="'
            + str(DEFAULT_VHDX)
            + '"\nattach vdisk readonly\ncompact vdisk\n'
            'detach vdisk\nexit\n'
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".diskpart.txt", delete=False, encoding="ascii"
        ) as handle:
            handle.write(script)
            diskpart_script = handle.name
        try:
            compact = subprocess.run(["diskpart", "/s", diskpart_script])
        finally:
            Path(diskpart_script).unlink(missing_ok=True)

    print("[compact] starting Docker Desktop", flush=True)
    subprocess.run(["docker", "desktop", "start"], check=False)
    return compact.returncode == 0


def main() -> int:
    args = parse_args()

    if shutil.which("docker") is None:
        print("[error] docker was not found in PATH", file=sys.stderr)
        return 1

    if not DOCKERFILE.is_file():
        print(f"[error] Dockerfile not found: {DOCKERFILE}", file=sys.stderr)
        return 1

    if not ADAPTER_SOURCE.is_dir():
        print(f"[error] adapter not found: {ADAPTER_SOURCE}", file=sys.stderr)
        return 1
    print(f"[build] staging adapter: {ADAPTER_SOURCE}", flush=True)
    shutil.copytree(ADAPTER_SOURCE, ADAPTER_STAGE, dirs_exist_ok=True)

    command = [
        "docker",
        "build",
        "--progress=plain",
        "-f",
        str(DOCKERFILE),
        "-t",
        args.tag,
    ]
    if args.no_cache:
        command.append("--no-cache")
    if args.pull:
        command.append("--pull")
    command.append(str(PROJECT_ROOT))

    print(f"[build] context: {PROJECT_ROOT}", flush=True)
    print(f"[build] dockerfile: {DOCKERFILE}", flush=True)
    print(f"[build] image: {args.tag}", flush=True)
    result_code = 1
    interrupted = False
    try:
        result = subprocess.run(command, cwd=PROJECT_ROOT)
        result_code = result.returncode
    except KeyboardInterrupt:
        interrupted = True
        print("[build] interrupted; running cleanup", file=sys.stderr, flush=True)

    cleanup_ok = True
    if args.cleanup_cache or args.compact_vhdx:
        cleanup_ok = cleanup_cache()
    compact_ok = True
    # Compact only after a successful build. A failed BuildKit session can leave
    # Docker Desktop in a transitional state where stopping it is unsafe.
    if args.compact_vhdx and result_code == 0:
        compact_ok = compact_vhdx()

    if result_code == 0:
        if args.push:
            print(f"[push] uploading {args.tag}", flush=True)
            push = subprocess.run(["docker", "push", args.tag])
            if push.returncode != 0:
                print("[error] docker push failed", file=sys.stderr)
                return push.returncode
        print(f"[ok] image built: {args.tag}", flush=True)
    else:
        if not interrupted:
            print(
                f"[error] docker build failed with code {result_code}",
                file=sys.stderr,
            )
    if not cleanup_ok or not compact_ok:
        return 1
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
