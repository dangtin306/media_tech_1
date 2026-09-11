# YOLO26 — cấu trúc thư mục

## Project

```text
Windows:
D:\hustmedia\python\llms\media_tech_ai\ai\yolo\test_1

Ubuntu:
/root/media_tech_ai/ai/yolo/test_1
```

Project gồm code train và cấu hình dataset. Không commit các output train lớn vào Git.

## Model và dataset trên Ubuntu

```text
/root/model/yolo/yolo26n.pt
/root/model/yolo/vietnam_flag/
/root/model/yolo/vietnam_flag/best.pt
```

Có thể giữ dataset trong project nếu nhỏ, nhưng dataset lớn nên đặt ngoài repo để pull code không làm nặng Git.

## Quy tắc đồng bộ

```bash
cd /root/media_tech_ai
git pull --ff-only
git log -1 --oneline
```

Windows sửa code rồi push GitHub; Ubuntu chỉ pull commit cần chạy. Không copy đè nguyên repo bằng `scp -r` sau khi đã clone.

