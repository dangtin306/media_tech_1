# YOLO26 - dua model va dataset tu Windows sang Ubuntu

Model va dataset khong dua len Git. Dung SCP sau khi da clone code.

## Model

Chay tren PowerShell Windows:

~~~powershell
scp -P <SSH_PORT> `
  "D:\hustmedia\python\llms\media_tech_ai\ai\yolo\yolo26n\yolo26n.pt" `
  root@<UBUNTU_HOST>:/root/model/yolo/yolo26n.pt
~~~

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
test -f /root/model/yolo/yolo26n.pt
~~~
