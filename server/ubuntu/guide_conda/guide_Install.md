# guide_cai.md

## Muc tieu

Cai moi tren Ubuntu de chay duoc repo nay on dinh.

## Luu y Windows / Ubuntu

- Windows: dung de sua code, chay server local, smoke test.
- Ubuntu: dung de train 4B/4bit va chay DeepSpeed offload.
- Cung mot code base, nhung khac path:
  - Windows model: `D:\huggingface\hub\Qwen\Qwen3.5-4B`
  - Ubuntu model: `/root/model/Qwen/Qwen3.5-4B`
  - Windows repo: `D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_4B_vn`
  - Ubuntu repo: `/root/media_tech/ai/qwen/qwen3.5_4B_vn`

## Thu tu doc

1. `guide_env.md`
2. `guide_folder.md`
3. `guide_run.md`

## 1. Tao env

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
conda create -y -n qwen python=3.11
conda activate qwen
```

## 2. Cai env day du

Doc va lam theo:

```text
guide_env.md
```

Phan nay da gom:
- build-essential, gcc, g++
- curl
- torch
- transformers
- accelerate
- peft
- bitsandbytes
- datasets
- tiktoken
- sentencepiece
- deepspeed
- pandas
- pyarrow
- scikit-learn
- scipy
- cuda-nvcc
- cuda-cudart
- cuda-cudart-dev
- libcurand-dev
- symlink `libcurand.so`
- bien moi truong `CC`, `CXX`, `QWEN_BASE_MODEL`, `QWEN_OUTPUT_DIR`, `PYTORCH_CUDA_ALLOC_CONF`, `QWEN_CPU_MAX_MEMORY`

Neu `torch` import bi loi `undefined symbol: iJIT_NotifyEvent` tren Ubuntu, them:

```bash
export LD_PRELOAD=/root/miniconda3/envs/qwen/lib/libittnotify.so
export KMP_DUPLICATE_LIB_OK=TRUE
```

Thuong chi can set dong nay sau khi cai `torch` xong va truoc khi chay server.

## 3. Chuan bi thu muc

Doc va lam theo:

```text
guide_folder.md
```

Phan nay dung de dam bao cac duong dan chuan:
- `/root/model/Qwen/Qwen3.5-4B`
- `/root/model/Qwen/Qwen3.5-4B_vn_1`
- `/root/media_tech/ai/qwen/qwen3.5_4B_vn`

## 4. Download model neu chua co

```bash
mkdir -p /root/model/Qwen
python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Qwen/Qwen3.5-4B",
    local_dir="/root/model/Qwen/Qwen3.5-4B",
)
PY
```

Neu model gated hoac bi rate limit, dang nhap truoc:

```bash
huggingface-cli login
```

## 5. Dua code len server

Neu repo da nam o:

```text
/root/media_tech/ai/qwen/qwen3.5_4B_vn
```

thi bo qua.

Neu chua co:

```bash
rm -rf /root/media_tech
git clone --depth 1 https://github.com/dangtin306/media_tech_1.git /root/media_tech
```

Neu can cap nhat lai code, dung `git pull` trong `/root/media_tech`.

## 6. Kiem tra nhanh

```bash
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
python -c "import transformers, accelerate, peft, bitsandbytes, datasets, tiktoken, sentencepiece, deepspeed, pandas, pyarrow, sklearn, scipy, huggingface_hub; print('ok')"
nvcc -V
ls -lah /root/model/Qwen/Qwen3.5-4B
ls -lh /root/model/Qwen/Qwen3.5-4B/model.safetensors-* /root/model/Qwen/Qwen3.5-4B/model.safetensors.index.json
```

## 7. Chay

Doc va lam theo:

```text
guide_run.md
```

## 8. Neu loi

### Loi tokenizer

Xem lai:

```text
guide_env.md
```

Can co:

```bash
pip install tiktoken sentencepiece
```

### Loi DeepSpeed / CPUAdam

Xem lai:

```text
guide_env.md
```

Can co:

```bash
apt-get install -y build-essential gcc g++
conda install -y -c nvidia cuda-nvcc=12.4.131
conda install -y -c nvidia cuda-cudart=12.4.127
conda install -y -c nvidia cuda-cudart-dev=12.4.127
conda install -y -c nvidia libcurand-dev=10.3.5.147
rm -f /root/miniconda3/envs/qwen/lib/libcurand.so
ln -s /root/miniconda3/envs/qwen/targets/x86_64-linux/lib/libcurand.so.10 /root/miniconda3/envs/qwen/lib/libcurand.so
ls -l /root/miniconda3/envs/qwen/lib/libcurand.so*
```

### Loi OOM

Xem lai:

```text
guide_run.md
```

### Loi Conda TOS

Neu `conda create` bi chan boi Terms of Service:

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

### Download model bi treo lau

Phai tach 2 buoc:

1. download model xong
2. kiem tra du 2 shard roi moi smoke test hoac train

Lenh check:

```bash
ls -lh /root/model/Qwen/Qwen3.5-4B/model.safetensors-* /root/model/Qwen/Qwen3.5-4B/model.safetensors.index.json
```

## 9. Lenh check khi dang train

```bash
nvidia-smi
free -h
ps -eo pid,pmem,rss,cmd --sort=-rss | head
```
