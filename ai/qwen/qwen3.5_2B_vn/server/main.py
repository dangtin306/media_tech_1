import os
import sys
from datetime import datetime
from typing import Any, Dict, List


EXPECTED_CONDA_PREFIX = r"D:\hustmedia\conda_envs\qwen"
if os.name == "nt":
    BASE_MODEL_FALLBACK = r"D:\huggingface\hub\Qwen\Qwen3.5-2B"
    LORA_ADAPTER_FALLBACK = r"D:\huggingface\hub\Qwen\Qwen3.5-2B_vn_1\adapter"
else:
    BASE_MODEL_FALLBACK = "/root/model/Qwen/Qwen3.5-2B"
    LORA_ADAPTER_FALLBACK = "/root/model/Qwen/Qwen3.5-2B_vn_1/adapter"
BASE_MODEL_PATH = os.environ.get("QWEN_BASE_MODEL", BASE_MODEL_FALLBACK)
LORA_ADAPTER_PATH = os.environ.get("QWEN_LORA_ADAPTER", LORA_ADAPTER_FALLBACK)
STRICT_CUDA_ONLY = True
LOG_PATH = os.path.join(os.path.dirname(__file__), "log.txt")
LOG_MAX_LINES = 100
LOG_KEEP_FILES = 3
SYSTEM_PROMPT_NO_THINKING = "Trả lời ngắn gọn, trực tiếp, không trình bày quá trình suy nghĩ. Chỉ đưa ra câu trả lời cuối cùng."
SYSTEM_PROMPT_RAG = (
    "Bạn là trợ lý tiếng Việt. Hãy dùng ngữ cảnh truy xuất nếu hữu ích. "
    "Nếu ngữ cảnh không đủ, hãy trả lời trung thực là chưa đủ thông tin."
)


def rotate_logs() -> None:
    if not os.path.exists(LOG_PATH):
        return
    line_count = 0
    with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for _ in f:
            line_count += 1
            if line_count > LOG_MAX_LINES:
                break
    if line_count <= LOG_MAX_LINES:
        return
    for idx in range(LOG_KEEP_FILES - 1, 0, -1):
        src = f"{LOG_PATH}.{idx}"
        dst = f"{LOG_PATH}.{idx + 1}"
        if os.path.exists(src):
            os.replace(src, dst)
    os.replace(LOG_PATH, f"{LOG_PATH}.1")


def log_line(message: str) -> None:
    rotate_logs()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{ts} {message}\n")


def is_docker_runtime() -> bool:
    return os.environ.get("QWEN_DOCKER") == "1" or os.path.exists("/.dockerenv")


def ensure_conda_env(expected_prefix: str) -> None:
    if is_docker_runtime():
        return

    current_prefix = os.environ.get("CONDA_PREFIX") or sys.prefix
    expected_norm = os.path.normcase(os.path.normpath(expected_prefix))
    current_norm = os.path.normcase(os.path.normpath(current_prefix))
    if current_norm != expected_norm:
        log_line(f"[fatal] wrong env: current={current_prefix} expected={expected_prefix}")
        raise SystemExit(1)


ensure_conda_env(EXPECTED_CONDA_PREFIX)

from flask import Flask, jsonify, request  # noqa: E402
import torch  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

from lora import load_lora_model  # noqa: E402
from rag import retrieve_context  # noqa: E402


app = Flask(__name__)

TOKENIZER = None
MODEL = None
DEVICE = None


def resolve_dtype() -> torch.dtype:
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


def resolve_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_model():
    global TOKENIZER, MODEL, DEVICE
    if TOKENIZER is not None and MODEL is not None and DEVICE is not None:
        return TOKENIZER, MODEL, DEVICE

    if not os.path.isdir(BASE_MODEL_PATH):
        raise FileNotFoundError(f"Base model path not found: {BASE_MODEL_PATH}")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")

    dtype = resolve_dtype()
    DEVICE = resolve_device()
    TOKENIZER = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True, use_fast=True)
    if TOKENIZER.pad_token is None:
        TOKENIZER.pad_token = TOKENIZER.eos_token
    TOKENIZER.padding_side = "left"

    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        trust_remote_code=True,
        dtype=dtype,
        device_map={"": 0} if STRICT_CUDA_ONLY else "auto",
        attn_implementation="sdpa",
    )
    MODEL = base_model.to(DEVICE)
    if STRICT_CUDA_ONLY:
        offloaded = getattr(MODEL, "hf_device_map", None)
        if offloaded:
            bad_targets = {str(v) for v in offloaded.values() if str(v) not in {"0", "cuda:0"}}
            if bad_targets:
                raise RuntimeError(f"Model offloaded to non-CUDA devices: {sorted(bad_targets)}")
    MODEL.eval()
    log_line("[startup] model_loaded")
    return TOKENIZER, MODEL, DEVICE


