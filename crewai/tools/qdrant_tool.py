"""Outil CrewAI — Recherche vectorielle dans Qdrant."""

from __future__ import annotations

import os
from typing import Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

_QDRANT_URL  = os.getenv("QDRANT_URL",  "http://qdrant:6333")
_LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:4000")
_LITELLM_KEY = os.getenv("LITELLM_API_KEY", "sk-local")
_EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic")


class QdrantSearchInput(BaseModel):
    query: str = Field(..., description="Requête de recherche sémantique")
    collection: str = Field(default="memory_default", description="Collection Qdrant à chercher")
    limit: int = Field(default=5, description="Nombre de résultats")


class QdrantSearchTool(BaseTool):
    name: str = "Qdrant Knowledge Base Search"
    description: str = (
        "Recherche dans la base de connaissances vectorielle locale (Qdrant). "
        "Utilise cet outil pour retrouver des informations mémorisées ou des documents ingérés."
    )
    args_schema: Type[BaseModel] = QdrantSearchInput

    def _get_embedding(self, text: str) -> list[float]:
        resp = requests.post(
            f"{_LITELLM_URL}/v1/embeddings",
            headers={"Authorization": f"Bearer {_LITELLM_KEY}"},
            json={"model": _EMBED_MODEL, "input": text},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    def _run(self, query: str, collection: str = "memory_default", limit: int = 5) -> str:
        try:
            embedding = self._get_embedding(query)
            resp = requests.post(
                f"{_QDRANT_URL}/collections/{collection}/points/search",
                json={"vector": embedding, "limit": limit, "with_payload": True},
                timeout=15,
            )
            if resp.status_code == 404:
                return f"Collection '{collection}' introuvable dans Qdrant."
            resp.raise_for_status()
            points = resp.json().get("result", [])
            if not points:
                return "Aucun document trouvé dans la base de connaissances."
            lines = []
            for i, p in enumerate(points, 1):
                payload = p.get("payload", {})
                score = round(p.get("score", 0), 3)
                content = payload.get("memory") or payload.get("text") or payload.get("content") or str(payload)
                lines.append(f"{i}. [score={score}] {content[:400]}")
            return "\n\n".join(lines)
        except Exception as e:
            return f"Erreur Qdrant: {e}"
