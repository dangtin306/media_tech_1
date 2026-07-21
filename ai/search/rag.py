import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import chromadb
import torch
from importlib import util as importlib_util
from pathlib import Path
from transformers import AutoModel, AutoTokenizer, BitsAndBytesConfig


QWEN_EMBED_MODEL_PATH = os.environ.get("QWEN_RAG_EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B")
IBM_EMBED_MODEL_PATH = os.environ.get(
    "QWEN_RAG_IBM_EMBED_MODEL",
    "ibm-granite/granite-embedding-311m-multilingual-r2",
)
EMBED_DEVICE = os.environ.get("QWEN_RAG_EMBED_DEVICE", "").strip().lower()
EMBED_USE_4BIT = os.environ.get("QWEN_RAG_USE_4BIT", "1").strip().lower() not in {"0", "false", "no", "off"}
EMBED_BATCH_SIZE = max(
    1,
    int(os.environ.get("QWEN_RAG_BATCH_SIZE", "8" if not torch.cuda.is_available() else "16")),
)
PERSIST_DIR = os.environ.get(
    "QWEN_RAG_PERSIST_DIR",
    os.path.join(os.path.dirname(__file__), "rag_chroma"),
)
QWEN_COLLECTION_NAME = os.environ.get("QWEN_RAG_COLLECTION", "qwen35_vi_rag")
IBM_COLLECTION_NAME = os.environ.get(
    "QWEN_RAG_IBM_COLLECTION",
    "qwen35_vi_rag_ibm_granite_311m_multilingual_r2",
)
TOP_K_DEFAULT = 4

if os.name == "nt":
    IBM_MODEL_CACHE_DIR = os.environ.get("QWEN_RAG_IBM_CACHE_DIR", r"D:\huggingface\hub")
else:
    IBM_MODEL_CACHE_DIR = os.environ.get("QWEN_RAG_IBM_CACHE_DIR", "/root/model/ibm")


def _resolve_corpus_path() -> str:
    env_path = os.environ.get("QWEN_RAG_CORPUS", "").strip()
    if env_path:
        return os.path.abspath(env_path)

    base_dir = os.path.dirname(__file__)
    candidates = [
        os.path.abspath(os.path.join(base_dir, "..", "datasheet", "rag_media_tech.jsonl")),
        os.path.abspath(os.path.join(base_dir, "..", "train", "datasheet", "rag_media_tech.jsonl")),
        r"D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_4B_vn\train\datasheet\rag_media_tech.jsonl",
        "/root/media_tech/ai/qwen/qwen3.5_4B_vn/train/datasheet/rag_media_tech.jsonl",
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return candidates[0]


CORPUS_PATH = _resolve_corpus_path()
CORPUS_STATE_FILE = "corpus_state.json"


def _resolve_dtype() -> torch.dtype:
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


def _resolve_embed_device() -> torch.device:
    if EMBED_DEVICE == "cpu":
        return torch.device("cpu")
    if EMBED_DEVICE == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _load_corpus(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for line_no, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no} in {path}: {exc}") from exc
            text = obj.get("text")
            if not isinstance(text, str) or not text.strip():
                text = obj.get("document")
            if not isinstance(text, str) or not text.strip():
                text = obj.get("content")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"Line {line_no} must contain non-empty string field 'text', 'document', or 'content'.")
            rows.append(
                {
                    "id": str(obj.get("id", f"row-{line_no}")),
                    "text": text.strip(),
                    "metadata": obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {},
                }
            )
    if not rows:
        raise ValueError(f"No usable rows found in {path}")
    return rows


def _corpus_state(path: str) -> Dict[str, Any]:
    stat = os.stat(path)
    return {
        "path": os.path.abspath(path),
        "mtime": stat.st_mtime,
        "size": stat.st_size,
    }


