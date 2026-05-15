"""Configuration management — stored in ~/.jarvis/config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR  = Path.home() / ".jarvis"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    "litellm_url":  "http://localhost:4000",
    "litellm_key":  "sk-local",
    "model":        "mistral",
    "qdrant_url":   "http://localhost:6333",
    "ollama_url":   "http://localhost:11434",
    "embed_model":  "nomic-embed-text",
    "searxng_url":  "http://localhost:8888",
    "max_tokens":   4096,
    "temperature":  0.7,
    "memory_limit": 5,
}


def load() -> dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**DEFAULTS, **data}
        except Exception:
            pass
    return dict(DEFAULTS)


def save(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def set_value(key: str, value: Any) -> None:
    cfg = load()
    cfg[key] = value
    save(cfg)
