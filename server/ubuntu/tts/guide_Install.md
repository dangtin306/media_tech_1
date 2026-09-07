# VieNeu-TTS trên Ubuntu — cài đặt chuẩn

Tài liệu này là quy trình chuẩn để dựng một Ubuntu GPU mới. Mọi code được lấy từ GitHub, không copy từng phiên bản rời từ Windows.

## 1. Biến đường dẫn dùng chung

```bash
export REPO_DIR=/root/media_tech_ai/vie_neu
export CONDA_DIR=/root/miniconda3
export ENV_NAME=tts_5
```

Nếu dùng user khác `root`, đổi ba biến trên cho phù hợp. Không đổi cấu trúc bên trong repo.

## 2. Kiểm tra GPU và cài gói hệ thống

Ubuntu phải có driver NVIDIA trước. Kiểm tra:

```bash
nvidia-smi
```

Cài các gói cần cho audio, Git và build Python:

```bash
apt-get update
apt-get install -y build-essential gcc g++ git curl ca-certificates bzip2 ffmpeg libsndfile1
```

Nếu `nvidia-smi` chưa chạy, cài/sửa driver NVIDIA trước; không xử lý bằng cách đổi phiên bản PyTorch.

## 3. Cài Miniconda và tạo env

```bash
if [ ! -x "$CONDA_DIR/bin/conda" ]; then
  cd /tmp
  curl -fL -o miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  bash miniconda.sh -b -p "$CONDA_DIR"
  rm -f miniconda.sh
fi

source "$CONDA_DIR/etc/profile.d/conda.sh"
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

if ! conda env list | grep -q "^${ENV_NAME}[[:space:]]"; then
  conda create -y -n "$ENV_NAME" python=3.11
fi
conda activate "$ENV_NAME"

grep -qxF "source $CONDA_DIR/etc/profile.d/conda.sh" ~/.bashrc || \
  echo "source $CONDA_DIR/etc/profile.d/conda.sh" >> ~/.bashrc
```

## 4. Lấy code từ GitHub

```bash
mkdir -p "$(dirname "$REPO_DIR")"
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone https://github.com/dangtin306/vie_neu.git "$REPO_DIR"
else
  git -C "$REPO_DIR" pull --ff-only
fi
```

Không chạy `scp -r` đè lên repo đã clone. Windows chỉ cần push code lên GitHub, Ubuntu dùng `git pull --ff-only`.

## 5. Cài PyTorch CUDA và VieNeu

```bash
conda activate "$ENV_NAME"

python -m pip install torch==2.8.0 torchaudio==2.8.0 \
  --index-url https://download.pytorch.org/whl/cu128

cd "$REPO_DIR/source_code/audio_model"
python -m pip install -e .

python -m pip install \
  neucodec==0.0.5 \
  torchao==0.12.0 \
  transformers==4.57.6 \
  tokenizers==0.22.1 \
  datasets \
  peft==0.13.2 \
  accelerate==1.14.0 \
  librosa \
  tqdm
```

Bộ version trên đã chạy được với Qwen3, NeuCodec và LoRA. Không nâng `torchao`, `transformers` hoặc `peft` tùy ý trong env train.

## 6. Đăng nhập Hugging Face cho NeuCodec

`neuphonic/neucodec` là gated model. Trên Windows cần đăng nhập và được cấp quyền trước. Token Windows thường ở:

```text
%USERPROFILE%\.cache\huggingface\token
```

Chuyển token qua SSH, chạy trên PowerShell Windows:

```powershell
scp -P <SSH_PORT> "$env:USERPROFILE\.cache\huggingface\token" root@<UBUNTU_HOST>:/tmp/hf_token
```

Sau đó chạy trên Ubuntu:

```bash
conda activate tts_5
chmod 600 /tmp/hf_token
hf auth login --token "$(cat /tmp/hf_token)"
rm -f /tmp/hf_token
hf auth whoami

hf download neuphonic/neucodec config.json --local-dir /tmp/neucodec_probe
rm -rf /tmp/neucodec_probe
```

Không commit token, không ghi token vào file guide. Token sau khi login nằm trong `/root/.cache/huggingface/`.

## 7. Kiểm tra môi trường

```bash
conda activate tts_5
python --version
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
python -c "import torch; print(torch.cuda.get_device_name(0))"
python -c "import vieneu, neucodec, peft, transformers; print('VieNeu environment: OK')"
nvidia-smi
ffmpeg -version | head -n 1
```

## 8. Chạy training Nghệ An

```bash
conda activate tts_5
python "$REPO_DIR/train/process/v2/train_nghean_v2_advanced.py" --overwrite
```

Chạy nền và lưu log:

```bash
nohup "$CONDA_DIR/envs/$ENV_NAME/bin/python" \
  "$REPO_DIR/train/process/v2/train_nghean_v2_advanced.py" \
  --overwrite > /tmp/nghean_advanced.log 2>&1 < /dev/null &
tail -f /tmp/nghean_advanced.log
```

Kết quả nằm ở:

```text
$REPO_DIR/train/output/nghean_v2_advanced/
```

Không xóa dataset gốc và không chạy đè pipeline v3.

## 9. Kiểm tra model sau train

```bash
python "$REPO_DIR/train/process/v2/test_1/test_merged_model.py"
```

WAV test nằm ở:

```text
$REPO_DIR/train/process/v2/test_1/outputs/
```

Script test có giới hạn fallback khi model không sinh token EOS, nên không để output chạy tới 32 giây.