def _read_corpus_state(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
            return obj if isinstance(obj, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def _mean_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).type_as(last_hidden_state)
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


def _normalize_model_name(model_name: str) -> str:
    return model_name.strip().lower() if isinstance(model_name, str) else ""


def _use_ibm_rag_model(model_name: str) -> bool:
    normalized = _normalize_model_name(model_name)
    return normalized in {
        "qwen3.5-4b-v4",
        "qwen-3.5-4b-v4",
        "qwen-3.5-v4",
        "qwen-token/qwen-3.5-v4",
    }


class QwenEmbedder:
    def __init__(self, model_name: str = QWEN_EMBED_MODEL_PATH):
        self.model_name = model_name
        self.device = _resolve_embed_device()
        model_dtype = torch.float32 if self.device.type == "cpu" else _resolve_dtype()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, use_fast=True)
        load_kwargs = {
            "trust_remote_code": True,
            "dtype": model_dtype,
            "low_cpu_mem_usage": True,
        }
        if self.device.type == "cuda":
            if EMBED_USE_4BIT:
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=model_dtype,
                )
            load_kwargs["device_map"] = "auto"
        try:
            self.model = AutoModel.from_pretrained(model_name, **load_kwargs)
        except Exception as exc:
            if self.device.type != "cuda" or not EMBED_USE_4BIT:
                raise
            fallback_kwargs = {
                "trust_remote_code": True,
                "dtype": model_dtype,
                "low_cpu_mem_usage": True,
                "device_map": "auto",
            }
            self.model = AutoModel.from_pretrained(model_name, **fallback_kwargs)
        if self.device.type == "cpu":
            self.model.to(self.device)
        self.model.eval()

    @torch.inference_mode()
    def encode(self, texts: List[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        batch_size = max(1, EMBED_BATCH_SIZE)
        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start : start + batch_size]
            encoded = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512,
            ).to(self.device)
            outputs = self.model(**encoded)
            pooled = _mean_pool(outputs.last_hidden_state, encoded["attention_mask"])
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            embeddings.extend(pooled.detach().cpu().float().tolist())
        return embeddings


class GraniteEmbedder:
    def __init__(self, model_name: str = IBM_EMBED_MODEL_PATH):
        self.model_name = model_name
        self.device = _resolve_embed_device()
        self.model_cache_dir = IBM_MODEL_CACHE_DIR

    def _embed_with_sentence_transformers(self, texts: List[str]) -> torch.Tensor:
        from sentence_transformers import SentenceTransformer

        os.makedirs(self.model_cache_dir, exist_ok=True)
        model = SentenceTransformer(self.model_name, device=str(self.device), cache_folder=str(self.model_cache_dir))
        return model.encode(
            texts,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def _embed_with_transformers(self, texts: List[str]) -> torch.Tensor:
        model_dtype = torch.float32 if self.device.type == "cpu" else _resolve_dtype()
        os.makedirs(self.model_cache_dir, exist_ok=True)
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=True,
            use_fast=True,
            cache_dir=str(self.model_cache_dir),
        )
        model = AutoModel.from_pretrained(
            self.model_name,
            trust_remote_code=True,
            cache_dir=str(self.model_cache_dir),
            dtype=model_dtype,
            low_cpu_mem_usage=True,
        )
        model.eval()
        if self.device.type == "cpu":
            model.to(self.device)

        with torch.inference_mode():
            encoded = tokenizer(
                texts,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512,
            ).to(self.device)
            outputs = model(**encoded)
            hidden = outputs.last_hidden_state
            pooled = hidden[:, 0, :]
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=-1)
            return pooled

    def encode(self, texts: List[str]) -> List[List[float]]:
        try:
            embeddings = self._embed_with_sentence_transformers(texts)
        except Exception as st_exc:
            print(f"[warn] sentence-transformers failed, fallback to transformers: {st_exc}")
            embeddings = self._embed_with_transformers(texts)

        if isinstance(embeddings, torch.Tensor):
            return embeddings.detach().cpu().float().tolist()
        return embeddings


@dataclass
class RetrievalResult:
    query: str
    contexts: List[Dict[str, Any]]

    @property
    def combined_context(self) -> str:
        if not self.contexts:
            return ""
        parts: List[str] = []
        for idx, item in enumerate(self.contexts, start=1):
            text = item.get("text", "").strip()
            if text:
                parts.append(f"[{idx}] {text}")
        return "\n".join(parts)


