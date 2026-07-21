# -*- coding: utf-8 -*-
"""
Upsert dữ liệu đã chuẩn hóa vào Qdrant.
Bản fixed: Qdrant point ID dùng số nguyên, không dùng string kiểu store_1.

Chạy:
  python qdrant_upsert_hash384_fixed.py --url http://localhost:6333 --collection dulich_demo --file qdrant_points_intid_hash384.jsonl
"""
import argparse, json, urllib.request, urllib.error, sys
from pathlib import Path


def request_json(method, url, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        print(f"HTTP {e.code} khi gọi {url}\n{detail}", file=sys.stderr)
        raise


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i+size]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:6333")
    ap.add_argument("--collection", default="dulich_demo")
    ap.add_argument("--file", default="qdrant_points_intid_hash384.jsonl")
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--recreate", action="store_true", help="Xóa collection cũ rồi tạo lại")
    args = ap.parse_args()

    base = args.url.rstrip("/")
    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"Không thấy file: {path}")

    if args.recreate:
        try:
            print(f"Xóa collection cũ nếu có: {args.collection}")
            request_json("DELETE", f"{base}/collections/{args.collection}")
        except Exception:
            pass

    create_body = {"vectors": {"size": 384, "distance": "Cosine"}}
    print(f"Tạo collection: {args.collection}")
    request_json("PUT", f"{base}/collections/{args.collection}", create_body)

    points = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                points.append(json.loads(line))

    print(f"Đang upsert {len(points)} points...")
    total = 0
    for batch in chunks(points, args.batch_size):
        request_json("PUT", f"{base}/collections/{args.collection}/points?wait=true", {"points": batch})
        total += len(batch)
        print(f"Uploaded {total}/{len(points)}")

    print("Xong. Test collection:")
    info = request_json("GET", f"{base}/collections/{args.collection}")
    print(json.dumps(info, ensure_ascii=False, indent=2)[:2000])


if __name__ == "__main__":
    main()
