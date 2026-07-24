from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import torch
import context as qwen_context

try:
    from . import key_words as keyword_module
except Exception:
    from importlib import util as importlib_util

    _KEY_WORDS_PATH = Path(__file__).resolve().with_name("key_words.py")
    _KEY_WORDS_SPEC = importlib_util.spec_from_file_location("media_tech_ai_search_ibm_key_words", _KEY_WORDS_PATH)
    if _KEY_WORDS_SPEC is None or _KEY_WORDS_SPEC.loader is None:
        raise RuntimeError(f"Cannot load keyword module: {_KEY_WORDS_PATH}")
    keyword_module = importlib_util.module_from_spec(_KEY_WORDS_SPEC)
    sys.modules[_KEY_WORDS_SPEC.name] = keyword_module
    _KEY_WORDS_SPEC.loader.exec_module(keyword_module)


V4_MODEL_NAMES = {
    "qwen3.5-4b-v4",
    "qwen-3.5-4b-v4",
    "qwen-3.5-v4",
    "qwen-token/qwen-3.5-v4",
}

SEARCH_LOG_DIR = Path(__file__).resolve().parents[1] / "log"
KEYWORD_LOG_FILE = SEARCH_LOG_DIR / "ibm_in_out.txt"
SEARCH_LOG_FILE = SEARCH_LOG_DIR / "ibm_search.txt"
IBM_EMBED_MODEL_ID = "ibm-granite/granite-embedding-311m-multilingual-r2"
IBM_MODEL_CACHE_DIR = Path(os.environ.get("QWEN_RAG_IBM_CACHE_DIR", r"D:\huggingface\hub" if os.name == "nt" else "/root/model/ibm"))
IBM_BATCH_SIZE = max(1, int(os.environ.get("QWEN_RAG_BATCH_SIZE", "8" if not torch.cuda.is_available() else "16")))
_IBM_INDEX_CACHE: Dict[str, "IBMSearchIndex"] = {}
_IBM_SENTENCE_MODEL: Any | None = None
_IBM_SENTENCE_MODEL_DEVICE: str | None = None
_IBM_TRANSFORMERS_TOKENIZER: Any | None = None
_IBM_TRANSFORMERS_MODEL: Any | None = None
_IBM_TRANSFORMERS_MODEL_DEVICE: str | None = None


def normalize_model_name(model_name: str) -> str:
    return model_name.strip().lower() if isinstance(model_name, str) else ""


def is_v4_model(model_name: str) -> bool:
    return normalize_model_name(model_name) in V4_MODEL_NAMES


def stringify_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                text = str(item).strip()
                if text:
                    parts.append(text)
        return " ".join(parts).strip()
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    return str(content).strip()


def normalize_message(item: Any) -> Dict[str, str] | None:
    if not isinstance(item, dict):
        return None

    role = item.get("role")
    content = stringify_content(item.get("content"))
    if not content:
        return None

    if not isinstance(role, str):
        role = "user"
    role = role.strip().lower()
    if role not in {"system", "user", "assistant", "tool"}:
        role = "user"
    return {"role": role, "content": content}


def collect_user_texts(messages: List[Dict[str, str]]) -> List[str]:
    texts: List[str] = []
    for message in messages:
        if message.get("role") != "user":
            continue
        text = stringify_content(message.get("content"))
        if text:
            texts.append(text)
    return texts


def build_keyword_prompt(user_texts: List[str]) -> str:
    if not user_texts:
        return ""

    last_user = user_texts[-1].strip()
    previous_users = [text.strip() for text in user_texts[:-1] if text.strip()]
    previous_block = "\n".join(f"- {text}" for text in previous_users) if previous_users else "- (không có)"

    return (
        "Bạn là bộ tách cụm từ tìm kiếm cho RAG.\n"
        "Chỉ ưu tiên câu user cuối cùng.\n\n"
        f"Câu user cuối cùng:\n{last_user}\n\n"
        f"Các câu user trước đó:\n{previous_block}\n\n"
        "Yêu cầu:\n"
        "- Chỉ trả về đúng 1 cụm từ tìm kiếm.\n"
        "- Không giải thích, không markdown, không code block, không thêm nhãn.\n"
        "- Ưu tiên cụm từ tự nhiên, gọn và sát nhu cầu tìm kiếm.\n"
    )


