from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Mapping
from uuid import uuid4

import context as qwen_context
import torch
from call_ai import call_model
import use_rag as qwen_use_rag


LOG_API_DIR = os.path.join(os.path.dirname(__file__), "log_api")
LOG_API_RUN_INPUT_PATH = os.path.join(LOG_API_DIR, "agent_run_input.json")
LOG_API_RUN_OUTPUT_PATH = os.path.join(LOG_API_DIR, "agent_run_output.json")
DEFAULT_SYSTEM_MESSAGE = (
    "Bạn là trợ lý tư vấn dịch vụ/quán/sản phẩm chạy sau OpenClaw. "
    "Trả lời tiếng Việt ngắn gọn, rõ ý."
)


def write_run_log(file_path: str, data: Any) -> None:
    try:
        os.makedirs(LOG_API_DIR, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    except Exception:
        pass


def parse_bool(value: Any, default: bool = True) -> bool:
    return qwen_context.parse_bool(value, default=default)


def limit_run_messages(messages: List[Dict[str, str]], limit: int = 5) -> List[Dict[str, str]]:
    system_messages = [item for item in messages if item.get("role") == "system"]
    other_messages = [item for item in messages if item.get("role") != "system"]
    return system_messages[:1] + other_messages[-limit:]


def remove_system_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [message for message in messages if message.get("role") != "system"]


def move_system_context_to_penultimate_assistant(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not messages:
        return messages

    system_index = next((index for index, message in enumerate(messages) if message.get("role") == "system"), -1)
    if system_index < 0:
        return messages

    system_message = dict(messages[system_index])
    system_content = str(system_message.get("content", "")).strip()
    if not system_content:
        return [message for message in messages if message.get("role") != "system"]

    remaining_messages = [dict(message) for index, message in enumerate(messages) if index != system_index]
    if not remaining_messages:
        return [{"role": "assistant", "content": system_content}]

    last_user_index = next(
        (
            index
            for index in range(len(remaining_messages) - 1, -1, -1)
            if remaining_messages[index].get("role") == "user"
        ),
        -1,
    )
    if last_user_index < 0:
        return [{"role": "assistant", "content": system_content}] + remaining_messages

    return (
        remaining_messages[:last_user_index]
        + [{"role": "assistant", "content": system_content}]
        + remaining_messages[last_user_index:]
    )


def generate_v4_answer(
    messages: List[Dict[str, str]],
    context_text: str,
    tokenizer: Any,
    model: Any,
    device: Any,
    model_name: str,
    enable_thinking: bool,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
) -> Dict[str, Any]:
    context_text_for_model = ""
    if context_text.strip():
        context_text_for_model = qwen_use_rag.build_v4_rag_prompt(context_text).strip()

    history_messages = [dict(message) for message in messages if message.get("role") != "system"]
    answer_messages: List[Dict[str, str]] = []
    if history_messages:
        answer_messages = [dict(message) for message in history_messages]
        last_user_index = next(
            (
                index
                for index in range(len(answer_messages) - 1, -1, -1)
                if answer_messages[index].get("role") == "user"
            ),
            -1,
        )
        if last_user_index >= 0:
            original_user_content = str(answer_messages[last_user_index].get("content", "")).strip()
            merged_user_content = original_user_content
            if context_text_for_model:
                merged_user_content = (
                    context_text_for_model + "\n\n" + original_user_content
                    if original_user_content
                    else context_text_for_model
                )
            answer_messages[last_user_index] = {"role": "user", "content": merged_user_content}
        elif context_text_for_model:
            answer_messages.append({"role": "user", "content": context_text_for_model})
    elif context_text_for_model:
        answer_messages = [{"role": "user", "content": context_text_for_model}]
    else:
        answer_messages = [{"role": "user", "content": "xin chao"}]

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
    return {
        "response": tokenizer.decode(generated_ids, skip_special_tokens=True).strip(),
        "prompt_tokens": int(prompt_len),
        "completion_tokens": int(generated_ids.shape[-1]),
        "total_tokens": int(prompt_len + generated_ids.shape[-1]),
        "merged_messages": answer_messages,
    }


def create_run_handler(
    load_base_model: Callable[[], tuple[Any, Any, Any]],
    load_lora_model: Callable[[], tuple[Any, Any, Any]],
    log_line: Callable[[str], None],
):
    rag_run_handler = qwen_use_rag.create_v4_rag_run_handler(load_base_model, load_lora_model, log_line)

    def handle_run(payload: Dict[str, Any], headers: Mapping[str, str] | None = None) -> Dict[str, Any]:
        del headers

        messages = limit_run_messages(qwen_context.build_agent_messages(payload), limit=5)
        model_name = str(payload.get("model") or "openclaw/default").strip()
        reasoning_effort = str(payload.get("reasoning_effort", "low") or "low").strip().lower()
        enable_thinking = parse_bool(payload.get("enable_thinking"), default=(reasoning_effort != "low"))
        use_lora = parse_bool(payload.get("use_lora"), default=True)
        use_rag = parse_bool(payload.get("use_rag"), default=False)
        rag_top_k = int(payload.get("rag_top_k", 4))
        max_tokens = int(payload.get("max_tokens", payload.get("max_new_tokens", 256)))
        temperature = float(payload.get("temperature", 0.7))
        top_p = float(payload.get("top_p", 0.9))

        if use_rag:
            return rag_run_handler(payload, None)

        if use_lora:
            tokenizer, model, device = load_lora_model()
            log_line("[run] use_lora_on")
        else:
            tokenizer, model, device = load_base_model()
            log_line("[run] use_lora_off")

        messages = move_system_context_to_penultimate_assistant(messages)

        log_line(
            "[run] outbound_json "
            + json.dumps(
                {
                    "model": model_name,
                    "messages": messages,
                    "enable_thinking": enable_thinking,
                    "use_lora": use_lora,
                    "use_rag": use_rag,
                    "rag_top_k": rag_top_k,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )

        request_to_qwen = {
            "messages": messages,
            "context_text": "",
            "model": model_name,
            "enable_thinking": enable_thinking,
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }
        write_run_log(
            LOG_API_RUN_INPUT_PATH,
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "route": "run",
                "request_to_qwen": request_to_qwen,
            },
        )

        generation = generate_v4_answer(
            messages=messages,
            context_text="",
            tokenizer=tokenizer,
            model=model,
            device=device,
            model_name=model_name,
            enable_thinking=enable_thinking,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        decoded = generation["response"]
        response = {
            "id": f"chatcmpl-{uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "output_text": decoded,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": decoded}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": int(generation["prompt_tokens"]),
                "completion_tokens": int(generation["completion_tokens"]),
                "total_tokens": int(generation["total_tokens"]),
            },
            "use_lora": use_lora,
            "enable_thinking": enable_thinking,
            "use_rag": use_rag,
            "rag_top_k": rag_top_k,
            "retrieved_context": "",
        }
        write_run_log(
            LOG_API_RUN_OUTPUT_PATH,
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "route": "run",
                "response_from_qwen": response,
            },
        )
        return response

    return handle_run
