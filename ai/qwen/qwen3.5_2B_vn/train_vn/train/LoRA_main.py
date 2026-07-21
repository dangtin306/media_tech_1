import argparse
import os
from pathlib import Path

from lora_env import ensure_conda_env
from lora_train import run_smoke_test, train_adapter


SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_DIR = SCRIPT_DIR.parent / "datasheet"
BASE_MODEL_DEFAULT = r"D:\huggingface\hub\Qwen\Qwen3.5-2B"
OUTPUT_DIR_DEFAULT = r"D:\huggingface\hub\Qwen\Qwen3.5-2B_vn_1"
if os.name != "nt":
    BASE_MODEL_DEFAULT = "/root/model/Qwen/Qwen3.5-2B"
    OUTPUT_DIR_DEFAULT = "/root/model/Qwen/Qwen3.5-2B_vn_1"
DATASET_DEFAULT = str(DATASET_DIR / "LoRA.json")


def resolve_dataset_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or path.parent != Path("."):
        return str(path)
    return str(DATASET_DIR / path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train LoRA on Qwen3.5-2B with a Qwen-style JSON/JSONL dataset.")
    parser.add_argument("--base_model", default=BASE_MODEL_DEFAULT, help="Base model directory.")
    parser.add_argument("--dataset", default=DATASET_DEFAULT, help="Dataset path in Qwen-style JSON or JSONL format.")
    parser.add_argument("--output_dir", default=OUTPUT_DIR_DEFAULT, help="Directory to store adapter and merged model.")
    parser.add_argument("--max_seq_length", type=int, default=1024, help="Maximum token length per example.")
    parser.add_argument("--epochs", type=float, default=3.0, help="Training epochs.")
    parser.add_argument("--train_batch_size", type=int, default=2, help="Per-device train batch size.")
    parser.add_argument("--grad_accum", type=int, default=1, help="Gradient accumulation steps.")
    parser.add_argument("--learning_rate", type=float, default=2e-4, help="Learning rate.")
    parser.add_argument("--weight_decay", type=float, default=0.0, help="Weight decay.")
    parser.add_argument("--lora_r", type=int, default=16, help="LoRA rank.")
    parser.add_argument("--lora_alpha", type=int, default=32, help="LoRA alpha.")
    parser.add_argument("--lora_dropout", type=float, default=0.05, help="LoRA dropout.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--sample_ratio", type=float, default=1.0, help="Randomly sample this fraction of the dataset before training. 1.0 means use all samples.")
    parser.add_argument("--max_samples", type=int, default=0, help="Limit training to the first N samples. 0 means use all samples.")
    parser.add_argument("--use_4bit", action="store_true", help="Load the base model in 4-bit for QLoRA-style training.")
    parser.add_argument("--no_4bit", dest="use_4bit", action="store_false", help="Disable 4-bit loading.")
    parser.set_defaults(use_4bit=False)
    parser.add_argument("--cpu_offload", action="store_true", help="Allow weights to spill to CPU RAM when GPU memory is tight.")
    parser.add_argument("--no_cpu_offload", dest="cpu_offload", action="store_false", help="Keep all model weights on GPU when possible.")
    parser.set_defaults(cpu_offload=True)
    parser.add_argument("--checkpointing", action="store_true", help="Enable gradient checkpointing for lower VRAM use but slower training.")
    parser.add_argument("--smoke_test", action="store_true", help="Only validate dataset loading and one forward pass.")
    args = parser.parse_args()
    args.dataset = resolve_dataset_path(args.dataset)
    return args


def main() -> None:
    ensure_conda_env()
    args = parse_args()
    if args.smoke_test:
        run_smoke_test(args)
        return
    train_adapter(args)


if __name__ == "__main__":
    main()
