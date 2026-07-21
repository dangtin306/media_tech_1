import json
import shutil
from pathlib import Path


PATH = Path(__file__).resolve().parent / "ura-hcmut_test.jsonl"
BACKUP = PATH.with_suffix(".original.jsonl")


def repair_text(value: str) -> str:
    if not isinstance(value, str):
        return value
    try:
        fixed = value.encode("latin1").decode("utf-8")
    except Exception:
        return value
    return fixed


def repair_value(value):
    if isinstance(value, str):
        return repair_text(value)
    if isinstance(value, list):
        return [repair_value(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_value(val) for key, val in value.items()}
    return value


def main() -> None:
    if not BACKUP.exists():
        shutil.copy2(PATH, BACKUP)

    repaired_lines = []
    with PATH.open("r", encoding="utf-8-sig") as f:
        for line_no, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            obj = json.loads(raw)
            obj = repair_value(obj)
            repaired_lines.append(json.dumps(obj, ensure_ascii=False))

    with PATH.open("w", encoding="utf-8-sig", newline="\n") as f:
        for line in repaired_lines:
            f.write(line + "\n")

    print(f"repaired {len(repaired_lines)} lines")


if __name__ == "__main__":
    main()
