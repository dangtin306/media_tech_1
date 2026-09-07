# VieNeu-TTS — kiểm tra và cố định môi trường `tts_5`

File này dùng sau `guide_Install.md` để kiểm tra một Ubuntu mới có đúng môi trường đã dùng train hay chưa.

## Kích hoạt env

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate tts_5
```

## Bộ version đã xác nhận

```text
Python       3.11
torch        2.8.0+cu128
torchaudio   2.8.0+cu128
torchao      0.12.0
transformers 4.57.6
tokenizers   0.22.1
neucodec     0.0.5
peft         0.13.2
accelerate   1.14.0
```

Kiểm tra version thực tế:

```bash
python - <<'PY'
import importlib.metadata as md
import torch

for name in ("torch", "torchaudio", "torchao", "transformers", "tokenizers", "neucodec", "peft", "accelerate"):
    try:
        print(f"{name}: {md.version(name)}")
    except md.PackageNotFoundError:
        print(f"{name}: MISSING")
print("cuda:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))
PY
```

## Sửa env nếu package bị lệch

Chỉ chạy trong `tts_5`:

```bash
python -m pip install --force-reinstall --no-cache-dir \
  torch==2.8.0 torchaudio==2.8.0 \
  --index-url https://download.pytorch.org/whl/cu128

python -m pip install --force-reinstall \
  neucodec==0.0.5 torchao==0.12.0 transformers==4.57.6 \
  tokenizers==0.22.1 peft==0.13.2 accelerate==1.14.0
```

Sau đó kiểm tra lại bằng lệnh ở trên.

## Lỗi đã gặp và cách xử lý

### `CondaToSNonInteractiveError`

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

### `ModuleNotFoundError: neucodec` hoặc `peft`

Đảm bảo đã chạy `conda activate tts_5`, sau đó cài lại nhóm package ở `guide_Install.md`.

### `Found an incompatible version of torchao`

Không dùng `torchao 0.12.0` với bản PEFT mới tùy ý. Bộ ổn định cho pipeline này là `torchao==0.12.0` và `peft==0.13.2`.

### `model type qwen3 not recognized`

Transformers quá cũ. Cài `transformers==4.57.6` và `tokenizers==0.22.1`.

### NeuCodec trả về `401 Unauthorized`

Model là gated. Xin quyền trên Hugging Face, login bằng token rồi kiểm tra:

```bash
hf auth whoami
hf download neuphonic/neucodec config.json --local-dir /tmp/neucodec_probe
rm -rf /tmp/neucodec_probe
```

### CUDA không khả dụng

```bash
nvidia-smi
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Nếu `nvidia-smi` lỗi thì xử lý driver trước. Nếu `nvidia-smi` chạy nhưng PyTorch không thấy GPU, cài lại đúng wheel `cu128`.

## Đồng bộ code

```bash
git -C /root/media_tech_ai/vie_neu pull --ff-only
```

Windows là nơi chỉnh sửa và push GitHub; Ubuntu chỉ pull commit cần chạy.
