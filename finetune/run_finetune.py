"""
Fine-tuning LoRA avec Unsloth — RTX 5070 Ti, CUDA 12.4, bf16.
À exécuter dans l'environnement Linux/WSL2 avec GPU (via Docker ou native).

Usage:
  python finetune/run_finetune.py --dataset finetune/dataset.json --steps 100
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# ── Détection VRAM ────────────────────────────────────────────────────────────

def get_vram_gb() -> float:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            text=True,
        ).strip().split("\n")[0]
        return int(out) / 1024
    except Exception:
        return 8.0  # fallback


def auto_batch_size(vram_gb: float) -> int:
    if vram_gb >= 16:
        return 4
    if vram_gb >= 12:
        return 2
    return 1


# ── Script principal ──────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Fine-tuning LoRA via Unsloth")
    p.add_argument("--model",   default="unsloth/mistral-7b-v0.3-bnb-4bit",
                   help="Modèle HuggingFace (Unsloth)")
    p.add_argument("--dataset", default="finetune/dataset.json",
                   help="Dataset Alpaca JSON")
    p.add_argument("--output",  default="finetune/output", help="Dossier de sortie")
    p.add_argument("--steps",   type=int, default=200,     help="Nombre de steps")
    p.add_argument("--lora-r",  type=int, default=16)
    p.add_argument("--dry-run", action="store_true",       help="Valide config sans entraîner")
    args = p.parse_args()

    vram = get_vram_gb()
    batch = auto_batch_size(vram)
    print(f"[finetune] VRAM détectée: {vram:.1f} GB → batch_size={batch}")

    # Chargement dataset
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"[finetune] Dataset introuvable: {dataset_path}")
        print("[finetune] Générez-le avec: python finetune/prepare_dataset.py --demo")
        sys.exit(1)

    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)
    print(f"[finetune] Dataset: {len(dataset)} exemples")

    if args.dry_run:
        print("[finetune] Dry-run OK — config validée")
        return

    # ── Import Unsloth (Linux/WSL2 avec CUDA requis) ─────────────────────────
    try:
        from unsloth import FastLanguageModel
        import torch
        from datasets import Dataset
        from trl import SFTTrainer
        from transformers import TrainingArguments
    except ImportError as e:
        print(f"[finetune] Unsloth non disponible: {e}")
        print("[finetune] Installez via: pip install unsloth[cu124]")
        sys.exit(1)

    # ── Chargement modèle ─────────────────────────────────────────────────────
    print(f"[finetune] Chargement {args.model}…")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=2048,
        load_in_4bit=True,
        dtype=None,  # auto (bf16 sur Ampere+)
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
        lora_alpha=args.lora_r * 2,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    # ── Format Alpaca ─────────────────────────────────────────────────────────
    ALPACA_TMPL = (
        "Below is an instruction that describes a task. "
        "Write a response that appropriately completes the request.\n\n"
        "### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n### Response:\n{output}"
    )

    def format_sample(row: dict) -> dict:
        return {"text": ALPACA_TMPL.format(**row)}

    hf_dataset = Dataset.from_list([format_sample(r) for r in dataset])

    # ── Entraînement ──────────────────────────────────────────────────────────
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=hf_dataset,
        dataset_text_field="text",
        max_seq_length=2048,
        args=TrainingArguments(
            per_device_train_batch_size=batch,
            gradient_accumulation_steps=max(1, 4 // batch),
            warmup_steps=5,
            max_steps=args.steps,
            learning_rate=2e-4,
            fp16=False,
            bf16=True,
            logging_steps=10,
            output_dir=str(output_dir),
            optim="adamw_8bit",
            save_strategy="no",
        ),
    )
    trainer.train()

    # ── Export GGUF ───────────────────────────────────────────────────────────
    gguf_path = output_dir / "model-q4_k_m.gguf"
    print(f"[finetune] Export GGUF → {gguf_path}")
    model.save_pretrained_gguf(str(output_dir / "gguf"), tokenizer, quantization_method="q4_k_m")

    # ── Modelfile Ollama ──────────────────────────────────────────────────────
    model_name = Path(args.model).name.lower().replace("/", "-")
    modelfile_path = output_dir / "Modelfile"
    modelfile_path.write_text(
        f"FROM {gguf_path}\n"
        f"PARAMETER temperature 0.1\n"
        f"PARAMETER num_ctx 4096\n"
        f'SYSTEM "Modèle fine-tuné Jarvis."\n'
    )
    print(f"[finetune] Modelfile → {modelfile_path}")
    print(f"[finetune] Importez dans Ollama: ollama create {model_name}-ft -f {modelfile_path}")


if __name__ == "__main__":
    main()
