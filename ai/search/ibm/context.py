from __future__ import annotations

import os
from datetime import datetime
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
IBM_CONTEXT_LOG_FILE = SEARCH_LOG_DIR / "ibm_context.txt"


def normalize_model_name(model_name: str) -> str:
    return model_name.strip().lower() if isinstance(model_name, str) else ""


def is_v4_model(model_name: str) -> bool:
    return normalize_model_name(model_name) in V4_MODEL_NAMES


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, list):
        parts = [_stringify(item) for item in value]
        parts = [part for part in parts if part]
        return " ".join(parts)
    if isinstance(value, dict):
        return " ".join(f"{key}:{_stringify(item)}" for key, item in value.items() if _stringify(item))
    return " ".join(str(value).split())


def _shorten(text: Any, limit: int = 240) -> str:
    value = _stringify(text)
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _append_block(lines: List[str], title: str, value: Any, indent: str = "  ") -> None:
    lines.append(f"{indent}{title}:")
    text = _stringify(value)
    if not text:
        lines.append(f"{indent}  <empty>")
        return
    for line in text.splitlines():
        lines.append(f"{indent}  {line}")


def _extract_last_user_text(messages: List[Dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = _stringify(message.get("content"))
        if content:
            return content
    return ""


def merge_system_messages(messages: List[Dict[str, str]], system_parts: List[str]) -> List[Dict[str, str]]:
    merged_system_parts = [part.strip() for part in system_parts if isinstance(part, str) and part.strip()]
    non_system_messages: List[Dict[str, str]] = []

    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "system" and isinstance(content, str) and content.strip():
            merged_system_parts.append(content.strip())
            continue
        non_system_messages.append(message)

    if not merged_system_parts:
        return non_system_messages

    return [{"role": "system", "content": "\n\n".join(merged_system_parts)}] + non_system_messages


def build_rag_prompt(context_text: str, use_v4: bool = False) -> str:
    return (
        "Dùng ngữ cảnh nếu hữu ích. Nếu không đủ, trả lời chưa đủ thông tin.\n\n"
        f"Ngữ cảnh truy xuất:\n{context_text}\n\n"
        "Chỉ dùng ngữ cảnh nếu liên quan. Không bịa thêm nếu không chắc. Bắt buộc trả lời có ngữ cảnh."
    )


def build_answer_prompt(last_user: str, list_search: str, prompt_guide: str) -> str:
    return "\n".join(
        [
            "SYSTEM",
            f"  list_search: {_shorten(list_search, 400)}",
            f"  prompt_guide: {_shorten(prompt_guide, 240)}",
            "USER",
            f"  last_user: {_shorten(last_user, 400)}",
        ]
    )


def _format_context_log(entry: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append(f"TIME: {entry.get('timestamp', '')}")
    lines.append(f"MODEL: {entry.get('model_name', '')}")
    lines.append("")
    lines.append("MESSAGES")
    messages = entry.get("messages", [])
    if isinstance(messages, list) and messages:
        for idx, message in enumerate(messages, start=1):
            lines.append(f"  [{idx}] role={_stringify(message.get('role', ''))}")
            content = _stringify(message.get("content"))
            lines.append("      content:")
            if content:
                for line in content.splitlines() or ["<empty>"]:
                    lines.append(f"        {line}")
            else:
                lines.append("        <empty>")
    else:
        lines.append("  <empty>")
    lines.append("")
    lines.append("SYSTEM")
    _append_block(lines, "list_search", entry.get("list_search"))
    _append_block(lines, "prompt_guide", entry.get("prompt_guide"))
    lines.append("")
    lines.append("USER")
    _append_block(lines, "last_user", entry.get("last_user"))
    lines.append("")
    lines.append("PROMPT")
    _append_block(lines, "prompt", entry.get("prompt"))
    _append_block(lines, "prompt_raw", entry.get("prompt_raw"))
    lines.append("")
    lines.append("OUTPUT")
    _append_block(lines, "response", entry.get("response"))
    lines.append(f"  prompt_tokens: {entry.get('prompt_tokens', '')}")
    lines.append(f"  completion_tokens: {entry.get('completion_tokens', '')}")
    lines.append(f"  total_tokens: {entry.get('total_tokens', '')}")
    return "\n".join(lines) + "\n"


def write_context_log(entry: Dict[str, Any]) -> None:
    os.makedirs(SEARCH_LOG_DIR, exist_ok=True)
    with open(IBM_CONTEXT_LOG_FILE, "w", encoding="utf-8") as f:
        f.write(_format_context_log(entry))


def generate_rag_response(
    messages: List[Dict[str, str]],
    context_text: str,
    tokenizer: Any,
    model: Any,
    device: Any,
    model_name: str = "",
    *,
    enable_thinking: bool = True,
    max_new_tokens: int = 256,
    temperature: float = 0.7,
    top_p: float = 0.9,
    extra_system_parts: List[str] | None = None,
) -> Dict[str, Any]:
    system_parts = [part.strip() for part in (extra_system_parts or []) if isinstance(part, str) and part.strip()]

    rag_prompt = ""
    if isinstance(context_text, str) and context_text.strip():
        rag_prompt = build_rag_prompt(context_text, use_v4=is_v4_model(model_name))
        if rag_prompt:
            system_parts.append(rag_prompt)

    last_user = _extract_last_user_text(messages)
    answer_messages: List[Dict[str, str]] = []
    if system_parts:
        answer_messages.append({"role": "system", "content": "\n\n".join(system_parts)})
    if last_user:
        answer_messages.append({"role": "user", "content": last_user})
    elif messages:
        answer_messages = [message for message in messages if message.get("role") != "assistant"]

    if not answer_messages:
        answer_messages = messages

    prompt_text = tokenizer.apply_chat_template(
        answer_messages,
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
    decoded = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    result = {
        "response": decoded,
        "prompt_tokens": int(prompt_len),
        "completion_tokens": int(generated_ids.shape[-1]),
        "total_tokens": int(prompt_len + generated_ids.shape[-1]),
        "rag_prompt": rag_prompt,
        "merged_messages": answer_messages,
    }
    write_context_log(
        {
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "model_name": model_name,
            "messages": answer_messages,
            "last_user": last_user,
            "list_search": context_text,
            "prompt": build_answer_prompt(
                last_user=last_user,
                list_search=context_text,
                prompt_guide="Dùng ngữ cảnh nếu hữu ích. Trả lời ngắn gọn, không bịa.",
            ),
            "prompt_raw": prompt_text,
            "prompt_guide": "Dùng ngữ cảnh nếu hữu ích. Trả lời ngắn gọn, không bịa.",
            "response": decoded,
            "prompt_tokens": int(prompt_len),
            "completion_tokens": int(generated_ids.shape[-1]),
            "total_tokens": int(prompt_len + generated_ids.shape[-1]),
        }
    )
    return result
