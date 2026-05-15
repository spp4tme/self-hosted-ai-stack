"""Tests de l'ensemble de modèles."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_ensemble_parallel_calls():
    from agents.ensemble import ensemble_query, EnsembleResult

    responses = {"deepseek": "Paris est la capitale.", "mistral": "Paris est la capitale de France."}
    call_count = 0

    async def fake_call(model, messages, temperature=0.2):
        return responses.get(model, "réponse")

    with patch("agents.ensemble._call_model", side_effect=fake_call):
        result = await ensemble_query("Quelle est la capitale de la France ?")

    assert isinstance(result, EnsembleResult)
    assert result.final
    assert "deepseek" in result.responses
    assert "mistral"  in result.responses


@pytest.mark.asyncio
async def test_ensemble_high_divergence_uses_arbiter():
    from agents.ensemble import ensemble_query

    async def fake_call(model, messages, temperature=0.2):
        if model == "deepseek": return "La réponse est A, absolument certain."
        if model == "mistral":  return "Non, la réponse est Z, complètement différent."
        return "Arbitrage : la bonne réponse est A."  # arbitre

    with patch("agents.ensemble._call_model", side_effect=fake_call):
        result = await ensemble_query(
            "Question très ambiguë ?",
            strategy="majority_vote",
            divergence_threshold=0.1,   # seuil très bas → force l'arbitrage
        )

    assert result.arbiter_used or result.divergence > 0


@pytest.mark.asyncio
async def test_divergence_calculation():
    from agents.ensemble import _divergence
    d1 = _divergence(["Paris", "Paris"])
    d2 = _divergence(["Paris", "Berlin"])
    assert d1 < d2


def test_ensemble_result_fields():
    from agents.ensemble import EnsembleResult
    r = EnsembleResult(
        strategy="majority_vote",
        final="réponse",
        responses={"m1": "r1"},
        divergence=0.2,
    )
    assert r.arbiter_used is False
    assert r.divergence == 0.2
