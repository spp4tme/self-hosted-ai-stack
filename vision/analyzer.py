"""Analyse multimodale via LLaVA (général) et Moondream (actions/computer use)."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Literal

import aiohttp
from dotenv import load_dotenv

load_dotenv()

_OLLAMA_URL   = os.getenv("OLLAMA_URL",  "http://localhost:11434")
_VISION_MODEL = os.getenv("VISION_MODEL","llava:13b")
_CU_MODEL     = os.getenv("COMPUTER_USE_MODEL", "moondream")

AnalysisMode = Literal[
    "general", "error", "network", "dashboard",
    "document", "code", "diagram"
]

_PROMPTS: dict[AnalysisMode, str] = {
    "general":   "Décris précisément ce que tu vois sur cette image.",
    "error":     "Identifie les erreurs, messages d'erreur ou anomalies visibles. Propose des solutions.",
    "network":   "Analyse ce diagramme réseau ou cette capture d'écran réseau. Identifie les composants et flux.",
    "dashboard": "Analyse ce dashboard. Résume les métriques clés et signale les valeurs anormales.",
    "document":  "Extrais et structure le contenu textuel de ce document. Conserve la hiérarchie.",
    "code":      "Analyse ce code. Identifie les problèmes, bugs potentiels et améliorations.",
    "diagram":   "Décris et explique ce diagramme : composants, relations, flux.",
}


def _encode_image(path: str | Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


class VisionAnalyzer:
    """Analyse d'images via Ollama — LLaVA pour l'analyse, Moondream pour computer-use."""

    def __init__(self) -> None:
        self.ollama_url   = _OLLAMA_URL
        self.vision_model = _VISION_MODEL
        self.cu_model     = _CU_MODEL

    # ── API principale ────────────────────────────────────────────────────────

    async def analyze(
        self,
        image_path: str | Path,
        question: str | None = None,
        mode: AnalysisMode = "general",
        model: str | None = None,
    ) -> str:
        """Analyse une image. Retourne la réponse textuelle."""
        img_b64 = _encode_image(image_path)
        prompt  = question or _PROMPTS[mode]
        mdl     = model or self.vision_model
        return await self._call_ollama(mdl, prompt, img_b64)

    async def analyze_bytes(
        self,
        image_bytes: bytes,
        question: str | None = None,
        mode: AnalysisMode = "general",
    ) -> str:
        """Analyse des bytes d'image directement (upload web)."""
        img_b64 = base64.b64encode(image_bytes).decode()
        prompt  = question or _PROMPTS[mode]
        return await self._call_ollama(self.vision_model, prompt, img_b64)

    async def analyze_for_action(self, image_path: str | Path, task: str) -> str:
        """Utilise Moondream pour déduire l'action à effectuer (computer use)."""
        img_b64 = _encode_image(image_path)
        prompt  = (
            f"Task: {task}\n"
            "Respond with ONE action in this exact format:\n"
            "click(x, y) | type(\"text\") | scroll(dy) | done\n"
            "Use screen coordinates. dy is positive=down."
        )
        return await self._call_ollama(self.cu_model, prompt, img_b64)

    # ── Sync wrappers ─────────────────────────────────────────────────────────

    def analyze_sync(self, image_path: str | Path, question: str | None = None,
                     mode: AnalysisMode = "general") -> str:
        return asyncio.run(self.analyze(image_path, question, mode))

    # ── Interne ───────────────────────────────────────────────────────────────

    async def _call_ollama(self, model: str, prompt: str, img_b64: str) -> str:
        payload = {
            "model":  model,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
        }
        url = f"{self.ollama_url}/api/generate"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
                return data.get("response", "").strip()

    async def check_model_available(self, model: str) -> bool:
        url = f"{self.ollama_url}/api/tags"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json(content_type=None)
                names = [m["name"] for m in data.get("models", [])]
                return any(model in n for n in names)
