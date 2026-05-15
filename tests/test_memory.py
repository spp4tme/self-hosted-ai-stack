"""Tests de la mémoire long terme (Mem0 + Qdrant)."""

import pytest
from unittest.mock import patch, MagicMock


def test_memory_store_import():
    from memory.store import MemoryStore
    assert MemoryStore is not None


def test_memory_add_and_search(monkeypatch):
    """Test add + search avec mock Mem0."""
    from memory.store import MemoryStore

    mock_mem = MagicMock()
    mock_mem.add.return_value = {"results": [{"id": "abc", "memory": "Test souvenir"}]}
    mock_mem.search.return_value = {"results": [{"id": "abc", "memory": "Test souvenir", "score": 0.95}]}

    with patch("memory.store.Memory") as MockMemory:
        MockMemory.from_config.return_value = mock_mem
        store = MemoryStore(user_id="test_user")
        store.add("Je m'appelle Anthony")
        results = store.search("nom")

    assert len(results) == 1
    assert results[0]["memory"] == "Test souvenir"


def test_memory_build_context(monkeypatch):
    from memory.store import MemoryStore

    mock_mem = MagicMock()
    mock_mem.search.return_value = {
        "results": [
            {"memory": "L'utilisateur préfère Python"},
            {"memory": "L'utilisateur a une RTX 5070 Ti"},
        ]
    }

    with patch("memory.store.Memory") as MockMemory:
        MockMemory.from_config.return_value = mock_mem
        store = MemoryStore()
        ctx = store.build_context("quel GPU as-tu ?")

    assert "RTX 5070 Ti" in ctx
    assert "Python" in ctx


def test_memory_delete(monkeypatch):
    from memory.store import MemoryStore

    mock_mem = MagicMock()
    mock_mem.add.return_value = {"results": [{"id": "xyz"}]}

    with patch("memory.store.Memory") as MockMemory:
        MockMemory.from_config.return_value = mock_mem
        store = MemoryStore()
        store.add("souvenir temporaire")
        store.delete("xyz")
        mock_mem.delete.assert_called_once_with("xyz")
