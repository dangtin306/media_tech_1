from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "backend" / "openclaw" / "config.json"
SERVER_MAIN = ROOT / "ai" / "qwen" / "qwen3.5_4B_vn" / "server" / "main.py"
DEFAULT_PORT = 8005
DEFAULT_PYTHON = r"D:\hustmedia\conda_envs\qwen\python.exe"


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass(slots=True)
class WinServerConfig:
    python_exe: str
    server_main: str
    port: int
    auto_kill_on_start: bool


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing config: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a JSON object: {path}")
    return data


def as_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def as_str(value: Any, fallback: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def as_bool(value: Any, fallback: bool = True) -> bool:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return fallback


def load_config() -> WinServerConfig:
    config = read_json_file(CONFIG_PATH)
    return WinServerConfig(
        python_exe=as_str(
            os.environ.get("QWEN_PYTHON_EXE")
            or config.get("windows_python_exe")
            or config.get("python_exe"),
            DEFAULT_PYTHON,
        ),
        server_main=as_str(
            os.environ.get("QWEN_SERVER_MAIN")
            or config.get("windows_qwen_main")
            or config.get("qwen_main"),
            str(SERVER_MAIN),
        ),
        port=as_int(
            os.environ.get("QWEN_SERVER_PORT")
            or config.get("app_port")
            or config.get("windows_qwen_port"),
            DEFAULT_PORT,
        ),
        auto_kill_on_start=as_bool(
            os.environ.get("QWEN_WIN_AUTO_KILL")
            if os.environ.get("QWEN_WIN_AUTO_KILL") is not None
            else config.get("windows_auto_kill_on_start", True),
            True,
        ),
    )


def get_listener_pids(port: int) -> list[int]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: list[int] = []
    needle = f":{port} "
    for line in result.stdout.splitlines():
        if needle not in line or "LISTENING" not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid not in pids:
            pids.append(pid)
    return pids


def kill_pid(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/F", "/T"],
        capture_output=True,
        text=True,
        check=False,
    )


def kill_existing_server(port: int) -> list[int]:
    pids = get_listener_pids(port)
    for pid in pids:
        kill_pid(pid)
    time.sleep(1.0)
    return pids


def build_start_command(cfg: WinServerConfig) -> list[str]:
    return [cfg.python_exe, cfg.server_main]


def start_server(cfg: WinServerConfig) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    return subprocess.Popen(
        build_start_command(cfg),
        cwd=str(SERVER_MAIN.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def stream_process(proc: subprocess.Popen[str]) -> int:
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            print(line.rstrip("\n"))
    except KeyboardInterrupt:
        kill_pid(proc.pid)
        raise
    return proc.wait()


def restart_server(cfg: WinServerConfig) -> int:
    if cfg.auto_kill_on_start:
        killed = kill_existing_server(cfg.port)
        if killed:
            print(f"[info] killed existing listeners on port {cfg.port}: {killed}")
        else:
            print(f"[info] no existing listener found on port {cfg.port}")

    proc = start_server(cfg)
    print(f"[ok] started: pid={proc.pid} python={cfg.python_exe}")
    print(f"[ok] main: {cfg.server_main}")
    print(f"[ok] port: {cfg.port}")
    return stream_process(proc)


def stop_server(cfg: WinServerConfig) -> int:
    pids = get_listener_pids(cfg.port)
    if not pids:
        print(f"[down] no process is listening on port {cfg.port}")
        return 1
    for pid in pids:
        kill_pid(pid)
    print(f"[ok] killed listeners on port {cfg.port}: {pids}")
    return 0


def status_server(cfg: WinServerConfig) -> int:
    pids = get_listener_pids(cfg.port)
    if not pids:
        print(f"[down] no process is listening on port {cfg.port}")
        return 1
    print(f"[ok] listening on port {cfg.port}: {pids}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start/stop qwen server on Windows.")
    parser.add_argument("--stop", action="store_true", help="Stop the local server only.")
    parser.add_argument("--status", action="store_true", help="Check the local server status.")
    parser.add_argument("--no-auto-kill", action="store_true", help="Do not kill existing listeners on start.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config()
    if args.no_auto_kill:
        cfg.auto_kill_on_start = False

    if args.stop:
        return stop_server(cfg)
    if args.status:
        return status_server(cfg)
    return restart_server(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
