"""Tests du pipeline Constitutional AI."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_pipeline_structure():
    from agents.constitutional import constitutional_pipeline, ConstitutionalResult

    fake_original = "Paris est la capitale de la France."
    fake_critique = "[OK] Exactitude\n[OK] Sécurité\n[OK] Biais"
    fake_revised  = "Paris est la capitale et plus grande ville de France."

    call_count = 0
    async def fake_chat(model, system, user, temperature=0.2):
        nonlocal call_count
        call_count += 1
        if call_count == 1: return fake_original
        if call_count == 2: return fake_critique
        return fake_revised

    with patch("agents.constitutional._chat", side_effect=fake_chat):
        result = await constitutional_pipeline("Quelle est la capitale de la France ?")

    assert isinstance(result, ConstitutionalResult)
    assert result.original == fake_original
    assert result.critique == fake_critique
    assert result.revised  == fake_revised
    assert call_count == 3  # 3 appels LLM


@pytest.mark.asyncio
async def test_principles_violated_detection():
    from agents.constitutional import constitutional_pipeline

    async def fake_chat(model, system, user, temperature=0.2):
        call = getattr(fake_chat, "_call", 0)
        fake_chat._call = call + 1
        if fake_chat._call == 1: return "Réponse initiale"
        if fake_chat._call == 2:
            return "[PROBLÈME: hallucination détectée ligne 1]\n[OK] Sécurité"
        return "Réponse révisée"

    with patch("agents.constitutional._chat", side_effect=fake_chat):
        result = await constitutional_pipeline("Question test")

    assert len(result.principles_violated) > 0
    assert "PROBLÈME" in result.principles_violated[0].upper()


def test_middleware_enabled():
    from agents.constitutional import ConstitutionalMiddleware
    mw = ConstitutionalMiddleware(enabled=False)
    assert not mw.enabled


@pytest.mark.asyncio
async def test_middleware_passthrough():
    from agents.constitutional import ConstitutionalMiddleware
    mw = ConstitutionalMiddleware(enabled=False)
    result = await mw.process("question", "réponse brute")
    assert result == "réponse brute"
