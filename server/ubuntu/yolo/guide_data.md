# YOLO26 - dua dataset tu Windows sang Ubuntu

Dataset duoc dong goi trong Release `media_tech_yolo`.
Sau khi clone repo, dataset duoc giai nen thang vao thu muc `test_1/datasets`.

## Tai package YOLO tu GitHub

Package dung chung cua project co ten `media_tech_yolo`. Package gom toan bo
dataset YOLO, khong chua model va khong can `scp` dataset:

~~~bash
PACKAGE_URL="https://github.com/dangtin306/media_tech_1/releases/download/media_tech_yolo/media_tech_yolo.zip"
DATASETS_DIR=/root/media_tech_ai/ai/images/yolo/test_1/datasets
mkdir -p "$DATASETS_DIR"
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
root = pathlib.Path('/root/media_tech_ai/ai/images/yolo/test_1/datasets')
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

Dat bien moi truong toi dataset da giai nen. Model duoc quan ly rieng:

~~~bash
export YOLO_MODEL=/root/model/yolo26n.pt
export YOLO_DATA=/root/media_tech_ai/ai/images/yolo/test_1/datasets/vietnam_flag/data.yaml
~~~

Khi package duoc cap nhat, chi can tai lai cung URL va ghi de file cu.

## Cap nhat package va Release tren Windows

Git chi day code nhe. Dataset lon phai dong goi thanh asset cua
GitHub Release `media_tech_yolo`; khong commit truc tiep vao repo.

Package phai co dung cau truc:

~~~text
vietnam_flag/
├── train/
├── valid/
├── test/
└── data.yaml
cobasoc_1/
├── train/
├── valid/
├── test/
└── data.yaml
~~~

Moi dataset phai co `data.yaml`; file se tu gom toan bo dataset co trong
thu muc `datasets`. Khong nen tu copy hoac tu nen bang tay.

~~~powershell
cd D:\hustmedia\python\llms\media_tech_ai
python git_auto\github\up_to_github.py
~~~

Script tu doc token tai `git_auto/github/config.json` (truong
`github_token_env`). Neu co bien moi truong `GITHUB_TOKEN`, bien moi truong
duoc uu tien. File `config.json` la file bi mat local va khong duoc commit.
Fine-grained PAT phai duoc cap quyen vao repository `dangtin306/media_tech_1`
voi `Contents: Read and write`; thieu quyen nay se bi GitHub tra ve `403` khi
xoa hoac upload Release asset.

`up_to_github.py` tu dong tao ZIP, bo qua file `.py`, `.zip`,
`__pycache__`, xoa asset cu va upload asset moi vao Release
`media_tech_yolo`, sau do commit/push code len repo.

Script tao file ZIP tai:

~~~text
D:\hustmedia\python\llms\media_tech_ai\ai\images\yolo\test_1\datasets\media_tech_yolo.zip
~~~

ZIP co truc tiep cac thu muc `vietnam_flag/` va `cobasoc_1/`; khong co model.

`up_to_github.py` tu dong doc token local, cap nhat repo va Release; khong can
thao tac truc tiep tren giao dien GitHub. Khong dua `config.json` len GitHub.
Sau khi chay `up_to_github.py`, Ubuntu tai lai package bang cung URL o dau guide.
Khong dung `scp` de truyen model/dataset va khong commit `runs/`, model
hoac dataset lon vao Git.

## Ubuntu sau khi publish

Sau khi Windows chay xong `up_to_github.py`, Ubuntu tai ca code va package:

~~~bash
PACKAGE_URL="https://github.com/dangtin306/media_tech_1/releases/download/media_tech_yolo/media_tech_yolo.zip"
DATASETS_DIR=/root/media_tech_ai/ai/images/yolo/test_1/datasets
rm -rf "$DATASETS_DIR/vietnam_flag" "$DATASETS_DIR/cobasoc_1"
mkdir -p "$DATASETS_DIR"
wget -O /tmp/media_tech_yolo.zip "$PACKAGE_URL"
python3 - <<'PY'
import pathlib
import zipfile

archive = zipfile.ZipFile('/tmp/media_tech_yolo.zip')
root = pathlib.Path('/root/media_tech_ai/ai/images/yolo/test_1/datasets')
for item in archive.infolist():
    relative = item.filename.replace(chr(92), '/')
    target = root / relative
    if item.is_dir() or relative.endswith('/'):
        target.mkdir(parents=True, exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(item))
print('Datasets da cap nhat:', root)
PY
~~~

`git pull` lay code; doan tai ZIP lay toan bo dataset tu Release. Model duoc
quan ly rieng qua `YOLO_MODEL` theo guide_run.md.
