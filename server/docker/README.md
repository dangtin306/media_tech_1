# Qwen Docker image

This image packages the Qwen 3.5 4B Flask service and the LoRA/QLoRA training
environment. The same image can run the API on port `8005` or execute the
training entry point.

Docker replaces Conda inside this image. The application keeps the Conda
environment check for native Windows/Ubuntu runs, and accepts the explicit
Docker marker `QWEN_DOCKER=1`.

## Build

Build from the `media_tech` directory:

```powershell
cd D:\hustmedia\python\llms\media_tech
docker build -f server/docker/Dockerfile -t media-tech-qwen:latest .
```

The image build does not download CUDA. The GPU host must provide an NVIDIA
driver, Docker GPU runtime, and network access. CUDA Toolkit 12.4 and the
PyTorch `cu124` wheels are installed by the container bootstrap on first run.

## Cloud host startup

For the development-style deployment, keep code and model outside the image.
On the Ubuntu host, configure an SSH key (never put a password in this repo)
and run:

```bash
export SOURCE_SSH_HOST=vip.tecom.pro
export SOURCE_SSH_USER=<windows-ssh-user>
export SOURCE_SSH_KEY=/root/.ssh/id_ed25519
export SOURCE_SSH_PATH='D:/hustmedia/python/llms/media_tech'
export MODEL_SSH_PATH='D:/path/to/model'
docker run --rm --gpus all \
  -p 8005:8005 \
  -v /root/media_tech:/root/media_tech \
  -v /root/model:/root/model \
  -v /root/.ssh:/root/.ssh:ro \
  -e SOURCE_SSH_HOST -e SOURCE_SSH_USER -e SOURCE_SSH_KEY \
  -e SOURCE_SSH_PATH -e MODEL_SSH_PATH \
  media-tech-qwen:latest
```

The entrypoint checks `/root/media_tech` and `/root/model`, synchronizes missing
directories over SSH, compiles the Python source, then starts the service. The
Windows host must have OpenSSH Server enabled and the public key authorized for
the configured user. Existing directories are not overwritten automatically.

## Model layout

The model and adapter are runtime data, not image layers. Prepare this layout
on the host before starting the container:

```text
/root/model/Qwen/Qwen3.5-4B
/root/model/Qwen/Qwen3.5-4B_vn_1/adapter
```

If the base model is not present, download it before starting the service:

```bash
mkdir -p /root/model/Qwen
python - <<'PY'
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Qwen/Qwen3.5-4B",
    local_dir="/root/model/Qwen/Qwen3.5-4B",
)
PY
```

Check that both model shards and the index exist:

```bash
ls -lh /root/model/Qwen/Qwen3.5-4B/model.safetensors-*
ls -lh /root/model/Qwen/Qwen3.5-4B/model.safetensors.index.json
```

## GPU check

The host needs a working NVIDIA driver and Docker GPU runtime. Check the host
GPU before starting Qwen:

```bash
nvidia-smi
```

Run with the model stored on the host:

```powershell
docker run --rm --gpus all `
  -p 8005:8005 `
  -v "D:\huggingface\hub:/root/model" `
  media-tech-qwen:latest
```

The host must provide an NVIDIA driver and Docker GPU runtime. The container
loads the model during startup, so `/root/model/Qwen/Qwen3.5-4B` and the LoRA
adapter must exist before the container is started.

Check the service after startup:

```bash
curl http://localhost:8005/health
```

The first container start can take several minutes while CUDA 12.4 and the
PyTorch wheels are downloaded. Reuse the same container when possible; a
short-lived `--rm` container will repeat the bootstrap on every start.

The container keeps the Ubuntu-style paths used by the application:

```text
/root/media_tech
/root/model/Qwen/Qwen3.5-4B
/root/model/Qwen/Qwen3.5-4B_vn_1/adapter
```

The model is intentionally not copied into the image. It is mounted at runtime because it is large and changes independently from the application image.

Run the 4B training entry point inside the same image:

```bash
docker run --rm --gpus all \
  -v /root/model:/root/model \
  media-tech-qwen:latest \
  python /root/media_tech/ai/qwen/qwen3.5_4B_vn/train/fine_tuning/LoRA_main.py \
  --use_4bit --checkpointing --runtime_offload deepspeed
```

For a short smoke test:

```bash
docker run --rm --gpus all \
  -v /root/model:/root/model \
  media-tech-qwen:latest \
  python /root/media_tech/ai/qwen/qwen3.5_4B_vn/train/fine_tuning/LoRA_main.py \
  --smoke_test --use_4bit --checkpointing \
  --runtime_offload deepspeed --max_seq_length 128 --max_samples 1
```

On an Ubuntu GPU host, use the equivalent bind mount:

```bash
docker run --rm --gpus all \
  -p 8005:8005 \
  -v /root/model:/root/model \
  media-tech-qwen:latest
```
