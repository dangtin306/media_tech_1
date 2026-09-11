#!/usr/bin/env bash
set -euo pipefail

CONDA_DIR="${CONDA_DIR:-/root/miniconda3}"
ENV_NAME="${ENV_NAME:-yolo26}"
REPO_URL="${REPO_URL:-https://github.com/dangtin306/media_tech_1.git}"

echo "[1/6] Checking network"
getent hosts github.com >/dev/null
getent hosts repo.anaconda.com >/dev/null

if [[ ! -x "$CONDA_DIR/bin/conda" ]]; then
  echo "[2/6] Installing Miniconda at $CONDA_DIR"
  INSTALLER="/tmp/miniconda-yolo.sh"
  if command -v curl >/dev/null 2>&1; then
    curl -fL -o "$INSTALLER" https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$INSTALLER" https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  else
    python3 - "$INSTALLER" <<'PY'
import sys
import urllib.request
urllib.request.urlretrieve(
    "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh",
    sys.argv[1],
)
PY
  fi
  bash "$INSTALLER" -b -p "$CONDA_DIR"
fi

source "$CONDA_DIR/etc/profile.d/conda.sh"

echo "[3/6] Accepting Conda terms and creating environment"
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || true
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || true
if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  conda create -y -n "$ENV_NAME" python=3.10
fi
conda activate "$ENV_NAME"

echo "[4/6] Installing PyTorch"
python -m pip install --upgrade pip
if [[ -n "${TORCH_INDEX_URL:-}" ]]; then
  python -m pip install torch torchvision torchaudio --index-url "$TORCH_INDEX_URL"
elif command -v nvidia-smi >/dev/null 2>&1; then
  python -m pip install torch torchvision torchaudio
else
  python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
fi

echo "[5/6] Installing Ultralytics from GitHub"
python -m pip install --upgrade "git+$REPO_URL"

echo "[6/6] Verifying"
python - <<'PY'
import torch
import ultralytics

print("torch=", torch.__version__)
print("ultralytics=", ultralytics.__version__)
print("cuda=", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device=", torch.cuda.get_device_name(0))
PY

