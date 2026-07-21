import os
import json
import sys
import shutil
import subprocess
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


SCRIPT_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, os.pardir, "config.json"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_config() -> dict[str, Any]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


CONFIG = load_config()


def is_windows() -> bool:
    return os.name == "nt"


def current_platform_key() -> str:
    return "windows" if is_windows() else "ubuntu"


def get_config_value(key: str, default: Any = None) -> Any:
    platform_cfg = CONFIG.get(current_platform_key(), {})
    if isinstance(platform_cfg, dict) and key in platform_cfg:
        return platform_cfg.get(key, default)
    return default


def _default_expected_prefix() -> str:
    fallback = r"D:\hustmedia\conda_envs\qwen" if is_windows() else "/root/miniconda3/envs/qwen"
    return str(get_config_value("expected_conda_prefix", fallback))


EXPECTED_CONDA_PREFIX = os.environ.get("QWEN_EXPECTED_CONDA_PREFIX", _default_expected_prefix())
IS_UBUNTU = os.name != "nt"
BASE_MODEL_FALLBACK = str(
    get_config_value(
        "base_model",
        r"D:\huggingface\hub\Qwen\Qwen3.5-4B" if is_windows() else "/root/model/Qwen/Qwen3.5-4B",
    )
)
LORA_ADAPTER_FALLBACK = str(
    get_config_value(
        "lora_adapter",
        r"D:\huggingface\hub\Qwen\Qwen3.5-4B_vn_1\adapter" if is_windows() else "/root/model/Qwen/Qwen3.5-4B_vn_1/adapter",
    )
)
BASE_MODEL_PATH = os.environ.get("QWEN_BASE_MODEL", BASE_MODEL_FALLBACK)
LORA_ADAPTER_PATH = os.environ.get("QWEN_LORA_ADAPTER", LORA_ADAPTER_FALLBACK)
STRICT_CUDA_ONLY = bool(get_config_value("strict_cuda_only", True))
DEFAULT_USE_4BIT = bool(get_config_value("default_use_4bit", True))
DEFAULT_CPU_OFFLOAD = bool(get_config_value("default_cpu_offload", True))
OFFLOAD_FOLDER = os.environ.get(
    "QWEN_OFFLOAD_DIR",
    str(get_config_value("offload_folder", os.path.join(SCRIPT_DIR, "offload"))),
)
APP_PORT = int(get_config_value("app_port", 8005))
KILL_PORT_ON_START = os.environ.get(
    "QWEN_KILL_PORT_ON_START",
    str(get_config_value("kill_port_on_start", "1")),
).strip().lower() not in {"0", "false", "no", "off"}
AUTO_RELOAD = os.environ.get(
    "QWEN_AUTO_RELOAD",
    str(get_config_value("auto_reload", "1")),
).strip().lower() not in {"0", "false", "no", "off"}
if os.name == "nt" and AUTO_RELOAD:
    KILL_PORT_ON_START = False
if IS_UBUNTU:
    AUTO_RELOAD = False
LOG_PATH = os.path.join(SCRIPT_DIR, "log.txt")
INOUT_JSON_DIR = os.path.join(SCRIPT_DIR, "log_api")
INOUT_JSON_PATH = os.path.join(INOUT_JSON_DIR, "inout_json.txt")
MAIN_INPUT_JSON_PATH = os.path.join(INOUT_JSON_DIR, "main_input.json")
LOG_MAX_LINES = int(get_config_value("log_max_lines", 100))
LOG_KEEP_FILES = int(get_config_value("log_keep_files", 3))
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


