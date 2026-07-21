from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import paramiko


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "server" / "ubuntu" / "config.json"
REMOTE_MAIN = "/root/media_tech/ai/qwen/qwen3.5_4B_vn/server/main.py"
REMOTE_APP_DIR = "/root/media_tech/ai/qwen/qwen3.5_4B_vn"
REMOTE_CONDA_SH = "/root/miniconda3/etc/profile.d/conda.sh"
REMOTE_CONDA_ENV = "qwen"
REMOTE_LOG_DIR = "/root/media_tech/ai/qwen/qwen3.5_4B_vn/server/logs"
REMOTE_LOG_FILE = f"{REMOTE_LOG_DIR}/ubuntu_run.log"
REMOTE_PID_FILE = "/tmp/qwen3.5_4B_vn_server.pid"
DEFAULT_START_TIMEOUT = 30

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass(slots=True)
class UbuntuSSHConfig:
    host: str
    port: int
    user: str
    password: str
    conda_sh: str
    conda_env: str
    remote_main: str
    remote_app_dir: str
    remote_log_file: str
    remote_pid_file: str


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


def load_ssh_config() -> UbuntuSSHConfig:
    config = read_json_file(CONFIG_PATH)
    return UbuntuSSHConfig(
        host=as_str(config.get("ubuntu_ssh_host"), "n1.msk.cloreai.ru"),
        port=as_int(config.get("ubuntu_ssh_port"), 1843),
        user=as_str(config.get("ubuntu_ssh_user"), "root"),
        password=as_str(config.get("ubuntu_ssh_password"), ""),
        conda_sh=as_str(
            config.get("ubuntu_conda_sh")
            or os.environ.get("UBUNTU_CONDA_SH"),
            REMOTE_CONDA_SH,
        ),
        conda_env=as_str(
            config.get("ubuntu_conda_env")
            or os.environ.get("UBUNTU_CONDA_ENV"),
            REMOTE_CONDA_ENV,
        ),
        remote_main=as_str(
            config.get("ubuntu_qwen_main")
            or os.environ.get("UBUNTU_QWEN_MAIN"),
            REMOTE_MAIN,
        ),
        remote_app_dir=as_str(
            config.get("ubuntu_qwen_app_dir")
            or os.environ.get("UBUNTU_QWEN_APP_DIR"),
            REMOTE_APP_DIR,
        ),
        remote_log_file=as_str(
            config.get("ubuntu_qwen_log_file")
            or os.environ.get("UBUNTU_QWEN_LOG_FILE"),
            REMOTE_LOG_FILE,
        ),
        remote_pid_file=as_str(
            config.get("ubuntu_qwen_pid_file")
            or os.environ.get("UBUNTU_QWEN_PID_FILE"),
            REMOTE_PID_FILE,
        ),
    )


def connect_ssh(cfg: UbuntuSSHConfig) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=cfg.host,
        port=cfg.port,
        username=cfg.user,
        password=cfg.password,
        look_for_keys=False,
        allow_agent=False,
        timeout=15,
        banner_timeout=15,
        auth_timeout=15,
    )
    return client


def exec_remote(client: paramiko.SSHClient, command: str, timeout: int = 60) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    exit_status = stdout.channel.recv_exit_status()
    out_text = stdout.read().decode("utf-8", errors="replace")
    err_text = stderr.read().decode("utf-8", errors="replace")
    return exit_status, out_text, err_text


def build_stop_command(cfg: UbuntuSSHConfig) -> str:
    pid_file = shlex.quote(cfg.remote_pid_file)
    # The daemon may be launched with an absolute path or as `python server/run/ubuntu_run.py`.
    target = "[s]erver/main.py"
    return (
        "bash -lc "
        + shlex.quote(
            f"set +e; "
            f"if [ -f {pid_file} ]; then "
            f"  pid=$(cat {pid_file} 2>/dev/null || true); "
            f"  if [ -n \"$pid\" ] && kill -0 \"$pid\" 2>/dev/null; then kill \"$pid\" || true; fi; "
            f"  rm -f {pid_file}; "
            f"fi; "
            f"pkill -f {shlex.quote(target)} || true; "
            f"exit 0"
        )
    )


def build_start_command(cfg: UbuntuSSHConfig) -> str:
    conda_sh = shlex.quote(cfg.conda_sh)
    conda_env = shlex.quote(cfg.conda_env)
    remote_main = shlex.quote(cfg.remote_main)
    remote_dir = shlex.quote(cfg.remote_app_dir)
    remote_log = shlex.quote(cfg.remote_log_file)
    remote_pid = shlex.quote(cfg.remote_pid_file)

    inner = (
        "set -e; "
        f"mkdir -p {shlex.quote(cfg.remote_log_file.rsplit('/', 1)[0])}; "
        f"cd {remote_dir}; "
        f"source {conda_sh}; "
        f"conda activate {conda_env}; "
        f"export PYTHONUNBUFFERED=1; "
        f": > {remote_log}; "
        f"nohup python {remote_main} >> {remote_log} 2>&1 < /dev/null & "
        f"echo $! > {remote_pid}; "
        f"echo STARTED:$!; "
        f"sleep 1; "
        f"ps -p \"$!\" -o pid=,cmd="
    )
    return "bash -lc " + shlex.quote(inner)


