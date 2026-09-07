# VieNeu-TTS — chạy server, train và test

## Kích hoạt môi trường

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate tts_5
cd /root/media_tech_ai/vie_neu
```

## Đồng bộ code trước khi chạy

```bash
git pull --ff-only
git log -1 --oneline
```

## Chạy server TTS

Nếu repo có `server_3.py`:

```bash
python server_3.py
```

Kiểm tra từ terminal khác:

```bash
curl http://127.0.0.1:8791/health
```

## Train Nghệ An

```bash
python train/process/v2/train_nghean_v2_advanced.py --overwrite
```

Chạy nền:

```bash
nohup /root/miniconda3/envs/tts_5/bin/python \
  /root/media_tech_ai/vie_neu/train/process/v2/train_nghean_v2_advanced.py \
  --overwrite > /tmp/nghean_advanced.log 2>&1 < /dev/null &
```

Theo dõi:

```bash
tail -f /tmp/nghean_advanced.log
nvidia-smi
```

Kiểm tra đã xong:

```bash
cat train/output/nghean_v2_advanced/training_report.json
find train/output/nghean_v2_advanced/merged_model -maxdepth 1 -type f
```

## Test model merged

```bash
python train/process/v2/test_1/test_merged_model.py
find train/process/v2/test_1/outputs -name '*.wav' -ls
```

Script test dùng `merged_model`, tự chọn reference Nghệ An hợp lệ và có giới hạn fallback nếu model không phát token EOS. WAV dài bất thường sẽ được in cảnh báo.

## Dừng job cũ trước khi chạy lại

```bash
pkill -f train_nghean_v2_advanced.py || true
pkill -f test_merged_model.py || true
```

Chỉ dùng lệnh này khi chắc chắn không còn job train/test cần giữ.

## Kiểm tra kết quả

```bash
python - <<'PY'
import json
from pathlib import Path

p = Path('train/output/nghean_v2_advanced/training_report.json')
if p.is_file():
    r = json.loads(p.read_text(encoding='utf-8'))
    print('status:', r.get('status'))
    print('train:', r.get('training'))
    print('ab_test:', r.get('ab_test'))
else:
    print('Chưa có training_report.json')
PY
```

## Lưu ý về EOS

EOS là token kết thúc phần speech. Train vẫn được phép tiếp tục khi một sample có vấn đề; pipeline audit chỉ loại sample không hợp lệ hoặc vượt context. Khi inference, `test_merged_model.py` không chờ EOS vô hạn mà giới hạn số token để tránh WAV runaway.
