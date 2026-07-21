# guide_run.md

## Kich hoat env

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate qwen
export CC=/usr/bin/gcc
export CXX=/usr/bin/g++
export QWEN_BASE_MODEL=/root/model/Qwen/Qwen3.5-4B
export QWEN_OUTPUT_DIR=/root/model/Qwen/Qwen3.5-4B_vn_1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export QWEN_CPU_MAX_MEMORY=48GiB
# export HF_TOKEN=hf_xxx
```

## Neu chay tren Windows

```powershell
conda activate qwen
$env:QWEN_BASE_MODEL='D:\huggingface\hub\Qwen\Qwen3.5-4B'
$env:QWEN_OUTPUT_DIR='D:\huggingface\hub\Qwen\Qwen3.5-4B_vn_1'
$env:PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True'
```

## Download model truoc khi test hoac train

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

## Kiem tra model da tai du

```bash
ls -lh /root/model/Qwen/Qwen3.5-4B/model.safetensors-* /root/model/Qwen/Qwen3.5-4B/model.safetensors.index.json
```

Phai thay du:

- `model.safetensors-00001-of-00002.safetensors`
- `model.safetensors-00002-of-00002.safetensors`
- `model.safetensors.index.json`

## Smoke test

```bash
python /root/media_tech/ai/qwen/qwen3.5_4B_vn/train/fine_tuning/LoRA_main.py --smoke_test
```

## Smoke test 4bit

```bash
python /root/media_tech/ai/qwen/qwen3.5_4B_vn/train/fine_tuning/LoRA_main.py \
  --smoke_test \
  --use_4bit \
  --checkpointing \
  --runtime_offload deepspeed \
  --train_batch_size 1 \
  --max_seq_length 128 \
  --max_samples 1
```

## Train co ban

```bash
python /root/media_tech/ai/qwen/qwen3.5_4B_vn/train/fine_tuning/LoRA_main.py
```

## Train co ban voi 4bit

```bash
python /root/media_tech/ai/qwen/qwen3.5_4B_vn/train/fine_tuning/LoRA_main.py \
  --use_4bit
```

## Windows note

Windows dung de chay server va test nhanh. Neu `--use_4bit` chay on dinh thi co the smoke test, nhung Ubuntu van la noi uu tien de train 4B da so truong hop.

## Train khuyen nghi

```bash
python /root/media_tech/ai/qwen/qwen3.5_4B_vn/train/fine_tuning/LoRA_main.py \
  --use_4bit \
  --checkpointing \
  --runtime_offload deepspeed \
  --train_batch_size 1 \
  --max_seq_length 512 \
  --empty_cache_steps 20
```

## Train an toan hon neu van OOM

```bash
python /root/media_tech/ai/qwen/qwen3.5_4B_vn/train/fine_tuning/LoRA_main.py \
  --use_4bit \
  --checkpointing \
  --runtime_offload deepspeed \
  --train_batch_size 1 \
  --max_seq_length 384 \
  --empty_cache_steps 10
```

## Train cuc ngan de test

```bash
python /root/media_tech/ai/qwen/qwen3.5_4B_vn/train/fine_tuning/LoRA_main.py \
  --use_4bit \
  --checkpointing \
  --runtime_offload deepspeed \
  --train_batch_size 1 \
  --max_seq_length 128 \
  --max_samples 1 \
  --epochs 1 \
  --empty_cache_steps 1
```

## Tuy chon hay dung

```bash
--dataset /duong/dan/file.json
--output_dir /duong/dan/output
--max_samples 10
--sample_ratio 0.1
--checkpointing
--runtime_offload none
--runtime_offload auto
--runtime_offload deepspeed
--empty_cache_steps 20
```

## Check khi dang train

```bash
nvidia-smi
free -h
ps -eo pid,pmem,rss,cmd --sort=-rss | head
```

## Neu train fail ngay luc khoi tao DeepSpeed

Kiem tra lai `libcurand`:

```bash
ls -l /root/miniconda3/envs/qwen/lib/libcurand.so*
```

Neu sai thi sua:

```bash
rm -f /root/miniconda3/envs/qwen/lib/libcurand.so
ln -s /root/miniconda3/envs/qwen/targets/x86_64-linux/lib/libcurand.so.10 /root/miniconda3/envs/qwen/lib/libcurand.so
```

## Ghi chu

- da co length-grouped batching
- da co activation offload sang CPU RAM
- da co merge adapter tren CPU
- da co DeepSpeed CPU offload
- khong offload ra disk
- `--runtime_offload auto` se tu chon theo runtime, nhung tren may VRAM it van nen uu tien `deepspeed`
- `--checkpointing` giam VRAM luc train, doi lai toc do cham hon
- neu download model va test chung mot script thi de tuong la bi treo; nen download xong roi moi test/train


