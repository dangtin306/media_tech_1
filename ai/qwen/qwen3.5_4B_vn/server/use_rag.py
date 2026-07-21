from __future__ import annotations

import json
import re
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict, List, Tuple

import context as qwen_context
from call_ai import call_model


V4_MODEL_NAMES = {
    "qwen3.5-4b-v4",
    "qwen-3.5-4b-v4",
    "qwen-3.5-v4",
    "qwen-token/qwen-3.5-v4",
}


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

    return {
        "role": role,
        "content": content,
    }


def collect_user_texts(messages: List[Dict[str, str]]) -> List[str]:
    texts: List[str] = []

    for message in messages:
        if message.get("role") != "user":
            continue

        text = stringify_content(message.get("content"))

        if text:
            texts.append(text)

    return texts


def get_last_user_content(messages: List[Dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue

        content = stringify_content(message.get("content"))

        if content:
            return content

    return ""


def build_keyword_system_prompt() -> str:
    return (
        "Tách một cụm từ search RAG sát nhu cầu user. "
        "Chỉ trả cụm từ, không giải thích, không nhãn, không markdown."
    )


def build_keyword_prompt(messages: List[Dict[str, str]]) -> str:
    recent_user_messages = [
        message
        for message in messages
        if message.get("role") == "user"
    ][-5:]

    if not recent_user_messages:
        return ""

    lines = ["Các tin nhắn user gần nhất:"]

    for message in recent_user_messages:
        content = stringify_content(message.get("content"))

        if content:
            lines.append(content)

    lines.append("")
    lines.append("Trả về một cụm từ search phù hợp nhất.")

    return "\n".join(lines)


def normalize_search_query(text: str) -> str:
    query = stringify_content(text)

    if not query:
        return ""

    query = re.sub(
        r"```(?:json|text)?",
        "",
        query,
        flags=re.IGNORECASE,
    )

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
                    items = [
                        stringify_content(item)
                        for item in value
                    ]

                    items = [item for item in items if item]

                    if items:
                        return ", ".join(items)

    except Exception:
        pass

    lines = [
        line.strip()
        for line in query.splitlines()
        if line.strip()
    ]

    if lines:
        query = lines[0]

    query = re.sub(r"^[\-\*•]+\s*", "", query)
    query = re.sub(r"^\d+[\.\)]\s*", "", query)

    query = re.sub(
        r"^(keyword|keywords|query|search query)\s*[:?]\s*",
        "",
        query,
        flags=re.IGNORECASE,
    )

    query = re.sub(r"\s+", " ", query).strip(" ,;")

    return query


def generate_v4_search_query(
    messages: List[Dict[str, str]],
    tokenizer: Any,
    model: Any,
    device: Any,
    model_name: str = "",
    max_new_tokens: int = 64,
) -> str:
    del tokenizer, model, device

    normalized_messages = [
        message
        for message in (
            normalize_message(item)
            for item in messages
        )
        if message
    ]

    user_texts = collect_user_texts(normalized_messages)

    selected_query = (
        user_texts[-1].strip()
        if user_texts
        else ""
    )

    if not user_texts or not is_v4_model(model_name):
        return selected_query

    prompt = build_keyword_prompt(normalized_messages)

    if not prompt:
        return selected_query

    raw_output = qwen_context.generate_loaded_qwen_text(
        prompt,
        system_prompt=build_keyword_system_prompt(),
        enable_thinking=False,
        max_new_tokens=max_new_tokens,
        temperature=0.1,
        top_p=0.9,
    )

    normalized = normalize_search_query(raw_output)

    return normalized or selected_query


def build_v4_rag_system_prompt(
    context_text: str,
    enable_thinking: bool = False,
) -> str:
    context_text = stringify_content(context_text)

    if not context_text:
        context_text = "Không có kết quả RAG."

    thinking_rule = ""

    if enable_thinking:
        thinking_rule = (
            "Trước khi trả lời, phân tích ngắn trong <think>...</think>: "
            "nhu cầu user, độ phù hợp của từng kết quả và cách trả lời. "
            "Sau </think> mới trả lời user.\n"
        )

    return (
        "Bạn là AI tư vấn khách hàng bằng tiếng Việt.\n"
        f"{thinking_rule}"
        "Trả lời trực tiếp dựa trên toàn bộ danh sách RAG.\n"
        "Bắt buộc:\n"
        "- Đọc và sử dụng đủ tất cả mục [1], [2], [3]... trong ngữ cảnh.\n"
        "- Không được bỏ qua, tự xóa hoặc chỉ chọn một phần danh sách.\n"
        "- Tóm tắt mỗi kết quả có thông tin hữu ích như tên, món/dịch vụ, "
        "địa chỉ, khu vực, giá và trạng thái nếu có.\n"
        "- Ưu tiên kết quả phù hợp nhất trước nhưng vẫn phải nhắc đủ các kết quả còn lại.\n"
        "- Nếu kết quả sai khu vực hoặc sai nhu cầu, vẫn phải nói rõ kết quả đó "
        "không phù hợp, không được âm thầm bỏ qua.\n"
        "- Không bịa ngoài dữ liệu.\n"
        "- Trả lời gọn, tự nhiên và dễ đọc.\n\n"
        "Danh sách ngữ cảnh RAG:\n"
        f"{context_text}"
    )


def build_v4_rag_prompt(context_text: str) -> str:
    return build_v4_rag_system_prompt(context_text)


def prepare_v4_rag_context(
    messages: List[Dict[str, str]],
    top_k: int,
    model_name: str,
    tokenizer: Any,
    model: Any,
    device: Any,
) -> Tuple[List[Dict[str, str]], str, str]:
    rag_search_query = generate_v4_search_query(
        messages=messages,
        tokenizer=tokenizer,
        model=model,
        device=device,
        model_name=model_name,
    )

    messages, retrieved_context, _ = (
        qwen_context.prepare_rag_context_with_query(
            messages,
            top_k=top_k,
            enabled=True,
            model_name=model_name,
            search_query=rag_search_query,
        )
    )

    return messages, retrieved_context, rag_search_query


def write_call_ai_input_log(prompt_text: str) -> None:
    try:
        log_path = (
            Path(__file__).resolve().parent
            / "log_api"
            / "call_ai_input.txt"
        )

        log_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        log_path.write_text(
            prompt_text,
            encoding="utf-8",
        )

    except Exception:
        pass


def clean_special_tokens(text: str) -> str:
    output = stringify_content(text)

    output = output.replace("<|im_start|>", "")
    output = output.replace("<|im_end|>", "")

    output = re.sub(
        r"^\s*assistant\s*",
        "",
        output,
        flags=re.IGNORECASE,
    )

    return output.strip()


def split_thinking_and_answer(text: str) -> Tuple[str, str]:
    raw = stringify_content(text)

    if not raw:
        return "", ""

    raw = clean_special_tokens(raw)

    thinking = ""
    answer = raw

    if "<think>" in raw and "</think>" in raw:
        thinking_part, answer_part = raw.split(
            "</think>",
            1,
        )

        thinking = thinking_part.replace(
            "<think>",
            "",
        ).strip()

        answer = answer_part.strip()

    elif "<think>" in raw:
        answer = raw.replace(
            "<think>",
            "",
        ).strip()

    answer = (
        answer
        .replace("<think>", "")
        .replace("</think>", "")
        .strip()
    )

    return thinking, answer


def generate_v4_rag_answer(
    messages: List[Dict[str, str]],
    context_text: str,
    tokenizer: Any,
    model: Any,
    device: Any,
    enable_thinking: bool,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
) -> Dict[str, Any]:
    normalized_messages = [
        message
        for message in (
            normalize_message(item)
            for item in messages
        )
        if message
    ]

    last_user_content = get_last_user_content(
        normalized_messages
    )

    if not last_user_content:
        last_user_content = "Xin chào"

    answer_messages: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": build_v4_rag_system_prompt(
                context_text=context_text,
                enable_thinking=enable_thinking,
            ),
        },
        {
            "role": "user",
            "content": last_user_content,
        },
    ]

    prompt_text = tokenizer.apply_chat_template(
        answer_messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=enable_thinking,
    )

    write_call_ai_input_log(prompt_text)

    inputs = tokenizer(
        prompt_text,
        return_tensors="pt",
    ).to(device)

    output_ids = call_model(
        tokenizer=tokenizer,
        model=model,
        device=device,
        inputs=inputs,
        prompt_text=None,
        enable_thinking=enable_thinking,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
    )

    prompt_len = inputs["input_ids"].shape[-1]
    generated_ids = output_ids[0][prompt_len:]

    raw_response = tokenizer.decode(
        generated_ids,
        skip_special_tokens=True,
    ).strip()

    raw_response_full = tokenizer.decode(
        generated_ids,
        skip_special_tokens=False,
    ).strip()

    thinking_text, clean_response = (
        split_thinking_and_answer(
            raw_response_full
        )
    )

    if not clean_response:
        clean_response = (
            "Dạ hiện chưa đủ dữ liệu phù hợp "
            "để tư vấn chính xác ạ."
        )

    return {
        "response": clean_response,
        "raw_response": raw_response,
        "raw_response_full": raw_response_full,
        "thinking": thinking_text,
        "prompt_tokens": int(prompt_len),
        "completion_tokens": int(
            generated_ids.shape[-1]
        ),
        "total_tokens": int(
            prompt_len + generated_ids.shape[-1]
        ),
        "merged_messages": answer_messages,
    }


