# VieNeu-TTS — cấu trúc thư mục chuẩn

## Thư mục project trên Ubuntu

```text
/root/media_tech_ai/vie_neu/
├── source_code/audio_model/       # package VieNeu và finetune chính thức
├── train/data/                    # dataset gốc, không sửa/xóa
├── train/process/v2/              # pipeline train và test
│   ├── train_nghean_v2_advanced.py
│   └── test_1/test_merged_model.py
├── train/output/                  # output sinh ra, không commit Git
├── server/                        # server/API nếu repo có
└── server_3.py                    # entrypoint server nếu repo có
```

## Dataset

Dataset gốc Nghệ An dùng theo đường dẫn tương đối:

```text
/root/media_tech_ai/vie_neu/train/data/dataset_nghean/
```

Không dùng đường dẫn Windows kiểu `D:\...` trong code. Code phải lấy root bằng `Path(__file__).resolve()` hoặc biến `REPO_DIR`.

## Output train

Pipeline advanced tạo riêng:

```text
train/output/nghean_v2_advanced/
├── dataset/
│   ├── metadata.csv
│   ├── metadata_cleaned.csv
│   ├── metadata_encoded.csv
│   ├── metadata_encoded_safe.csv
│   ├── train_encoded.csv
│   └── valid_encoded.csv
├── dataset_token_audit.csv
├── adapter/
├── merged_model/
├── ab_test/
└── training_report.json
```

Các file này là artifact lớn, không đưa lên GitHub. Chỉ commit code, guide và metadata nhỏ cần thiết.

## GitHub và đồng bộ

```bash
cd /root/media_tech_ai/vie_neu
git pull --ff-only
git log -1 --oneline
```

Luồng chuẩn:

```text
Windows sửa code → git commit/push → Ubuntu git pull → chạy
```

Không vừa `git pull` vừa `scp -r` đè cùng một repo vì sẽ tạo file untracked làm Git không thể fast-forward.

## Model và cache

Hugging Face cache thường nằm ở:

```text
/root/.cache/huggingface/
```

Không đặt token trong repo. Model gốc và cache có thể tải lại trên Ubuntu mới; output train nên giữ ngoài Git.
