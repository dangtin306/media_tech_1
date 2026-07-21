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

MODEL_DIR = Path(r"D:\huggingface\hub\Qwen\Qwen3.5-2B")
CUDA_DEVICE = torch.device("cuda:0")


def build_model():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available in the current environment.")
    if not MODEL_DIR.exists():
        raise FileNotFoundError(f"Model folder not found: {MODEL_DIR}")

    tokenizer = AutoTokenizer.from_pretrained(
        str(MODEL_DIR),
        trust_remote_code=True,
        use_fast=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        str(MODEL_DIR),
        trust_remote_code=True,
        low_cpu_mem_usage=True,
        torch_dtype=torch.float16,
        device_map={"": "cuda:0"},
    )
    model = model.to(CUDA_DEVICE)

    first_param_device = next(model.parameters()).device
    if first_param_device.type != "cuda":
        raise RuntimeError(f"Model did not load onto CUDA, got {first_param_device}")

    model.eval()
    return tokenizer, model


@torch.inference_mode()
def generate_reply(tokenizer, model, prompt: str, max_new_tokens: int = 256) -> str:
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=True,
    )
    inputs = tokenizer(text, return_tensors="pt")
    inputs = {k: v.to(CUDA_DEVICE) for k, v in inputs.items()}

    output = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
    )
    input_len = inputs["input_ids"].shape[-1]
    return tokenizer.decode(output[0][input_len:], skip_special_tokens=True).strip()


def main():
    tokenizer, model = build_model()
    print(f"model device: {next(model.parameters()).device}")
    prompt = "Trả lời ngắn gọn bằng tiếng Việt, hãy nghĩ kỹ trước khi trả lời: model này dùng để làm gì?"
    print(generate_reply(tokenizer, model, prompt))


if __name__ == "__main__":
    main()