def log_inout_json(tag: str, data: Any) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    try:
        payload_text = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
    except TypeError:
        payload_text = json.dumps(str(data), ensure_ascii=False)

    entry = f"{ts} {tag}\n{payload_text}\n\n"
    os.makedirs(INOUT_JSON_DIR, exist_ok=True)
    with open(INOUT_JSON_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


def log_main_input(data: Any) -> None:
    try:
        os.makedirs(INOUT_JSON_DIR, exist_ok=True)
        with open(MAIN_INPUT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


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
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # noqa: E402

from lora import load_lora_model  # noqa: E402

from backend import register_backend_routes  # noqa: E402
from openclaw import create_openclaw_handler  # noqa: E402
from run_v4 import create_run_handler  # noqa: E402
from webservice import start_background_worker as start_webservice_background  # noqa: E402
import context as qwen_context  # noqa: E402


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


def parse_bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def should_use_4bit() -> bool:
    return parse_bool_env("QWEN_USE_4BIT", DEFAULT_USE_4BIT)


def should_cpu_offload() -> bool:
    return parse_bool_env("QWEN_CPU_OFFLOAD", DEFAULT_CPU_OFFLOAD)


def get_listener_pids(port: int) -> list[int]:
    current_pid = os.getpid()

    def add_pid(pids: list[int], pid: int) -> None:
        if pid <= 1 or pid == current_pid:
            return
        if pid not in pids:
            pids.append(pid)

    try:
        if os.name == "nt":
            result = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                text=True,
                check=True,
            )
            needle = f":{port} "
            pids: list[int] = []
            for line in result.stdout.splitlines():
                if needle not in line or "LISTENING" not in line:
                    continue
                parts = line.split()
                if not parts:
                    continue
                try:
                    pid = int(parts[-1])
                except ValueError:
                    continue
                add_pid(pids, pid)
            return pids

        for cmd in (
            ["fuser", "-n", "tcp", str(port)],
            ["ss", "-ltnp"],
            ["lsof", "-tiTCP:%d" % port, "-sTCP:LISTEN"],
        ):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            except Exception:
                continue

            pids: list[int] = []
            if cmd[0] == "fuser":
                for token in result.stdout.replace("\n", " ").split():
                    token = token.strip()
                    if token.endswith("c") or token.endswith("m"):
                        token = token[:-1]
                    try:
                        pid = int(token)
                    except ValueError:
                        continue
                    add_pid(pids, pid)
                if pids:
                    return pids

            for token in result.stdout.replace("\n", " ").split():
                if token.startswith("pid="):
                    raw = token.split("=", 1)[1].split(",", 1)[0]
                    try:
                        pid = int(raw)
                    except ValueError:
                        continue
                    add_pid(pids, pid)
                elif token.isdigit():
                    pid = int(token)
                    add_pid(pids, pid)
            if pids:
                return pids
    except Exception:
        return []

    return []


def kill_port(port: int, label: str) -> None:
    pids = get_listener_pids(port)
    if not pids:
        print(f"[port] {label} {port} is free", flush=True)
        return

    print(f"[port] {label} {port} already in use, stopping PID(s): {', '.join(map(str, pids))}", flush=True)
    for pid in pids:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True)
            else:
                if pid <= 1:
                    continue
                subprocess.run(["kill", "-9", str(pid)], capture_output=True, text=True)
        except Exception:
            pass


def build_model_load_kwargs(dtype: torch.dtype, use_4bit: bool, cpu_offload: bool) -> dict:
    kwargs: dict = {
        "trust_remote_code": True,
        "attn_implementation": "sdpa",
        "low_cpu_mem_usage": True,
    }

    if use_4bit:
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype,
        )
        kwargs["device_map"] = "auto"
    elif cpu_offload:
        kwargs["device_map"] = "auto"
    else:
        kwargs["device_map"] = {"": 0} if STRICT_CUDA_ONLY else "auto"
        kwargs["dtype"] = dtype

    if use_4bit or cpu_offload:
        kwargs["offload_folder"] = OFFLOAD_FOLDER
        kwargs["offload_state_dict"] = True

    return kwargs


