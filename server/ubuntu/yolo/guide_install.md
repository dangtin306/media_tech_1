# YOLO26 - cai dat tren Ubuntu

## Lay code

~~~bash
git clone --depth 1 https://github.com/dangtin306/media_tech_1.git /root/media_tech_ai
cd /root/media_tech_ai
~~~

Neu repo da co:

~~~bash
cd /root/media_tech_ai
git pull --ff-only
~~~

Neu Could not resolve host, kiem tra DNS bang getent hosts github.com truoc.

## Cai tu dong

~~~bash
cd /root/media_tech_ai/server/ubuntu/yolo
bash install_yolo_ubuntu.sh
~~~

Script tao env /root/miniconda3/envs/yolo26, cai PyTorch theo CPU/GPU, cai Ultralytics tu GitHub chinh thuc va cai Polars runtime tuong thich voi CPU host cu.

## Layout khuyen nghi

~~~text
/root/media_tech_ai/                         # code
/root/model/yolo/yolo26n.pt                  # model goc
/root/model/yolo/vietnam_flag/               # dataset/output lon
~~~

Model ngoai repo:

~~~bash
export YOLO_MODEL=/root/model/yolo/yolo26n.pt
~~~

Dataset ngoai repo can co data.yaml, anh va label YOLO. Truyen duong dan:

~~~bash
export YOLO_DATA=/root/model/yolo/vietnam_flag/data.yaml
~~~

YAML cho dataset ngoai repo phai dung duong dan Linux, khong dung duong dan Windows:

~~~yaml
path: /root/model/yolo/vietnam_flag
train: train/images
val: valid/images
test: test/images
names:
  0: covn
~~~

Hoac dung mau co san:

~~~bash
cp /root/media_tech_ai/server/ubuntu/yolo/data_external.yaml /root/model/yolo/vietnam_flag/data.yaml
~~~

Khong commit model, dataset, API key hoac runs/ len Git.

Sau khi install, verify khong phu thuoc shell activation:

~~~bash
/root/miniconda3/bin/conda run --no-capture-output -n yolo26 python -c "import torch, ultralytics; print(torch.__version__, torch.cuda.is_available(), ultralytics.__version__)"
~~~
