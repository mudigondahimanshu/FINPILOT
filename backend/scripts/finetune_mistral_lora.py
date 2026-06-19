"""Mistral-7B LoRA fine-tuning for financial Q&A (Phase 3.5).

This script fine-tunes Mistral-7B-Instruct-v0.2 with QLoRA (4-bit quantisation +
Low-Rank Adaptation) on a financial Q&A dataset. The resulting adapter can replace
the template fallback in app/ml/rag.py for fully on-premise inference without
an Anthropic API key.

Requirements (GPU instance, ≥24 GB VRAM recommended — e.g. A10G / L4):
  pip install transformers==4.41.0 peft==0.11.1 bitsandbytes==0.43.1 \
              trl==0.9.4 datasets==2.19.1 accelerate==0.30.1 torch==2.3.0

Dataset format (JSONL, one instruction per line):
  {"instruction": "What is a SIP?", "output": "SIP (Systematic Investment Plan)…"}

Usage:
  python scripts/finetune_mistral_lora.py \
      --dataset data/financial_qa.jsonl \
      --output_dir models/mistral_lora \
      --epochs 3

The adapter is saved in HuggingFace format and can be loaded via:
  from peft import PeftModel
  model = PeftModel.from_pretrained(base_model, "models/mistral_lora")
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

BASE_MODEL = "mistralai/Mistral-7B-Instruct-v0.2"
DEFAULT_OUTPUT = "models/mistral_lora"
MAX_SEQ_LEN = 1024
LORA_R = 16          # LoRA rank
LORA_ALPHA = 32      # LoRA scaling factor
LORA_DROPOUT = 0.05


def load_dataset_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def format_prompt(example: dict) -> str:
    """Convert a Q&A pair to Mistral instruct format."""
    return (
        f"<s>[INST] {example['instruction']} [/INST] "
        f"{example['output']} </s>"
    )


def run_training(
    dataset_path: Path,
    output_dir: Path,
    epochs: int = 3,
    batch_size: int = 4,
    lr: float = 2e-4,
) -> None:
    try:
        import torch  # noqa: PLC0415
        from datasets import Dataset  # noqa: PLC0415
        from peft import LoraConfig, TaskType, get_peft_model  # noqa: PLC0415
        from transformers import (  # noqa: PLC0415
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            TrainingArguments,
        )
        from trl import SFTTrainer  # noqa: PLC0415
    except ImportError as exc:
        print(f"Missing dependency: {exc}")
        print("Install: pip install transformers peft bitsandbytes trl datasets accelerate torch")
        return

    print(f"Loading base model: {BASE_MODEL}")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model.config.use_cache = False
    model.config.pretraining_tp = 1

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load + format dataset
    raw = load_dataset_jsonl(dataset_path)
    hf_dataset = Dataset.from_list([{"text": format_prompt(e)} for e in raw])
    print(f"Dataset size: {len(hf_dataset)} examples")

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        optim="paged_adamw_32bit",
        save_steps=100,
        logging_steps=25,
        learning_rate=lr,
        weight_decay=0.001,
        fp16=False,
        bf16=True,
        max_grad_norm=0.3,
        max_steps=-1,
        warmup_ratio=0.03,
        group_by_length=True,
        lr_scheduler_type="cosine",
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=hf_dataset,
        dataset_text_field="text",
        tokenizer=tokenizer,
        args=training_args,
        max_seq_length=MAX_SEQ_LEN,
        packing=False,
    )

    print("Starting LoRA fine-tuning…")
    trainer.train()

    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    print(f"LoRA adapter saved → {output_dir}")
    print(f"\nTo use: load via PeftModel.from_pretrained(base_model, '{output_dir}')")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune Mistral-7B with LoRA on financial Q&A")
    parser.add_argument("--dataset", type=Path, default=Path("data/financial_qa.jsonl"))
    parser.add_argument("--output_dir", type=Path, default=Path(DEFAULT_OUTPUT))
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"Dataset not found: {args.dataset}")
        print("Expected JSONL with fields: instruction, output")
        print(
            'Example: {"instruction": "What is a mutual fund?",'
            ' "output": "A mutual fund is…"}'
        )
        return

    run_training(args.dataset, args.output_dir, args.epochs, args.batch_size, args.lr)


if __name__ == "__main__":
    main()
