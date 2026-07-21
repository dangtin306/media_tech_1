#!/usr/bin/env python3
import json
import os
import sys
from copy import deepcopy
from typing import Any, Dict, List


DEFAULT_SYSTEM_MESSAGE = (
    "Bạn là trợ lý tư vấn dịch vụ/quán/sản phẩm chạy sau OpenClaw. "
    "Trả lời tiếng Việt ngắn gọn, rõ ý."
)


def _parse_json(raw: str):
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        raw = raw.lstrip("\ufeff")
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _read_stdin_text() -> str:
    raw = sys.stdin.buffer.read()
    if not raw:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def _write_stdout_json(data: Dict[str, Any]) -> None:
    text = json.dumps(data, ensure_ascii=False)
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


def _stringify_content(content: Any) -> str:
    if content is None:
        return ""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
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


def _normalize_message(message):
    if not isinstance(message, dict):
        return None

    role = str(message.get("role", "user")).strip().lower()
    if role not in {"system", "user", "assistant", "tool"}:
        role = "user"

    content = _stringify_content(message.get("content", ""))
    if not content:
        return None

    normalized = {
        "role": role,
        "content": content,
    }

    for key in ("name", "tool_call_id", "id"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = value.strip()

    function_call = message.get("function_call")
    if isinstance(function_call, dict):
        fn_name = function_call.get("name")
        fn_args = function_call.get("arguments")
        if isinstance(fn_name, str) and fn_name.strip():
            normalized["function_call"] = {
                "name": fn_name.strip(),
                "arguments": _stringify_content(fn_args),
            }

    return normalized


def _normalize_history(history):
    if not isinstance(history, list):
        return []

    normalized = []
    for item in history:
        entry = _normalize_message(item)
        if entry:
            normalized.append(entry)

    return normalized


def _first_nonempty(*values: Any, default: Any = "") -> Any:
    for value in values:
        if isinstance(value, str):
            if value.strip():
                return value.strip()
        elif value not in (None, "", [], {}, ()):
            return value
    return default


def _parse_number(value: Any) -> Any:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return value

    if isinstance(value, str) and value.strip():
        try:
            parsed = float(value)
        except Exception:
            return None
        return int(parsed) if parsed.is_integer() else parsed

    return None


def _parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _default_options(options: Dict[str, Any]) -> Dict[str, Any]:
    current = dict(options) if isinstance(options, dict) else {}

    current.setdefault("mode", "run")
    current.setdefault("need_decision", True)
    current.setdefault("allow_tool_call", True)
    current.setdefault("max_history", 20)

    return current


def _ensure_first_system_message(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not messages:
        return [
            {"role": "system", "content": DEFAULT_SYSTEM_MESSAGE},
            {"role": "user", "content": "xin chào"},
        ]

    has_system = any(m.get("role") == "system" for m in messages)

    if not has_system:
        return [{"role": "system", "content": DEFAULT_SYSTEM_MESSAGE}] + messages

    if messages[0].get("role") == "system":
        return messages

    system_messages = [m for m in messages if m.get("role") == "system"]
    non_system_messages = [m for m in messages if m.get("role") != "system"]

    merged_system_content = "\n\n".join(
        _stringify_content(m.get("content", ""))
        for m in system_messages
        if _stringify_content(m.get("content", ""))
    ).strip()

    if not merged_system_content:
        merged_system_content = DEFAULT_SYSTEM_MESSAGE

    return [{"role": "system", "content": merged_system_content}] + non_system_messages


def _default_messages_from_payload(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []

    raw_messages = data.get("messages")

    # Ưu tiên messages do JS backend đã build sẵn.
    # Nếu JS đã đưa system_context vào role system thì Python giữ nguyên.
    if isinstance(raw_messages, list) and raw_messages:
        for item in raw_messages:
            normalized = _normalize_message(item)
            if normalized:
                messages.append(normalized)

    else:
        # Fallback ổn định:
        # Nếu JS chưa build messages nhưng có system_context,
        # Python tự đưa system_context vào role system.
        system_context = _stringify_content(data.get("system_context"))
        if system_context:
            messages.append({
                "role": "system",
                "content": system_context,
            })

        history = _normalize_history(data.get("history"))
        if history:
            messages.extend(history)

        user_message = _stringify_content(data.get("user_message"))
        if user_message:
            messages.append({
                "role": "user",
                "content": user_message,
            })

    if not messages:
        messages = [{"role": "user", "content": "xin chào"}]

    return _ensure_first_system_message(messages)


def normalize_payload(payload):
    data = deepcopy(payload) if isinstance(payload, dict) else {}

    runtime = data.get("runtime") if isinstance(data.get("runtime"), dict) else {}
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    options = data.get("options") if isinstance(data.get("options"), dict) else {}
    config = data.get("config") if isinstance(data.get("config"), dict) else {}

    model = str(
        _first_nonempty(
            runtime.get("model"),
            data.get("model"),
            data.get("upstream_model"),
            data.get("ubuntu_model"),
            os.getenv("QWEN_MODEL_NAME"),
            default="Qwen3.5-4B-V3",
        )
    ).strip()

    user = str(data.get("user", "")).strip() or "media_tech:request"
    session_key = str(data.get("session_key", "")).strip() or "agent:media_tech:ubuntu"

    temperature = _first_nonempty(
        _parse_number(data.get("temperature")),
        _parse_number(config.get("temperature")),
        _parse_number(os.getenv("QWEN_TEMPERATURE")),
        default=0.4,
    )

    max_tokens = _first_nonempty(
        _parse_number(data.get("max_tokens")),
        _parse_number(config.get("max_tokens")),
        _parse_number(os.getenv("QWEN_MAX_TOKENS")),
        default=128,
    )

    enable_thinking = _parse_bool(
        data.get("enable_thinking"),
        _parse_bool(config.get("enable_thinking"), False),
    )

    normalized = {
        "model": model,
        "user": user,
        "session_key": session_key,
        "messages": _default_messages_from_payload(data),
        "reasoning_effort": str(data.get("reasoning_effort", "minimal")).strip() or "minimal",
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": data.get("top_p", 0.9),
        "enable_thinking": enable_thinking,
        "use_lora": bool(data.get("use_lora", True)),
        "use_rag": bool(data.get("use_rag", False)),
        "rag_top_k": data.get("rag_top_k", 4),
        "options": _default_options(options),
        "normalized": True,
    }

    # Giữ lại system_context để backend/server sau còn debug hoặc forward nếu cần.
    for key in ("session_id", "turn_id", "user_message", "scenario", "system_context"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = value.strip()

    for key in ("user_state", "runtime", "metadata"):
        value = data.get(key)
        if isinstance(value, dict):
            normalized[key] = value

    if "history" in data:
        normalized["history"] = _normalize_history(data.get("history"))

    model_server = _first_nonempty(
        data.get("model_server"),
        runtime.get("model_server"),
        metadata.get("model_server"),
        os.getenv("QWEN_MODEL_SERVER"),
        default="",
    )
    if isinstance(model_server, str) and model_server.strip():
        normalized["model_server"] = model_server.strip()

    for key in (
        "x_openclaw_model",
        "ubuntu_model",
        "message_channel",
        "upstream_model",
    ):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = value.strip()

    return normalized


def _build_base_output(normalized: Dict[str, Any], error_reason: str = "") -> Dict[str, Any]:
    base = deepcopy(normalized) if isinstance(normalized, dict) else {}

    if not base.get("messages"):
        base["messages"] = [
            {"role": "system", "content": DEFAULT_SYSTEM_MESSAGE},
            {"role": "user", "content": "xin chào"},
        ]
    else:
        base["messages"] = _ensure_first_system_message(base["messages"])

    base["options"] = _default_options(
        base.get("options") if isinstance(base.get("options"), dict) else {}
    )

    base["model"] = base.get("model") or "Qwen3.5-4B-V3"
    base["user"] = base.get("user") or "media_tech:request"
    base["session_key"] = base.get("session_key") or "agent:media_tech:ubuntu"
    base["temperature"] = base.get("temperature", 0.4)
    base["max_tokens"] = base.get("max_tokens", 128)
    base["top_p"] = base.get("top_p", 0.9)
    base["enable_thinking"] = bool(base.get("enable_thinking", False))
    base["use_lora"] = bool(base.get("use_lora", True))
    base["use_rag"] = bool(base.get("use_rag", False))
    base["rag_top_k"] = base.get("rag_top_k", 4)
    base["normalized"] = bool(base.get("normalized", False))

    if error_reason:
        base["normalized"] = False
        base["formatter_reason"] = error_reason

    return base


def main():
    try:
        raw = _read_stdin_text()
        payload = _parse_json(raw)
        normalized = normalize_payload(payload)
        result = _build_base_output(normalized)

    except Exception as ex:
        result = {
            "normalized": False,
            "error": str(ex),
            "model": "Qwen3.5-4B-V3",
            "user": "media_tech:request",
            "session_key": "agent:media_tech:ubuntu",
            "messages": [
                {"role": "system", "content": DEFAULT_SYSTEM_MESSAGE},
                {"role": "user", "content": "xin chào"},
            ],
            "options": _default_options({}),
            "temperature": _parse_number(os.getenv("QWEN_TEMPERATURE")) or 0.4,
            "max_tokens": _parse_number(os.getenv("QWEN_MAX_TOKENS")) or 128,
            "top_p": 0.9,
            "enable_thinking": _parse_bool(os.getenv("QWEN_ENABLE_THINKING"), False),
            "use_lora": True,
            "use_rag": False,
            "rag_top_k": 4,
        }

    _write_stdout_json(result)


if __name__ == "__main__":
    main()
