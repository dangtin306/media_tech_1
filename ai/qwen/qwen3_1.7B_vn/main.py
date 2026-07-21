import os
import sys
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from peft import PeftModel
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: peft. Install it with `pip install peft` "
        "before running this script."
    ) from exc


if os.name == "nt":
    BASE_MODEL_DIR = Path(r"D:\huggingface\hub\Qwen\Qwen3-1.7B")
    ADAPTER_DIR = Path(r"D:\huggingface\hub\Qwen\Qwen3-1.7B-VN-AI4LI_SFT")
    CACHE_DIR = Path(r"D:\huggingface\hub")
else:
    BASE_MODEL_DIR = Path("/root/model/Qwen/Qwen3-1.7B")
    ADAPTER_DIR = Path("/root/model/Qwen/Qwen3-1.7B-VN-AI4LI_SFT")
    CACHE_DIR = Path("/root/model/Qwen")
CUDA_DEVICE = torch.device("cuda:0")


def build_model():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available in the current environment.")
    if not BASE_MODEL_DIR.exists():
        raise FileNotFoundError(f"Base model folder not found: {BASE_MODEL_DIR}")
    if not ADAPTER_DIR.exists():
        raise FileNotFoundError(f"Adapter folder not found: {ADAPTER_DIR}")

    os.environ.setdefault("HF_HOME", str(CACHE_DIR))
    os.environ.setdefault("HF_HUB_CACHE", str(CACHE_DIR))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(CACHE_DIR))

    tokenizer = AutoTokenizer.from_pretrained(
        str(BASE_MODEL_DIR),
        cache_dir=str(CACHE_DIR),
        trust_remote_code=True,
        use_fast=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        str(BASE_MODEL_DIR),
        trust_remote_code=True,
        low_cpu_mem_usage=True,
        torch_dtype=torch.float16,
        device_map={"": "cuda:0"},
    )
    model = PeftModel.from_pretrained(model, str(ADAPTER_DIR))
    model = model.to(CUDA_DEVICE)

    first_param_device = next(model.parameters()).device
    if first_param_device.type != "cuda":
        raise RuntimeError(f"Model did not load onto CUDA, got {first_param_device}")
    model.eval()
    return tokenizer, model


@torch.inference_mode()
def generate_reply(tokenizer, model, prompt: str, max_new_tokens: int = 128) -> str:
    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=True,
    )
    inputs = tokenizer(text, return_tensors="pt")
    inputs = {k: v.to(CUDA_DEVICE) for k, v in inputs.items()}

    generation_config = model.generation_config
    if hasattr(generation_config, "clone"):
        generation_config = generation_config.clone()
    for attr in ("temperature", "top_p", "top_k"):
        if hasattr(generation_config, attr):
            setattr(generation_config, attr, None)

    output = model.generate(
        **inputs,
        generation_config=generation_config,
        max_new_tokens=max_new_tokens,
        do_sample=False,
    )
    input_len = inputs["input_ids"].shape[-1]
    return tokenizer.decode(output[0][input_len:], skip_special_tokens=True).strip()


def main():
    tokenizer, model = build_model()
    prompt = (
        "Trả lời ngắn gọn bằng tiếng Việt, nhưng hãy nghĩ kỹ trước khi trả lời: "
        "Model này có thể dùng để làm gì?"
    )
    reply = generate_reply(tokenizer, model, prompt)
    print(reply)


if __name__ == "__main__":
    main()
