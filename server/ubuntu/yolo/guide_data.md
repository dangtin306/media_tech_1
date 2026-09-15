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

Moi dataset phai co anh va label cung ten, co `train`, `valid`, `test`, va
`data.yaml` dung duong dan. Tao ZIP tren PowerShell:

~~~powershell
$stage="D:\yolo_release\media_tech_yolo"
$zip="D:\yolo_release\media_tech_yolo.zip"
New-Item -ItemType Directory -Force "$stage\model","$stage\datasets" | Out-Null
Copy-Item "D:\duong-dan\yolo26n.pt" "$stage\model\yolo26n.pt" -Force
Copy-Item "D:\duong-dan\vietnam_flag" "$stage\datasets\vietnam_flag" -Recurse -Force
Copy-Item "D:\duong-dan\cobasoc_1" "$stage\datasets\cobasoc_1" -Recurse -Force
Compress-Archive -Path $stage -DestinationPath $zip -CompressionLevel Optimal -Force
~~~

Vao GitHub repo `dangtin306/media_tech_1` → Releases → release
`media_tech_yolo` → Edit release. Xoa asset ZIP cu, them file moi va giu
dung ten `media_tech_yolo.zip`. Code nhe thi day rieng bang Git:

~~~powershell
cd D:\hustmedia\python\llms\media_tech_ai
git add server/ubuntu/yolo ai/images/yolo/test_1
git commit -m "Update YOLO package guide"
git push origin main
~~~

Sau khi thay asset, Ubuntu tai lai package bang cung URL o dau guide.
Khong dung `scp` de truyen model/dataset va khong commit `runs/`, model
hoac dataset lon vao Git.

## Quy trinh moi lan cap nhat

Neu chi sua code/guide: Windows push repo, sau do Ubuntu pull repo:

~~~powershell
cd D:\hustmedia\python\llms\media_tech_ai
git add server/ubuntu/yolo ai/images/yolo/test_1
git commit -m "Update YOLO code or guide"
git push origin main
~~~

~~~bash
cd /root/media_tech_ai
git pull --ff-only origin main
~~~

Neu them dataset hoac doi model: tao lai `media_tech_yolo.zip`, xoa asset
cu trong Release `media_tech_yolo`, upload lai dung ten
`media_tech_yolo.zip`, roi Ubuntu tai lai package:

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

Phai thuc hien ca hai phan neu vua doi code vua doi dataset/model: `git pull`
de lay code va tai lai Release de lay file nang. `git pull` khong tu dong lay
asset cua Release.
