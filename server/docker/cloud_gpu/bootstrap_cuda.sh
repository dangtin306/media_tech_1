#!/usr/bin/env bash
set -euo pipefail

MARKER=/opt/qwen-runtime/cuda-12.4.ready

if [[ -f "$MARKER" ]]; then
    export CUDA_HOME=/usr/local/cuda
    export PATH="$CUDA_HOME/bin:$PATH"
    export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
    exit 0
fi

echo "[cuda] installing CUDA Toolkit 12.4 in the container"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates wget gnupg

wget -q \
    https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb \
    -O /tmp/cuda-keyring.deb
dpkg -i /tmp/cuda-keyring.deb
rm -f /tmp/cuda-keyring.deb

apt-get update
apt-get install -y --no-install-recommends cuda-toolkit-12-4
rm -rf /var/lib/apt/lists/*

export CUDA_HOME=/usr/local/cuda
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

echo "[cuda] installing PyTorch CUDA 12.4 wheels"
python -m pip install --upgrade pip
python -m pip install \
    torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 \
    --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r /tmp/requirements.txt

mkdir -p "$(dirname "$MARKER")"
touch "$MARKER"
echo "[cuda] runtime setup complete"
