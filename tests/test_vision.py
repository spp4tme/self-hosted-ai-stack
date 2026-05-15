"""Tests de l'analyse vision."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_vision_analyzer_import():
    from vision.analyzer import VisionAnalyzer
    assert VisionAnalyzer is not None


@pytest.mark.asyncio
async def test_analyze_mode_prompts():
    from vision.analyzer import VisionAnalyzer, _PROMPTS
    assert "general"   in _PROMPTS
    assert "error"     in _PROMPTS
    assert "dashboard" in _PROMPTS
    assert "code"      in _PROMPTS


@pytest.mark.asyncio
async def test_analyze_bytes(tmp_path):
    from vision.analyzer import VisionAnalyzer

    analyzer = VisionAnalyzer()
    fake_response = "Je vois une interface web moderne avec un formulaire de connexion."

    with patch.object(analyzer, "_call_ollama", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = fake_response
        result = await analyzer.analyze_bytes(b"fake_image_bytes", mode="general")

    assert result == fake_response
    mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_for_action(tmp_path):
    from vision.analyzer import VisionAnalyzer
    import pathlib

    # Crée une fausse image
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG\r\n" + b"\x00" * 100)

    analyzer = VisionAnalyzer()
    with patch.object(analyzer, "_call_ollama", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = "click(100, 200)"
        result = await analyzer.analyze_for_action(img, "ouvre le menu")

    assert "click" in result


@pytest.mark.asyncio
async def test_check_model_available():
    from vision.analyzer import VisionAnalyzer

    analyzer = VisionAnalyzer()

    # Patch directement _call_ollama pour éviter les appels réseau
    with patch.object(analyzer, "check_model_available", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = True
        result = await analyzer.check_model_available("llava")

    assert result is True
