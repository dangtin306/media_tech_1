import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import chromadb
import torch
from transformers import AutoModel, AutoTokenizer


EMBED_MODEL_PATH = os.environ.get("QWEN_RAG_EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B")
PERSIST_DIR = os.environ.get(
    "QWEN_RAG_PERSIST_DIR",
    os.path.join(os.path.dirname(__file__), "rag_chroma"),
)
COLLECTION_NAME = os.environ.get("QWEN_RAG_COLLECTION", "qwen35_vi_rag")
TOP_K_DEFAULT = 4


def _resolve_corpus_path() -> str:
    env_path = os.environ.get("QWEN_RAG_CORPUS", "").strip()
    if env_path:
        return os.path.abspath(env_path)

    base_dir = os.path.dirname(__file__)
    candidates = [
        os.path.abspath(os.path.join(base_dir, "..", "train_vn", "datasheet", "rag_corpus.jsonl")),
        r"D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_2B_vn\train_vn\datasheet\rag_corpus.jsonl",
        "/root/media_tech/ai/qwen/qwen3.5_2B_vn/train_vn/datasheet/rag_corpus.jsonl",
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return candidates[0]


CORPUS_PATH = _resolve_corpus_path()


def _resolve_dtype() -> torch.dtype:
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


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
                raise ValueError(f"Line {line_no} must contain non-empty string field 'text'.")
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


def _mean_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).type_as(last_hidden_state)
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


class QwenEmbedder:
    def __init__(self, model_name: str = EMBED_MODEL_PATH):
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, use_fast=True)
        self.model = AutoModel.from_pretrained(
            model_name,
            trust_remote_code=True,
            dtype=_resolve_dtype(),
            device_map="auto" if torch.cuda.is_available() else None,
        )
        self.model.eval()
        self.device = next(self.model.parameters()).device

    @torch.inference_mode()
    def encode(self, texts: List[str]) -> List[List[float]]:
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=512,
        ).to(self.device)
        outputs = self.model(**encoded)
        pooled = _mean_pool(outputs.last_hidden_state, encoded["attention_mask"])
        pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
        return pooled.detach().cpu().float().tolist()


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
        collection_name: str = COLLECTION_NAME,
    ):
        self.corpus_path = corpus_path
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedder = QwenEmbedder()
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
        self._ensure_index()

    def _ensure_index(self) -> None:
        existing = self.collection.count()
        if existing > 0:
            return
        rows = _load_corpus(self.corpus_path)
        texts = [row["text"] for row in rows]
        embeddings = self.embedder.encode(texts)
        self.collection.add(
            ids=[row["id"] for row in rows],
            documents=texts,
            metadatas=[row["metadata"] for row in rows],
            embeddings=embeddings,
        )

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


_RAG_INDEX: Optional[RagIndex] = None


def get_rag_index() -> RagIndex:
    global _RAG_INDEX
    if _RAG_INDEX is None:
        _RAG_INDEX = RagIndex()
    return _RAG_INDEX


def retrieve_context(question: str, top_k: int = TOP_K_DEFAULT) -> RetrievalResult:
    return get_rag_index().retrieve(question, top_k=top_k)
