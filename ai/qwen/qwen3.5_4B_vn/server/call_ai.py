from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import torch


def call_model(
    *,
    tokenizer: Any,
    model: Any,
    device: Any,
    inputs: Dict[str, Any] | None = None,
    prompt_text: str | None = None,
    messages: List[Dict[str, str]] | None = None,
    enable_thinking: bool = False,
    max_new_tokens: int = 256,
    temperature: float = 0.7,
    top_p: float = 0.9,
    do_sample: bool | None = None,
    pad_token_id: int | None = None,
    eos_token_id: int | None = None,
    **generation_kwargs: Any,
) -> Any:
    """Build optional chat input and perform the single model generation call."""
    if inputs is None:
        if prompt_text is None:
            if messages is None:
                raise ValueError("messages, prompt_text, or inputs is required")
            prompt_text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=enable_thinking,
            )
        inputs = tokenizer(prompt_text, return_tensors="pt")

    inputs = inputs.to(device)
    if do_sample is None:
        do_sample = temperature > 0

    generate_kwargs: Dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "do_sample": do_sample,
        "pad_token_id": pad_token_id if pad_token_id is not None else tokenizer.pad_token_id,
        "eos_token_id": eos_token_id if eos_token_id is not None else tokenizer.eos_token_id,
        "use_cache": True,
        **generation_kwargs,
    }
    if do_sample:
        generate_kwargs.update({"temperature": temperature, "top_p": top_p})

    if prompt_text is not None:
        try:
            log_path = Path(__file__).resolve().parent / "log_api" / "call_ai_input.txt"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(prompt_text, encoding="utf-8")
        except Exception:
            pass

    with torch.inference_mode():
        output_ids = model.generate(**inputs, **generate_kwargs)

    try:
        prompt_len = inputs["input_ids"].shape[-1]
        generated_ids = output_ids[0][prompt_len:]

        output_text = tokenizer.decode(
            generated_ids,
            skip_special_tokens=True,
        ).strip()

        output_full_text = tokenizer.decode(
            output_ids[0],
            skip_special_tokens=False,
        ).strip()

        log_dir = Path(__file__).resolve().parent / "log_api"
        log_dir.mkdir(parents=True, exist_ok=True)

        output_log_path = log_dir / "call_ai_output.txt"
        output_log_path.write_text(output_text, encoding="utf-8")

        output_full_log_path = log_dir / "call_ai_output_full.txt"
        output_full_log_path.write_text(output_full_text, encoding="utf-8")

    except Exception:
        pass

    return output_ids