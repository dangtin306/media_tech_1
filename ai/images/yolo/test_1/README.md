# Train YOLO nhận diện cờ Việt Nam

Project dùng `yolo26n.pt` để train một class: `covn`.

Dataset Roboflow được tải từ package `media_tech_yolo` tại:

```text
datasets/vietnam_flag/Vietnam Flag.v3-v3.yolo26/
```

Package cũng chứa model `yolo26n.pt`; code không còn giữ bản model trong repo.

## Chạy trên Windows

```powershell
conda activate images_1
cd D:\hustmedia\python\llms\media_tech_ai\ai\images\yolo\test_1
python train_1.py
```

## Test anh va luu ket qua

Dat anh can test vao `test.jpg` trong thu muc nay, sau do chay:

```powershell
python test_1.py
```

Anh da ve box se duoc luu tai:

```text
runs/test/
```

Neu dung anh/model o noi khac:

```powershell
$env:YOLO_SOURCE="D:\duong\dan\anh.jpg"
$env:YOLO_MODEL="D:\duong\dan\best.pt"
python test_1.py
```

Tren Ubuntu dung cung file:

```bash
YOLO_SOURCE=/duong/dan/anh.jpg \\
YOLO_MODEL=/root/media_tech_ai/ai/images/yolo/test_1/runs/vietnam_flag/weights/best.pt \\
python test_1.py
```

Co giao dien thi them `--show`; tren SSH khong co giao dien, mo file trong `runs/test/` de xem anh ket qua.

Script tự chọn CUDA nếu PyTorch thấy GPU, nếu không sẽ dùng CPU:

```powershell
$env:YOLO_EPOCHS="5"       # test nhanh; train thật dùng 100
$env:YOLO_DEVICE="auto"    # auto, cpu hoặc cuda:0
$env:YOLO_BATCH="auto"     # GPU tự dò; CPU dùng batch 2
$env:YOLO_MODEL="<đường-dẫn-đã-giải-nén>\model\yolo26n.pt"
$env:YOLO_DATA="<đường-dẫn-đã-giải-nén>\datasets\vietnam_flag\data.yaml"
python train_1.py
```

## Chạy trên Ubuntu

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate images_1
cd /root/media_tech_ai/ai/images/yolo/test_1
YOLO_EPOCHS=100 YOLO_DEVICE=auto YOLO_BATCH=auto python train_1.py
```

Sau khi tải và giải nén package trên Ubuntu:

```bash
export YOLO_MODEL=/root/model/yolo26n.pt
export YOLO_DATA=/root/media_tech_ai/ai/images/yolo/test_1/datasets/vietnam_flag/data.yaml
python train_1.py
```

Kết quả nằm trong `runs/vietnam_flag/`. Không commit dataset, model hoặc thư mục `runs` lên Git.

## Dữ liệu tự thêm

Mỗi ảnh cần file label YOLO cùng tên. Tọa độ có dạng:

```text
0 x_center y_center width height
```

Các tọa độ phải được chuẩn hóa từ 0 đến 1. Nên bổ sung ảnh cờ thật, cờ nhỏ, cờ nghiêng, thiếu sáng và ảnh không có cờ.
