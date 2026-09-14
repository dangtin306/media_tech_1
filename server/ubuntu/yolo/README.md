# YOLO26 Ubuntu

Quy trình đưa project YOLO26 từ Windows lên Ubuntu để train và inference.

## Thứ tự đọc trên máy mới

1. `guide_ubuntu_any_gpu.md` - kiểm tra máy và cài môi trường.
2. `guide_folder.md` - layout code/model/dataset.
3. `guide_install.md` - clone code và cài tự động.
4. `guide_data.md` - tải package model/dataset hoặc truyền dataset riêng.
5. `guide_run.md` - train, inference và export ONNX.

## Quy trình chuẩn

~~~text
Windows sửa code
    -> git commit / git push
Ubuntu git pull
    -> cài hoặc dùng env yolo26
    -> model trong Git, dataset ở ngoài Git
    -> train hoặc inference
~~~

Installer đã xử lý DNS preflight, Conda TOS, Miniconda fallback, Ubuntu
minimal thiếu OpenCV libraries và CPU host cũ thiếu AVX.