def build_status_command(cfg: UbuntuSSHConfig) -> str:
    remote_pid = shlex.quote(cfg.remote_pid_file)
    remote_main = shlex.quote(cfg.remote_main)
    return (
        "bash -lc "
        + shlex.quote(
            f"if [ -f {remote_pid} ]; then "
            f"  pid=$(cat {remote_pid} 2>/dev/null || true); "
            f"  if [ -n \"$pid\" ] && kill -0 \"$pid\" 2>/dev/null; then "
            f"    ps -p \"$pid\" -o pid=,cmd=; "
            f"    exit 0; "
            f"  fi; "
            f"fi; "
            f"pgrep -af {remote_main} || true"
        )
    )


def build_tail_command(cfg: UbuntuSSHConfig, lines: int = 40) -> str:
    remote_log = shlex.quote(cfg.remote_log_file)
    return "bash -lc " + shlex.quote(f"tail -n {int(lines)} -f {remote_log} 2>/dev/null || true")


def stream_remote_log(cfg: UbuntuSSHConfig, timeout: int = 60, lines: int = 40) -> None:
    client = connect_ssh(cfg)
    try:
        command = build_tail_command(cfg, lines=lines)
        stdin, stdout, stderr = client.exec_command(command, timeout=None, get_pty=True)
        while True:
            line = stdout.readline()
            if line:
                print(line.rstrip("\n"))
                continue
            if stdout.channel.exit_status_ready():
                break
            time.sleep(0.2)
    finally:
        client.close()


def restart_remote_daemon(
    cfg: UbuntuSSHConfig,
    timeout: int = DEFAULT_START_TIMEOUT,
    follow: bool = False,
    follow_lines: int = 40,
) -> int:
    client = connect_ssh(cfg)
    follow_enabled = False
    try:
        status_cmd = build_status_command(cfg)
        stop_cmd = build_stop_command(cfg)
        start_cmd = build_start_command(cfg)

        status_code, status_out, status_err = exec_remote(client, status_cmd, timeout=timeout)
        if status_out.strip():
            print(f"[info] existing daemon detected:\n{status_out.rstrip()}")
        else:
            print("[info] no running daemon found, starting a fresh one")
        if status_err.strip():
            print(status_err.rstrip(), file=sys.stderr)
        if status_code != 0 and status_out.strip():
            print(f"[warn] status command exited with code {status_code}", file=sys.stderr)

        stop_code, stop_out, stop_err = exec_remote(client, stop_cmd, timeout=timeout)
        if stop_out.strip():
            print(stop_out.rstrip())
        if stop_err.strip():
            print(stop_err.rstrip(), file=sys.stderr)
        if stop_code != 0:
            print(f"[warn] stop command exited with code {stop_code}", file=sys.stderr)

        start_code, start_out, start_err = exec_remote(client, start_cmd, timeout=timeout)
        if start_out.strip():
            print(start_out.rstrip())
        if start_err.strip():
            print(start_err.rstrip(), file=sys.stderr)
        if start_code != 0:
            print(f"[error] start command exited with code {start_code}", file=sys.stderr)
            return start_code

        print(f"[ok] remote daemon restarted: {cfg.host}:{cfg.port}")
        print(f"[ok] log: {cfg.remote_log_file}")
        print(f"[ok] pid file: {cfg.remote_pid_file}")
        follow_enabled = follow
    finally:
        client.close()

    if follow_enabled:
        time.sleep(0.5)
        print(f"[follow] attached to {cfg.remote_log_file} (Ctrl+C to stop)")
        stream_remote_log(cfg, timeout=timeout, lines=follow_lines)

    return 0


def stop_remote_daemon(cfg: UbuntuSSHConfig, timeout: int = DEFAULT_START_TIMEOUT) -> int:
    client = connect_ssh(cfg)
    try:
        stop_cmd = build_stop_command(cfg)
        code, out, err = exec_remote(client, stop_cmd, timeout=timeout)
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print(err.rstrip(), file=sys.stderr)
        return code
    finally:
        client.close()


def status_remote_daemon(cfg: UbuntuSSHConfig, timeout: int = DEFAULT_START_TIMEOUT) -> int:
    client = connect_ssh(cfg)
    try:
        status_cmd = build_status_command(cfg)
        code, out, err = exec_remote(client, status_cmd, timeout=timeout)
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print(err.rstrip(), file=sys.stderr)
        if out.strip():
            return 0
        print("[down] remote daemon is not running")
        return code if code != 0 else 1
    finally:
        client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restart qwen server on Ubuntu via SSH.")
    parser.add_argument("--stop", action="store_true", help="Stop the remote daemon only.")
    parser.add_argument("--status", action="store_true", help="Check the remote daemon status.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_START_TIMEOUT, help="SSH command timeout in seconds.")
    parser.add_argument("--follow", action="store_true", default=True, help="Print the remote log after restart.")
    parser.add_argument("--no-follow", dest="follow", action="store_false", help="Do not print the remote log after restart.")
    parser.add_argument("--follow-lines", type=int, default=40, help="How many log lines to print when using --follow.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_ssh_config()

    if args.stop:
        return stop_remote_daemon(cfg, timeout=args.timeout)
    if args.status:
        return status_remote_daemon(cfg, timeout=args.timeout)
    return restart_remote_daemon(cfg, timeout=args.timeout, follow=args.follow, follow_lines=args.follow_lines)


if __name__ == "__main__":
    raise SystemExit(main())
