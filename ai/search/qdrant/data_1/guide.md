# Guide `llms/media_tech/ai/search/qdrant/data_1`

Tài liệu này mô tả bộ file Qdrant trong thư mục `D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1` và các lệnh chạy tương ứng.

## 1) Cấu trúc file

```text
D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\
  qdrant_collection_config.json
  qdrant_documents_payload.jsonl
  qdrant_id_mapping.jsonl
  qdrant_points_intid_hash384.jsonl
  qdrant_query_hash384.py
  qdrant_upsert_hash384_fixed.py
  guide.md
```

## 2) Ý nghĩa từng file

- `qdrant_collection_config.json`
  - cấu hình collection, hiện dùng:
    - `collection_name`: `dulich_demo`
    - `vector_size`: `384`
    - `distance`: `Cosine`
- `qdrant_documents_payload.jsonl`
  - dữ liệu payload gốc của document/store
- `qdrant_id_mapping.jsonl`
  - mapping giữa `qdrant_int_id`, `point_uid`, `source_table`, `source_id`
- `qdrant_points_intid_hash384.jsonl`
  - danh sách point đã có `id`, `vector`, `payload` để upsert vào Qdrant
- `qdrant_upsert_hash384_fixed.py`
  - script tạo collection và upsert dữ liệu
- `qdrant_query_hash384.py`
  - script query/search Qdrant bằng cùng logic vector hóa

## 3) Chuẩn chạy local

Yêu cầu:
- Qdrant đang chạy tại `http://localhost:6333`
- Python đã cài `scikit-learn`

Cài dependency nếu thiếu:

```powershell
pip install scikit-learn
```

## 4) Lệnh tạo collection và upsert

### 4.1 Upsert mặc định

```powershell
python "D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\qdrant_upsert_hash384_fixed.py" --url "http://localhost:6333" --collection "dulich_demo" --file "D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\qdrant_points_intid_hash384.jsonl"
```

### 4.2 Xóa collection cũ rồi tạo lại

```powershell
python "D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\qdrant_upsert_hash384_fixed.py" --url "http://localhost:6333" --collection "dulich_demo" --file "D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\qdrant_points_intid_hash384.jsonl" --recreate
```

### 4.3 Đổi batch size khi upsert

```powershell
python "D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\qdrant_upsert_hash384_fixed.py" --url "http://localhost:6333" --collection "dulich_demo" --file "D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\qdrant_points_intid_hash384.jsonl" --batch-size 256
```

## 5) Lệnh query/search

### 5.1 Query cơ bản

```powershell
python "D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\qdrant_query_hash384.py" --url "http://localhost:6333" --collection "dulich_demo" --query "quán trà sữa ở hải phòng"
```

### 5.2 Query với số kết quả trả về tùy chỉnh

```powershell
python "D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\qdrant_query_hash384.py" --url "http://localhost:6333" --collection "dulich_demo" --query "spa ở hà nội" --limit 10
```

## 6) Quy trình chạy đầy đủ

1. Kiểm tra Qdrant đang chạy tại `http://localhost:6333`.
2. Chạy script upsert để tạo collection và nạp dữ liệu.
3. Chạy script query để kiểm tra kết quả tìm kiếm.

Ví dụ:

```powershell
python "D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\qdrant_upsert_hash384_fixed.py" --url "http://localhost:6333" --collection "dulich_demo" --file "D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\qdrant_points_intid_hash384.jsonl" --recreate
python "D:\hustmedia\python\llms\media_tech\ai\search\qdrant\data_1\qdrant_query_hash384.py" --url "http://localhost:6333" --collection "dulich_demo" --query "hair salon ở hà nội"
```

## 7) Ghi chú kỹ thuật

- Vector được tạo bằng `HashingVectorizer` với:
  - `n_features=384`
  - `analyzer="char_wb"`
  - `ngram_range=(3,5)`
  - `alternate_sign=False`
  - `norm="l2"`
- Đây là cách test nhanh local.
- Nếu chuyển sang production, nên thay bằng embedding thật như:
  - `OpenAI text-embedding-3-small`
  - `Qwen Embedding`
  - `bge-m3`

## 8) Lỗi thường gặp

- `Connection refused`:
  - Qdrant chưa chạy hoặc sai `--url`
- `HTTP 404` khi search/upsert:
  - collection chưa được tạo hoặc sai tên collection
- `ModuleNotFoundError: sklearn`:
  - chạy `pip install scikit-learn`
