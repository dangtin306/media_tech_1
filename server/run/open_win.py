"""Run the OpenClaw gateway natively on Windows."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(r"D:\hustmedia\python\llms\media_tech_ai\server\openclaw")
APP_DIR = PROJECT_DIR / "app"
CONFIG_DIR = PROJECT_DIR / "config"
DATA_DIR = PROJECT_DIR / "data"
CONFIG_PATH = CONFIG_DIR / "openclaw.json"


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print(f"[run] {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OpenClaw locally on Windows")
    parser.add_argument("--port", type=int, default=8803)
    parser.add_argument("--bind", default="lan", choices=("loopback", "lan"))
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()

    if not (APP_DIR / "openclaw.mjs").is_file():
        raise SystemExit(f"OpenClaw source not found: {APP_DIR}")
    if not CONFIG_PATH.is_file():
        raise SystemExit(f"OpenClaw config not found: {CONFIG_PATH}")

    pnpm = shutil.which("pnpm.cmd") or shutil.which("pnpm")
    node = shutil.which("node.exe") or shutil.which("node")
    if not pnpm or not node:
        raise SystemExit("Node.js and pnpm must be available on PATH")

    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_CONFIG_DIR": str(CONFIG_DIR),
            "OPENCLAW_CONFIG_PATH": str(CONFIG_PATH),
            "OPENCLAW_STATE_DIR": str(DATA_DIR),
            "OPENCLAW_WORKSPACE_DIR": str(DATA_DIR / "workspace"),
            "OPENCLAW_GATEWAY_TOKEN": "media_tech",
        }
    )

    windows_native_package = (
        APP_DIR / "node_modules" / "@openai" / "codex-win32-x64" / "package.json"
    )
    if not (APP_DIR / "node_modules" / ".modules.yaml").is_file() or not windows_native_package.is_file():
        run(
            [
                pnpm,
                "install",
                "--frozen-lockfile",
                "--config.supportedArchitectures.os=win32",
                "--config.supportedArchitectures.cpu=x64",
            ],
            cwd=APP_DIR,
            env=env,
        )

    if not args.no_build and not any(
        (APP_DIR / name).is_file() for name in ("dist/entry.js", "dist/entry.mjs")
    ):
        run([pnpm, "build"], cwd=APP_DIR, env=env)

    command = [
        node,
        "openclaw.mjs",
        "gateway",
        "--force",
        "--bind",
        args.bind,
        "--port",
        str(args.port),
    ]
    print(f"[openclaw] config: {CONFIG_PATH}", flush=True)
    print(f"[openclaw] state: {DATA_DIR}", flush=True)
    print(f"[openclaw] listening target: {args.bind}:{args.port}", flush=True)
    return subprocess.call(command, cwd=APP_DIR, env=env)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[openclaw] stopped", file=sys.stderr)
        raise SystemExit(130)
