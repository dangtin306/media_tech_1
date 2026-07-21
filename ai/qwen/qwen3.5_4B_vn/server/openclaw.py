from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Mapping
from uuid import uuid4

import torch

import context as qwen_context


LOG_API_DIR = os.path.join(os.path.dirname(__file__), "log_api")
LOG_API_RUN_INPUT_PATH = os.path.join(LOG_API_DIR, "agent_run_input.json")
LOG_API_LEVEL_INPUT_PATH = os.path.join(LOG_API_DIR, "agent_level_input.json")


def write_level_or_run_input_log(payload: Dict[str, Any], messages: List[Dict[str, str]]) -> None:
    try:
        os.makedirs(LOG_API_DIR, exist_ok=True)
        mode = str(payload.get("options", {}).get("mode", "")).strip().lower()
        file_path = LOG_API_LEVEL_INPUT_PATH if mode == "level" else LOG_API_RUN_INPUT_PATH
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_to_qwen": {
                **payload,
                "messages": messages,
            },
            "request": {
                **payload,
                "messages": messages,
            },
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def parse_bool(value: Any, default: bool = True) -> bool:
    return qwen_context.parse_bool(value, default=default)


def parse_messages(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    return qwen_context.build_agent_messages(payload)


def normalize_model_name(payload: Dict[str, Any]) -> str:
    raw_model = payload.get("model")
    if isinstance(raw_model, str) and raw_model.strip():
        return raw_model.strip()
    return "openclaw/default"


def create_openclaw_handler(
    load_base_model: Callable[[], tuple[Any, Any, Any]],
    load_lora_model: Callable[[], tuple[Any, Any, Any]],
    log_line: Callable[[str], None],
):
    def handle_chat_completions(payload: Dict[str, Any], headers: Mapping[str, str] | None = None) -> Dict[str, Any]:
        del headers

        messages = parse_messages(payload)
        model_name = normalize_model_name(payload)
        reasoning_effort = str(payload.get("reasoning_effort", "low") or "low").strip().lower()
        enable_thinking = parse_bool(payload.get("enable_thinking"), default=(reasoning_effort != "low"))
        use_lora = parse_bool(payload.get("use_lora"), default=True)
        use_rag = parse_bool(payload.get("use_rag"), default=False)
        rag_top_k = int(payload.get("rag_top_k", 4))
        max_tokens = int(payload.get("max_tokens", payload.get("max_new_tokens", 256)))
        temperature = float(payload.get("temperature", 0.7))
        top_p = float(payload.get("top_p", 0.9))

        if use_lora:
            tokenizer, model, device = load_lora_model()
            log_line("[openclaw] use_lora_on")
        else:
            tokenizer, model, device = load_base_model()
            log_line("[openclaw] use_lora_off")

        outbound_payload = {
            "model": model_name,
            "messages": messages,
            "enable_thinking": enable_thinking,
            "use_lora": use_lora,
            "use_rag": use_rag,
            "rag_top_k": rag_top_k,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }
        log_line("[openclaw] outbound_json " + json.dumps(outbound_payload, ensure_ascii=False, sort_keys=True))

        retrieved_context = ""
        if use_rag:
            log_line("[openclaw] rag_stage=start")
            messages, retrieved_context, rag_prompt, rag_search_query = qwen_context.prepare_rag_context(
                messages,
                top_k=rag_top_k,
                enabled=True,
                model_name=model_name,
                tokenizer=tokenizer,
                model=model,
                device=device,
            )
            log_line("[openclaw] rag_stage=done query=" + json.dumps({"query": rag_search_query}, ensure_ascii=False))
        else:
            rag_prompt = ""

        write_level_or_run_input_log(payload, messages)

        generation = qwen_context.generate_rag_response(
            messages=messages,
            context_text=retrieved_context,
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

        response_id = f"chatcmpl-{uuid4().hex}"
        created = int(time.time())
        return {
            "id": response_id,
            "object": "chat.completion",
            "created": created,
            "model": model_name,
            "output_text": decoded,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": decoded,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": int(generation["prompt_tokens"]),
                "completion_tokens": int(generation["completion_tokens"]),
                "total_tokens": int(generation["total_tokens"]),
            },
            "use_lora": use_lora,
            "enable_thinking": enable_thinking,
            "use_rag": use_rag,
            "rag_top_k": rag_top_k,
            "retrieved_context": retrieved_context,
        }

    return handle_chat_completions
