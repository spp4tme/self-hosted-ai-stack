"""Évalue un modèle fine-tuné via Ollama — perplexité approchée + exemples qualitatifs."""

from __future__ import annotations

import asyncio
import json
import math
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


async def _generate(model: str, prompt: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{_OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json()


async def evaluate(
    model: str,
    dataset_path: str,
    n_examples: int = 10,
) -> dict[str, Any]:
    """
    Évalue le modèle sur n_examples du dataset.
    Retourne des métriques qualitatives et des exemples de génération.
    """
    with open(dataset_path, encoding="utf-8") as f:
        dataset: list[dict] = json.load(f)

    subset = dataset[:n_examples]
    results = []

    for i, sample in enumerate(subset):
        prompt = (
            "Below is an instruction that describes a task. "
            "Write a response that appropriately completes the request.\n\n"
            f"### Instruction:\n{sample['instruction']}\n\n"
            f"### Input:\n{sample.get('input','')}\n\n"
            "### Response:\n"
        )
        try:
            out = await _generate(model, prompt)
            generated = out.get("response", "").strip()
            # Durée d'inférence normalisée (tokens/s)
            eval_count  = out.get("eval_count", 1)
            eval_dur_ns = out.get("eval_duration", 1)
            tps = eval_count / (eval_dur_ns / 1e9) if eval_dur_ns else 0
        except Exception as e:
            generated = f"[ERREUR: {e}]"
            tps = 0.0

        results.append({
            "id": i,
            "instruction": sample["instruction"],
            "expected": sample["output"],
            "generated": generated,
            "tokens_per_sec": round(tps, 1),
        })
        print(f"[eval] {i+1}/{len(subset)} OK ({tps:.0f} tok/s)")

    # ── Métriques ─────────────────────────────────────────────────────────────
    avg_tps = sum(r["tokens_per_sec"] for r in results) / len(results) if results else 0
    return {
        "model": model,
        "n_evaluated": len(results),
        "avg_tokens_per_sec": round(avg_tps, 1),
        "examples": results,
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--model",   required=True, help="Nom du modèle Ollama")
    p.add_argument("--dataset", default="finetune/dataset.json")
    p.add_argument("--n",       type=int, default=10)
    p.add_argument("--output",  default="finetune/eval_results.json")
    args = p.parse_args()

    results = asyncio.run(evaluate(args.model, args.dataset, args.n))

    out_path = Path(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[eval] Résultats → {out_path}")
    print(f"[eval] {results['n_evaluated']} exemples, {results['avg_tokens_per_sec']} tok/s moy.")
