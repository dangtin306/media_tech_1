# Train YOLO nhận diện cờ Việt Nam

Project này dùng `yolo26n.pt` để train một class duy nhất:

```text
0 = vietnam_flag
```

## Cấu trúc dataset

Đặt ảnh và nhãn vào:

```text
datasets/vietnam_flag/
├── images/train/
├── images/val/
├── labels/train/
└── labels/val/
```

Mỗi ảnh cần có một file `.txt` cùng tên trong thư mục `labels`. Ví dụ:

```text
images/train/flag_001.jpg
labels/train/flag_001.txt
```

Nội dung nhãn YOLO có dạng:

```text
0 x_center y_center width height
```

Các giá trị tọa độ phải được chuẩn hóa từ `0` đến `1`. Có thể dùng LabelImg, CVAT hoặc Roboflow để vẽ bounding box.

## Chạy train

Chạy bằng Python trong môi trường YOLO đã cài:

```powershell
cd D:\hustmedia\python\llms\media_tech_ai\ai\yolo\yolo26n
.\.venv\Scripts\Activate.ps1
cd ..\test_1
python train.py
```

Kết quả sẽ nằm trong:

```text
runs/vietnam_flag/
```

Chưa có ảnh/label thì chưa thể train. Nên chuẩn bị nhiều bối cảnh khác nhau: cờ thật, cờ nhỏ, cờ nghiêng, thiếu sáng và một ảnh không có cờ.
