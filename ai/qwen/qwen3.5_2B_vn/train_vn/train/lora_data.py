import json
import os
from typing import Any, Dict, List

import torch
from transformers import AutoTokenizer


def _normalize_messages(messages: Any, line_desc: str) -> List[Dict[str, str]]:
    if not isinstance(messages, list) or not messages:
        raise ValueError(f"{line_desc} must contain a non-empty 'messages' list.")
    normalized: List[Dict[str, str]] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if isinstance(role, str) and isinstance(content, str) and content.strip():
            normalized.append({"role": role.strip(), "content": content.strip()})
    if not normalized:
        raise ValueError(f"{line_desc} has no usable chat messages.")
    return normalized


def _normalize_example(obj: Dict[str, Any], line_desc: str) -> Dict[str, object]:
    if isinstance(obj.get("messages"), list):
        return {"messages": _normalize_messages(obj["messages"], line_desc)}

    prompt = obj.get("prompt")
    response = obj.get("response")
    if isinstance(prompt, str) and isinstance(response, str):
        return {"prompt": prompt.strip(), "response": response.strip()}

    question = obj.get("question")
    answer = obj.get("answer")
    if isinstance(question, str) and isinstance(answer, str):
        return {"prompt": question.strip(), "response": answer.strip()}

    raise ValueError(
        f"{line_desc} must contain either 'messages', 'prompt'/'response', or 'question'/'answer'."
    )


def load_jsonl_dataset(path: str) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for line_no, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no} in {path}: {exc}") from exc
            rows.append(_normalize_example(obj, f"Line {line_no} in {path}"))
    if not rows:
        raise ValueError(f"No usable rows found in {path}")
    return rows


def load_json_dataset(path: str) -> List[Dict[str, object]]:
    with open(path, "r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for key in ("data", "items", "examples", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                items = value
                break
        else:
            items = [payload]
    else:
        raise ValueError(f"Unsupported JSON root in {path}: expected list or object.")

    rows: List[Dict[str, object]] = []
    for idx, obj in enumerate(items, start=1):
        if not isinstance(obj, dict):
            raise ValueError(f"Item {idx} in {path} must be an object.")
        rows.append(_normalize_example(obj, f"Item {idx} in {path}"))
    if not rows:
        raise ValueError(f"No usable rows found in {path}")
    return rows


def load_dataset(path: str) -> List[Dict[str, object]]:
    lower = path.lower()
    if lower.endswith(".jsonl"):
        return load_jsonl_dataset(path)
    if lower.endswith(".json"):
        return load_json_dataset(path)
    return load_jsonl_dataset(path)


def build_tokenizer(base_model: str) -> AutoTokenizer:
    cache_dir = os.environ.get("HUGGINGFACE_HUB_CACHE")
    tokenizer = AutoTokenizer.from_pretrained(
        base_model,
        trust_remote_code=True,
        use_fast=True,
        cache_dir=cache_dir,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return tokenizer


def format_prompt(tokenizer: AutoTokenizer, prompt: str, response: str | None = None) -> tuple[str, str]:
    prompt_messages = [{"role": "user", "content": prompt}]
    prompt_text = tokenizer.apply_chat_template(
        prompt_messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    if response is None:
        return prompt_text, ""
    full_messages = [{"role": "user", "content": prompt}, {"role": "assistant", "content": response}]
    full_text = tokenizer.apply_chat_template(
        full_messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    return prompt_text, full_text


def tokenize_example(tokenizer: AutoTokenizer, row: Dict[str, object], max_seq_length: int) -> Dict[str, List[int]]:
    if isinstance(row.get("messages"), list):
        messages = row["messages"]
        if not messages:
            raise ValueError("Encountered empty messages row.")
        prompt_messages = messages[:-1]
        full_text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )
        if prompt_messages:
            prompt_text = tokenizer.apply_chat_template(
                prompt_messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            prompt_text = tokenizer.apply_chat_template(
                [{"role": "user", "content": ""}],
                tokenize=False,
                add_generation_prompt=True,
            )
    else:
        prompt = str(row["prompt"])
        response = str(row["response"])
        prompt_text, full_text = format_prompt(tokenizer, prompt, response)

    prompt_ids = tokenizer(prompt_text, add_special_tokens=False).input_ids
    full = tokenizer(full_text, add_special_tokens=False, truncation=True, max_length=max_seq_length)
    input_ids = full["input_ids"]
    attention_mask = full["attention_mask"]
    labels = input_ids.copy()
    prompt_len = min(len(prompt_ids), len(labels))
    for idx in range(prompt_len):
        labels[idx] = -100
    return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


class SFTDataset(torch.utils.data.Dataset):
    def __init__(self, tokenizer: AutoTokenizer, rows: List[Dict[str, object]], max_seq_length: int):
        self.examples = [tokenize_example(tokenizer, row, max_seq_length) for row in rows]

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> Dict[str, List[int]]:
        return self.examples[idx]


class DataCollatorForSFT:
    def __init__(self, pad_token_id: int):
        self.pad_token_id = pad_token_id

    def __call__(self, features):
        batch = {}
        max_len = max(len(item["input_ids"]) for item in features)
        for key in ("input_ids", "attention_mask", "labels"):
            values = []
            if key == "input_ids":
                pad_value = self.pad_token_id
            elif key == "attention_mask":
                pad_value = 0
            else:
                pad_value = -100
            for item in features:
                seq = item[key]
                pad_len = max_len - len(seq)
                if pad_len > 0:
                    seq = seq + [pad_value] * pad_len
                values.append(seq)
            batch[key] = torch.tensor(values, dtype=torch.long)
        return batch


def make_tokenized_dataset(tokenizer: AutoTokenizer, rows: List[Dict[str, object]], max_seq_length: int) -> SFTDataset:
    return SFTDataset(tokenizer, rows, max_seq_length)
