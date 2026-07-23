# guide_env.md

## Muc tieu

Env Ubuntu day du de chay repo nay voi:

- QLoRA 4bit
- DeepSpeed CPU offload
- activation offload sang RAM
- merge adapter tren CPU

## Song song Windows

Windows dung chung code nay nhung chu yeu nen:

- chay server local
- chay smoke test
- sua code / debug API

Khong nen ep train 4B 4bit tren Windows neu native crash xay ra.

## Python

```text
Python 3.11
```

## Tao env

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
conda create -y -n qwen python=3.11
conda activate qwen
```

## Neu conda bi chan TOS

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

## Cai compiler he thong

```bash
apt-get update
apt-get install -y build-essential gcc g++ curl
```

## Torch CUDA

Neu GPU tu doi 5x tro len, vi du RTX 50xx / 60xx / 80xx / 90xx:

```bash
python -m pip install torch==2.12.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
```

Neu GPU doi cu hon, vi du 40xx / 20xx / 30xx:

```bash
python -m pip install torch==2.6.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

## Thu vien Python

```bash
python -m pip install \
  transformers==5.12.1 \
  accelerate==1.14.0 \
  peft==0.19.1 \
  bitsandbytes==0.49.2 \
  datasets==5.0.0 \
  tiktoken==0.13.0 \
  sentencepiece==0.2.1 \
  sentence-transformers \
  deepspeed==0.19.2 \
  huggingface_hub \
  flask \
  chromadb \
  pandas==3.0.3 \
  pyarrow==24.0.0 \
  scikit-learn==1.9.0 \
  scipy==1.17.1
```

## CUDA tools va libs cho DeepSpeed

```bash
conda install -y -c nvidia cuda-nvcc=12.4.131
conda install -y -c nvidia cuda-cudart=12.4.127
conda install -y -c nvidia cuda-cudart-dev=12.4.127
conda install -y -c nvidia libcurand-dev=10.3.5.147
```

## Sua symlink neu can

```bash
rm -f /root/miniconda3/envs/qwen/lib/libcurand.so
ln -s /root/miniconda3/envs/qwen/targets/x86_64-linux/lib/libcurand.so.10 /root/miniconda3/envs/qwen/lib/libcurand.so
```

Neu van loi `cannot find -lcurand` thi kiem tra:

```bash
ls -l /root/miniconda3/envs/qwen/lib/libcurand.so*
```

`libcurand.so` phai tro dung toi:

```text
/root/miniconda3/envs/qwen/targets/x86_64-linux/lib/libcurand.so.10
```

## Bien moi truong can dung

```bash
export CC=/usr/bin/gcc
export CXX=/usr/bin/g++
export QWEN_BASE_MODEL=/root/model/Qwen/Qwen3.5-4B
export QWEN_OUTPUT_DIR=/root/model/Qwen/Qwen3.5-4B_vn_1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export QWEN_CPU_MAX_MEMORY=48GiB
```

## Adapter tu Windows sang Ubuntu

Adapter phai duoc dua tu Windows sang va luu rieng tai:

```text
/root/model/Qwen/Qwen3.5-4B_vn_1/adapter
```

Khong merge vao base model o buoc env nay. Phan merge neu co chi lam o buoc khac.

## Bien huu ich nhung khong bat buoc

```bash
export HF_TOKEN=hf_xxx
```

Dung khi can download tu Hugging Face on dinh hon.

## Stack da dung duoc thuc te

```text
Neu GPU doi 5x tro len: torch 2.12.1+cu130
Neu GPU doi cu hon: torch 2.6.0+cu124
transformers 5.12.1
accelerate 1.14.0
peft 0.19.1
bitsandbytes 0.49.2
datasets 5.0.0
tiktoken 0.13.0
sentencepiece 0.2.1
deepspeed 0.19.2
flask 3.1.3
chromadb
pandas 3.0.3
pyarrow 24.0.0
scikit-learn 1.9.0
scipy 1.17.1
cuda-nvcc 12.4.131
cuda-cudart 12.4.127
cuda-cudart-dev 12.4.127
libcurand-dev 10.3.5.147
```

## Kiem tra nhanh

```bash
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
python -c "import transformers, accelerate, peft, bitsandbytes, datasets, tiktoken, sentencepiece, deepspeed, pandas, pyarrow, sklearn, scipy, huggingface_hub, flask, chromadb; print('ok')"
nvcc -V
curl --version | head -n 1
ls -l /root/miniconda3/envs/qwen/lib/libcudart.so*
ls -l /root/miniconda3/envs/qwen/lib/libcurand.so*
```

## Kiem tra them nen chay

```bash
python -c "import bitsandbytes as bnb; print('bnb ok')"
python -c "import deepspeed; print(deepspeed.__version__)"
python -c "import flask, chromadb; print(flask.__version__, 'chromadb ok')"
```

## Loi thuc te da gap

- `CondaToSNonInteractiveError`
  - chay 2 lenh `conda tos accept` o tren roi tao env lai
- `RuntimeError: cannot find -lcurand`
  - xoa symlink `libcurand.so` cu
  - tao lai dung vao `targets/x86_64-linux/lib/libcurand.so.10`
- `fast path is not available`
  - khong chan train
  - chi la chua cai `flash-linear-attention` va `causal-conv1d`
