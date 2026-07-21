import os
import torch
# from flask import Flask, request, jsonify
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig  # không cần BitsAndBytesConfig nếu dùng phương án B
import gc
import time
# ─── 1) Thư mục cache ──────────────────────────────────────────────────────────
CACHE_D = "D:/huggingface/hub"     # nơi bạn đã download model/tokenizer
MODEL_NAME = "Qwen/Qwen3-4B-Thinking-2507"
CACHE_E = os.path.join("E:/huggingface/hub", MODEL_NAME)     # nơi lưu safetensors

HF_TOKEN = os.getenv("HF_TOKEN")


# ─── 3) Khởi tạo model/tokenizer & lưu safetensors (chạy 1 lần khi startup) ──
print("→ Initializing from D…")
os.environ["HF_HUB_CACHE"]    = CACHE_D
os.environ["TRANSFORMERS_CACHE"] = CACHE_D

bnb_conf = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",        # hoặc "fp4" tùy model/support
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16
)
gc.collect()
torch.cuda.empty_cache()

# load lần đầu từ D:
print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    cache_dir=CACHE_D,
    use_auth_token=HF_TOKEN
)

num_gpu_layers = 18
num_total_layers = 24


device_map = {
    "model.embed_tokens": 0,
    **{f"model.layers.{i}": 0 for i in range(num_gpu_layers)},
    **{f"model.layers.{i}": "cpu" for i in range(num_gpu_layers, num_total_layers)},
    "model.norm": "cpu",
    "lm_head": "cpu"
}

print("Loading model (legacy bitsandbytes kwargs)...")
# === Đây là phần sửa: truyền trực tiếp các kwargs bitsandbytes thay vì BitsAndBytesConfig ===

print("Attempting to load model in 4-bit ON GPU only...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    cache_dir="D:/huggingface/hub",
    device_map="cuda:0",       # ép toàn bộ lên GPU 0
    low_cpu_mem_usage=True,
    trust_remote_code=True,
    use_auth_token=HF_TOKEN,
    torch_dtype=torch.float16  # FP16
)
# chuyển sang safetensors trên E:
print(f"current attention impl: {model.config._attn_implementation}")

messages = [
    {
        "role": "user",
        "content": (
            'Phản hồi kết quả bắt buộc theo định dạng JSON, không giải thích thêm. '
            'Nội dung: "Người này đã tư vấn và đã scam tôi 50000 đồng, khi đã chuyển khoản xong họ đã block và chặn tôi và họ không cung cấp hoặc đưa tài khoản mxh mà tôi mua". '
            'Kết quả JSON phải có dạng: '
            '{"status": số nguyên 1 hoặc 0 (1 = nếu nội dung là tố cáo scam; 0 = không xác định), '
            '"jop_name": "thể loại của nội dung scam"}'
        )
    }
]

text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True
    )
model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

# conduct text completion
generated_ids = model.generate(
    **model_inputs,
    max_new_tokens=512
)
output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist() 

# parsing thinking content
try:
    # rindex finding 151668 (</think>)
    index = len(output_ids) - output_ids[::-1].index(2048)
except ValueError:
    index = 0

thinking_content = tokenizer.decode(output_ids[:index], skip_special_tokens=True).strip("\n")
content = tokenizer.decode(output_ids[index:], skip_special_tokens=True).strip("\n")

print("thinking content:", thinking_content)
print("content:", content)