def create_v4_rag_run_handler(
    load_base_model: Any,
    load_lora_model: Any,
    log_line: Any,
):
    def handle_run(
        payload: Dict[str, Any],
        headers: Any = None,
    ) -> Dict[str, Any]:
        del headers

        source_messages = (
            qwen_context.build_agent_messages(
                payload
            )
        )

        rag_messages = [
            dict(message)
            for message in source_messages
        ]

        model_name = str(
            payload.get("model")
            or "openclaw/default"
        ).strip()

        # Luồng RAG luôn dùng base model, không dùng LoRA.
        use_lora = False

        enable_thinking = qwen_context.parse_bool(
            payload.get("enable_thinking"),
            default=True,
        )

        rag_top_k = int(
            payload.get("rag_top_k", 4)
        )

        max_tokens = int(
            payload.get(
                "max_tokens",
                payload.get(
                    "max_new_tokens",
                    256,
                ),
            )
        )

        temperature = float(
            payload.get("temperature", 0.7)
        )

        top_p = float(
            payload.get("top_p", 0.5)
        )

        tokenizer, model, device = (
            load_base_model()
        )

        log_line("[run_rag] use_lora_off")

        log_line("[run_rag] rag_stage=start")

        (
            rag_messages,
            retrieved_context,
            rag_search_query,
        ) = prepare_v4_rag_context(
            messages=rag_messages,
            top_k=rag_top_k,
            model_name=model_name,
            tokenizer=tokenizer,
            model=model,
            device=device,
        )

        log_line(
            "[run_rag] rag_stage=done query="
            + json.dumps(
                {"query": rag_search_query},
                ensure_ascii=False,
            )
        )

        response = generate_v4_rag_answer(
            messages=source_messages,
            context_text=retrieved_context,
            tokenizer=tokenizer,
            model=model,
            device=device,
            enable_thinking=enable_thinking,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )

        request_to_qwen = {
            "messages": rag_messages,
            "answer_messages": response.get(
                "merged_messages",
                [],
            ),
            "context_text": retrieved_context,
            "model": model_name,
            "enable_thinking": enable_thinking,
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        return {
            "id": f"chatcmpl-{uuid4().hex}",
            "object": "chat.completion",
            "created": int(
                datetime.utcnow().timestamp()
            ),
            "model": model_name,
            "output_text": response["response"],
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response["response"],
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": int(
                    response["prompt_tokens"]
                ),
                "completion_tokens": int(
                    response["completion_tokens"]
                ),
                "total_tokens": int(
                    response["total_tokens"]
                ),
            },
            "use_lora": use_lora,
            "enable_thinking": enable_thinking,
            "use_rag": True,
            "rag_top_k": rag_top_k,
            "rag_search_query": rag_search_query,
            "retrieved_context": retrieved_context,
            "thinking": response.get(
                "thinking",
                "",
            ),
            "raw_response": response.get(
                "raw_response",
                "",
            ),
            "raw_response_full": response.get(
                "raw_response_full",
                "",
            ),
            "request_to_qwen": request_to_qwen,
        }

    return handle_run