import json
import os
import time
from pathlib import Path

import requests


DATASET = "ura-hcmut/Vietnamese-Customer-Support-QA"
CONFIG = "default"
OUT_DIR = Path(__file__).resolve().parent
TOKEN = os.environ.get("HF_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
SPLITS = {
    "train": 8349,
    "test": 1500,
}
PAGE_SIZE = 100
TIMEOUT = 60


def fetch_rows(split: str, offset: int, length: int = PAGE_SIZE):
    url = (
        "https://datasets-server.huggingface.co/rows"
        f"?dataset={DATASET.replace('/', '%2F')}"
        f"&config={CONFIG}&split={split}&offset={offset}&length={length}"
    )
    for attempt in range(6):
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 429:
            sleep_s = min(30, 2 ** attempt)
            print(f"[rate-limit] split={split} offset={offset} sleep={sleep_s}s")
            time.sleep(sleep_s)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Too many 429 responses for split={split} offset={offset}")


def dump_split(split: str, total_rows: int) -> None:
    out_file = OUT_DIR / f"ura-hcmut_{split}.jsonl"
    if out_file.exists():
        out_file.unlink()
    written = 0
    for offset in range(0, total_rows, PAGE_SIZE):
        payload = fetch_rows(split, offset)
        rows = payload.get("rows", [])
        if not rows:
            break
        with out_file.open("a", encoding="utf-8", newline="\n") as f:
            for row in rows:
                obj = row.get("row", {})
                item = {
                    "question": obj.get("question"),
                    "answer": obj.get("answer"),
                    "type": obj.get("type"),
                    "row_idx": row.get("row_idx"),
                }
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                written += 1
        print(f"[{split}] wrote {written}/{total_rows}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for split, total in SPLITS.items():
        dump_split(split, total)


if __name__ == "__main__":
    main()
