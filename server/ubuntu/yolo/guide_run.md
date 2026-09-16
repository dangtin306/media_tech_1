# YOLO26 - train va inference

File train:

~~~text
/root/media_tech_ai/ai/images/yolo/test_1/train_1.py
/root/media_tech_ai/ai/images/yolo/test_1/train_2.py
~~~

## Train dataset co Viet Nam

~~~bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate images_1
cd /root/media_tech_ai/ai/images/yolo/test_1
~~~

Model va dataset duoc tai tu package chung:

~~~bash
export YOLO_MODEL=/root/model/images/yolo/main/yolo26n.pt
export YOLO_DATA=/root/media_tech_ai/ai/images/yolo/test_1/datasets/vietnam_flag/data.yaml
export YOLO_RUNS=/root/model/images/yolo
~~~

Test nhanh tren CPU/GPU:

~~~bash
YOLO_EPOCHS=5 YOLO_DEVICE=auto YOLO_BATCH=auto \
python /root/media_tech_ai/ai/images/yolo/test_1/train_1.py
~~~

Train day du:

~~~bash
YOLO_EPOCHS=100 YOLO_DEVICE=auto YOLO_BATCH=auto \
python /root/media_tech_ai/ai/images/yolo/test_1/train_1.py
~~~

## Train dataset cobasoc_1

~~~bash
export YOLO_DATA=/root/media_tech_ai/ai/images/yolo/test_1/datasets/cobasoc_1/data.yaml
YOLO_EPOCHS=5 YOLO_DEVICE=auto YOLO_BATCH=auto \
python /root/media_tech_ai/ai/images/yolo/test_1/train_2.py
~~~

Train day du:

~~~bash
YOLO_EPOCHS=100 YOLO_DEVICE=auto YOLO_BATCH=auto \
python /root/media_tech_ai/ai/images/yolo/test_1/train_2.py
~~~

Lenh khuyen nghi cho SSH session moi, khong can activate:

~~~bash
YOLO_EPOCHS=100 YOLO_DEVICE=auto YOLO_BATCH=auto \
/root/miniconda3/bin/conda run --no-capture-output -n images_1 \
python /root/media_tech_ai/ai/images/yolo/test_1/train_1.py
~~~

Neu muon dung model/dataset khac:

~~~bash
export YOLO_MODEL=/duong/dan/toi/model.pt
export YOLO_DATA=/duong/dan/toi/data.yaml
python /root/media_tech_ai/ai/images/yolo/test_1/train_1.py
~~~

Voi dataset nam ngoai repo, YOLO_DATA phai tro toi YAML co path tuyet doi:

~~~yaml
path: /root/model/images/yolo/vietnam_flag
train: train/images
val: valid/images
test: test/images
names:
  0: covn
~~~

Model output:

~~~text
/root/model/images/yolo/vietnam_flag/weights/best.pt
/root/model/images/yolo/vietnam_flag/weights/last.pt
~~~

## Inference

~~~bash
yolo predict \
  model=/root/model/images/yolo/vietnam_flag/weights/best.pt \
  source=/path/to/image.jpg \
  project=/root/model/images/yolo \
  name=predict
~~~

## Export cho C#

~~~bash
yolo export model=/root/model/images/yolo/vietnam_flag/weights/best.pt format=onnx
~~~

Sau do dung file .onnx voi Microsoft.ML.OnnxRuntime.
