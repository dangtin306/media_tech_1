# YOLO26 Ubuntu

Hướng dẫn đưa project YOLO26 từ Windows lên Ubuntu để train và chạy inference.

## Luồng chuẩn

```text
Windows sửa code
    -> git commit / git push
Ubuntu git pull
    -> kích hoạt Conda env YOLO
    -> đặt model và dataset ngoài Git
    -> train hoặc inference
```

Đọc theo thứ tự:

1. `guide_folder.md`
2. `guide_env.md`
3. `guide_install.md`
4. `guide_run.md`

Cho Ubuntu mới hoặc GPU khác nhau, dùng guide chính:

```text
guide_ubuntu_any_gpu.md
install_yolo_ubuntu.sh
```

Guide này có kiểm tra DNS, Conda TOS, Miniconda fallback bằng Python, CPU fallback và biến `TORCH_INDEX_URL` để chọn bản PyTorch CUDA phù hợp.
