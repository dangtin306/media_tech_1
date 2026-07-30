# Git Auto CLI Guide

Thư mục gốc:

```powershell
D:\hustmedia\python\llms\media_tech_ai\backend\git_auto
```

## 1) Chạy auto commit/push

Chạy từ bất kỳ đâu:

```powershell
python D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\auto\test.py --repo D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\project_test -m "auto push"
```

Nếu đang đứng ngay trong repo cần đẩy:

```powershell
python D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\auto\test.py
```

## 2) Kiểm tra nhanh repo

Xem trạng thái:

```powershell
git status
```

Xem branch hiện tại:

```powershell
git branch --show-current
```

Xem remote:

```powershell
git remote -v
```

## 3) Luồng thủ công

```powershell
cd D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\project_test
git status
git add .
git commit -m "update"
git push
```

## 4) Gitea local

Web UI hiện đang chạy ở:

```text
http://localhost:33443/
```

Trong cấu hình Gitea, web service map từ container port `3000` ra host port `33443`.
