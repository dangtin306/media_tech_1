# Guide `llms/media_tech_ai/ai/search/qdrant/data_1`

TĂ i liá»‡u nĂ y mĂ´ táº£ bá»™ file Qdrant trong thÆ° má»¥c `D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1` vĂ  cĂ¡c lá»‡nh cháº¡y tÆ°Æ¡ng á»©ng.

## 1) Cáº¥u trĂºc file

```text
D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\
  qdrant_collection_config.json
  qdrant_documents_payload.jsonl
  qdrant_id_mapping.jsonl
  qdrant_points_intid_hash384.jsonl
  qdrant_query_hash384.py
  qdrant_upsert_hash384_fixed.py
  guide.md
```

## 2) Ă nghÄ©a tá»«ng file

- `qdrant_collection_config.json`
  - cáº¥u hĂ¬nh collection, hiá»‡n dĂ¹ng:
    - `collection_name`: `dulich_demo`
    - `vector_size`: `384`
    - `distance`: `Cosine`
- `qdrant_documents_payload.jsonl`
  - dá»¯ liá»‡u payload gá»‘c cá»§a document/store
- `qdrant_id_mapping.jsonl`
  - mapping giá»¯a `qdrant_int_id`, `point_uid`, `source_table`, `source_id`
- `qdrant_points_intid_hash384.jsonl`
  - danh sĂ¡ch point Ä‘Ă£ cĂ³ `id`, `vector`, `payload` Ä‘á»ƒ upsert vĂ o Qdrant
- `qdrant_upsert_hash384_fixed.py`
  - script táº¡o collection vĂ  upsert dá»¯ liá»‡u
- `qdrant_query_hash384.py`
  - script query/search Qdrant báº±ng cĂ¹ng logic vector hĂ³a

## 3) Chuáº©n cháº¡y local

YĂªu cáº§u:
- Qdrant Ä‘ang cháº¡y táº¡i `http://localhost:6333`
- Python Ä‘Ă£ cĂ i `scikit-learn`

CĂ i dependency náº¿u thiáº¿u:

```powershell
pip install scikit-learn
```

## 4) Lá»‡nh táº¡o collection vĂ  upsert

### 4.1 Upsert máº·c Ä‘á»‹nh

```powershell
python "D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\qdrant_upsert_hash384_fixed.py" --url "http://localhost:6333" --collection "dulich_demo" --file "D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\qdrant_points_intid_hash384.jsonl"
```

### 4.2 XĂ³a collection cÅ© rá»“i táº¡o láº¡i

```powershell
python "D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\qdrant_upsert_hash384_fixed.py" --url "http://localhost:6333" --collection "dulich_demo" --file "D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\qdrant_points_intid_hash384.jsonl" --recreate
```

### 4.3 Äá»•i batch size khi upsert

```powershell
python "D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\qdrant_upsert_hash384_fixed.py" --url "http://localhost:6333" --collection "dulich_demo" --file "D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\qdrant_points_intid_hash384.jsonl" --batch-size 256
```

## 5) Lá»‡nh query/search

### 5.1 Query cÆ¡ báº£n

```powershell
python "D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\qdrant_query_hash384.py" --url "http://localhost:6333" --collection "dulich_demo" --query "quĂ¡n trĂ  sá»¯a á»Ÿ háº£i phĂ²ng"
```

### 5.2 Query vá»›i sá»‘ káº¿t quáº£ tráº£ vá» tĂ¹y chá»‰nh

```powershell
python "D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\qdrant_query_hash384.py" --url "http://localhost:6333" --collection "dulich_demo" --query "spa á»Ÿ hĂ  ná»™i" --limit 10
```

## 6) Quy trĂ¬nh cháº¡y Ä‘áº§y Ä‘á»§

1. Kiá»ƒm tra Qdrant Ä‘ang cháº¡y táº¡i `http://localhost:6333`.
2. Cháº¡y script upsert Ä‘á»ƒ táº¡o collection vĂ  náº¡p dá»¯ liá»‡u.
3. Cháº¡y script query Ä‘á»ƒ kiá»ƒm tra káº¿t quáº£ tĂ¬m kiáº¿m.

VĂ­ dá»¥:

```powershell
python "D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\qdrant_upsert_hash384_fixed.py" --url "http://localhost:6333" --collection "dulich_demo" --file "D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\qdrant_points_intid_hash384.jsonl" --recreate
python "D:\hustmedia\python\llms\media_tech_ai\ai\search\qdrant\data_1\qdrant_query_hash384.py" --url "http://localhost:6333" --collection "dulich_demo" --query "hair salon á»Ÿ hĂ  ná»™i"
```

## 7) Ghi chĂº ká»¹ thuáº­t

- Vector Ä‘Æ°á»£c táº¡o báº±ng `HashingVectorizer` vá»›i:
  - `n_features=384`
  - `analyzer="char_wb"`
  - `ngram_range=(3,5)`
  - `alternate_sign=False`
  - `norm="l2"`
- ÄĂ¢y lĂ  cĂ¡ch test nhanh local.
- Náº¿u chuyá»ƒn sang production, nĂªn thay báº±ng embedding tháº­t nhÆ°:
  - `OpenAI text-embedding-3-small`
  - `Qwen Embedding`
  - `bge-m3`

## 8) Lá»—i thÆ°á»ng gáº·p

- `Connection refused`:
  - Qdrant chÆ°a cháº¡y hoáº·c sai `--url`
- `HTTP 404` khi search/upsert:
  - collection chÆ°a Ä‘Æ°á»£c táº¡o hoáº·c sai tĂªn collection
- `ModuleNotFoundError: sklearn`:
  - cháº¡y `pip install scikit-learn`


