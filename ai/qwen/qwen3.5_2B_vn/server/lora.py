import os
from typing import Tuple

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


if os.name == "nt":
    BASE_MODEL_FALLBACK = r"D:\huggingface\hub\Qwen\Qwen3.5-2B"
    LORA_ADAPTER_FALLBACK = r"D:\huggingface\hub\Qwen\Qwen3.5-2B_vn_1\adapter"
else:
    BASE_MODEL_FALLBACK = "/root/model/Qwen/Qwen3.5-2B"
    LORA_ADAPTER_FALLBACK = "/root/model/Qwen/Qwen3.5-2B_vn_1/adapter"
BASE_MODEL_PATH = os.environ.get("QWEN_BASE_MODEL", BASE_MODEL_FALLBACK)
LORA_ADAPTER_PATH = os.environ.get("QWEN_LORA_ADAPTER", LORA_ADAPTER_FALLBACK)
STRICT_CUDA_ONLY = True

TOKENIZER = None
MODEL = None
DEVICE = None


def resolve_dtype() -> torch.dtype:
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


def resolve_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_lora_model() -> Tuple[AutoTokenizer, torch.nn.Module, torch.device]:
    global TOKENIZER, MODEL, DEVICE
    if TOKENIZER is not None and MODEL is not None and DEVICE is not None:
        return TOKENIZER, MODEL, DEVICE

    if not os.path.isdir(BASE_MODEL_PATH):
        raise FileNotFoundError(f"Base model path not found: {BASE_MODEL_PATH}")
    if not os.path.isdir(LORA_ADAPTER_PATH):
        raise FileNotFoundError(f"LoRA adapter path not found: {LORA_ADAPTER_PATH}")
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
    MODEL = PeftModel.from_pretrained(base_model, LORA_ADAPTER_PATH)
    MODEL = MODEL.to(DEVICE)

    if STRICT_CUDA_ONLY:
        offloaded = getattr(MODEL, "hf_device_map", None)
        if offloaded:
            bad_targets = {str(v) for v in offloaded.values() if str(v) not in {"0", "cuda:0"}}
            if bad_targets:
                raise RuntimeError(f"Model offloaded to non-CUDA devices: {sorted(bad_targets)}")

    MODEL.eval()
    return TOKENIZER, MODEL, DEVICE
