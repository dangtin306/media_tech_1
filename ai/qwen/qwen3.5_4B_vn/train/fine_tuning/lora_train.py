import math
import os
import sys
import random
import json
import time
import importlib.util
import shutil
import contextlib
from argparse import Namespace
from pathlib import Path

import torch
from peft import LoraConfig, TaskType, get_peft_model
from transformers import Trainer, TrainerCallback, TrainingArguments, set_seed
from transformers.trainer_pt_utils import LengthGroupedSampler

from lora_data import DataCollatorForSFT, build_tokenizer, load_dataset, make_tokenized_dataset
from lora_model import get_target_modules, load_base_model, merge_adapter, resolve_device


class MemoryAwareTrainer(Trainer):
    def _activation_offload_context(self):
        if not torch.cuda.is_available():
            return contextlib.nullcontext()
        return torch.autograd.graph.save_on_cpu(pin_memory=True)

    def _get_train_sampler(self, train_dataset=None):
        dataset = train_dataset if train_dataset is not None else self.train_dataset
        if dataset is None:
            return None
        if not hasattr(dataset, "examples"):
            return super()._get_train_sampler(train_dataset)
        lengths = [int(example.get("length", len(example["input_ids"]))) for example in dataset.examples]
        return LengthGroupedSampler(
            batch_size=self.args.train_batch_size,
            dataset=dataset,
            lengths=lengths,
            model_input_name="input_ids",
        )

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        model_inputs = dict(inputs)
        with self._activation_offload_context():
            return super().compute_loss(
                model,
                model_inputs,
                return_outputs=return_outputs,
                num_items_in_batch=num_items_in_batch,
            )


class ProgressEtaCallback(TrainerCallback):
    def __init__(self) -> None:
        self._start_time: float | None = None

    def on_train_begin(self, args, state, control, **kwargs):
        self._start_time = time.time()
        return control

    def on_log(self, args, state, control, logs=None, **kwargs):
        if self._start_time is None:
            return control

        total_steps = int(getattr(state, "max_steps", 0) or 0)
        current_step = int(getattr(state, "global_step", 0) or 0)
        if total_steps <= 0 or current_step <= 0:
            return control

        elapsed = max(0.0, time.time() - self._start_time)
        avg_step = elapsed / max(1, current_step)
        steps_left = max(0, total_steps - current_step)
        eta_seconds = int(round(avg_step * steps_left))
        eta_hours, rem = divmod(eta_seconds, 3600)
        eta_minutes, eta_seconds = divmod(rem, 60)
        progress = (current_step / total_steps) * 100.0
        print(
            f"[eta] step={current_step}/{total_steps} progress={progress:.2f}% "
            f"elapsed={int(elapsed)}s avg_step={avg_step:.2f}s "
            f"remaining={steps_left} eta={eta_hours:02d}:{eta_minutes:02d}:{eta_seconds:02d}",
            flush=True,
        )
        return control


def _select_rows(rows, seed: int, sample_ratio: float, max_samples: int):
    if max_samples and max_samples > 0:
        sample_size = min(max_samples, len(rows))
        if sample_size < len(rows):
            return random.Random(seed).sample(rows, sample_size)
        return rows[:sample_size]
    if sample_ratio and 0 < sample_ratio < 1:
        sample_size = max(1, int(len(rows) * sample_ratio))
        if sample_size < len(rows):
            return random.Random(seed).sample(rows, sample_size)
    return rows


def _resolve_runtime_offload(args: Namespace) -> str:
    if args.runtime_offload == "none":
        return "none"
    if sys.platform.startswith("win"):
        return "none"
    if not (torch.cuda.is_available() and args.cpu_offload):
        return "none"
    if args.runtime_offload == "deepspeed":
        return "deepspeed"
    return "deepspeed"


