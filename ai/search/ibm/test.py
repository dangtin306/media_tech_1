from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, List

import torch


MODEL_ID = "ibm-granite/granite-embedding-311m-multilingual-r2"
if os.name == "nt":
    MODEL_CACHE_DIR = Path(r"D:\huggingface\hub")
else:
    MODEL_CACHE_DIR = Path("/root/model/ibm")


def _resolve_corpus_path() -> Path:
    env_value = os.environ.get("QWEN_RAG_CORPUS", "").strip()
    if env_value:
        return Path(env_value)

    base_dir = Path(__file__).resolve().parents[2]
    candidates = [
        base_dir / "datasheet" / "rag_media_tech.jsonl",
        Path(r"D:\hustmedia\python\llms\media_tech\ai\datasheet\rag_media_tech.jsonl"),
        Path("/root/media_tech/ai/datasheet/rag_media_tech.jsonl"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


DEFAULT_CORPUS = _resolve_corpus_path()


def _resolve_device(value: str) -> str:
    value = value.strip().lower()
    if value in {"cpu", "cuda", "mps"}:
        return value
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _normalize(tensor: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.normalize(tensor, p=2, dim=-1)


def _embed_with_sentence_transformers(texts: List[str], device: str) -> torch.Tensor:
    from sentence_transformers import SentenceTransformer

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    model = SentenceTransformer(MODEL_ID, device=device, cache_folder=str(MODEL_CACHE_DIR))
    embeddings = model.encode(
        texts,
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings


def _embed_with_transformers(texts: List[str], device: str) -> torch.Tensor:
    from transformers import AutoModel, AutoTokenizer

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, use_fast=True, cache_dir=str(MODEL_CACHE_DIR))
    model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True, cache_dir=str(MODEL_CACHE_DIR))
    model.eval()
    model.to(device)

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
        pooled = _normalize(pooled)
        return pooled


def embed(texts: List[str], device: str) -> torch.Tensor:
    try:
        return _embed_with_sentence_transformers(texts, device)
    except Exception as st_exc:
        print(f"[warn] sentence-transformers failed, fallback to transformers: {st_exc}")
        return _embed_with_transformers(texts, device)


def cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    return float(torch.nn.functional.cosine_similarity(a.unsqueeze(0), b.unsqueeze(0)).item())


def load_corpus(path: Path) -> List[dict[str, Any]]:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick RAG smoke test for Granite Embedding 311M Multilingual R2")
    parser.add_argument("--device", default="", help="cpu, cuda, mps, or empty for auto")
    parser.add_argument(
        "--query",
        default="Cafe Mộc có trà đào không?",
        help="Query text to search in the corpus",
    )
    parser.add_argument(
        "--corpus",
        default=str(DEFAULT_CORPUS),
        help="Path to rag_media_tech.jsonl",
    )
    parser.add_argument("--top_k", type=int, default=5, help="Number of hits to print")
    parser.add_argument(
        "--dump-json",
        default="",
        help="Optional path to save query and scores as JSON",
    )
    args = parser.parse_args()

    device = _resolve_device(args.device)
    corpus_path = Path(args.corpus)
    if not corpus_path.is_file():
        raise FileNotFoundError(f"Corpus not found: {corpus_path}")

    rows = load_corpus(corpus_path)
    texts = [args.query] + [row["text"] for row in rows]

    print(f"model: {MODEL_ID}")
    print(f"cache_dir: {MODEL_CACHE_DIR}")
    print(f"device: {device}")
    print(f"corpus: {corpus_path}")
    print(f"corpus_size: {len(rows)}")

    embeddings = embed(texts, device=device)
    print(f"embedding_shape: {tuple(embeddings.shape)}")
    print(f"query: {args.query}")

    query_vec = embeddings[0]
    scored = []
    for idx, row in enumerate(rows, start=1):
        score = cosine(query_vec, embeddings[idx])
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)

    top_k = max(1, min(args.top_k, len(scored)))
    print("top_matches:")
    for rank, (score, row) in enumerate(scored[:top_k], start=1):
        print(f"[{rank}] score={score:.6f} id={row['id']}")
        print(row["text"])
        print("-" * 80)

    if args.dump_json:
        payload = {
            "model": MODEL_ID,
            "device": device,
            "query": args.query,
            "corpus": str(corpus_path),
            "top_k": top_k,
            "results": [
                {
                    "score": score,
                    "id": row["id"],
                    "text": row["text"],
                    "metadata": row["metadata"],
                }
                for score, row in scored[:top_k]
            ],
        }
        with open(args.dump_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"saved: {args.dump_json}")


if __name__ == "__main__":
    main()
