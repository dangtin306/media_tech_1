# YOLO26 - dua dataset tu Windows sang Ubuntu

Model va dataset duoc dong goi trong package `media_tech_yolo`.
Sau khi clone repo, khong can SCP model hoac dataset nua.

## Tai package YOLO tu GitHub

Package dung chung cua project co ten `media_tech_yolo`. Package gom model
goc va toan bo dataset YOLO, khong can `git clone` hay `scp` tung dataset:

~~~bash
PACKAGE_URL="https://github.com/dangtin306/media_tech_1/releases/download/media_tech_yolo/media_tech_yolo.zip"
mkdir -p /root/model/yolo_package
if command -v curl >/dev/null 2>&1; then
  curl -fL "$PACKAGE_URL" -o /tmp/media_tech_yolo.zip
elif command -v wget >/dev/null 2>&1; then
  wget -O /tmp/media_tech_yolo.zip "$PACKAGE_URL"
else
  python3 - <<'PY'
import urllib.request
urllib.request.urlretrieve(
    "https://github.com/dangtin306/media_tech_1/releases/download/media_tech_yolo/media_tech_yolo.zip",
    "/tmp/media_tech_yolo.zip",
)
PY
fi
python3 - <<'PY'
import pathlib
import zipfile

archive = zipfile.ZipFile('/tmp/media_tech_yolo.zip')
root = pathlib.Path('/root/model/yolo_package')
for item in archive.infolist():
    relative = item.filename.replace(chr(92), '/')
    target = root / relative
    if item.is_dir() or relative.endswith('/'):
        if target.exists() and target.is_file():
            target.unlink()
        target.mkdir(parents=True, exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(item))
PY
~~~

Dat bien moi truong de dung model va dataset trong package:

~~~bash
export YOLO_MODEL=/root/model/yolo_package/media_tech_yolo/model/yolo26n.pt
export YOLO_DATA=/root/model/yolo_package/media_tech_yolo/datasets/vietnam_flag/data.yaml
~~~

Khi package duoc cap nhat, chi can tai lai cung URL va ghi de file cu.

## Cap nhat package va Release tren Windows

Git chi day code nhe. Model va dataset lon phai dong goi thanh asset cua
GitHub Release `media_tech_yolo`; khong commit truc tiep vao repo.

Package phai co dung cau truc:

~~~text
media_tech_yolo/
├── model/
│   └── yolo26n.pt
└── datasets/
    ├── vietnam_flag/
    │   ├── train/
    │   ├── valid/
    │   ├── test/
    │   └── data.yaml
    └── cobasoc_1/
        ├── train/
        ├── valid/
        ├── test/
        └── data.yaml
~~~

Moi dataset phai co `data.yaml`; file se tu gom toan bo dataset co trong
thu muc `datasets`. Khong nen tu copy hoac tu nen bang tay.

~~~powershell
cd D:\hustmedia\python\llms\media_tech_ai
$env:GITHUB_TOKEN="<GITHUB_TOKEN>"
python git_auto\github\up_to_github.py
~~~

`up_to_github.py` tu dong tao ZIP, bo qua file `.py`, `.zip`,
`__pycache__`, xoa asset cu va upload asset moi vao Release
`media_tech_yolo`, sau do commit/push code len repo.

Script tao file ZIP tai:

~~~text
D:\hustmedia\python\llms\media_tech_ai\ai\images\yolo\test_1\datasets\media_tech_yolo.zip
~~~

ZIP co dang `media_tech_yolo/model/` va
`media_tech_yolo/datasets/<ten_dataset>/`.

Token chi dat trong terminal hien tai, khong commit vao Git:

~~~powershell
$env:GITHUB_TOKEN="<GITHUB_TOKEN>"
~~~

`up_to_github.py` tu dong cap nhat repo va Release; khong can thao tac
truc tiep tren giao dien GitHub.
Sau khi chay `up_to_github.py`, Ubuntu tai lai package bang cung URL o dau guide.
Khong dung `scp` de truyen model/dataset va khong commit `runs/`, model
hoac dataset lon vao Git.

## Ubuntu sau khi publish

Sau khi Windows chay xong `up_to_github.py`, Ubuntu tai ca code va package:

~~~bash
PACKAGE_URL="https://github.com/dangtin306/media_tech_1/releases/download/media_tech_yolo/media_tech_yolo.zip"
rm -rf /root/model/yolo_package/media_tech_yolo
mkdir -p /root/model/yolo_package
wget -O /tmp/media_tech_yolo.zip "$PACKAGE_URL"
python3 - <<'PY'
import pathlib
import zipfile

archive = zipfile.ZipFile('/tmp/media_tech_yolo.zip')
root = pathlib.Path('/root/model/yolo_package')
for item in archive.infolist():
    relative = item.filename.replace(chr(92), '/')
    target = root / relative
    if item.is_dir() or relative.endswith('/'):
        target.mkdir(parents=True, exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(item))
print('Package da cap nhat:', root / 'media_tech_yolo')
PY
~~~

`git pull` lay code; doan tai ZIP lay model va toan bo dataset tu Release.