def _build_deepspeed_config(
    adapter_dir: str,
    effective_use_4bit: bool,
    train_batch_size: int,
    grad_accum: int,
    learning_rate: float,
    weight_decay: float,
    warmup_steps: int,
) -> str:
    stage = 2 if effective_use_4bit else 3
    zero_optimization = {
        "stage": stage,
        "offload_optimizer": {"device": "cpu", "pin_memory": True},
        "contiguous_gradients": True,
        "overlap_comm": False,
        "reduce_bucket_size": 2e7,
        "allgather_bucket_size": 2e7,
    }
    if stage == 3:
        zero_optimization["offload_param"] = {"device": "cpu", "pin_memory": True}
        zero_optimization["stage3_gather_16bit_weights_on_model_save"] = True

    config = {
        "train_micro_batch_size_per_gpu": train_batch_size,
        "gradient_accumulation_steps": grad_accum,
        "gradient_clipping": 1.0,
        "zero_optimization": zero_optimization,
        "optimizer": {
            "type": "AdamW",
            "params": {
                "lr": learning_rate,
                "betas": [0.9, 0.999],
                "eps": 1e-8,
                "weight_decay": weight_decay,
            },
        },
        "scheduler": {
            "type": "WarmupDecayLR",
            "params": {
                "total_num_steps": "auto",
                "warmup_min_lr": 0,
                "warmup_max_lr": learning_rate,
                "warmup_num_steps": warmup_steps,
            },
        },
        "zero_force_ds_cpu_optimizer": False,
        "bf16": {"enabled": torch.cuda.is_available() and torch.cuda.is_bf16_supported()},
        "fp16": {"enabled": torch.cuda.is_available() and not torch.cuda.is_bf16_supported()},
        "steps_per_print": 2000,
        "wall_clock_breakdown": False,
    }
    config_path = os.path.join(adapter_dir, "deepspeed_zero_offload.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config_path


def _resolve_deepspeed_config(args: Namespace, adapter_dir: str, effective_use_4bit: bool, warmup_steps: int) -> str | None:
    runtime_offload = _resolve_runtime_offload(args)
    if runtime_offload != "deepspeed":
        return None
    if importlib.util.find_spec("deepspeed") is None:
        print("[warn] runtime_offload=deepspeed requested but deepspeed is not installed; continuing without runtime offload.")
        return None
    nvcc_path = shutil.which("nvcc")
    if nvcc_path is None:
        print("[warn] nvcc not found on PATH; cannot use DeepSpeed runtime offload safely. Continuing without runtime offload.")
        return None
    else:
        cuda_home = str(Path(nvcc_path).resolve().parent.parent)
        os.environ["CUDA_HOME"] = cuda_home
        os.environ["CUDA_PATH"] = cuda_home
        os.environ["PATH"] = str(Path(cuda_home) / "bin") + os.pathsep + os.environ.get("PATH", "")
        print(f"[runtime_offload] CUDA_HOME={cuda_home}")
    os.environ.setdefault("MASTER_ADDR", "127.0.0.1")
    os.environ.setdefault("MASTER_PORT", "29500")
    os.environ.setdefault("RANK", "0")
    os.environ.setdefault("LOCAL_RANK", "0")
    os.environ.setdefault("WORLD_SIZE", "1")
    config_path = _build_deepspeed_config(
        adapter_dir=adapter_dir,
        effective_use_4bit=effective_use_4bit,
        train_batch_size=args.train_batch_size,
        grad_accum=args.grad_accum,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        warmup_steps=warmup_steps,
    )
    stage = 2 if effective_use_4bit else 3
    print(f"[runtime_offload] deepspeed zero_stage={stage} config={config_path}")
    return config_path


def train_adapter(args: Namespace) -> None:
    set_seed(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)
    adapter_dir = os.path.join(args.output_dir, "adapter")
    merged_dir = os.path.join(args.output_dir, "merged")
    os.makedirs(adapter_dir, exist_ok=True)
    os.makedirs(merged_dir, exist_ok=True)

    tokenizer = build_tokenizer(args.base_model)
    rows = load_dataset(args.dataset)
    rows = _select_rows(rows, args.seed, args.sample_ratio, args.max_samples)
    dataset = make_tokenized_dataset(tokenizer, rows, args.max_seq_length)

    runtime_offload = _resolve_runtime_offload(args)
    model, effective_use_4bit = load_base_model(
        args.base_model,
        args.use_4bit,
        args.checkpointing,
        args.cpu_offload,
        runtime_offload=runtime_offload,
    )
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=get_target_modules(),
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    total_steps = max(1, math.ceil((len(dataset) / max(1, args.train_batch_size)) / max(1, args.grad_accum)) * max(1, math.ceil(args.epochs)))
    warmup_steps = max(1, int(total_steps * 0.03))
    num_workers = 0 if sys.platform == "win32" else 4
    persistent_workers = num_workers > 0
    deepspeed_config = _resolve_deepspeed_config(args, adapter_dir, effective_use_4bit, warmup_steps)
    optim_name = "paged_adamw_8bit" if effective_use_4bit and deepspeed_config is None else "adamw_torch"

    training_args = TrainingArguments(
        output_dir=adapter_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.train_batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.learning_rate,
        warmup_steps=warmup_steps,
        weight_decay=args.weight_decay,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=2,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
        optim=optim_name,
        report_to=[],
        remove_unused_columns=False,
        dataloader_num_workers=num_workers,
        dataloader_pin_memory=True,
        dataloader_persistent_workers=persistent_workers,
        length_column_name="length",
        torch_empty_cache_steps=args.empty_cache_steps if args.empty_cache_steps > 0 else None,
        deepspeed=deepspeed_config,
    )

    trainer = MemoryAwareTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=DataCollatorForSFT(tokenizer.pad_token_id),
    )
    trainer.add_callback(ProgressEtaCallback())
    trainer.train()
    trainer.save_model(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    merge_adapter(args.base_model, adapter_dir, merged_dir, tokenizer)


def run_smoke_test(args: Namespace) -> None:
    tokenizer = build_tokenizer(args.base_model)
    rows = load_dataset(args.dataset)[:2]
    dataset = make_tokenized_dataset(tokenizer, rows, min(args.max_seq_length, 512))
    print(f"[smoke] dataset_size={len(dataset)}")
    model, _ = load_base_model(args.base_model, args.use_4bit, args.checkpointing, args.cpu_offload)
    sample = dataset[0]
    device = next(model.parameters()).device
    batch = {
        key: torch.tensor([sample[key]], dtype=torch.long).to(device)
        for key in ("input_ids", "attention_mask", "labels")
    }
    model.train()
    device_type = "cuda" if torch.cuda.is_available() else "cpu"
    autocast_dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float32
    with torch.autocast(device_type=device_type, dtype=autocast_dtype, enabled=torch.cuda.is_available()):
        out = model(**batch)
    loss = out.loss
    print(f"[smoke] forward_ok loss={float(loss.detach().cpu())}")
