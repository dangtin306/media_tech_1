# VieNeu-TTS Ubuntu GPU — guide chuẩn mới

Guide này dùng cho Ubuntu GPU mới. Code lấy từ GitHub, không copy repo bằng
`scp -r` sau khi đã clone.

## Cài máy mới

```bash
export REPO_DIR=/root/media_tech_ai/vie_neu
export CONDA_DIR=/root/miniconda3
export ENV_NAME=tts_5

nvidia-smi
apt-get update
apt-get install -y build-essential gcc g++ git curl ca-certificates bzip2 ffmpeg libsndfile1

if [ ! -x "$CONDA_DIR/bin/conda" ]; then
  cd /tmp
  curl -fL -o miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  bash miniconda.sh -b -p "$CONDA_DIR"
  rm -f miniconda.sh
fi

source "$CONDA_DIR/etc/profile.d/conda.sh"
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
conda create -y -n "$ENV_NAME" python=3.11
conda activate "$ENV_NAME"

mkdir -p "$(dirname "$REPO_DIR")"
git clone https://github.com/dangtin306/vie_neu.git "$REPO_DIR"

python -m pip install torch==2.8.0 torchaudio==2.8.0 \
  --index-url https://download.pytorch.org/whl/cu128
cd "$REPO_DIR/source_code/audio_model"
python -m pip install -e .
python -m pip install \
  neucodec==0.0.5 torchao==0.12.0 transformers==4.57.6 \
  tokenizers==0.22.1 datasets peft==0.13.2 accelerate==1.14.0 \
  librosa tqdm
```

`nvidia-smi` phải chạy được trước khi cài PyTorch. Driver NVIDIA có thể có
CUDA version khác, miễn là driver đủ mới để chạy wheel `cu128`.

## Hugging Face / NeuCodec

```bash
chmod 600 /tmp/hf_token
TOKEN=$(cat /tmp/hf_token)
hf auth login --token "$TOKEN"
rm -f /tmp/hf_token
hf auth whoami
hf download neuphonic/neucodec config.json --local-dir /tmp/neucodec_probe
rm -rf /tmp/neucodec_probe
```

Không commit token vào GitHub. Token chỉ lưu tại `/root/.cache/huggingface/`.

## Kiểm tra môi trường

```bash
python - <<'PY'
import torch, vieneu, neucodec, peft, transformers
print(torch.__version__, torch.version.cuda)
print(torch.cuda.is_available(), torch.cuda.get_device_name(0))
print(transformers.__version__)
print('VieNeu environment: OK')
PY
```

## Train Nghệ An

File train tự đặt GPU ổn định: GPU `cuda:0`, CUDA synchronous, tắt TF32,
attention eager và gradient checkpointing. Không cần export biến CUDA thủ công.

```bash
cd "$REPO_DIR"
python train/process/v2/train_nghean_v2_advanced.py \
  --run-name nghean_v2_new \
  --epochs 125 \
  --learning-rate 9e-6 \
  --fp32 \
  --skip-infer
```

Chạy nền:

```bash
nohup "$CONDA_DIR/envs/$ENV_NAME/bin/python" \
  "$REPO_DIR/train/process/v2/train_nghean_v2_advanced.py" \
  --run-name nghean_v2_new --epochs 125 --learning-rate 9e-6 \
  --fp32 --skip-infer > /tmp/nghean_new.log 2>&1 < /dev/null &
tail -f /tmp/nghean_new.log
```

Output nằm tại:

```text
$REPO_DIR/train/output/nghean_v2_new/
```

Nếu job dừng sau khi có checkpoint, tiếp tục bằng:

```bash
python train/process/v2/train_nghean_v2_advanced.py \
  --run-name nghean_v2_resume --epochs 125 --learning-rate 9e-6 \
  --fp32 \
  --resume-from-checkpoint \
  "$REPO_DIR/train/output/nghean_v2_new/adapter/checkpoint-XXX" \
  --skip-infer
```

CPU vẫn dùng cho đọc WAV, tokenizer và DataLoader; model/LoRA train toàn bộ
trên GPU. Không xóa dataset gốc và không chạy pipeline v3.
