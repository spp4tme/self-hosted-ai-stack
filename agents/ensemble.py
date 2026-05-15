"""Vote majoritaire / best-of sur plusieurs modèles LLM en parallèle."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

import httpx
from dotenv import load_dotenv

load_dotenv()

_LITELLM_URL = os.getenv("LITELLM_URL",    "http://localhost:4000")
_LITELLM_KEY = os.getenv("LITELLM_API_KEY","sk-local")
_ARBITER     = os.getenv("REASONING_MODEL","deepseek")

FusionStrategy = Literal["majority_vote", "best_of", "weighted_avg"]

ENSEMBLE_MODELS: list[tuple[str, float]] = [
    ("deepseek", 0.55),   # (model_name, weight)
    ("mistral",  0.45),
]


@dataclass
class EnsembleResult:
    strategy:   str
    final:      str
    responses:  dict[str, str]
    divergence: float          # 0.0 = identiques, 1.0 = complètement différents
    arbiter_used: bool = False


async def _call_model(model: str, messages: list[dict], temperature: float = 0.2) -> str:
    payload = {
        "model":  model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{_LITELLM_URL}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {_LITELLM_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _divergence(responses: list[str]) -> float:
    if len(responses) < 2:
        return 0.0
    pairs = [(responses[i], responses[j])
             for i in range(len(responses))
             for j in range(i + 1, len(responses))]
    avg_sim = sum(_similarity(a, b) for a, b in pairs) / len(pairs)
    return 1.0 - avg_sim


async def _majority_vote(responses: dict[str, str]) -> str:
    """Retourne la réponse la plus proche de toutes les autres (barycentre sémantique)."""
    texts = list(responses.values())
    if len(texts) == 1:
        return texts[0]
    scores = {
        name: sum(_similarity(resp, other)
                  for other_name, other in responses.items()
                  if other_name != name)
        for name, resp in responses.items()
    }
    return responses[max(scores, key=scores.get)]  # type: ignore[arg-type]


async def _best_of(responses: dict[str, str], question: str) -> str:
    """Demande à l'arbitre de choisir la meilleure réponse."""
    options = "\n\n".join(
        f"=== Réponse {i+1} ({name}) ===\n{resp}"
        for i, (name, resp) in enumerate(responses.items())
    )
    prompt = (
        f"Question : {question}\n\n"
        f"{options}\n\n"
        "Choisis la réponse la plus exacte, complète et utile. "
        "Réponds UNIQUEMENT avec le texte de la meilleure réponse, sans modification."
    )
    messages = [
        {"role": "system", "content": "Tu es un évaluateur expert. Sélectionne la meilleure réponse."},
        {"role": "user",   "content": prompt},
    ]
    return await _call_model(_ARBITER, messages, temperature=0.1)


async def _weighted_avg(responses: dict[str, str], weights: dict[str, float], question: str) -> str:
    """Synthèse pondérée — l'arbitre fusionne avec les poids donnés."""
    weighted_block = "\n\n".join(
        f"=== Source ({name}, poids {weights.get(name, 0.5):.0%}) ===\n{resp}"
        for name, resp in responses.items()
    )
    prompt = (
        f"Question : {question}\n\n"
        f"{weighted_block}\n\n"
        "Synthétise ces réponses en pondérant selon les poids indiqués. "
        "Produis une réponse finale unique, cohérente et complète."
    )
    messages = [
        {"role": "system", "content": "Tu es un synthétiseur expert. Fusionne les réponses avec les poids indiqués."},
        {"role": "user",   "content": prompt},
    ]
    return await _call_model(_ARBITER, messages, temperature=0.15)


async def ensemble_query(
    question: str,
    strategy: FusionStrategy = "majority_vote",
    models: list[tuple[str, float]] | None = None,
    divergence_threshold: float = 0.45,
) -> EnsembleResult:
    """
    Envoie la question à tous les modèles en parallèle et fusionne.
    Si divergence > threshold → relance l'arbitre quelle que soit la stratégie.
    """
    mdls = models or ENSEMBLE_MODELS
    messages = [
        {"role": "system", "content": "Tu es un assistant IA précis et factuel."},
        {"role": "user",   "content": question},
    ]

    # ── Appels parallèles ─────────────────────────────────────────────────────
    tasks   = {name: _call_model(name, messages) for name, _ in mdls}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    responses: dict[str, str] = {}
    for (name, _), result in zip(mdls, results):
        if isinstance(result, Exception):
            responses[name] = f"[ERREUR: {result}]"
        else:
            responses[name] = result  # type: ignore[assignment]

    # ── Calcul de la divergence ───────────────────────────────────────────────
    div = _divergence(list(responses.values()))
    arbiter_used = False

    # ── Fusion ────────────────────────────────────────────────────────────────
    if div > divergence_threshold:
        # Réponses très divergentes → l'arbitre tranche
        final = await _best_of(responses, question)
        arbiter_used = True
    elif strategy == "majority_vote":
        final = await _majority_vote(responses)
    elif strategy == "best_of":
        final = await _best_of(responses, question)
        arbiter_used = True
    else:  # weighted_avg
        weights = {name: w for name, w in mdls}
        final = await _weighted_avg(responses, weights, question)
        arbiter_used = True

    return EnsembleResult(
        strategy=strategy,
        final=final,
        responses=responses,
        divergence=div,
        arbiter_used=arbiter_used,
    )


def ensemble_query_sync(question: str, strategy: FusionStrategy = "majority_vote") -> EnsembleResult:
    return asyncio.run(ensemble_query(question, strategy))
