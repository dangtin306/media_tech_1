## Git Auto Guide

Script chĂ­nh:

```powershell
python D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\auto\test.py --repo D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\project_test -m "auto push"
```

Náº¿u Ä‘ang Ä‘á»©ng ngay trong repo cáº§n Ä‘áº©y:

```powershell
python D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\auto\test.py
```

Lá»‡nh nĂ y sáº½:

1. TĂ¬m root repo Git.
2. Dá»n cache phá»• biáº¿n nhÆ° `__pycache__`, `.pytest_cache`, `*.pyc`.
3. `git add .`
4. Commit náº¿u cĂ³ thay Ä‘á»•i.
5. Push lĂªn `origin`.

Gá»£i Ă½ quy trĂ¬nh thá»§ cĂ´ng náº¿u cáº§n:

```powershell
cd D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\project_test
git status
git add .
git commit -m "update"
git push
```

