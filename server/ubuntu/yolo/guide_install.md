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

Script tao env /root/miniconda3/envs/yolo26, cai PyTorch theo CPU/GPU va cai Ultralytics tu GitHub chinh thuc.

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

Khong commit model, dataset, API key hoac runs/ len Git.
