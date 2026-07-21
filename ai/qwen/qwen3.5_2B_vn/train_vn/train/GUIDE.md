# Qwen3.5-2B LoRA Training Guide

This folder contains the LoRA training scripts for `Qwen/Qwen3.5-2B`.

## Paths

- Conda env: `D:\hustmedia\conda_envs\qwen`
- Base model: `D:\huggingface\hub\Qwen\Qwen3.5-2B`
- Ubuntu model: `/root/model/Qwen/Qwen3.5-2B`
- Default dataset: `D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\train_vn\datasheet\LoRA.json`
- Default output: `D:\huggingface\hub\Qwen\Qwen3.5-2B_vn_1`
- Ubuntu output: `/root/model/Qwen/Qwen3.5-2B_vn_1`

## 1. Activate env

```powershell
conda activate D:\hustmedia\conda_envs\qwen
```

Use `python`, not `py`.

## 2. Smoke test

Run one forward pass to verify the env, dataset, tokenizer, and model load:

```powershell
python D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\train_vn\train\LoRA_main.py --smoke_test
```

If this passes, the base model loads and the CUDA pipeline is alive.

## 3. Change dataset at runtime

You can switch the datasheet on each run with `--dataset` without touching code.

Example:

```powershell
python D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\train_vn\train\LoRA_main.py --dataset D:\path\to\new_dataset.json
```

If you pass only a file name, the script resolves it under:

```text
D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\train_vn\datasheet
```

So this is valid:

```powershell
python D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\train_vn\train\LoRA_main.py --use_4bit --dataset LoRA_3.json
```

That command uses:

```text
D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\train_vn\datasheet\LoRA_3.json
```

Change the output location too if needed:

```powershell
python D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\train_vn\train\LoRA_main.py --dataset D:\path\to\new_dataset.json --output_dir D:\path\to\output_dir
```

Supported formats:

- `.json`
- `.jsonl`

Each item must contain one of:

- `messages`
- `prompt` + `response`
- `question` + `answer`

## 4. Train

Safer default for RTX 2060 6GB:

```powershell
python D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\train_vn\train\LoRA_main.py --use_4bit --checkpointing
```

Current defaults in code:

- `max_seq_length = 1024`
- `train_batch_size = 2`
- `grad_accum = 1`
- `sample_ratio = 1.0`
- `cpu_offload = on`

## 5. Reduce OOM

If VRAM still overflows, reduce in this order:

```powershell
python D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\train_vn\train\LoRA_main.py --use_4bit --checkpointing --train_batch_size 1 --max_seq_length 512 --sample_ratio 0.3
```

Notes:

- `--use_4bit`: reduces base weight memory
- `--checkpointing`: reduces activation memory
- `--train_batch_size 1`: reduces peak VRAM
- `--max_seq_length 512`: reduces context memory
- `--sample_ratio 0.3`: test a smaller slice of the dataset

## 6. Outputs

The script writes:

- `D:\huggingface\hub\Qwen\Qwen3.5-2B_vn_1\adapter`
- `D:\huggingface\hub\Qwen\Qwen3.5-2B_vn_1\merged`
- `/root/model/Qwen/Qwen3.5-2B_vn_1/adapter`
- `/root/model/Qwen/Qwen3.5-2B_vn_1/merged`

Meaning:

- `adapter`: LoRA adapter for loading with the base model
- `merged`: base model merged with the adapter for inference

## 7. Common issues

### CUDA out of memory

This is usually not a Python bug. Lower:

1. `--train_batch_size`
2. `--max_seq_length`
3. `--sample_ratio`
4. enable `--use_4bit`
5. enable `--checkpointing`

### Wrong env

If the script says the env is wrong:

```powershell
conda activate D:\hustmedia\conda_envs\qwen
python -c "import sys; print(sys.prefix)"
```

Expected prefix:

```text
D:\hustmedia\conda_envs\qwen
```

### `py` runs the wrong interpreter

`py` can bypass the active conda env. Use:

```powershell
python ...
```

or call the env Python directly:

```powershell
D:\hustmedia\conda_envs\qwen\python.exe ...
```

## 8. Notes

- `device_map="auto"` and `cpu_offload` are there to reduce OOM risk.
- Offload helps when VRAM is tight, but it also makes CPU/RAM participate more.
- For a post-train check, use the inference script in `D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\server\main.py` or create a new inference file that points to `merged`.
