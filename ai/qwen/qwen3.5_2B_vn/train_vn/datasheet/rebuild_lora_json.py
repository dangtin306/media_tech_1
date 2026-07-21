import json
import re
import unicodedata
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
SRC = DATA_DIR / "ura-hcmut_Vietnamese-Customer-Support-QA_train.jsonl"
OUT = DATA_DIR / "LoRA.json"

SYSTEM_PROMPT = (
    "\u0042\u1ea1n l\u00e0 tr\u1ee3 l\u00fd ch\u0103m s\u00f3c kh\u00e1ch h\u00e0ng ti\u1ebfng Vi\u1ec7t. "
    "Tr\u1ea3 l\u1eddi ng\u1eafn g\u1ecdn, r\u00f5 r\u00e0ng, t\u1ef1 nhi\u00ean, \u0111\u00fang tr\u1ecdng t\u00e2m v\u00e0 kh\u00f4ng b\u1ecba."
)


def clean_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" ?\n ?", "\n", value)
    return value.strip()


def main() -> None:
    items = []
    with SRC.open("r", encoding="utf-8-sig") as f:
        for line_no, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            obj = json.loads(raw)
            question = obj.get("question")
            answer = obj.get("answer")
            if not isinstance(question, str) or not isinstance(answer, str):
                raise ValueError(f"Line {line_no} missing question/answer")
            question = clean_text(question)
            answer = clean_text(answer)
            item = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer},
                ],
                "question": question,
                "answer": answer,
                "type": obj.get("type"),
                "row_idx": obj.get("row_idx"),
                "source": SRC.name,
            }
            items.append(item)

    with OUT.open("w", encoding="utf-8-sig", newline="\n") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"wrote {len(items)} items to {OUT}")


if __name__ == "__main__":
    main()
