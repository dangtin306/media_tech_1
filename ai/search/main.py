from __future__ import annotations

import json
import re
import sys
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Callable, Dict, List

import torch


V4_MODEL_NAMES = {
    "qwen3.5-4b-v4",
    "qwen-3.5-4b-v4",
    "qwen-3.5-v4",
    "qwen-token/qwen-3.5-v4",
}

_RAG_MODULE = None
_IBM_CONTEXT_MODULE = None
_IBM_KEY_WORDS_MODULE = None


def _load_rag_module():
    global _RAG_MODULE
    if _RAG_MODULE is None:
        module_path = Path(__file__).resolve().parent / "rag.py"
        spec = importlib_util.spec_from_file_location("media_tech_ai_search_rag", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load search rag module: {module_path}")
        module = importlib_util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _RAG_MODULE = module
    return _RAG_MODULE


def _load_ibm_context_module():
    global _IBM_CONTEXT_MODULE
    if _IBM_CONTEXT_MODULE is None:
        module_path = Path(__file__).resolve().parent / "ibm" / "context.py"
        spec = importlib_util.spec_from_file_location("media_tech_ai_search_ibm_context", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load IBM context module: {module_path}")
        module = importlib_util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _IBM_CONTEXT_MODULE = module
    return _IBM_CONTEXT_MODULE


def _load_ibm_key_words_module():
    global _IBM_KEY_WORDS_MODULE
    if _IBM_KEY_WORDS_MODULE is None:
        module_path = Path(__file__).resolve().parent / "ibm" / "key_words.py"
        spec = importlib_util.spec_from_file_location("media_tech_ai_search_ibm_key_words", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load IBM key words module: {module_path}")
        module = importlib_util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _IBM_KEY_WORDS_MODULE = module
    return _IBM_KEY_WORDS_MODULE


def parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


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


def ensure_first_system_message(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not messages:
        return [{"role": "user", "content": "xin chào"}]

    if not any(item.get("role") == "system" for item in messages):
        return messages

    if messages[0].get("role") == "system":
        return messages

    system_parts: List[str] = []
    non_system_messages: List[Dict[str, str]] = []

    for item in messages:
        if item.get("role") == "system":
            content = stringify_content(item.get("content"))
            if content:
                system_parts.append(content)
        else:
            non_system_messages.append(item)

    system_content = "\n\n".join(system_parts).strip()
    if not system_content:
        return non_system_messages

    return [{"role": "system", "content": system_content}] + non_system_messages


def build_agent_messages(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    system_context = stringify_content(payload.get("system_context"))
    messages: List[Dict[str, str]] = []

    if system_context:
        messages.append({"role": "system", "content": system_context})

    raw_messages = payload.get("messages")
    if isinstance(raw_messages, list) and raw_messages:
        for item in raw_messages:
            normalized = normalize_message(item)
            if normalized and normalized["role"] != "system":
                messages.append(normalized)
        if messages:
            return ensure_first_system_message(messages)

    history = payload.get("history")
    if isinstance(history, list):
        for item in history:
            normalized = normalize_message(item)
            if not normalized or normalized["role"] == "system":
                continue
            messages.append(normalized)

    user_message = stringify_content(payload.get("user_message"))
    if user_message:
        messages.append({"role": "user", "content": user_message})
    else:
        prompt = stringify_content(payload.get("prompt"))
        if prompt:
            messages.append({"role": "user", "content": prompt})

    if not messages:
        messages.append({"role": "user", "content": "xin chào"})

    return ensure_first_system_message(messages)


def collect_user_texts(messages: List[Dict[str, str]]) -> List[str]:
    texts: List[str] = []
    for message in messages:
        if message.get("role") != "user":
            continue
        content = stringify_content(message.get("content"))
        if content:
            texts.append(content)
    return texts


def is_v4_model(model_name: str) -> bool:
    normalized = model_name.strip().lower() if isinstance(model_name, str) else ""
    return normalized in V4_MODEL_NAMES


def build_keyword_prompt(user_texts: List[str]) -> str:
    if not user_texts:
        return ""

    last_user = user_texts[-1].strip()
    previous_users = [text.strip() for text in user_texts[:-1] if text.strip()]
    previous_block = "\n".join(f"- {text}" for text in previous_users) if previous_users else "- (không có)"

    return (
        "Bạn là bộ tách keyword tìm kiếm cho hệ thống RAG.\n"
        "Hãy ưu tiên ý nghĩa của câu user cuối cùng, nhưng vẫn dùng các câu user trước đó để hiểu đúng ngữ cảnh.\n\n"
        f"Câu user cuối cùng:\n{last_user}\n\n"
        f"Các câu user trước đó:\n{previous_block}\n\n"
        "Yêu cầu:\n"
        "- Chỉ trả về đúng 1 dòng duy nhất.\n"
        "- Chỉ gồm keyword ngắn gọn hoặc cụm tìm kiếm ngắn gọn.\n"
        "- Không giải thích, không đánh số, không markdown, không code block.\n"
        "- Nếu có thể, gom thành 1 cụm truy vấn ngắn gọn.\n"
    )


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
    if use_v4:
        return (
            "Bạn là trợ lý tiếng Việt. Hãy dùng ngữ cảnh truy xuất nếu hữu ích. "
            "Nếu ngữ cảnh không đủ, hãy trả lời trung thực là chưa đủ thông tin.\n\n"
            f"Ngữ cảnh truy xuất:\n{context_text}\n\n"
            "Chỉ dùng ngữ cảnh nếu liên quan. Không bịa thêm nếu không chắc. Bắt buộc trả lời có ngữ cảnh."
        )

    return (
        "Bạn là trợ lý tiếng Việt. Hãy dùng ngữ cảnh truy xuất nếu hữu ích. "
        "Nếu ngữ cảnh không đủ, hãy trả lời trung thực là chưa đủ thông tin.\n\n"
        f"Ngữ cảnh truy xuất:\n{context_text}\n\n"
        "Chỉ dùng ngữ cảnh nếu liên quan. Không bịa thêm nếu không chắc. Bắt buộc trả lời có ngữ cảnh."
    )


def retrieve_context(
    question: str,
    top_k: int = 4,
    model_name: str = "",
    messages: List[Dict[str, str]] | None = None,
):
    module = _load_rag_module()
    try:
        return module.retrieve_context(question=question, top_k=top_k, model_name=model_name, messages=messages)
    except TypeError:
        return module.retrieve_context(question=question, top_k=top_k, model_name=model_name)


def warmup_rag_index(model_name: str = "") -> None:
    if _load_rag_module()._use_ibm_rag_model(model_name):  # type: ignore[attr-defined]
        module = _load_rag_module()._load_ibm_search_module()  # type: ignore[attr-defined]
        warmup = getattr(module, "warmup_index", None)
        if callable(warmup):
            warmup()
            return
        module.retrieve_context(question="warmup", top_k=1, model_name=model_name)
        return
    _load_rag_module().get_rag_index(model_name=model_name)


def generate_rag_search_query(
    messages: List[Dict[str, str]],
    tokenizer: Any,
    model: Any,
    device: Any,
    model_name: str = "",
    max_new_tokens: int = 64,
) -> str:
    if is_v4_model(model_name):
        return _load_ibm_key_words_module().generate_rag_search_query(
            messages=messages,
            tokenizer=tokenizer,
            model=model,
            device=device,
            model_name=model_name,
            max_new_tokens=max_new_tokens,
        )
    ibm_module = _load_rag_module()._load_ibm_search_module()  # type: ignore[attr-defined]
    return ibm_module.generate_rag_search_query(
        messages=messages,
        tokenizer=tokenizer,
        model=model,
        device=device,
        model_name=model_name,
        max_new_tokens=max_new_tokens,
    )


def prepare_rag_context_with_query(
    messages: List[Dict[str, str]],
    top_k: int,
    enabled: bool,
    model_name: str = "",
    search_query: str = "",
    retrieve_context_fn: Callable[[str, int, str], Any] | None = None,
) -> tuple[List[Dict[str, str]], str, str]:
    if not enabled:
        return messages, "", ""
    if retrieve_context_fn is None:
        retrieve_context_fn = retrieve_context

    user_texts = collect_user_texts(messages)
    query = search_query.strip() if isinstance(search_query, str) and search_query.strip() else ""
    if not query and user_texts:
        query = user_texts[-1].strip()
    if not query:
        return messages, "", ""

    try:
        retrieval = retrieve_context_fn(
            query,
            top_k=top_k,
            model_name=model_name,
            messages=messages,
        )
    except TypeError:
        retrieval = retrieve_context_fn(query, top_k=top_k, model_name=model_name)
    context_text = getattr(retrieval, "combined_context", "")
    if not isinstance(context_text, str) or not context_text.strip():
        return messages, "", ""

    rag_prompt = build_rag_prompt(context_text, use_v4=is_v4_model(model_name))
    return messages, context_text, rag_prompt


def prepare_rag_context(
    messages: List[Dict[str, str]],
    top_k: int,
    enabled: bool,
    model_name: str,
    tokenizer: Any,
    model: Any,
    device: Any,
    retrieve_context_fn: Callable[[str, int, str], Any] | None = None,
    max_new_tokens: int = 64,
) -> tuple[List[Dict[str, str]], str, str, str]:
    if not enabled:
        return messages, "", "", ""
    if retrieve_context_fn is None:
        retrieve_context_fn = retrieve_context

    search_query = generate_rag_search_query(
        messages=messages,
        tokenizer=tokenizer,
        model=model,
        device=device,
        model_name=model_name,
        max_new_tokens=max_new_tokens,
    )
    messages, context_text, rag_prompt = prepare_rag_context_with_query(
        messages=messages,
        top_k=top_k,
        enabled=enabled,
        model_name=model_name,
        search_query=search_query,
        retrieve_context_fn=retrieve_context_fn,
    )
    return messages, context_text, rag_prompt, search_query
