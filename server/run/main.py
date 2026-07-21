import os
import subprocess
import shutil
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
FRONTEND_ROOT = ROOT / "fontend"
BACKEND_PORT = 8006
FRONTEND_PORT = 8008
IGNORED_FRONTEND_DIRS = {".git", ".nuxt", ".output", "node_modules", "__pycache__"}
IGNORED_FRONTEND_FILES = {".DS_Store"}


def env_flag(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() not in {"0", "false", "no", "off"}


def npm_bin() -> str:
    binary = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if not binary:
        raise FileNotFoundError("Could not find npm in PATH")
    return binary


def start_npm_script(name: str, cwd: Path, script: str) -> subprocess.Popen:
    if not (cwd / "package.json").exists():
        raise FileNotFoundError(f"Missing package.json in {cwd}")

    binary = npm_bin()
    print(f"[start] {name}: npm run {script} ({cwd})", flush=True)
    return subprocess.Popen(
        [binary, "run", script],
        cwd=str(cwd),
    )


def run_npm_build(name: str, cwd: Path) -> None:
    if not (cwd / "package.json").exists():
        raise FileNotFoundError(f"Missing package.json in {cwd}")

    binary = npm_bin()
    print(f"[build] {name}: npm run build ({cwd})", flush=True)
    result = subprocess.run(
        [binary, "run", "build"],
        cwd=str(cwd),
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, [binary, "run", "build"])


def terminate_process(proc: subprocess.Popen | None, label: str) -> None:
    if proc is None or proc.poll() is not None:
        return

    print(f"[stop] terminating {label} (pid {proc.pid})", flush=True)
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            text=True,
        )
    else:
        try:
            proc.terminate()
        except Exception:
            pass

    try:
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def snapshot_files(root: Path) -> dict[Path, tuple[int, int]]:
    snapshot: dict[Path, tuple[int, int]] = {}
    if not root.exists():
        return snapshot

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        try:
            relative_parts = path.relative_to(root).parts
        except ValueError:
            continue

        if any(part in IGNORED_FRONTEND_DIRS for part in relative_parts):
            continue

        if path.name in IGNORED_FRONTEND_FILES:
            continue

        try:
            stat = path.stat()
        except OSError:
            continue

        snapshot[path] = (int(stat.st_mtime_ns), int(stat.st_size))

    return snapshot


def watch_and_restart_frontend(frontend_root: Path, process_ref: dict[str, subprocess.Popen | None], stop_event: threading.Event) -> None:
    previous = snapshot_files(frontend_root)
    pending_change = False
    change_detected_at = 0.0
    debounce_seconds = 1.5

    while not stop_event.is_set():
        time.sleep(1.0)

        current = snapshot_files(frontend_root)
        if current == previous:
            pending_change = False
            continue

        if not pending_change:
            pending_change = True
            change_detected_at = time.time()
            continue

        if time.time() - change_detected_at < debounce_seconds:
            continue

        previous = current
        pending_change = False

        proc = process_ref.get("proc")
        if proc is None or proc.poll() is not None:
            continue

        print("[watch] frontend files changed, restarting build...", flush=True)
        terminate_process(proc, "frontend")
        run_npm_build("frontend", frontend_root)
        process_ref["proc"] = start_npm_script("frontend", frontend_root, "start")


def get_listener_pids(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

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


def kill_port(port: int, label: str) -> None:
    pids = get_listener_pids(port)
    if not pids:
        return

    print(f"[port] {label} {port} already in use, stopping PID(s): {', '.join(map(str, pids))}", flush=True)
    for pid in pids:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            text=True,
        )


def main() -> int:
    backend_proc: subprocess.Popen | None = None
    frontend_ref: dict[str, subprocess.Popen | None] = {"proc": None}
    stop_event = threading.Event()
    watcher: threading.Thread | None = None

    try:
        if env_flag("KILL_PORTS_ON_START", "1"):
            kill_port(BACKEND_PORT, "backend")
            kill_port(FRONTEND_PORT, "frontend")

        if env_flag("RUN_BACKEND", "1"):
            backend_proc = start_npm_script("backend", BACKEND_DIR, "dev")

        if env_flag("RUN_FRONTEND", "1"):
            run_npm_build("frontend", FRONTEND_ROOT)
            frontend_ref["proc"] = start_npm_script("frontend", FRONTEND_ROOT, "start")
            watcher = threading.Thread(
                target=watch_and_restart_frontend,
                args=(FRONTEND_ROOT, frontend_ref, stop_event),
                daemon=True,
            )
            watcher.start()

        if backend_proc is None and frontend_ref["proc"] is None:
            print("No process started. Check RUN_BACKEND / RUN_FRONTEND.", flush=True)
            return 1

        print("[ready] Press Ctrl+C to stop all processes.", flush=True)

        while True:
            if backend_proc is not None:
                code = backend_proc.poll()
                if code is not None:
                    print(f"[exit] backend exited with code {code}", flush=True)
                    return code
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[stop] Ctrl+C received, terminating child processes...", flush=True)
        return 130
    finally:
        stop_event.set()

        if backend_proc is not None and backend_proc.poll() is None:
            terminate_process(backend_proc, "backend")

        frontend_proc = frontend_ref["proc"]
        if frontend_proc is not None and frontend_proc.poll() is None:
            terminate_process(frontend_proc, "frontend")

        for proc in [backend_proc, frontend_ref["proc"]]:
            if proc is None:
                continue
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
