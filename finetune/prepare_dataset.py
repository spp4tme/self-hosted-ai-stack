"""Convertit les conversations Open WebUI (JSON) → format Alpaca pour fine-tuning."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _extract_alpaca(conversation: dict[str, Any]) -> list[dict[str, str]]:
    """Extrait les paires instruction/output d'une conversation Open WebUI."""
    messages: list[dict] = conversation.get("messages", [])
    samples = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "user" and i + 1 < len(messages):
            nxt = messages[i + 1]
            if nxt.get("role") == "assistant":
                samples.append({
                    "instruction": msg["content"].strip(),
                    "input": "",
                    "output": nxt["content"].strip(),
                })
    return samples


def convert(input_path: str, output_path: str, min_length: int = 20) -> int:
    """
    Convertit un fichier JSON Open WebUI (liste de conversations) → Alpaca JSON.
    Retourne le nombre d'exemples générés.
    """
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = [data]

    samples: list[dict[str, str]] = []
    for conv in data:
        extracted = _extract_alpaca(conv)
        for s in extracted:
            if (len(s["instruction"]) >= min_length and
                    len(s["output"]) >= min_length):
                samples.append(s)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)

    print(f"[prepare_dataset] {len(samples)} exemples → {output_path}")
    return len(samples)


def create_demo_dataset(output_path: str, n: int = 20) -> None:
    """Crée un mini-dataset de démonstration."""
    samples = [
        {
            "instruction": f"Explique le concept de {topic} en 2 phrases simples.",
            "input": "",
            "output": f"Le {topic} est un concept fondamental en informatique. "
                      f"Il permet d'optimiser et de structurer les données efficacement.",
        }
        for topic, _ in [
            ("réseau de neurones", 1), ("algorithme de tri", 2), ("base de données vectorielle", 3),
            ("attention transformer", 4), ("quantification GGUF", 5), ("LoRA fine-tuning", 6),
            ("embedding sémantique", 7), ("RAG retrieval", 8), ("agent autonome", 9),
            ("chaîne de Markov", 10), ("gradient descent", 11), ("batch normalization", 12),
            ("tokenisation BPE", 13), ("apprentissage par renforcement", 14), ("inférence ONNX", 15),
            ("distillation de modèle", 16), ("prompt engineering", 17), ("hallucination LLM", 18),
            ("constitutional AI", 19), ("VRAM GPU", 20),
        ]
    ][:n]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    print(f"[prepare_dataset] Dataset démo : {len(samples)} exemples → {output_path}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Prépare un dataset Alpaca pour fine-tuning")
    p.add_argument("--input",  help="Fichier JSON Open WebUI")
    p.add_argument("--output", default="finetune/dataset.json")
    p.add_argument("--demo",   action="store_true", help="Génère un dataset de démo")
    p.add_argument("--n",      type=int, default=20)
    args = p.parse_args()

    if args.demo:
        create_demo_dataset(args.output, args.n)
    elif args.input:
        convert(args.input, args.output)
    else:
        p.print_help()
        sys.exit(1)
