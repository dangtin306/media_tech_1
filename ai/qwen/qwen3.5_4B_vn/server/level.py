from __future__ import annotations

import json
import os
import re
import traceback
from datetime import datetime
from typing import Any, Dict, List

import context as qwen_context
from call_ai import call_model


LOG_API_DIR = os.path.join(os.path.dirname(__file__), "log_api")
LOG_API_LEVEL_INPUT_PATH = os.path.join(LOG_API_DIR, "agent_level_input.json")
LOG_API_LEVEL_OUTPUT_PATH = os.path.join(LOG_API_DIR, "agent_level_output.json")


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
    if not isinstance(role, str):
        role = "user"
    role = role.strip().lower()
    if role not in {"system", "user", "assistant", "tool"}:
        role = "user"
    text = stringify_content(item.get("content"))
    if not text:
        return None
    return {"role": role, "content": text}


def normalize_level_reply(reply: str) -> str:
    text = stringify_content(reply)
    if not text:
        return "4"
    match = re.search(r"\b([1-4])\b", text)
    if match:
        return match.group(1)
    if text.strip() in {"1", "2", "3", "4"}:
        return text.strip()
    return "4"


def build_level_messages(payload: Dict[str, Any], limit: int = 10) -> List[Dict[str, str]]:
    system_context = stringify_content(payload.get("system_context"))
    user_messages: List[Dict[str, str]] = []

    raw_messages = payload.get("messages")
    if isinstance(raw_messages, list):
        for item in raw_messages:
            normalized = normalize_message(item)
            if normalized and normalized["role"] == "user":
                user_messages.append(normalized)

    if not user_messages:
        history = payload.get("history")
        if isinstance(history, list):
            for item in history:
                normalized = normalize_message(item)
                if normalized and normalized["role"] == "user":
                    user_messages.append(normalized)

    user_message = stringify_content(payload.get("user_message"))
    if not user_messages and user_message:
        user_messages.append({"role": "user", "content": user_message})
    elif not user_messages:
        prompt = stringify_content(payload.get("prompt"))
        if prompt:
            user_messages.append({"role": "user", "content": prompt})

    if limit > 0 and len(user_messages) > limit:
        user_messages = user_messages[-limit:]

    messages: List[Dict[str, str]] = []
    for index, user_item in enumerate(user_messages):
        content = user_item["content"]
        if index == len(user_messages) - 1 and system_context:
            content = f"{system_context}\n\nTin nhắn cần phân loại:\n{content}"
        messages.append({"role": "user", "content": content})
        # Close only earlier user turns; the final turn is the generation target.
        if index < len(user_messages) - 1:
            messages.append({"role": "assistant", "content": ""})
    if not user_messages:
        fallback_content = "xin chào"
        if system_context:
            fallback_content = f"{system_context}\n\nTin nhắn cần phân loại:\n{fallback_content}"
        messages.append({"role": "user", "content": fallback_content})
    return messages


def write_log_api(file_path: str, data: Any) -> None:
    try:
        os.makedirs(LOG_API_DIR, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def handle_level_request(payload: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")

    system_text = stringify_content(payload.get("system_context"))
    level_messages = build_level_messages(payload, limit=10)
    level_request_payload = {
        "model": model_name,
        "system_context": system_text,
        "messages": level_messages,
        "temperature": 0.0,
        "max_new_tokens": 2,
        "top_p": 1.0,
        "enable_thinking": False,
        "use_lora": False,
        "use_rag": False,
        "rag_top_k": int(payload.get("rag_top_k", 4)),
    }

    output_path = LOG_API_LEVEL_OUTPUT_PATH
    level_text = (
        "\n".join(
            item.get("content", "")
            for item in level_messages
            if item.get("role") == "user" and isinstance(item.get("content"), str)
        ).strip()
        or stringify_content(payload.get("user_message"))
        or stringify_content(payload.get("prompt"))
        or "xin chào"
    )

    request_to_qwen = {
        "text": level_text,
        "system_prompt": system_text,
        "enable_thinking": False,
        "max_new_tokens": 2,
        "temperature": 0.0,
        "top_p": 1.0,
    }
    try:
        server_main = qwen_context._load_server_main_module()
        tokenizer, model, device = server_main.load_model()
        prompt_text = tokenizer.apply_chat_template(
            level_messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = tokenizer(prompt_text, return_tensors="pt")
        write_log_api(
            LOG_API_LEVEL_INPUT_PATH,
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "route": "level",
                "input_before_qwen": request_to_qwen,
                "input_to_qwen": {
                    "messages": level_messages,
                    "prompt_text": prompt_text,
                    "generation": {
                        "enable_thinking": False,
                        "max_new_tokens": 2,
                        "temperature": 0.0,
                        "top_p": 1.0,
                    },
                },
            },
        )
        output_ids = call_model(
            tokenizer=tokenizer,
            model=model,
            device=device,
            inputs=inputs,
            prompt_text=prompt_text,
            do_sample=False,
            max_new_tokens=2,
            temperature=0.0,
            top_p=1.0,
        )
        prompt_len = inputs["input_ids"].shape[-1]
        generated_ids = output_ids[0][prompt_len:]
        raw_text = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        reply = normalize_level_reply(raw_text)
        raw_result = {
            "id": f"chatcmpl-level-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "object": "chat.completion",
            "created": int(datetime.utcnow().timestamp()),
            "model": model_name,
            "output_text": reply,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": reply,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": None,
            "use_lora": False,
            "enable_thinking": False,
            "use_rag": False,
            "rag_top_k": int(payload.get("rag_top_k", 4)),
            "normalized_level": reply,
            "reply": reply,
            "raw_output": raw_text,
        }
    except Exception as exc:
        tb = traceback.format_exc()
        write_log_api(
            output_path,
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "route": "level",
                "response_error": str(exc),
                "response_traceback": tb,
            },
        )
        raise

    write_log_api(
        output_path,
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "route": "level",
            "response_from_qwen": raw_result,
            "response": raw_result,
        },
    )

    return {
        "reply": reply,
        "decision": {},
        "state_patch": {},
        "tool_calls": [],
        "usage": None,
        "raw": raw_result,
    }