def normalize_search_query(text: str) -> str:
    query = stringify_content(text)
    if not query:
        return ""

    query = re.sub(r"```(?:json|text)?", "", query, flags=re.IGNORECASE)
    query = query.replace("```", "")
    query = query.strip().strip('"').strip("'")

    try:
        parsed = json.loads(query)
        if isinstance(parsed, dict):
            for key in ("query", "keywords", "keyword", "search_query"):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, list):
                    items = [stringify_content(item) for item in value]
                    items = [item for item in items if item]
                    if items:
                        return ", ".join(items)
    except Exception:
        pass

    lines = [line.strip() for line in query.splitlines() if line.strip()]
    if lines:
        query = lines[0]

    query = re.sub(r"^[\-\*\u2022]+\s*", "", query)
    query = re.sub(r"^\d+[\.\)]\s*", "", query)
    query = re.sub(r"^(keyword|keywords|query|search query)\s*[:：]\s*", "", query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip(" ,;")
    return query


def build_log_entry(
    messages: List[Dict[str, str]],
    model_name: str,
    prompt: str,
    raw_output: str,
    normalized: str,
    selected_query: str,
) -> Dict[str, Any]:
    return {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "model_name": model_name,
        "used_v4": is_v4_model(model_name),
        "context_input": {
            "messages": messages,
            "user_texts": collect_user_texts(messages),
            "prompt": prompt,
        },
        "context_output": {
            "raw_output": raw_output,
            "normalized": normalized,
            "selected_query": selected_query,
        },
    }


def build_search_log_entry(
    model_name: str,
    query: str,
    top_k: int,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "model_name": model_name,
        "search_input": {
            "query": query,
            "top_k": top_k,
        },
        "search_output": {
            "results": results,
        },
    }


def _format_text_value(value: Any) -> str:
    if value is None:
        return "<empty>"
    if isinstance(value, str):
        text = value.strip()
        return text if text else "<empty>"
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            parts.append(f"{key}: {_format_text_value(item)}")
        return "{" + ", ".join(parts) + "}"
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.append(_format_text_value(item))
        return "\n".join(parts) if parts else "<empty>"
    return str(value)


def _format_keyword_log(entry: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append(f"TIME: {entry.get('timestamp', '')}")
    lines.append(f"MODEL: {entry.get('model_name', '')}")
    lines.append(f"USED_V4: {entry.get('used_v4', False)}")
    lines.append("")
    lines.append("CONTEXT INPUT")
    context_input = entry.get("context_input", {})
    if isinstance(context_input, dict):
        messages = context_input.get("messages", [])
        user_texts = context_input.get("user_texts", [])
        prompt = context_input.get("prompt", "")
        lines.append("  messages:")
        for idx, message in enumerate(messages, start=1):
            lines.append(f"    [{idx}] role={message.get('role', '')}")
            lines.append(f"        content={_format_text_value(message.get('content'))}")
        lines.append("  user_texts:")
        for idx, text in enumerate(user_texts, start=1):
            lines.append(f"    [{idx}] {text}")
        lines.append("  prompt:")
        for line in _format_text_value(prompt).splitlines() or ["<empty>"]:
            lines.append(f"    {line}")
    lines.append("")
    lines.append("CONTEXT OUTPUT")
    context_output = entry.get("context_output", {})
    if isinstance(context_output, dict):
        lines.append("  raw_output:")
        for line in _format_text_value(context_output.get("raw_output", "")).splitlines() or ["<empty>"]:
            lines.append(f"    {line}")
        lines.append("  normalized:")
        for line in _format_text_value(context_output.get("normalized", "")).splitlines() or ["<empty>"]:
            lines.append(f"    {line}")
        lines.append("  selected_query:")
        for line in _format_text_value(context_output.get("selected_query", "")).splitlines() or ["<empty>"]:
            lines.append(f"    {line}")
    return "\n".join(lines) + "\n"


def _format_search_log(entry: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append(f"TIME: {entry.get('timestamp', '')}")
    lines.append(f"MODEL: {entry.get('model_name', '')}")
    lines.append("")
    lines.append("SEARCH INPUT")
    search_input = entry.get("search_input", {})
    if isinstance(search_input, dict):
        lines.append(f"  query: {search_input.get('query', '')}")
        lines.append(f"  top_k: {search_input.get('top_k', '')}")
    lines.append("")
    lines.append("SEARCH OUTPUT")
    search_output = entry.get("search_output", {})
    results = search_output.get("results", []) if isinstance(search_output, dict) else []
    for idx, item in enumerate(results, start=1):
        lines.append(f"  [{idx}] score={item.get('score', '')}")
        lines.append(f"      id: {item.get('id', '')}")
        lines.append("      text:")
        for line in _format_text_value(item.get("text", "")).splitlines() or ["<empty>"]:
            lines.append(f"        {line}")
        metadata = item.get("metadata", {})
        if metadata:
            lines.append("      metadata:")
            for line in _format_text_value(metadata).splitlines() or ["<empty>"]:
                lines.append(f"        {line}")
    if not results:
        lines.append("  <empty>")
    return "\n".join(lines) + "\n"


def write_keyword_log(entry: Dict[str, Any]) -> None:
    os.makedirs(SEARCH_LOG_DIR, exist_ok=True)

    if "context_input" in entry and "context_output" in entry:
        payload = _format_keyword_log(entry)
        with open(KEYWORD_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(payload)
        return
    elif "search_input" in entry and "search_output" in entry:
        with open(SEARCH_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(_format_search_log(entry))
        return
    else:
        payload = _format_text_value(entry) + "\n"
    with open(KEYWORD_LOG_FILE, "w", encoding="utf-8") as f:
        f.write(payload)


def _resolve_corpus_path() -> Path:
    env_value = os.environ.get("QWEN_RAG_CORPUS", "").strip()
    if env_value:
        return Path(env_value)

    base_dir = Path(__file__).resolve().parents[2]
    candidates = [
        base_dir / "datasheet" / "rag_media_tech.jsonl",
        base_dir / "qwen" / "qwen3.5_4B_vn" / "train" / "datasheet" / "rag_media_tech.jsonl",
        Path(r"D:\hustmedia\python\llms\media_tech\ai\datasheet\rag_media_tech.jsonl"),
        Path(r"D:\hustmedia\python\llms\media_tech\ai\qwen\qwen3.5_4B_vn\train\datasheet\rag_media_tech.jsonl"),
        Path("/root/media_tech/ai/datasheet/rag_media_tech.jsonl"),
        Path("/root/media_tech/ai/qwen/qwen3.5_4B_vn/train/datasheet/rag_media_tech.jsonl"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


CORPUS_PATH = _resolve_corpus_path()


def _resolve_device(value: str = "") -> str:
    normalized = value.strip().lower()
    if normalized in {"cpu", "cuda", "mps"}:
        return normalized
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _load_corpus(path: Path) -> List[dict[str, Any]]:
    rows: List[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            obj = json.loads(raw)
            text = obj.get("text")
            if not isinstance(text, str) or not text.strip():
                text = obj.get("document")
            if not isinstance(text, str) or not text.strip():
                text = obj.get("content")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"Line {line_no} in {path} missing non-empty text/document/content")
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


def _normalize_tensor(tensor: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.normalize(tensor, p=2, dim=-1)


def _corpus_state(path: Path) -> Dict[str, Any]:
    stat = path.stat()
    return {"path": str(path.resolve()), "mtime": stat.st_mtime, "size": stat.st_size}


def _embed_with_sentence_transformers(texts: List[str], device: str) -> torch.Tensor:
    from sentence_transformers import SentenceTransformer

    IBM_MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    global _IBM_SENTENCE_MODEL, _IBM_SENTENCE_MODEL_DEVICE
    if _IBM_SENTENCE_MODEL is None or _IBM_SENTENCE_MODEL_DEVICE != device:
        _IBM_SENTENCE_MODEL = SentenceTransformer(
            IBM_EMBED_MODEL_ID,
            device=device,
            cache_folder=str(IBM_MODEL_CACHE_DIR),
        )
        _IBM_SENTENCE_MODEL_DEVICE = device
    model = _IBM_SENTENCE_MODEL
    return model.encode(texts, convert_to_tensor=True, normalize_embeddings=True, show_progress_bar=False)


def _embed_with_transformers(texts: List[str], device: str) -> torch.Tensor:
    from transformers import AutoModel, AutoTokenizer

    IBM_MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    global _IBM_TRANSFORMERS_TOKENIZER, _IBM_TRANSFORMERS_MODEL, _IBM_TRANSFORMERS_MODEL_DEVICE
    if _IBM_TRANSFORMERS_TOKENIZER is None or _IBM_TRANSFORMERS_MODEL is None or _IBM_TRANSFORMERS_MODEL_DEVICE != device:
        _IBM_TRANSFORMERS_TOKENIZER = AutoTokenizer.from_pretrained(
            IBM_EMBED_MODEL_ID,
            trust_remote_code=True,
            use_fast=True,
            cache_dir=str(IBM_MODEL_CACHE_DIR),
        )
        _IBM_TRANSFORMERS_MODEL = AutoModel.from_pretrained(
            IBM_EMBED_MODEL_ID,
            trust_remote_code=True,
            cache_dir=str(IBM_MODEL_CACHE_DIR),
        )
        _IBM_TRANSFORMERS_MODEL.eval()
        _IBM_TRANSFORMERS_MODEL.to(device)
        _IBM_TRANSFORMERS_MODEL_DEVICE = device
    tokenizer = _IBM_TRANSFORMERS_TOKENIZER
    model = _IBM_TRANSFORMERS_MODEL

    with torch.inference_mode():
        encoded = tokenizer(
            texts,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=512,
        ).to(device)
        outputs = model(**encoded)
        hidden = outputs.last_hidden_state
        pooled = hidden[:, 0, :]
        pooled = _normalize_tensor(pooled)
        return pooled


def _embed(texts: List[str], device: str) -> torch.Tensor:
    try:
        return _embed_with_sentence_transformers(texts, device)
    except Exception as st_exc:
        print(f"[warn] sentence-transformers failed, fallback to transformers: {st_exc}")
        return _embed_with_transformers(texts, device)


def _cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    return float(torch.nn.functional.cosine_similarity(a.unsqueeze(0), b.unsqueeze(0)).item())


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


class IBMSearchIndex:
    def __init__(self, corpus_path: Path):
        self.corpus_path = corpus_path
        self.device = _resolve_device()
        self._state: Dict[str, Any] = {}
        self._rows: List[dict[str, Any]] = []
        self._embeddings: torch.Tensor | None = None
        self._query_embedding_cache: Dict[str, torch.Tensor] = {}
        self.refresh(force=True)

    def refresh(self, force: bool = False) -> None:
        current_state = _corpus_state(self.corpus_path)
        if not force and self._state == current_state and self._embeddings is not None and self._rows:
            return

        rows = _load_corpus(self.corpus_path)
        texts = [row["text"] for row in rows]
        embeddings = _embed(texts, self.device).detach().cpu().float()
        embeddings = _normalize_tensor(embeddings)
        self._rows = rows
        self._embeddings = embeddings
        self._state = current_state
        self._query_embedding_cache.clear()

    def _get_query_embedding(self, query: str) -> torch.Tensor:
        cache_key = query.strip()
        cached = self._query_embedding_cache.get(cache_key)
        if cached is not None:
            return cached

        query_embedding = _embed([query], self.device)[0].detach().cpu().float()
        query_embedding = _normalize_tensor(query_embedding.unsqueeze(0))[0]
        self._query_embedding_cache[cache_key] = query_embedding
        return query_embedding

    def retrieve(self, query: str, top_k: int = 4) -> RetrievalResult:
        self.refresh()
        if self._embeddings is None or not self._rows:
            return RetrievalResult(query=query, contexts=[])

        query_embedding = self._get_query_embedding(query)
        scores = torch.matmul(self._embeddings, query_embedding)
        limit = min(max(1, top_k), scores.shape[0])
        top_scores, top_indices = torch.topk(scores, k=limit, largest=True, sorted=True)
        contexts: List[Dict[str, Any]] = []
        for score, index in zip(top_scores.tolist(), top_indices.tolist()):
            row = self._rows[index]
            contexts.append(
                {
                    "id": row["id"],
                    "text": row["text"],
                    "metadata": row["metadata"],
                    "score": float(score),
                }
            )
        return RetrievalResult(query=query, contexts=contexts)


def _get_ibm_index() -> IBMSearchIndex:
    key = str(CORPUS_PATH.resolve())
    index = _IBM_INDEX_CACHE.get(key)
    if index is None:
        index = IBMSearchIndex(CORPUS_PATH)
        _IBM_INDEX_CACHE[key] = index
    return index


def _render_query_for_search(messages: List[Dict[str, str]], raw_query: str) -> str:
    user_texts = collect_user_texts(messages)
    if not user_texts:
        return normalize_search_query(raw_query)
    return normalize_search_query(raw_query) or user_texts[-1].strip()


def generate_rag_search_query(
    messages: List[Dict[str, str]],
    tokenizer: Any,
    model: Any,
    device: Any,
    model_name: str = "",
    max_new_tokens: int = 64,
) -> str:
    return keyword_module.generate_rag_search_query(
        messages=messages,
        tokenizer=tokenizer,
        model=model,
        device=device,
        model_name=model_name,
        max_new_tokens=max_new_tokens,
    )


def retrieve_context(
    question: str,
    top_k: int = 4,
    model_name: str = "",
    messages: List[Dict[str, str]] | None = None,
) -> RetrievalResult:
    del model_name
    normalized_question = normalize_search_query(question)
    query = normalized_question or question.strip()
    if not query:
        return RetrievalResult(query="", contexts=[])

    index = _get_ibm_index()
    result = index.retrieve(query, top_k=top_k)
    keyword_module.write_keyword_log(
        keyword_module.build_search_log_entry(
            model_name="qwen-token/qwen-3.5-v4",
            query=result.query,
            top_k=top_k,
            results=result.contexts,
            messages=messages,
        )
    )
    return result


def warmup_index() -> None:
    _get_ibm_index()