def load_model():
    global TOKENIZER, MODEL, DEVICE
    if TOKENIZER is not None and MODEL is not None and DEVICE is not None:
        return TOKENIZER, MODEL, DEVICE

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")

    dtype = resolve_dtype()
    use_4bit = should_use_4bit()
    cpu_offload = should_cpu_offload()
    DEVICE = resolve_device()
    TOKENIZER = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True, use_fast=True)
    if TOKENIZER.pad_token is None:
        TOKENIZER.pad_token = TOKENIZER.eos_token
    TOKENIZER.padding_side = "left"

    load_kwargs = build_model_load_kwargs(dtype, use_4bit=use_4bit, cpu_offload=cpu_offload)
    try:
        base_model = AutoModelForCausalLM.from_pretrained(BASE_MODEL_PATH, **load_kwargs)
    except Exception as exc:
        if not use_4bit:
            raise
        log_line(f"[quant] 4bit_failed_fallback_cpu_offload: {exc}")
        use_4bit = False
        cpu_offload = True
        load_kwargs = build_model_load_kwargs(dtype, use_4bit=False, cpu_offload=True)
        base_model = AutoModelForCausalLM.from_pretrained(BASE_MODEL_PATH, **load_kwargs)
    MODEL = base_model
    if not use_4bit and not cpu_offload:
        MODEL = MODEL.to(DEVICE)

    if STRICT_CUDA_ONLY and not use_4bit and not cpu_offload:
        offloaded = getattr(MODEL, "hf_device_map", None)
        if offloaded:
            bad_targets = {str(v) for v in offloaded.values() if str(v) not in {"0", "cuda:0"}}
            if bad_targets:
                raise RuntimeError(f"Model offloaded to non-CUDA devices: {sorted(bad_targets)}")
    MODEL.eval()
    log_line("[startup] model_loaded")
    return TOKENIZER, MODEL, DEVICE


handle_openclaw_chat_completions = None
if create_openclaw_handler is not None:
    handle_openclaw_chat_completions = create_openclaw_handler(load_model, load_lora_model, log_line)

handle_agent_run = create_run_handler(load_model, load_lora_model, log_line)


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


def inject_rag_context(
    messages: List[Dict[str, str]],
    top_k: int,
    model_name: str = "",
) -> tuple[List[Dict[str, str]], str, str]:
    user_texts = [m["content"] for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str)]
    query = user_texts[-1] if user_texts else ""
    if not query.strip():
        return messages, "", ""
    retrieve_context = qwen_context.get_rag_retrieve_context(model_name)
    retrieval = retrieve_context(query, top_k=top_k, model_name=model_name)
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


