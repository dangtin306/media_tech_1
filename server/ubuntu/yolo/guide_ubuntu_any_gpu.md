# YOLO26 Ubuntu - install on a new machine

This is the portable guide for a fresh Ubuntu machine. It supports:

- NVIDIA GPU with a working driver
- CPU-only inference/training
- Ubuntu 22.04 or 24.04
- Miniconda or an existing Conda installation

It does not assume a specific GPU model. The NVIDIA driver must be installed by the machine/provider first.

## 0. Network preflight

Run these before installing anything:

```bash
getent hosts github.com
getent hosts repo.anaconda.com
getent hosts download.pytorch.org
```

If any command returns nothing, fix DNS/network first. A failed `pip`, `conda`, or `git clone` with `NameResolutionError` is not a YOLO error.

## 1. Install the environment

Use the helper script in this folder:

```bash
cd /root/media_tech_ai/server/ubuntu/yolo
bash install_yolo_ubuntu.sh
```

The script creates:

```text
/root/miniconda3/envs/yolo26
```

It does not store API keys and does not download a dataset.

## 2. Choose the PyTorch build

Default behavior:

- NVIDIA detected: install the normal PyTorch package and verify CUDA.
- No NVIDIA detected: install CPU PyTorch.

For a specific NVIDIA CUDA wheel, set the official PyTorch index before running the script:

```bash
export TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124
bash install_yolo_ubuntu.sh
```

Use the index recommended by the [official PyTorch install selector](https://pytorch.org/get-started/locally/) for the installed driver. Very old GPUs may require an older PyTorch/CUDA build; no single wheel supports every GPU generation.

## 3. Verify

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate yolo26
python -c "import torch; print('torch=', torch.__version__); print('cuda=', torch.cuda.is_available()); print('device=', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
python -c "from ultralytics import YOLO; print('ultralytics import ok')"
```

