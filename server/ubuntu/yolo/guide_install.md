# YOLO26 — cài đặt trên Ubuntu

## 1. Lấy code

```bash
cd /root/media_tech_ai
git pull --ff-only
```

## 2. Tạo thư mục model

```bash
mkdir -p /root/model/yolo/vietnam_flag
```

Đưa `yolo26n.pt` vào:

```text
/root/model/yolo/yolo26n.pt
```

Có thể dùng `scp` từ Windows:

```powershell
scp -P <SSH_PORT> `
  "D:\hustmedia\python\llms\media_tech_ai\ai\yolo\yolo26n\yolo26n.pt" `
  root@<UBUNTU_HOST>:/root/model/yolo/yolo26n.pt
```

Dataset YOLO đưa vào:

```text
/root/model/yolo/vietnam_flag/
```

Dataset cần có ảnh, label và `data.yaml` theo format Ultralytics.

## 3. Kiểm tra project

```bash
test -f /root/media_tech_ai/ai/yolo/test_1/train.py
test -f /root/model/yolo/yolo26n.pt
find /root/model/yolo/vietnam_flag -maxdepth 2 -type d
```

