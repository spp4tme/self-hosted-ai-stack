"""Mémoire long terme via Mem0 + Qdrant + Ollama embeddings."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from mem0 import Memory

load_dotenv()

_QDRANT_URL    = os.getenv("QDRANT_URL",   "http://localhost:6333")
_LITELLM_URL   = os.getenv("LITELLM_URL",  "http://localhost:4000")
_LITELLM_KEY   = os.getenv("LITELLM_API_KEY", "sk-local")
_OLLAMA_URL    = os.getenv("OLLAMA_URL",   "http://localhost:11434")
_EMBED_MODEL   = os.getenv("EMBED_MODEL",  "nomic-embed-text")
_DEFAULT_MODEL = os.getenv("DEFAULT_MODEL","mistral")


def _make_config(collection: str) -> dict[str, Any]:
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "url": _QDRANT_URL,
                "collection_name": collection,
                "embedding_model_dims": 768,
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": _EMBED_MODEL,
                "ollama_base_url": _OLLAMA_URL,
            },
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": _DEFAULT_MODEL,
                "openai_base_url": _LITELLM_URL,
                "api_key": _LITELLM_KEY,
            },
        },
        "version": "v1.1",
    }


class MemoryStore:
    """Interface unifiée Mem0 — une collection Qdrant par utilisateur."""

    def __init__(self, user_id: str = "default") -> None:
        self.user_id   = user_id
        self.collection = f"memory_{user_id}"
        self._mem = Memory.from_config(_make_config(self.collection))

    # ── Écriture ─────────────────────────────────────────────────────────────

    def add(self, messages: str | list[dict[str, str]],
            metadata: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Ajoute un ou plusieurs souvenirs depuis un texte ou une conversation."""
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        result = self._mem.add(messages, user_id=self.user_id, metadata=metadata or {})
        return result.get("results", []) if isinstance(result, dict) else result

    # ── Lecture ───────────────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Cherche les souvenirs les plus pertinents pour une requête."""
        result = self._mem.search(
            query,
            filters={"user_id": self.user_id},
            limit=limit,
        )
        return result.get("results", []) if isinstance(result, dict) else result

    def get_all(self) -> list[dict[str, Any]]:
        """Retourne tous les souvenirs de cet utilisateur."""
        result = self._mem.get_all(filters={"user_id": self.user_id})
        return result.get("results", []) if isinstance(result, dict) else result

    # ── Suppression ──────────────────────────────────────────────────────────

    def delete(self, memory_id: str) -> None:
        self._mem.delete(memory_id)

    def delete_all(self) -> None:
        self._mem.delete_all(user_id=self.user_id)

    # ── Injection contexte ───────────────────────────────────────────────────

    def build_context(self, query: str, limit: int = 5) -> str:
        """Construit un bloc de contexte à injecter dans le system prompt."""
        memories = self.search(query, limit=limit)
        if not memories:
            return ""
        lines = [f"- {m['memory']}" for m in memories if "memory" in m]
        if not lines:
            return ""
        return "Souvenirs pertinents sur l'utilisateur :\n" + "\n".join(lines)
