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

## Tai model rieng

Model khong nam trong Release dataset. Tai model YOLO26n chinh thuc vao
`/root/model/yolo26n.pt`:

~~~bash
mkdir -p /root/model
if command -v curl >/dev/null 2>&1; then
  curl -fL https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt \
    -o /root/model/yolo26n.pt
else
  wget -O /root/model/yolo26n.pt \
    https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt
fi
test -s /root/model/yolo26n.pt
~~~

Script tao env /root/miniconda3/envs/images_1, cai PyTorch theo CPU/GPU, cai Ultralytics tu GitHub chinh thuc va cai Polars runtime tuong thich voi CPU host cu.

## Layout khuyen nghi

~~~text
/root/media_tech_ai/                         # code
/root/model/yolo26n.pt                     # model rieng
/root/media_tech_ai/ai/images/yolo/test_1/datasets/ # dataset
~~~

Sau khi clone repo, tai dataset theo `guide_data.md` va dat `YOLO_MODEL`
toi file model rieng tren may.

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

Khong commit dataset, API key, model hoac `runs/` len Git.

Sau khi install, verify khong phu thuoc shell activation:

~~~bash
/root/miniconda3/bin/conda run --no-capture-output -n images_1 python -c "import torch, ultralytics; print(torch.__version__, torch.cuda.is_available(), ultralytics.__version__)"
~~~
