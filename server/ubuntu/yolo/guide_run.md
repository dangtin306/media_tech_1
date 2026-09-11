# YOLO26 — train và inference trên Ubuntu

## Train cờ Việt Nam

Kích hoạt env:

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate yolo26
cd /root/media_tech_ai/ai/yolo/test_1
```

Nếu `data.yaml` đang trỏ dataset trong project:

```bash
python train.py
```

`train.py` hiện tại của project đang tìm model ở thư mục sibling:
`/root/media_tech_ai/ai/yolo/yolo26n/yolo26n.pt`. Nếu model được giữ ngoài repo như layout chuẩn bên trên, cần đổi `MODEL_PATH` trong `train.py` thành `/root/model/yolo/yolo26n.pt` trước khi train.

Nếu dataset để ngoài `/root/model`, có thể sửa biến `path` trong `data.yaml` thành:

```yaml
path: /root/model/yolo/vietnam_flag
train: train/images
val: valid/images
names:
  0: vietnam_flag
```

Output nên lưu ngoài Git:

```text
/root/model/yolo/vietnam_flag/runs/
```

## Chạy model đã train

```bash
yolo predict \
  model=/root/model/yolo/vietnam_flag/best.pt \
  source=/root/media_tech_ai/ai/yolo/test_1/test.jpg \
  project=/root/model/yolo/vietnam_flag/runs \
  name=predict
```

## Chạy webcam/camera

```bash
yolo predict model=/root/model/yolo/vietnam_flag/best.pt source=0
```

## Export cho C#

```bash
yolo export \
  model=/root/model/yolo/vietnam_flag/best.pt \
  format=onnx
```

File `.onnx` sau đó dùng trong C# bằng `Microsoft.ML.OnnxRuntime`.
