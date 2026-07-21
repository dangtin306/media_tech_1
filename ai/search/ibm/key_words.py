from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Dict, List

import torch
from call_ai import call_model


V4_MODEL_NAMES = {
    "qwen3.5-4b-v4",
    "qwen-3.5-4b-v4",
    "qwen-3.5-v4",
    "qwen-token/qwen-3.5-v4",
}

SEARCH_LOG_DIR = Path(__file__).resolve().parents[1] / "log"
KEYWORD_LOG_FILE = SEARCH_LOG_DIR / "ibm_in_out.txt"
SEARCH_LOG_FILE = SEARCH_LOG_DIR / "ibm_search.txt"
_QWEN_SERVER_MAIN_MODULE = None


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


def build_keyword_system_prompt() -> str:
    return (
        "Bạn là bộ tách cụm từ tìm kiếm cho RAG. "
        "Đọc ngữ cảnh hội thoại và trả về đúng một cụm từ tìm kiếm tự nhiên, "
        "sát nhu cầu tra cứu. Không giải thích, không markdown, không thêm nhãn."
    )


def build_keyword_prompt(messages: List[Dict[str, str]]) -> str:
    recent_messages = messages[-5:]
    if not recent_messages:
        return ""

    lines = ["Ngữ cảnh hội thoại (5 message gần nhất):"]
    for message in recent_messages:
        role = message.get("role", "user").strip().lower()
        content = stringify_content(message.get("content"))
        if content:
            lines.append(f"{role}: {content}")
    lines.append("")
    lines.append("Hãy lấy cụm từ search phù hợp nhất từ ngữ cảnh trên.")
    return "\n".join(lines)


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
    system_prompt: str,
    prompt: str,
    raw_output: str,
    normalized: str,
    selected_query: str,
) -> Dict[str, Any]:
    user_texts = collect_user_texts(messages)
    last_user = user_texts[-1] if user_texts else ""
    previous_user = ""
    if len(user_texts) > 1:
        for text in reversed(user_texts[:-1]):
            candidate = text.strip()
            if candidate and candidate != last_user:
                previous_user = candidate
                break

    return {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "model_name": model_name,
        "used_v4": is_v4_model(model_name),
        "context_input": {
            "messages": messages[-5:],
            "system_prompt": system_prompt,
            "last_user": last_user,
            "previous_user": previous_user,
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
    messages: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    return {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "model_name": model_name,
        "search_input": {
            "query": query,
            "top_k": top_k,
            "messages": (messages or [])[-5:],
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
        system_prompt = context_input.get("system_prompt", "")
        prompt = context_input.get("prompt", "")
        lines.append("  system prompt:")
        for line in _format_text_value(system_prompt).splitlines() or ["<empty>"]:
            lines.append(f"    {line}")
        lines.append("  messages (5 gan nhat):")
        for idx, message in enumerate(messages[-5:], start=1):
            lines.append(f"    [{idx}] role={message.get('role', '')}")
            for line in _format_text_value(message.get("content", "")).splitlines() or ["<empty>"]:
                lines.append(f"        {line}")
        lines.append("  prompt gui Qwen:")
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
        messages = search_input.get("messages", [])
        if messages:
            lines.append("  messages (5 gan nhat):")
            for idx, message in enumerate(messages[-5:], start=1):
                lines.append(f"    [{idx}] role={message.get('role', '')}")
                for line in _format_text_value(message.get("content", "")).splitlines() or ["<empty>"]:
                    lines.append(f"        {line}")
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
    if "search_input" in entry and "search_output" in entry:
        with open(SEARCH_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(_format_search_log(entry))
        return

    payload = _format_text_value(entry) + "\n"
    with open(KEYWORD_LOG_FILE, "w", encoding="utf-8") as f:
        f.write(payload)


def _load_server_main_module():
    global _QWEN_SERVER_MAIN_MODULE
    if _QWEN_SERVER_MAIN_MODULE is not None:
        return _QWEN_SERVER_MAIN_MODULE

    main_path = Path(__file__).resolve().parents[2] / "qwen" / "qwen3.5_4B_vn" / "server" / "main.py"
    for module_name in ("main", "__main__"):
        module = sys.modules.get(module_name)
        module_file = getattr(module, "__file__", None) if module is not None else None
        if not module_file:
            continue
        try:
            if Path(module_file).resolve() == main_path and hasattr(module, "load_model"):
                _QWEN_SERVER_MAIN_MODULE = module
                return module
        except Exception:
            continue

    spec = importlib_util.spec_from_file_location("media_tech_ai_qwen_server_main", main_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load server main module: {main_path}")
    module = importlib_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _QWEN_SERVER_MAIN_MODULE = module
    return module


def generate_loaded_qwen_text(
    text: str,
    system_prompt: str = "",
    *,
    enable_thinking: bool = False,
    max_new_tokens: int = 256,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> str:
    server_main = _load_server_main_module()
    tokenizer, model, device = server_main.load_model()

    messages: List[Dict[str, str]] = []
    system_text = stringify_content(system_prompt)
    user_text = stringify_content(text)

    if system_text:
        messages.append({"role": "system", "content": system_text})
    if user_text:
        messages.append({"role": "user", "content": user_text})
    else:
        messages.append({"role": "user", "content": "xin chao"})

    prompt_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=enable_thinking,
    )
    inputs = tokenizer(prompt_text, return_tensors="pt").to(device)

    output_ids = call_model(
        tokenizer=tokenizer,
        model=model,
        device=device,
        inputs=inputs,
        prompt_text=prompt_text,
        enable_thinking=enable_thinking,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
    )

    prompt_len = inputs["input_ids"].shape[-1]
    generated_ids = output_ids[0][prompt_len:]
    return tokenizer.decode(generated_ids, skip_special_tokens=True).strip()


def generate_rag_search_query(
    messages: List[Dict[str, str]],
    tokenizer: Any,
    model: Any,
    device: Any,
    model_name: str = "",
    max_new_tokens: int = 64,
) -> str:
    normalized_messages = [m for m in (normalize_message(item) for item in messages) if m]
    user_texts = collect_user_texts(normalized_messages)
    selected_query = user_texts[-1].strip() if user_texts else ""
    prompt = ""
    raw_output = ""
    normalized = ""
    system_prompt = ""

    if user_texts and is_v4_model(model_name):
        prompt = build_keyword_prompt(normalized_messages)
        if prompt:
            system_prompt = build_keyword_system_prompt()
            raw_output = generate_loaded_qwen_text(
                prompt,
                system_prompt=system_prompt,
                enable_thinking=False,
                max_new_tokens=max_new_tokens,
                temperature=0.1,
                top_p=0.9,
            )
            normalized = normalize_search_query(raw_output)
            selected_query = normalized or selected_query

    write_keyword_log(
        build_log_entry(
            messages=normalized_messages,
            model_name=model_name,
            system_prompt=system_prompt,
            prompt=prompt,
            raw_output=raw_output,
            normalized=normalized,
            selected_query=selected_query,
        )
    )
    return selected_query
