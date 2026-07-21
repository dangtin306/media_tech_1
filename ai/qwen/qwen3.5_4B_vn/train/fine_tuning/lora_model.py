from typing import Tuple
from pathlib import Path
import os
import sys

import importlib.util
import torch
from peft import PeftModel, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, BitsAndBytesConfig


def resolve_dtype() -> torch.dtype:
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


def resolve_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def resolve_device_map():
    if torch.cuda.is_available():
        return {"": "cuda:0"}
    return {"": "cpu"}


def resolve_max_memory(cpu_offload: bool):
    if not (cpu_offload and torch.cuda.is_available()):
        return None
    total_gb = int(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3))
    if sys.platform.startswith("win"):
        reserve_gb = 1.0
    else:
        reserve_gb = 1.5
    gpu_cap = max(4.0, total_gb - reserve_gb)
    cpu_cap = os.environ.get("QWEN_CPU_MAX_MEMORY", "48GiB")
    return {0: f"{gpu_cap:.1f}GiB", "cpu": cpu_cap}


def get_target_modules() -> list[str]:
    return [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ]


def load_base_model(
    base_model: str,
    use_4bit: bool,
    enable_checkpointing: bool,
    cpu_offload: bool = True,
    runtime_offload: str = "none",
) -> Tuple[torch.nn.Module, bool]:
    bnb_available = importlib.util.find_spec("bitsandbytes") is not None
    if use_4bit and not bnb_available:
        print("[warn] bitsandbytes not installed, falling back to non-4bit loading.")
        use_4bit = False
    use_runtime_offload = runtime_offload == "deepspeed"
    offload_folder = None
    max_memory = None if use_runtime_offload else resolve_max_memory(cpu_offload)
    if max_memory is not None:
        print(
            "[offload] auto "
            f"max_memory={max_memory} "
            "offload_target=cpu_only "
            "offload_state_dict=True offload_buffers=True low_cpu_mem_usage=True"
        )
    if use_runtime_offload:
        print("[runtime_offload] deepspeed active optimizer/state offload will be handled by Trainer/DeepSpeed.")
    if use_4bit:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=resolve_dtype(),
        )
        print(
            "[4bit] enabled "
            f"quant_type={quant_config.bnb_4bit_quant_type} "
            f"double_quant={quant_config.bnb_4bit_use_double_quant} "
            f"compute_dtype={quant_config.bnb_4bit_compute_dtype} "
            f"cpu_offload={cpu_offload}"
        )
        load_kwargs = dict(
            trust_remote_code=True,
            dtype=resolve_dtype(),
            low_cpu_mem_usage=True,
            quantization_config=quant_config,
            attn_implementation="sdpa",
        )
        if max_memory is not None:
            load_kwargs.update(
                device_map="auto",
                max_memory=max_memory,
                offload_state_dict=True,
                offload_buffers=True,
            )
        else:
            load_kwargs.update(device_map=resolve_device_map())
        model = AutoModelForCausalLM.from_pretrained(base_model, **load_kwargs)
        gc_kwargs = {"use_reentrant": False} if enable_checkpointing else None
        model = prepare_model_for_kbit_training(
            model,
            use_gradient_checkpointing=enable_checkpointing,
            gradient_checkpointing_kwargs=gc_kwargs,
        )
    else:
        load_kwargs = dict(
            trust_remote_code=True,
            dtype=resolve_dtype(),
            low_cpu_mem_usage=True,
            attn_implementation="sdpa",
        )
        if max_memory is not None:
            load_kwargs.update(
                device_map="auto",
                max_memory=max_memory,
                offload_state_dict=True,
                offload_buffers=True,
            )
        else:
            load_kwargs.update(device_map=resolve_device_map())
        model = AutoModelForCausalLM.from_pretrained(base_model, **load_kwargs)
    model.config.use_cache = False
    if enable_checkpointing and not use_4bit:
        # Avoid PyTorch's reentrant checkpointing warning on newer versions.
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    return model, use_4bit


def merge_adapter(base_model: str, adapter_dir: str, merged_dir: str, tokenizer) -> None:
    merge_on_cpu = not sys.platform.startswith("win")
    dtype = torch.float32 if merge_on_cpu else resolve_dtype()
    device_map = {"": "cpu"} if merge_on_cpu else resolve_device_map()
    if merge_on_cpu:
        print("[merge] loading base model on CPU to avoid post-train GPU OOM.")
    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        trust_remote_code=True,
        dtype=dtype,
        low_cpu_mem_usage=True,
        device_map=device_map,
    )
    peft_model = PeftModel.from_pretrained(base, adapter_dir)
    merged = peft_model.merge_and_unload()
    merged.save_pretrained(merged_dir, safe_serialization=True)
    tokenizer.save_pretrained(merged_dir)
