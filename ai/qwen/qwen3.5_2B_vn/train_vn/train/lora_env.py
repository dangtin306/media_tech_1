import os
import sys


EXPECTED_CONDA_PREFIX = r"D:\hustmedia\conda_envs\qwen"


def is_docker_runtime() -> bool:
    return os.environ.get("QWEN_DOCKER") == "1" or os.path.exists("/.dockerenv")


def ensure_conda_env(expected_prefix: str = EXPECTED_CONDA_PREFIX) -> None:
    if is_docker_runtime():
        return

    current_prefix = os.environ.get("CONDA_PREFIX") or sys.prefix
    expected_norm = os.path.normcase(os.path.normpath(expected_prefix))
    current_norm = os.path.normcase(os.path.normpath(current_prefix))
    if current_norm != expected_norm:
        raise SystemExit(
            f"[fatal] wrong env: current={current_prefix} expected={expected_prefix}"
        )
