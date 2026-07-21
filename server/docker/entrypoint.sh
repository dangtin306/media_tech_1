#!/usr/bin/env bash
set -euo pipefail

CODE_ROOT=/root/media_tech
MODEL_ROOT=/root/model
BASE_MODEL_REPO=${QWEN_BASE_MODEL_REPO:-Qwen/Qwen3.5-4B}
IMAGE_ADAPTER=/opt/media-tech/adapter
MODEL_ADAPTER=$MODEL_ROOT/Qwen/Qwen3.5-4B_vn_1/adapter
export QWEN_BASE_MODEL_REPO="$BASE_MODEL_REPO" QWEN_BASE_MODEL="$MODEL_ROOT/Qwen/Qwen3.5-4B"
SSH_KEY=${SOURCE_SSH_KEY:-/root/.ssh/id_ed25519}

ssh_args=(
    -i "$SSH_KEY"
    -o BatchMode=yes
    -o StrictHostKeyChecking=accept-new
)

sync_missing() {
    local source_path="$1"
    local destination="$2"
    local remote="${SOURCE_SSH_USER}@${SOURCE_SSH_HOST}:${source_path%/}/."

    if [[ -z "${SOURCE_SSH_USER:-}" || -z "${SOURCE_SSH_HOST:-}" ]]; then
        echo "[sync] SOURCE_SSH_USER and SOURCE_SSH_HOST are required" >&2
        exit 1
    fi
    if [[ ! -f "$SSH_KEY" ]]; then
        echo "[sync] SSH key not found: $SSH_KEY" >&2
        exit 1
    fi

    mkdir -p "$destination"
    scp "${ssh_args[@]}" -r "$remote" "$destination/"
}

if [[ ! -f "$CODE_ROOT/server/run/main.py" ]]; then
    if [[ -z "${SOURCE_SSH_PATH:-}" ]]; then
        echo "[sync] code is missing and SOURCE_SSH_PATH is not set" >&2
        exit 1
    fi
    echo "[sync] code is missing; downloading from ${SOURCE_SSH_HOST:-unset}" >&2
    sync_missing "$SOURCE_SSH_PATH" "$CODE_ROOT"
fi

BASE_MODEL=$MODEL_ROOT/Qwen/Qwen3.5-4B
if [[ ! -d "$BASE_MODEL" || ! -f "$BASE_MODEL/config.json" ]]; then
    echo "[model] downloading $BASE_MODEL_REPO from Hugging Face" >&2
    mkdir -p "$BASE_MODEL"
    python -c 'from huggingface_hub import snapshot_download; import os; snapshot_download(repo_id=os.environ["QWEN_BASE_MODEL_REPO"], local_dir=os.environ["QWEN_BASE_MODEL"])'
fi

if [[ ! -d "$MODEL_ADAPTER" ]]; then
    echo "[model] copying adapter from image" >&2
    mkdir -p "$(dirname "$MODEL_ADAPTER")"
    cp -a "$IMAGE_ADAPTER" "$MODEL_ADAPTER"
fi

python -m compileall -q "$CODE_ROOT"
cd "$CODE_ROOT/ai/qwen/qwen3.5_4B_vn/server"

/usr/local/bin/bootstrap-cuda
export CUDA_HOME=/usr/local/cuda
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

if [[ "${1:-}" == "python" || "${1:-}" == "python3" ]]; then
    exec "$@"
fi

exec python "$@"
