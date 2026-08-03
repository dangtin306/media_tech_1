"""Launch the OpenClaw ChatGPT/Codex login flow on Windows."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
APP_DIR = PROJECT_DIR / "app"
CONFIG_PATH = PROJECT_DIR / "config" / "openclaw.json"
STATE_DIR = PROJECT_DIR / "data"
AUTH_SECRET_DIR = PROJECT_DIR / "auth-profile-secrets"


def main() -> int:
    node = shutil.which("node.exe") or shutil.which("node")
    if not node:
        print("[FAIL] Node.js was not found on PATH.", file=sys.stderr)
        return 1

    openclaw_entry = APP_DIR / "openclaw.mjs"

    if not openclaw_entry.is_file():
        print(f"[FAIL] OpenClaw source not found: {openclaw_entry}", file=sys.stderr)
        return 1

    if not CONFIG_PATH.is_file():
        print(f"[FAIL] Config not found: {CONFIG_PATH}", file=sys.stderr)
        return 1

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_SECRET_DIR.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_CONFIG_PATH": str(CONFIG_PATH),
            "OPENCLAW_STATE_DIR": str(STATE_DIR),
            "OPENCLAW_AUTH_PROFILE_SECRET_DIR": str(AUTH_SECRET_DIR),
        }
    )

    command = [
        node,
        str(openclaw_entry),
        "models",
        "auth",
        "login",
        "--provider",
        "openai",
        "--set-default",
    ]

    print(f"[run] {' '.join(command)}", flush=True)

    try:
        result = subprocess.run(
            command,
            cwd=APP_DIR,
            env=env,
            check=False,
        )
    except KeyboardInterrupt:
        print("\n[CANCEL] Login cancelled.", file=sys.stderr)
        return 130
    except OSError as exc:
        print(f"[FAIL] Could not start login: {exc}", file=sys.stderr)
        return 1

    if result.returncode == 0:
        print("[PASS] OpenAI/Codex login completed.", flush=True)
    else:
        print(
            f"[FAIL] Login exited with code {result.returncode}.",
            file=sys.stderr,
        )

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())