@app.post("/search/ibm")
def ibm_search_test():
    """Run IBM Granite retrieval without running the Qwen answer stage."""
    try:
        payload = request.get_json(force=True, silent=False)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "JSON body must be an object"}), 400

        messages = payload.get("messages")
        if not isinstance(messages, list):
            messages = []

        query = payload.get("query") or payload.get("search_query")
        if not isinstance(query, str) or not query.strip():
            for message in reversed(messages):
                if isinstance(message, dict) and message.get("role") == "user":
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        query = content.strip()
                        break

        if not isinstance(query, str) or not query.strip():
            return jsonify({"ok": False, "error": "query or user messages is required"}), 400

        try:
            top_k = max(1, int(payload.get("top_k", payload.get("rag_top_k", 4))))
        except (TypeError, ValueError):
            top_k = 4

        model_name = str(payload.get("model", "Qwen3.5-4B-V4"))
        ibm_module = qwen_context._load_ibm_search_main_module()
        result = ibm_module.retrieve_context(
            question=query,
            top_k=top_k,
            model_name=model_name,
            messages=messages,
        )

        return jsonify(
            {
                "ok": True,
                "model": model_name,
                "query": result.query,
                "top_k": top_k,
                "results": result.contexts,
                "context": result.combined_context,
            }
        )
    except Exception as exc:
        log_line(f"[ibm_search_test] failed error={exc}")
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/generate")
def generate():
    log_line("[generate] request_received")
    payload = request.get_json(force=True, silent=False)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    log_main_input(payload)
    log_inout_json("[generate] inbound_json", payload)

    try:
        log_line("[generate] build_messages_before")
        messages = qwen_context.build_agent_messages(payload)
        log_line("[generate] build_messages_after")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    request_model_name = (
        (payload.get("model") if isinstance(payload.get("model"), str) else "")
        or (payload.get("ubuntu_model") if isinstance(payload.get("ubuntu_model"), str) else "")
        or (payload.get("x_openclaw_model") if isinstance(payload.get("x_openclaw_model"), str) else "")
        or "Qwen3.5-4B-V3"
    )
    enable_thinking = parse_bool(payload.get("enable_thinking"), default=parse_bool(payload.get("thinking"), default=True))
    use_lora = parse_bool(payload.get("use_lora"), default=False)
    use_rag = parse_bool(payload.get("use_rag"), default=not IS_UBUNTU)
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

    outbound_payload = {
        "messages": messages,
        "enable_thinking": enable_thinking,
        "use_lora": use_lora,
        "use_rag": use_rag,
        "rag_top_k": rag_top_k,
        "max_new_tokens": max_new_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }
    log_line("[generate] outbound_json " + json.dumps(outbound_payload, ensure_ascii=False, sort_keys=True))

    retrieved_context = ""
    if use_rag:
        log_line("[rag] retrieve_before")
        messages, retrieved_context, _, rag_search_query = qwen_context.prepare_rag_context(
            messages,
            top_k=rag_top_k,
            enabled=True,
            model_name=request_model_name,
            tokenizer=tokenizer,
            model=model,
            device=device,
        )
        log_line("[rag] search_query " + json.dumps({"query": rag_search_query}, ensure_ascii=False))
        log_line("[rag] retrieve_after")

    extra_system_parts: List[str] = []
    if not enable_thinking:
        extra_system_parts.append(SYSTEM_PROMPT_NO_THINKING)
        log_line("[generate] thinking_off")
    else:
        log_line("[generate] thinking_on")

    log_line("[generate] generate_before")
    generation = qwen_context.generate_rag_response(
        messages=messages,
        context_text=retrieved_context,
        tokenizer=tokenizer,
        model=model,
        device=device,
        model_name=request_model_name,
        enable_thinking=enable_thinking,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        extra_system_parts=extra_system_parts,
    )
    log_line("[generate] generate_after")
    decoded = generation["response"]
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


@app.post("/chat/completions")
@app.post("/v1/chat/completions")
def openclaw_chat_completions():
    if handle_openclaw_chat_completions is None:
        return jsonify({"ok": False, "error": "OpenClaw/RAG is disabled on Ubuntu."}), 503
    payload = request.get_json(force=True, silent=False)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "JSON body must be an object"}), 400
    log_main_input(payload)
    log_inout_json("[chat/completions] inbound_json", payload)
    result = handle_openclaw_chat_completions(payload, request.headers)
    return jsonify(result)


register_backend_routes(app, handle_openclaw_chat_completions, handle_agent_run)


def should_preload_model() -> bool:
    if not AUTO_RELOAD:
        return True

    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def should_manage_port() -> bool:
    if not AUTO_RELOAD:
        return True
    return False


def warmup_ibm_rag_if_needed() -> None:
    model_name = str(get_config_value("model", "Qwen3.5-4B-V4"))
    try:
        qwen_context.warmup_rag_index(model_name=model_name)
        log_line(f"[startup] rag_warmup_done model={model_name}")
    except Exception as exc:
        log_line(f"[startup] rag_warmup_failed model={model_name} error={exc}")


def preload_lora_if_needed() -> None:
    if not parse_bool_env("QWEN_PRELOAD_LORA", True):
        return
    try:
        load_lora_model()
        log_line("[startup] lora_loaded")
    except Exception as exc:
        log_line(f"[startup] lora_load_failed error={exc}")


if __name__ == "__main__":
    log_line("[startup] server_boot")
    if KILL_PORT_ON_START and should_manage_port():
        kill_port(APP_PORT, "server")
    if should_preload_model():
        load_model()
        preload_lora_if_needed()
        warmup_ibm_rag_if_needed()
        start_webservice_background()
    app.run(host="0.0.0.0", port=APP_PORT, debug=False, use_reloader=AUTO_RELOAD)
