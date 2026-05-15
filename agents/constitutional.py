"""Constitutional AI — génération → critique → révision → réponse finale."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()

_LITELLM_URL = os.getenv("LITELLM_URL",    "http://localhost:4000")
_LITELLM_KEY = os.getenv("LITELLM_API_KEY","sk-local")
_MODEL_GEN   = os.getenv("DEFAULT_MODEL",  "mistral")
_MODEL_CRIT  = os.getenv("REASONING_MODEL","deepseek")


PRINCIPLES = """
1. EXACTITUDE : Les faits affirmés sont-ils vérifiables ? Y a-t-il des hallucinations ou confusions ?
2. SÉCURITÉ : La réponse contient-elle des informations dangereuses, nocives ou illégales ?
3. BIAIS : La réponse est-elle équilibrée ? Y a-t-il des partis pris non justifiés ?
4. CLARTÉ : La réponse est-elle compréhensible, structurée et sans ambiguïté ?
5. COMPLÉTUDE : La question est-elle entièrement répondue ? Y a-t-il des omissions importantes ?
""".strip()


@dataclass
class ConstitutionalResult:
    original:   str
    critique:   str
    revised:    str
    principles_violated: list[str]


async def _chat(model: str, system: str, user: str, temperature: float = 0.2) -> str:
    payload = {
        "model":  model,
        "messages": [
            {"role": "system",  "content": system},
            {"role": "user",    "content": user},
        ],
        "temperature": temperature,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{_LITELLM_URL}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {_LITELLM_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


async def constitutional_pipeline(
    question: str,
    context: str = "",
    gen_model: str | None = None,
    crit_model: str | None = None,
) -> ConstitutionalResult:
    """
    Pipeline 3 étapes :
    1. Génère une réponse initiale
    2. Critique selon les principes constitutionnels
    3. Révise en tenant compte des critiques
    """
    gen_mdl  = gen_model  or _MODEL_GEN
    crit_mdl = crit_model or _MODEL_CRIT
    ctx_block = f"\nContexte : {context}\n" if context else ""

    # ── Étape 1 : Génération ──────────────────────────────────────────────────
    original = await _chat(
        gen_mdl,
        system="Tu es un assistant IA précis et honnête. Réponds de façon complète.",
        user=f"{ctx_block}Question : {question}",
    )

    # ── Étape 2 : Critique ────────────────────────────────────────────────────
    crit_prompt = f"""Évalue cette réponse selon les principes suivants :

{PRINCIPLES}

Question posée : {question}

Réponse à évaluer :
{original}

Pour chaque principe, indique : [OK] ou [PROBLÈME: description].
Liste ensuite les améliorations nécessaires."""

    critique = await _chat(
        crit_mdl,
        system="Tu es un évaluateur rigoureux. Ton rôle est d'identifier les failles dans les réponses IA.",
        user=crit_prompt,
        temperature=0.1,
    )

    # ── Extrait les principes violés ──────────────────────────────────────────
    violated = [
        line.strip()
        for line in critique.splitlines()
        if "[PROBLÈME" in line.upper()
    ]

    # ── Étape 3 : Révision ────────────────────────────────────────────────────
    rev_prompt = f"""Tu as répondu à cette question :
{question}

Voici ta réponse initiale :
{original}

Voici les critiques identifiées :
{critique}

Révise ta réponse pour corriger tous les problèmes identifiés.
Sois factuel, équilibré et complet. Ne mentionne pas le processus de révision."""

    revised = await _chat(
        gen_mdl,
        system="Tu es un assistant IA qui améliore ses réponses suite à une auto-critique.",
        user=rev_prompt,
    )

    return ConstitutionalResult(
        original=original,
        critique=critique,
        revised=revised,
        principles_violated=violated,
    )


def constitutional_pipeline_sync(question: str, context: str = "") -> ConstitutionalResult:
    return asyncio.run(constitutional_pipeline(question, context))


# ── Middleware LiteLLM (hook post-génération) ─────────────────────────────────

class ConstitutionalMiddleware:
    """
    Wrapper à appeler autour d'une requête LLM pour activer le pipeline.
    Utilisation : result = await middleware.process(question, raw_response)
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    async def process(self, question: str, raw_response: str) -> str:
        if not self.enabled:
            return raw_response
        result = await constitutional_pipeline(question)
        return result.revised
