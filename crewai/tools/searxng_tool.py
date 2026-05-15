"""Outil CrewAI — Recherche web via SearXNG."""

from __future__ import annotations

import os
from typing import Any, Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

_SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8888")


class SearXNGSearchInput(BaseModel):
    query: str = Field(..., description="Requête de recherche")
    limit: int = Field(default=5, description="Nombre de résultats")


class SearXNGSearchTool(BaseTool):
    name: str = "SearXNG Web Search"
    description: str = (
        "Recherche des informations sur le web via le moteur SearXNG local. "
        "Utilise cet outil pour obtenir des informations récentes ou des sources externes."
    )
    args_schema: Type[BaseModel] = SearXNGSearchInput

    def _run(self, query: str, limit: int = 5) -> str:
        try:
            resp = requests.get(
                f"{_SEARXNG_URL}/search",
                params={"q": query, "format": "json"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])[:limit]
            if not results:
                return "Aucun résultat trouvé."
            lines = []
            for i, r in enumerate(results, 1):
                lines.append(
                    f"{i}. **{r.get('title', '')}**\n"
                    f"   URL: {r.get('url', '')}\n"
                    f"   {r.get('content', '')[:300]}"
                )
            return "\n\n".join(lines)
        except Exception as e:
            return f"Erreur SearXNG: {e}"