def build_messages(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    if isinstance(payload.get("messages"), list) and payload["messages"]:
        messages: List[Dict[str, str]] = []
        for item in payload["messages"]:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if isinstance(role, str) and isinstance(content, str):
                messages.append({"role": role, "content": content})
        if messages:
            return messages

    prompt = payload.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return [{"role": "user", "content": prompt.strip()}]

    raise ValueError("Payload must include either non-empty 'messages' or 'prompt'.")


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


def inject_rag_context(messages: List[Dict[str, str]], top_k: int) -> tuple[List[Dict[str, str]], str, str]:
    user_texts = [m["content"] for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str)]
    query = user_texts[-1] if user_texts else ""
    if not query.strip():
        return messages, "", ""
    retrieval = retrieve_context(query, top_k=top_k)
    context_text = retrieval.combined_context
    if not context_text.strip():
        return messages, "", ""
    rag_prompt = (
        f"{SYSTEM_PROMPT_RAG}\n\n"
        f"Ngữ cảnh truy xuất:\n{context_text}\n\n"
        "Chỉ dùng ngữ cảnh nếu liên quan. Không bịa thêm nếu không chắc. Bắt buộc trả lời có ngữ cảnh."
    )
    return messages, context_text, rag_prompt


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


@app.get("/health")
def health():
    tokenizer, model, device = load_model()
    log_line("[health] ok")
    return jsonify(
        {
            "ok": True,
            "env": sys.prefix,
            "expected_env": EXPECTED_CONDA_PREFIX,
            "device": str(device),
            "strict_cuda_only": STRICT_CUDA_ONLY,
            "model_loaded": model is not None,
            "tokenizer_loaded": tokenizer is not None,
        }
    )


@app.post("/generate")
def generate():
    log_line("[generate] request_received")
    payload = request.get_json(force=True, silent=False)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON body must be an object"}), 400

    try:
        log_line("[generate] build_messages_before")
        messages = build_messages(payload)
        log_line("[generate] build_messages_after")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    enable_thinking = parse_bool(payload.get("enable_thinking"), default=parse_bool(payload.get("thinking"), default=True))
    use_lora = parse_bool(payload.get("use_lora"), default=False)
    use_rag = parse_bool(payload.get("use_rag"), default=True)
    rag_top_k = int(payload.get("rag_top_k", 4))
    max_new_tokens = int(payload.get("max_new_tokens", 256))
    temperature = float(payload.get("temperature", 0.7))
    top_p = float(payload.get("top_p", 0.9))

    if use_lora:
        tokenizer, model, device = load_lora_model()
        log_line("[generate] use_lora_on")
    else:
        tokenizer, model, device = load_model()
        log_line("[generate] use_lora_off")

    retrieved_context = ""
    system_parts: List[str] = []
    if use_rag:
        log_line("[rag] retrieve_before")
        messages, retrieved_context, rag_prompt = inject_rag_context(messages, top_k=rag_top_k)
        if rag_prompt:
            system_parts.append(rag_prompt)
        log_line("[rag] retrieve_after")

    if not enable_thinking:
        system_parts.append(SYSTEM_PROMPT_NO_THINKING)
        log_line("[generate] thinking_off")
    else:
        log_line("[generate] thinking_on")

    messages = merge_system_messages(messages, system_parts)

    log_line("[generate] tokenize_before")
    prompt_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=enable_thinking,
    )
    inputs = tokenizer(prompt_text, return_tensors="pt").to(device)
    log_line("[generate] tokenize_after")

    with torch.inference_mode():
        log_line("[generate] generate_before")
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0,
            temperature=temperature,
            top_p=top_p,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
            use_cache=True,
        )
        log_line("[generate] generate_after")

    prompt_len = inputs["input_ids"].shape[-1]
    generated_ids = output_ids[0][prompt_len:]
    decoded = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
    log_line("[generate] response_ready")
    return jsonify(
        {
            "response": decoded,
            "model": BASE_MODEL_PATH,
            "adapter": LORA_ADAPTER_PATH,
            "use_lora": use_lora,
            "enable_thinking": enable_thinking,
            "use_rag": use_rag,
            "rag_top_k": rag_top_k,
            "retrieved_context": retrieved_context,
        }
    )


if __name__ == "__main__":
    log_line("[startup] server_boot")
    load_model()
    app.run(host="0.0.0.0", port=8005, debug=False)
