import json
import os
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, List

from flask import jsonify, request

import context as qwen_context
import level as qwen_level

LOG_API_DIR = os.path.join(os.path.dirname(__file__), "log_api")
LOG_API_RUN_INPUT_PATH = os.path.join(LOG_API_DIR, "agent_run_input.json")
LOG_API_RUN_OUTPUT_PATH = os.path.join(LOG_API_DIR, "agent_run_output.json")
MAIN_INPUT_JSON_PATH = os.path.join(LOG_API_DIR, "main_input.json")


DEFAULT_SYSTEM_MESSAGE = (
    "Bạn là trợ lý tư vấn dịch vụ/quán/sản phẩm chạy sau OpenClaw. "
    "Trả lời tiếng Việt ngắn gọn, rõ ý."
)


def stringify_content(content: Any) -> str:
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


def normalize_message(item: Any) -> Dict[str, str] | None:
    if not isinstance(item, dict):
        return None

    role = item.get("role")
    content = item.get("content")

    if not isinstance(role, str):
        role = "user"

    role = role.strip().lower()
    if role not in {"system", "user", "assistant", "tool"}:
        role = "user"

    text = stringify_content(content)
    if not text:
        return None

    return {
        "role": role,
        "content": text,
    }


def ensure_first_system_message(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not messages:
        return [
            {"role": "system", "content": DEFAULT_SYSTEM_MESSAGE},
            {"role": "user", "content": "xin chào"},
        ]

    has_system = any(item.get("role") == "system" for item in messages)

    if not has_system:
        return [{"role": "system", "content": DEFAULT_SYSTEM_MESSAGE}] + messages

    if messages[0].get("role") == "system":
        return messages

    system_parts = []
    non_system_messages = []

    for item in messages:
        if item.get("role") == "system":
            content = stringify_content(item.get("content"))
            if content:
                system_parts.append(content)
        else:
            non_system_messages.append(item)

    system_content = "\n\n".join(system_parts).strip() or DEFAULT_SYSTEM_MESSAGE

    return [{"role": "system", "content": system_content}] + non_system_messages


def dedupe_leading_system_message(
    messages: List[Dict[str, str]],
    system_context: str,
) -> List[Dict[str, str]]:
    if not messages or not system_context:
        return messages

    first_message = messages[0]
    if first_message.get("role") != "system":
        return messages

    first_content = stringify_content(first_message.get("content"))
    if not first_content:
        return messages

    system_text = system_context.strip()

    if first_content == system_text:
        return messages[1:]

    if first_content.startswith(system_text):
        remainder = first_content[len(system_text):].strip()
        if remainder:
            messages[0] = {
                "role": "system",
                "content": remainder.lstrip("\n").strip(),
            }
            return messages
        return messages[1:]

    return messages


def build_agent_messages(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    system_context = stringify_content(payload.get("system_context"))
    messages: List[Dict[str, str]] = []

    if system_context:
        messages.append({
            "role": "system",
            "content": system_context,
        })

    # 1. Ưu tiên messages đã được JS/qwen.py build sẵn, nhưng bỏ mọi system khác.
    raw_messages = payload.get("messages")
    if isinstance(raw_messages, list) and raw_messages:
        for item in raw_messages:
            normalized = normalize_message(item)
            if normalized and normalized["role"] != "system":
                messages.append(normalized)

        if messages:
            return ensure_first_system_message(messages)

    # 2. Thêm history nếu có.
    history = payload.get("history")
    if isinstance(history, list):
        for item in history:
            normalized = normalize_message(item)
            if not normalized:
                continue

            if normalized["role"] == "system":
                continue

            messages.append(normalized)

    # 3. Thêm user_message/prompt cuối cùng.
    user_message = stringify_content(payload.get("user_message"))
    if user_message:
        messages.append({
            "role": "user",
            "content": user_message,
        })
    else:
        prompt = stringify_content(payload.get("prompt"))
        if prompt:
            messages.append({
                "role": "user",
                "content": prompt,
            })

    if not messages:
        messages.append({
            "role": "user",
            "content": "xin chào",
        })

    return ensure_first_system_message(messages)


def extract_reply(result: Any) -> str:
    if result is None:
        return ""

    if isinstance(result, str):
        return result.strip()

    if isinstance(result, dict):
        for key in ("reply", "message", "content", "output_text"):
            value = result.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

            if isinstance(value, dict):
                nested = value.get("content")
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()

        choices = result.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue

                message = choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()

        return ""

    if isinstance(result, list):
        for item in reversed(result):
            text = extract_reply(item)
            if text:
                return text
        return ""

    content = getattr(result, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()

    output_text = getattr(result, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    return ""


def extract_usage(result: Any) -> Dict[str, Any] | None:
    if not isinstance(result, dict):
        return None

    usage = result.get("usage")
    if isinstance(usage, dict):
        return usage

    raw = result.get("raw")
    if isinstance(raw, dict):
        raw_usage = raw.get("usage")
        if isinstance(raw_usage, dict):
            return raw_usage

    return None


def normalize_optional_object(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_tool_calls(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def write_log_api(file_path: str, data: Any) -> None:
    try:
        os.makedirs(LOG_API_DIR, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def write_main_input_json(data: Any) -> None:
    try:
        os.makedirs(LOG_API_DIR, exist_ok=True)
        with open(MAIN_INPUT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def unwrap_request_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    inner_payload = payload.get("request")
    if isinstance(inner_payload, dict):
        return inner_payload

    return payload


def is_v4_model(model_name: str) -> bool:
    normalized = str(model_name or "").strip().lower()
    return normalized in {
        "qwen3.5-4b-v4",
        "qwen-3.5-4b-v4",
        "qwen-3.5-v4",
        "qwen-token/qwen-3.5-v4",
    }


def run_agent_payload(
    payload: Dict[str, Any],
    handle_openclaw_chat_completions: Callable[[Dict[str, Any], Any], Dict[str, Any]],
    handle_v4_run: Callable[[Dict[str, Any], Any], Dict[str, Any]] | None = None,
    route_name: str = "run",
) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")

    write_main_input_json(payload)
    source_payload = unwrap_request_payload(payload)

    model_name = str(source_payload.get("model", "")).strip() or "qwen-token/qwen-3.5-v4"

    if route_name == "level":
        return qwen_level.handle_level_request(source_payload, model_name)

    input_path = LOG_API_RUN_INPUT_PATH
    output_path = LOG_API_RUN_OUTPUT_PATH

    messages = qwen_context.build_agent_messages(source_payload)

    request_payload = dict(source_payload)
    request_payload["model"] = model_name
    request_payload["messages"] = messages
    request_payload.setdefault("temperature", source_payload.get("temperature", 0.8))
    request_payload.setdefault(
        "max_tokens",
        source_payload.get("max_tokens", source_payload.get("max_new_tokens", 256)),
    )
    request_payload.setdefault("top_p", source_payload.get("top_p", 0.9))

    if isinstance(source_payload.get("system_context"), str):
        request_payload["system_context"] = source_payload.get("system_context")

    if handle_openclaw_chat_completions is None:
        raise RuntimeError("OpenClaw/RAG is disabled on Ubuntu.")

    run_handler = handle_v4_run if is_v4_model(model_name) and handle_v4_run is not None else handle_openclaw_chat_completions
    try:
        raw_result = run_handler(request_payload, None)
    except Exception as exc:
        tb = traceback.format_exc()
        try:
            with open(os.path.join(LOG_API_DIR, "agent_run_traceback.txt"), "a", encoding="utf-8") as f:
                f.write(f"{datetime.utcnow().isoformat()}Z {route_name}\n")
                f.write(tb)
                f.write("\n")
        except Exception:
            pass
        write_log_api(
            output_path,
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "route": route_name,
                "request_to_qwen": request_payload,
                "request": request_payload,
                "response_error": str(exc),
                "response_traceback": tb,
            },
        )
        raise

    reply = extract_reply(raw_result)

    log_response = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "route": route_name,
        "request_to_qwen": request_payload,
        "request": request_payload,
        "response_from_qwen": raw_result,
        "response": raw_result,
    }
    write_log_api(
        output_path,
        log_response,
    )

    return {
        "reply": reply,
        "decision": normalize_optional_object(
            raw_result.get("decision") if isinstance(raw_result, dict) else None
        ),
        "state_patch": normalize_optional_object(
            raw_result.get("state_patch") if isinstance(raw_result, dict) else None
        ),
        "tool_calls": normalize_tool_calls(
            raw_result.get("tool_calls") if isinstance(raw_result, dict) else None
        ),
        "usage": extract_usage(raw_result),
        "raw": raw_result,
    }


def register_backend_routes(
    app,
    handle_openclaw_chat_completions: Callable[[Dict[str, Any], Any], Dict[str, Any]],
    handle_v4_run: Callable[[Dict[str, Any], Any], Dict[str, Any]] | None = None,
):
    @app.get("/openclaw/agent/health")
    def agent_health():
        return jsonify(
            {
                "status": "ok",
                "service": "qwen-gpu-server",
                "runtime": "qwen-model",
                "routes": ["/chat/completions", "/openclaw/agent/run", "/openclaw/agent/level"],
            }
        )

    @app.post("/openclaw/agent/run")
    def openclaw_agent_run():
        return _handle_agent_route()

    @app.post("/openclaw/agent/level")
    def openclaw_agent_level():
        return _handle_agent_route()

    def _handle_agent_route():
        try:
            payload = request.get_json(force=True, silent=False)
            route_name = "level" if request.path.endswith("/level") else "run"

            if not isinstance(payload, dict):
                return jsonify(
                    {
                        "reply": "Lỗi GPU server: JSON body must be an object",
                        "decision": {},
                        "state_patch": {},
                        "tool_calls": [],
                        "usage": None,
                        "raw": {"error": "JSON body must be an object"},
                    }
                ), 400

            result = run_agent_payload(
                payload,
                handle_openclaw_chat_completions,
                handle_v4_run=handle_v4_run,
                route_name=route_name,
            )
            return jsonify(result)

        except Exception as exc:
            return jsonify(
                {
                    "reply": f"Lỗi GPU server: {exc}",
                    "decision": {},
                    "state_patch": {},
                    "tool_calls": [],
                    "usage": None,
                    "raw": {"error": str(exc)},
                }
            ), 500






