# -*- coding: utf-8 -*-
"""
Query thử Qdrant bằng cùng logic vector hash 384 đã dùng để tạo file.

Cài nếu thiếu:
  pip install scikit-learn

Chạy:
  python qdrant_query_hash384.py --url http://localhost:6333 --collection dulich_demo --query "quán trà sữa ở hải phòng"
"""
import argparse, json, urllib.request
from sklearn.feature_extraction.text import HashingVectorizer

def request_json(method, url, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}

def embed(text):
    hv = HashingVectorizer(
        n_features=384,
        analyzer="char_wb",
        ngram_range=(3,5),
        alternate_sign=False,
        norm="l2",
        lowercase=True
    )
    vec = hv.transform([text]).toarray()[0]
    return [round(float(v), 6) for v in vec]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:6333")
    ap.add_argument("--collection", default="dulich_demo")
    ap.add_argument("--query", required=True)
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    base = args.url.rstrip("/")
    body = {
        "vector": embed(args.query),
        "limit": args.limit,
        "with_payload": True
    }
    res = request_json("POST", f"{base}/collections/{args.collection}/points/search", body)
    for i, hit in enumerate(res.get("result", []), 1):
        p = hit.get("payload", {})
        print("="*80)
        print(f"#{i} score={hit.get('score')} id={hit.get('id')}")
        print("type:", p.get("type"))
        print("name/title:", p.get("name") or p.get("title") or p.get("menu_name"))
        print("store:", p.get("store_name"))
        print("address:", p.get("address") or p.get("store_address"))
        print("text:", p.get("text"))

if __name__ == "__main__":
    main()
