import os
import sys
from typing import Tuple

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


if sys.platform.startswith("win"):
    BASE_MODEL_FALLBACK = r"D:\huggingface\hub\Qwen\Qwen3.5-4B"
    LORA_ADAPTER_FALLBACK = r"D:\huggingface\hub\Qwen\Qwen3.5-4B_vn_1\adapter"
else:
    BASE_MODEL_FALLBACK = "/root/model/Qwen/Qwen3.5-4B"
    LORA_ADAPTER_FALLBACK = "/root/model/Qwen/Qwen3.5-4B_vn_1/adapter"
BASE_MODEL_PATH = os.environ.get("QWEN_BASE_MODEL", BASE_MODEL_FALLBACK)
LORA_ADAPTER_PATH = os.environ.get("QWEN_LORA_ADAPTER", LORA_ADAPTER_FALLBACK)
STRICT_CUDA_ONLY = True
DEFAULT_USE_4BIT = os.name != "nt"
DEFAULT_CPU_OFFLOAD = os.name != "nt"
OFFLOAD_FOLDER = os.environ.get("QWEN_OFFLOAD_DIR", os.path.join(os.path.dirname(__file__), "offload"))

TOKENIZER = None
MODEL = None
DEVICE = None


def _get_base_model():
    main_module = sys.modules.get("main") or sys.modules.get("__main__")
    if main_module is not None and hasattr(main_module, "load_model"):
        return main_module.load_model()

    from importlib import util as importlib_util
    from pathlib import Path

    main_path = Path(__file__).resolve().with_name("main.py")
    spec = importlib_util.spec_from_file_location("media_tech_ai_qwen_server_main", main_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load server main module: {main_path}")
    module = importlib_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_model()


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


def load_lora_model() -> Tuple[AutoTokenizer, torch.nn.Module, torch.device]:
    global TOKENIZER, MODEL, DEVICE
    if TOKENIZER is not None and MODEL is not None and DEVICE is not None:
        return TOKENIZER, MODEL, DEVICE

    if not os.path.isdir(LORA_ADAPTER_PATH):
        raise FileNotFoundError(f"LoRA adapter path not found: {LORA_ADAPTER_PATH}")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")

    TOKENIZER, base_model, DEVICE = _get_base_model()
    if TOKENIZER is None or base_model is None or DEVICE is None:
        raise RuntimeError("Base model is not available for LoRA loading.")

    use_4bit = should_use_4bit()
    cpu_offload = should_cpu_offload()
    MODEL = PeftModel.from_pretrained(base_model, LORA_ADAPTER_PATH)

    if not use_4bit and not cpu_offload:
        MODEL = MODEL.to(DEVICE)

    if STRICT_CUDA_ONLY and not use_4bit and not cpu_offload:
        offloaded = getattr(MODEL, "hf_device_map", None)
        if offloaded:
            bad_targets = {str(v) for v in offloaded.values() if str(v) not in {"0", "cuda:0"}}
            if bad_targets:
                raise RuntimeError(f"Model offloaded to non-CUDA devices: {sorted(bad_targets)}")

    MODEL.eval()
    return TOKENIZER, MODEL, DEVICE