class RagIndex:
    def __init__(
        self,
        corpus_path: str = CORPUS_PATH,
        persist_dir: str = PERSIST_DIR,
        collection_name: str = QWEN_COLLECTION_NAME,
        embedder: Any | None = None,
    ):
        self.corpus_path = corpus_path
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedder = embedder or QwenEmbedder()
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
        self.state_path = os.path.join(self.persist_dir, f"{collection_name}_{CORPUS_STATE_FILE}")
        self._ensure_index()

    def _ensure_index(self) -> None:
        corpus_state = _corpus_state(self.corpus_path)
        stored_state = _read_corpus_state(self.state_path)

        existing = self.collection.count()
        if existing > 0 and stored_state == corpus_state:
            return

        if existing > 0 and stored_state != corpus_state:
            try:
                self.client.delete_collection(name=self.collection_name)
            except Exception:
                pass
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

        rows = _load_corpus(self.corpus_path)
        texts = [row["text"] for row in rows]
        embeddings = self.embedder.encode(texts)
        self.collection.add(
            ids=[row["id"] for row in rows],
            documents=texts,
            metadatas=[row["metadata"] for row in rows],
            embeddings=embeddings,
        )
        os.makedirs(self.persist_dir, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(corpus_state, f, ensure_ascii=False)

    def retrieve(self, query: str, top_k: int = TOP_K_DEFAULT) -> RetrievalResult:
        query_embedding = self.embedder.encode([query])[0]
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        contexts: List[Dict[str, Any]] = []
        for idx in range(len(result["ids"][0])):
            contexts.append(
                {
                    "id": result["ids"][0][idx],
                    "text": result["documents"][0][idx],
                    "metadata": result["metadatas"][0][idx],
                    "distance": result["distances"][0][idx],
                }
            )
        return RetrievalResult(query=query, contexts=contexts)


_RAG_INDEXES: Dict[str, RagIndex] = {}
_IBM_SEARCH_MODULE = None


def _resolve_rag_profile(model_name: str) -> Dict[str, Any]:
    if _use_ibm_rag_model(model_name):
        return {
            "key": "ibm",
            "collection_name": IBM_COLLECTION_NAME,
            "embedder": GraniteEmbedder(),
        }
    return {
        "key": "qwen",
        "collection_name": QWEN_COLLECTION_NAME,
        "embedder": QwenEmbedder(),
    }


def get_rag_index(model_name: str = "") -> RagIndex:
    profile = _resolve_rag_profile(model_name)
    cache_key = profile["key"]
    global _RAG_INDEXES
    if cache_key not in _RAG_INDEXES:
        _RAG_INDEXES[cache_key] = RagIndex(
            corpus_path=CORPUS_PATH,
            persist_dir=PERSIST_DIR,
            collection_name=profile["collection_name"],
            embedder=profile["embedder"],
        )
    return _RAG_INDEXES[cache_key]


def _load_ibm_search_module():
    global _IBM_SEARCH_MODULE
    if _IBM_SEARCH_MODULE is None:
        module_path = Path(__file__).resolve().parent / "ibm" / "main.py"
        spec = importlib_util.spec_from_file_location("media_tech_ai_search_ibm_main", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load IBM search module: {module_path}")
        module = importlib_util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _IBM_SEARCH_MODULE = module
    return _IBM_SEARCH_MODULE


def retrieve_context(
    question: str,
    top_k: int = TOP_K_DEFAULT,
    model_name: str = "",
    messages: list[dict[str, str]] | None = None,
) -> RetrievalResult:
    if _use_ibm_rag_model(model_name):
        module = _load_ibm_search_module()
        return module.retrieve_context(
            question=question,
            top_k=top_k,
            model_name=model_name,
            messages=messages,
        )
    return get_rag_index(model_name=model_name).retrieve(question, top_k=top_k)

