# YOLO26 - train va inference

## Train dataset co Viet Nam

~~~bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate yolo26
cd /root/media_tech_ai/ai/yolo/test_1
~~~

Test nhanh tren CPU/GPU:

~~~bash
YOLO_EPOCHS=5 YOLO_DEVICE=auto YOLO_BATCH=auto python train.py
~~~

Train day du:

~~~bash
YOLO_EPOCHS=100 YOLO_DEVICE=auto YOLO_BATCH=auto python train.py
~~~

Neu model o ngoai repo:

~~~bash
export YOLO_MODEL=/root/model/yolo/yolo26n.pt
export YOLO_DATA=/root/media_tech_ai/ai/yolo/test_1/data.yaml
python train.py
~~~

Model output:

~~~text
runs/vietnam_flag/weights/best.pt
runs/vietnam_flag/weights/last.pt
~~~

## Inference

~~~bash
yolo predict \
  model=runs/vietnam_flag/weights/best.pt \
  source=/path/to/image.jpg \
  project=runs \
  name=predict
~~~

## Export cho C#

~~~bash
yolo export model=runs/vietnam_flag/weights/best.pt format=onnx
~~~

Sau do dung file .onnx voi Microsoft.ML.OnnxRuntime.
