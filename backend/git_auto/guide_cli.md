# Git Auto CLI Guide

ThÆ° má»¥c gá»‘c:

```powershell
D:\hustmedia\python\llms\media_tech_ai\backend\git_auto
```

## 1) Cháº¡y auto commit/push

Cháº¡y tá»« báº¥t ká»³ Ä‘Ă¢u:

```powershell
python D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\auto\test.py --repo D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\project_test -m "auto push"
```

Náº¿u Ä‘ang Ä‘á»©ng ngay trong repo cáº§n Ä‘áº©y:

```powershell
python D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\auto\test.py
```

## 2) Kiá»ƒm tra nhanh repo

Xem tráº¡ng thĂ¡i:

```powershell
git status
```

Xem branch hiá»‡n táº¡i:

```powershell
git branch --show-current
```

Xem remote:

```powershell
git remote -v
```

## 3) Luá»“ng thá»§ cĂ´ng

```powershell
cd D:\hustmedia\python\llms\media_tech_ai\backend\git_auto\project_test
git status
git add .
git commit -m "update"
git push
```

## 4) Gitea local

Web UI hiá»‡n Ä‘ang cháº¡y á»Ÿ:

```text
http://localhost:33443/
```

Trong cáº¥u hĂ¬nh Gitea, web service map tá»« container port `3000` ra host port `33443`.

