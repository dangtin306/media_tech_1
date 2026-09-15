# YOLO26 - cau truc thu muc

## Code

Windows:

~~~text
D:\hustmedia\python\llms\media_tech_ai\ai\images\yolo\test_1
~~~

Ubuntu:

~~~text
/root/media_tech_ai/ai/images/yolo/test_1
~~~

## Model va du lieu lon tren Ubuntu

~~~text
/root/model/yolo26n.pt
/root/media_tech_ai/ai/images/yolo/test_1/datasets/vietnam_flag/
/root/media_tech_ai/ai/images/yolo/test_1/datasets/vietnam_flag/data.yaml
/root/model/yolo/vietnam_flag/best.pt
~~~

Code duoc pull tu Git. Dataset duoc tai tu Release; model duoc quan ly rieng.
Cache va ket qua train de ngoai Git.

## Thu tu lam tren may moi

1. Doc guide_ubuntu_any_gpu.md va chay install_yolo_ubuntu.sh.
2. Doc guide_data.md de dua dataset sang dung layout.
3. Doc guide_run.md de train/inference.

## Dong bo code

~~~bash
cd /root/media_tech_ai
git pull --ff-only
git log -1 --oneline
~~~

Khong dung `scp -r` de ghi de toan bo repo sau khi da clone.
