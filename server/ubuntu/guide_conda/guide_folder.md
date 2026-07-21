# guide_folder.md

## Cau truc `media_tech`

### Windows

```text
D:\hustmedia\python\llms\media_tech
```

### Ubuntu

```text
/root/media_tech
```

## Thu muc chinh

```text
media_tech/
  ai/
  backend/
  fontend/
  server/
```

## Cac path quan trong

### OpenClaw backend

```text
Windows: D:\hustmedia\python\llms\media_tech\backend\openclaw\config.json
Ubuntu:   /root/media_tech/backend/openclaw/config.json
```

### Ubuntu launcher

```text
Windows: D:\hustmedia\python\llms\media_tech\server\run\ubuntu_run.py
Ubuntu:   /root/media_tech/server/run/ubuntu_run.py
```

### Ubuntu trainer

```text
Windows: D:\hustmedia\python\llms\media_tech\server\run\ubuntu_train.py
Ubuntu:   /root/media_tech/server/run/ubuntu_train.py
```

### Qwen 4B server

```text
Windows: D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_4B_vn\server\main.py
Ubuntu:   /root/media_tech/ai/qwen/qwen3.5_4B_vn/server/main.py
```

### Qwen 4B train entry

```text
Windows: D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_4B_vn\train\fine_tuning\LoRA_main.py
Ubuntu:   /root/media_tech/ai/qwen/qwen3.5_4B_vn/train/fine_tuning/LoRA_main.py
```

### Qwen 4B datasheet

```text
Windows: D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_4B_vn\train\datasheet
Ubuntu:   /root/media_tech/ai/qwen/qwen3.5_4B_vn/train/datasheet
```

### Qwen 2B server

```text
Windows: D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\server\main.py
Ubuntu:   /root/media_tech/ai/qwen/qwen3.5_2B_vn/server/main.py
```

### Qdrant guide

```text
Windows: D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\guide.md
Ubuntu:   /root/media_tech/ai/search/qdrant/data_1/guide.md
```

## Moi truong Ubuntu

```text
/root/miniconda3/envs/qwen
/root/miniconda3/etc/profile.d/conda.sh
/root/model/Qwen/Qwen3.5-4B
/root/model/Qwen/Qwen3.5-4B_vn_1
```

## Ghi chu

- Repo goc gio la `/root/media_tech`, khong con dung `/root/qwen3.5_4B_vn`.
- Cac script `ubuntu_run.py` va `ubuntu_train.py` da tro sang layout moi.
- Cac file guide cua Qwen chi la tai lieu rieng cho subproject, khong phai toan bo `media_tech`.
- Neu can doi them path model sang noi khac, nen lam qua env `QWEN_BASE_MODEL` va `QWEN_OUTPUT_DIR`.


