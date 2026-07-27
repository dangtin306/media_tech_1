## Git Auto Guide

Script chính:

```powershell
python D:\hustmedia\python\llms\media_tech\backend\git_auto\auto\test.py --repo D:\hustmedia\python\llms\media_tech\backend\git_auto\project_test -m "auto push"
```

Nếu đang đứng ngay trong repo cần đẩy:

```powershell
python D:\hustmedia\python\llms\media_tech\backend\git_auto\auto\test.py
```

Lệnh này sẽ:

1. Tìm root repo Git.
2. Dọn cache phổ biến như `__pycache__`, `.pytest_cache`, `*.pyc`.
3. `git add .`
4. Commit nếu có thay đổi.
5. Push lên `origin`.

Gợi ý quy trình thủ công nếu cần:

```powershell
cd D:\hustmedia\python\llms\media_tech\backend\git_auto\project_test
git status
git add .
git commit -m "update"
git push
```
