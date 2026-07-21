import math
import os
import sys
import random
from argparse import Namespace

import torch
from peft import LoraConfig, TaskType, get_peft_model
from transformers import Trainer, TrainingArguments, set_seed

from lora_data import DataCollatorForSFT, build_tokenizer, load_dataset, make_tokenized_dataset
from lora_model import get_target_modules, load_base_model, merge_adapter, resolve_device


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

    model, effective_use_4bit = load_base_model(args.base_model, args.use_4bit, args.checkpointing, args.cpu_offload)
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
        optim="paged_adamw_8bit" if effective_use_4bit else "adamw_torch_fused",
        report_to=[],
        remove_unused_columns=False,
        dataloader_num_workers=num_workers,
        dataloader_pin_memory=True,
        dataloader_persistent_workers=persistent_workers,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=DataCollatorForSFT(tokenizer.pad_token_id),
    )
    trainer.train()
    trainer.save_model(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    merge_adapter(args.base_model, adapter_dir, merged_dir, tokenizer)


def run_smoke_test(args: Namespace) -> None:
    tokenizer = build_tokenizer(args.base_model)
    rows = load_dataset(args.dataset)[:2]
    dataset = make_tokenized_dataset(tokenizer, rows, min(args.max_seq_length, 512))
    print(f"[smoke] dataset_size={len(dataset)}")
    model, _ = load_base_model(args.base_model, False, False)
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
