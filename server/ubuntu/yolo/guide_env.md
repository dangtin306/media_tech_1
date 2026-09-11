# YOLO26 — môi trường Conda trên Ubuntu

Không copy `.venv` Windows sang Ubuntu. Tạo môi trường Linux mới.

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda create -y -n yolo26 python=3.10
conda activate yolo26
```

## Cài Ultralytics từ GitHub

```bash
python -m pip install --upgrade pip
python -m pip install \
  git+https://github.com/ultralytics/ultralytics.git
```

Nếu dùng Roboflow SDK/API:

```bash
python -m pip install inference-sdk roboflow
```

## Kiểm tra GPU

```bash
nvidia-smi
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

Nếu `torch.cuda.is_available()` là `False`, cần cài PyTorch bản CUDA phù hợp với driver/GPU Ubuntu trước khi train.

## Secret

API key Roboflow/Hugging Face phải đặt bằng biến môi trường hoặc file `.env` riêng trên Ubuntu, không commit vào GitHub.

