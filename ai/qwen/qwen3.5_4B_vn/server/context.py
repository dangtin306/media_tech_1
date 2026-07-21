from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Dict, List

import torch
from call_ai import call_model


_IBM_RAG_MODEL_NAMES = {
    "qwen3.5-4b-v4",
    "qwen-3.5-4b-v4",
    "qwen-3.5-v4",
    "qwen-token/qwen-3.5-v4",
}

_IBM_MAIN_MODULE = None
_IBM_CONTEXT_MODULE = None
_IBM_SEARCH_MAIN_MODULE = None
_QWEN_SERVER_MAIN_MODULE = None


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
    content = item.get("content")

    if not isinstance(role, str):
        role = "user"

    role = role.strip().lower()
    if role not in {"system", "user", "assistant", "tool"}:
        role = "user"

    text = stringify_content(content)
    if not text and role != "assistant":
        return None

    return {"role": role, "content": text}


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


def is_ibm_rag_model(model_name: str) -> bool:
    normalized = model_name.strip().lower() if isinstance(model_name, str) else ""
    return normalized in _IBM_RAG_MODEL_NAMES


def build_rag_keyword_prompt(user_texts: List[str]) -> str:
    if not user_texts:
        return ""

    last_user = user_texts[-1].strip()
    previous_users = [text.strip() for text in user_texts[:-1] if text.strip()]
    previous_block = "\n".join(f"- {text}" for text in previous_users) if previous_users else "- (khong co)"

    return (
        "Ban la bo tach keyword tim kiem cho he thong RAG.\n"
        "Hay uu tien y nghia cua cau user cuoi cung, nhung dung cac cau user truoc do de hieu dung ngu canh.\n\n"
        f"Cau user cuoi cung:\n{last_user}\n\n"
        f"Cac cau user truoc do:\n{previous_block}\n\n"
        "Yeu cau:\n"
        "- Chi tra ve 1 dong duy nhat.\n"
        "- Chi gom keyword ngan gon de tim kiem.\n"
        "- Khong giai thich, khong danh so, khong markdown, khong code block.\n"
        "- Neu co the, gom thanh 1 cum truy van ngan gon.\n"
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


def generate_rag_search_query(
    messages: List[Dict[str, str]],
    tokenizer: Any,
    model: Any,
    device: Any,
    model_name: str = "",
    max_new_tokens: int = 64,
) -> str:
    global _IBM_MAIN_MODULE
    if _IBM_MAIN_MODULE is None:
        module_path = Path(__file__).resolve().parents[3] / "search" / "ibm" / "main.py"
        spec = importlib_util.spec_from_file_location("media_tech_ai_search_ibm_main", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load IBM RAG module: {module_path}")
        module = importlib_util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _IBM_MAIN_MODULE = module

    return _IBM_MAIN_MODULE.generate_rag_search_query(
        messages=messages,
        tokenizer=tokenizer,
        model=model,
        device=device,
        model_name=model_name,
        max_new_tokens=max_new_tokens,
    )


def _load_ibm_context_module():
    global _IBM_CONTEXT_MODULE
    if _IBM_CONTEXT_MODULE is None:
        module_path = Path(__file__).resolve().parents[3] / "search" / "ibm" / "context.py"
        spec = importlib_util.spec_from_file_location("media_tech_ai_search_ibm_context", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load IBM context module: {module_path}")
        module = importlib_util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _IBM_CONTEXT_MODULE = module
    return _IBM_CONTEXT_MODULE


def _load_ibm_search_main_module():
    global _IBM_SEARCH_MAIN_MODULE
    if _IBM_SEARCH_MAIN_MODULE is None:
        module_path = Path(__file__).resolve().parents[3] / "search" / "ibm" / "main.py"
        spec = importlib_util.spec_from_file_location("media_tech_ai_search_ibm_main", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load IBM search main module: {module_path}")
        module = importlib_util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _IBM_SEARCH_MAIN_MODULE = module
    return _IBM_SEARCH_MAIN_MODULE


def _load_server_main_module():
    global _QWEN_SERVER_MAIN_MODULE
    if _QWEN_SERVER_MAIN_MODULE is not None:
        return _QWEN_SERVER_MAIN_MODULE

    main_path = Path(__file__).resolve().with_name("main.py")
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
    messages: List[Dict[str, str]] | None = None,
    enable_thinking: bool = False,
    max_new_tokens: int = 256,
    temperature: float = 0.7,
    top_p: float = 0.9,
    input_log_path: str | None = None,
    input_log_metadata: Dict[str, Any] | None = None,
    input_log_format: str = "jsonl",
) -> str:
    server_main = _load_server_main_module()
    tokenizer, model, device = server_main.load_model()

    if messages is None:
        message_list: List[Dict[str, str]] = []
        system_text = stringify_content(system_prompt)
        user_text = stringify_content(text)

        if system_text:
            message_list.append({"role": "system", "content": system_text})
        if user_text:
            message_list.append({"role": "user", "content": user_text})
        else:
            message_list.append({"role": "user", "content": "xin chao"})
    else:
        message_list = [
            normalized
            for item in messages
            if (normalized := normalize_message(item)) is not None
        ]
        if not message_list:
            message_list = [{"role": "user", "content": "xin chao"}]

    prompt_text = tokenizer.apply_chat_template(
        message_list,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=enable_thinking,
    )

    if input_log_path:
        try:
            path = Path(input_log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            metadata = dict(input_log_metadata or {})
            log_entry: Dict[str, Any] = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "route": metadata.get("route", ""),
                "input_before_qwen": metadata.get("input_before_qwen", {}),
                "input_to_qwen": {
                    "messages": message_list,
                    "prompt_text": prompt_text,
                    "generation": {
                        "enable_thinking": enable_thinking,
                        "max_new_tokens": max_new_tokens,
                        "temperature": temperature,
                        "top_p": top_p,
                    },
                },
            }
            if input_log_format == "json":
                with path.open("w", encoding="utf-8") as file:
                    json.dump(log_entry, file, ensure_ascii=False, indent=2)
            else:
                with path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

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


def get_rag_retrieve_context(model_name: str = ""):
    if is_ibm_rag_model(model_name):
        return _load_ibm_search_main_module().retrieve_context
    return _load_search_main_module().retrieve_context


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


def inject_rag_context(
    messages: List[Dict[str, str]],
    top_k: int,
    enabled: bool,
    model_name: str = "",
) -> tuple[List[Dict[str, str]], str, str]:
    if not enabled:
        return messages, "", ""

    user_texts = [m["content"] for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str)]
    query = user_texts[-1] if user_texts else ""
    if not query.strip():
        return messages, "", ""

    if is_ibm_rag_model(model_name):
        retrieve_context = _load_ibm_search_main_module().retrieve_context
    else:
        retrieve_context = get_rag_retrieve_context(model_name)

    try:
        retrieval = retrieve_context(query, top_k=top_k, model_name=model_name, messages=messages)
    except TypeError:
        retrieval = retrieve_context(query, top_k=top_k, model_name=model_name)
    context_text = getattr(retrieval, "combined_context", "")
    if not isinstance(context_text, str) or not context_text.strip():
        return messages, "", ""

    rag_prompt = (
        "B?n l? tr? l? ti?ng Vi?t. H?y d?ng ng? c?nh truy xu?t n?u h?u ?ch. "
        "N?u ng? c?nh kh?ng ??, h?y tr? l?i trung th?c l? ch?a ?? th?ng tin.\n\n"
        f"Ng? c?nh truy xu?t:\n{context_text}\n\n"
        "Ch? d?ng ng? c?nh n?y n?u n? li?n quan. Kh?ng b?a th?m n?u kh?ng ch?c."
    )
    return messages, context_text, rag_prompt


def inject_rag_context_with_query(
    messages: List[Dict[str, str]],
    top_k: int,
    enabled: bool,
    model_name: str = "",
    search_query: str = "",
) -> tuple[List[Dict[str, str]], str, str]:
    if not enabled:
        return messages, "", ""

    user_texts = collect_user_texts(messages)
    query = search_query.strip() if isinstance(search_query, str) and search_query.strip() else ""
    if not query and user_texts:
        query = user_texts[-1].strip()
    if not query:
        return messages, "", ""

    if is_ibm_rag_model(model_name):
        retrieve_context = _load_ibm_search_main_module().retrieve_context
    else:
        retrieve_context = get_rag_retrieve_context(model_name)

    try:
        retrieval = retrieve_context(query, top_k=top_k, model_name=model_name, messages=messages)
    except TypeError:
        retrieval = retrieve_context(query, top_k=top_k, model_name=model_name)
    context_text = getattr(retrieval, "combined_context", "")
    if not isinstance(context_text, str) or not context_text.strip():
        return messages, "", ""

    rag_prompt = (
        "B?n l? tr? l? ti?ng Vi?t. H?y d?ng ng? c?nh truy xu?t n?u h?u ?ch. "
        "N?u ng? c?nh kh?ng ??, h?y tr? l?i trung th?c l? ch?a ?? th?ng tin.\n\n"
        f"Ng? c?nh truy xu?t:\n{context_text}\n\n"
        "Ch? d?ng ng? c?nh n?y n?u n? li?n quan. Kh?ng b?a th?m n?u kh?ng ch?c."
    )
    return messages, context_text, rag_prompt


def prepare_rag_context(
    messages: List[Dict[str, str]],
    top_k: int,
    enabled: bool,
    model_name: str,
    tokenizer: Any,
    model: Any,
    device: Any,
    retrieve_context_fn: Any = None,
    max_new_tokens: int = 64,
) -> tuple[List[Dict[str, str]], str, str, str]:
    if retrieve_context_fn is None:
        retrieve_context_fn = get_rag_retrieve_context(model_name)

    if is_ibm_rag_model(model_name):
        search_query = _load_ibm_search_main_module().generate_rag_search_query(
            messages=messages,
            tokenizer=tokenizer,
            model=model,
            device=device,
            model_name=model_name,
            max_new_tokens=max_new_tokens,
        )
        messages, context_text, rag_prompt = inject_rag_context_with_query(
            messages=messages,
            top_k=top_k,
            enabled=enabled,
            model_name=model_name,
            search_query=search_query,
        )
        return messages, context_text, rag_prompt, search_query

    return _load_search_main_module().prepare_rag_context(
        messages=messages,
        top_k=top_k,
        enabled=enabled,
        model_name=model_name,
        tokenizer=tokenizer,
        model=model,
        device=device,
        retrieve_context_fn=retrieve_context_fn,
        max_new_tokens=max_new_tokens,
    )

_SEARCH_MAIN_MODULE = None


def _load_search_main_module():
    global _SEARCH_MAIN_MODULE
    if _SEARCH_MAIN_MODULE is None:
        module_path = Path(__file__).resolve().parents[3] / "search" / "main.py"
        spec = importlib_util.spec_from_file_location("media_tech_ai_search_main", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load search main module: {module_path}")
        module = importlib_util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _SEARCH_MAIN_MODULE = module
    return _SEARCH_MAIN_MODULE


def merge_system_messages(messages: List[Dict[str, str]], system_parts: List[str]) -> List[Dict[str, str]]:  # type: ignore[override]
    return _load_search_main_module().merge_system_messages(messages, system_parts)


def generate_rag_search_query(
    messages: List[Dict[str, str]],
    tokenizer: Any,
    model: Any,
    device: Any,
    model_name: str = "",
    max_new_tokens: int = 64,
) -> str:  # type: ignore[override]
    return _load_search_main_module().generate_rag_search_query(
        messages=messages,
        tokenizer=tokenizer,
        model=model,
        device=device,
        model_name=model_name,
        max_new_tokens=max_new_tokens,
    )


def prepare_rag_context(
    messages: List[Dict[str, str]],
    top_k: int,
    enabled: bool,
    model_name: str,
    tokenizer: Any,
    model: Any,
    device: Any,
    retrieve_context_fn: Any = None,
    max_new_tokens: int = 64,
) -> tuple[List[Dict[str, str]], str, str, str]:
    if retrieve_context_fn is None:
        retrieve_context_fn = get_rag_retrieve_context(model_name)

    return _load_search_main_module().prepare_rag_context(
        messages=messages,
        top_k=top_k,
        enabled=enabled,
        model_name=model_name,
        tokenizer=tokenizer,
        model=model,
        device=device,
        retrieve_context_fn=retrieve_context_fn,
        max_new_tokens=max_new_tokens,
    )


def prepare_rag_context_with_query(
    messages: List[Dict[str, str]],
    top_k: int,
    enabled: bool,
    model_name: str = "",
    search_query: str = "",
    retrieve_context_fn: Any = None,
) -> tuple[List[Dict[str, str]], str, str]:
    if retrieve_context_fn is None:
        retrieve_context_fn = get_rag_retrieve_context(model_name)

    return _load_search_main_module().prepare_rag_context_with_query(
        messages=messages,
        top_k=top_k,
        enabled=enabled,
        model_name=model_name,
        search_query=search_query,
        retrieve_context_fn=retrieve_context_fn,
    )


def warmup_rag_index(model_name: str = "") -> None:
    _load_search_main_module().warmup_rag_index(model_name=model_name)


def build_rag_prompt(context_text: str, use_v4: bool = False) -> str:  # type: ignore[override]
    return _load_ibm_context_module().build_rag_prompt(context_text, use_v4=use_v4)


def merge_system_messages(messages: List[Dict[str, str]], system_parts: List[str]) -> List[Dict[str, str]]:  # type: ignore[override]
    return _load_ibm_context_module().merge_system_messages(messages, system_parts)


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
    return _load_ibm_context_module().generate_rag_response(
        messages=messages,
        context_text=context_text,
        tokenizer=tokenizer,
        model=model,
        device=device,
        model_name=model_name,
        enable_thinking=enable_thinking,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        extra_system_parts=extra_system_parts,
    )
