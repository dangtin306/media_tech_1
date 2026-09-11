# YOLO26 - moi truong Ubuntu

Khong copy .venv Windows sang Ubuntu. Tao moi truong Linux moi:

~~~bash
source /root/miniconda3/etc/profile.d/conda.sh
conda create -y -n yolo26 python=3.10
conda activate yolo26
which python
python --version
python -m pip --version
~~~

Neu Conda bao TOS:

~~~bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
~~~

Neu bao NameResolutionError, sua DNS/network truoc:

~~~bash
getent hosts repo.anaconda.com
getent hosts github.com
getent hosts download.pytorch.org
cat /etc/resolv.conf
~~~

## Cai thu vien

~~~bash
python -m pip install --upgrade pip
python -m pip install git+https://github.com/ultralytics/ultralytics.git
~~~

PyTorch CPU:

~~~bash
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
~~~

NVIDIA: chon dung index CUDA tai PyTorch selector, vi du cu124:

~~~bash
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
~~~

Khong cai CUDA wheel tren may khong co NVIDIA. Kiem tra:

~~~bash
nvidia-smi || true
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
~~~

## Bien train

~~~bash
export YOLO_DEVICE=auto
export YOLO_BATCH=auto
export YOLO_EPOCHS=100
export YOLO_WORKERS=4
~~~

YOLO_DEVICE=auto dung GPU khi PyTorch nhan ra CUDA, neu khong tu chuyen sang CPU.
