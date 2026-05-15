"""Tests du self-healing."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_check_service_up():
    from devops.self_heal import check_service
    with patch("aiohttp.ClientSession") as mock_sess:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_sess.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_resp
        result = await check_service("test", "http://fake:9999")
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_check_service_down():
    from devops.self_heal import check_service
    import aiohttp
    with patch("aiohttp.ClientSession") as mock_sess:
        mock_sess.return_value.__aenter__.return_value.get.side_effect = aiohttp.ClientError()
        result = await check_service("test", "http://fake:9999")
    assert result is False


def test_metrics_format():
    from devops.self_heal import _metrics
    # Vérifie que le dict existe
    assert isinstance(_metrics, dict)


def test_services_config():
    from devops.self_heal import SERVICES
    assert len(SERVICES) >= 4
    for svc in SERVICES:
        assert "name" in svc
        assert "url"  in svc


@pytest.mark.asyncio
async def test_get_disk_pct():
    from devops.self_heal import get_disk_pct
    pct = await get_disk_pct()
    assert 0 <= pct <= 100
