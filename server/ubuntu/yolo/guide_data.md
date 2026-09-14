# YOLO26 - dua dataset tu Windows sang Ubuntu

Model va dataset duoc dong goi trong package `media_tech_yolo`.
Sau khi clone repo, khong can SCP model hoac dataset nua.

## Tai package YOLO tu GitHub

Package dung chung cua project co ten `media_tech_yolo`. Package gom model
goc va dataset YOLO co Viet Nam, khong can `git clone` dataset:

~~~bash
PACKAGE_URL="https://github.com/dangtin306/media_tech_1/releases/download/media_tech_yolo/media_tech_yolo.zip"
mkdir -p /root/model/yolo_package
if command -v curl >/dev/null 2>&1; then
  curl -fL "$PACKAGE_URL" -o /tmp/media_tech_yolo.zip
else
  wget -O /tmp/media_tech_yolo.zip "$PACKAGE_URL"
fi
unzip -q -o /tmp/media_tech_yolo.zip -d /root/model/yolo_package
~~~

Neu Ubuntu chua co `unzip`, dung Python:

~~~bash
python3 - <<'PY'
import pathlib
import zipfile

archive = zipfile.ZipFile('/tmp/media_tech_yolo.zip')
root = pathlib.Path('/root/model/yolo_package')
for item in archive.infolist():
    relative = item.filename.replace(chr(92), '/')
    target = root / relative
    if item.is_dir():
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

## Dataset

Dataset co nhieu file nho nen nen truoc:

~~~powershell
$d="D:\hustmedia\python\llms\media_tech_ai\ai\yolo\test_1\datasets\vietnam_flag\Vietnam Flag.v3-v3.yolo26"
$z="$env:TEMP\vietnam_flag_dataset.zip"
Compress-Archive -Path "$d\train","$d\valid","$d\test" -DestinationPath $z -CompressionLevel Optimal -Force
scp -P <SSH_PORT> $z root@<UBUNTU_HOST>:/tmp/vietnam_flag_dataset.zip
~~~

Tren Ubuntu, dung Python de giai nen va doi dau phan cach Windows sang Linux:

~~~bash
mkdir -p /root/model/yolo/vietnam_flag
python3 - <<'PY'
import pathlib
import zipfile

archive = zipfile.ZipFile('/tmp/vietnam_flag_dataset.zip')
root = pathlib.Path('/root/model/yolo/vietnam_flag')
for item in archive.infolist():
    relative = item.filename.replace(chr(92), '/')
    target = root / relative
    if item.is_dir():
        target.mkdir(parents=True, exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(item))
PY
~~~

## YAML external

Copy mau YAML co san trong repo:

~~~bash
cp /root/media_tech_ai/server/ubuntu/yolo/data_external.yaml /root/model/yolo/vietnam_flag/data.yaml
~~~

Noi dung YAML dung duong dan Linux:

~~~yaml
path: /root/model/yolo/vietnam_flag
train: train/images
val: valid/images
test: test/images
names:
  0: covn
~~~

Kiem tra truoc khi train:

~~~bash
find /root/model/yolo/vietnam_flag/train/images -type f | wc -l
find /root/model/yolo/vietnam_flag/valid/images -type f | wc -l
test -f /root/model/yolo/vietnam_flag/data.yaml
test -f /root/model/yolo_package/media_tech_yolo/model/yolo26n.pt
~~~
