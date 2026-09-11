# Train YOLO nhận diện cờ Việt Nam

Project dùng `yolo26n.pt` để train một class: `covn`.

Dataset Roboflow đã có sẵn tại:

```text
datasets/vietnam_flag/Vietnam Flag.v3-v3.yolo26/
```

Hiện dataset có 182 ảnh train và 30 ảnh validation.

## Chạy trên Windows

```powershell
cd D:\hustmedia\python\llms\media_tech_ai\ai\yolo\yolo26n
.\.venv\Scripts\Activate.ps1
cd ..\test_1
python train.py
```

Script tự chọn CUDA nếu PyTorch thấy GPU, nếu không sẽ dùng CPU:

```powershell
$env:YOLO_EPOCHS="5"       # test nhanh; train thật dùng 100
$env:YOLO_DEVICE="auto"    # auto, cpu hoặc cuda:0
$env:YOLO_BATCH="auto"     # GPU tự dò; CPU dùng batch 2
$env:YOLO_MODEL="D:\model\yolo26n.pt"
python train.py
```

## Chạy trên Ubuntu

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate yolo26
cd /root/media_tech_ai/ai/yolo/test_1
YOLO_EPOCHS=100 YOLO_DEVICE=auto YOLO_BATCH=auto python train.py
```

Nếu model nằm ngoài repo:

```bash
export YOLO_MODEL=/root/model/yolo/yolo26n.pt
export YOLO_DATA=/root/media_tech_ai/ai/yolo/test_1/data.yaml
python train.py
```

Kết quả nằm trong `runs/vietnam_flag/`. Không commit dataset, model hoặc thư mục `runs` lên Git.

## Dữ liệu tự thêm

Mỗi ảnh cần file label YOLO cùng tên. Tọa độ có dạng:

```text
0 x_center y_center width height
```

Các tọa độ phải được chuẩn hóa từ 0 đến 1. Nên bổ sung ảnh cờ thật, cờ nhỏ, cờ nghiêng, thiếu sáng và ảnh không có cờ.
