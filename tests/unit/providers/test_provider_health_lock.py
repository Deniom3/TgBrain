"""
Тесты asyncio.Lock в кэше health check провайдеров.

Проверяют наличие и корректное использование _health_lock в:
- LocalLLMProvider
- GeminiProvider
- OpenRouterProvider

Требования:
- Lock предотвращает конкурентные проверки health
- TTL корректно инвалидирует кэш
- Исключения не вызывают deadlock
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.config import Settings


def _make_settings(provider: str) -> Settings:
    """Создать минимальные Settings для указанного провайдера."""
    return Settings(
        llm_active_provider=provider,
        gemini_api_key="test-gemini-key-1234567890",
        openrouter_api_key="test-openrouter-key-1234567890",
    )


def _make_mock_response(status_code: int = 200) -> AsyncMock:
    """Создать мок для httpx.Response с нужным статусом."""
    response = AsyncMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = {}
    response.aread = AsyncMock()
    response.json = MagicMock(return_value={"models": []})
    return response


class _MockStreamCtx:
    """Async context manager wrapper для мок-ответа."""

    def __init__(self, response: Any, event: asyncio.Event | None = None) -> None:
        self._response = response
        self._event = event

    async def __aenter__(self) -> Any:
        if self._event:
            await self._event.wait()
        return self._response

    async def __aexit__(self, *exc: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_local_llm_provider_health_cache_has_lock() -> None:
    """LocalLLMProvider имеет атрибут _health_lock типа asyncio.Lock."""
    from src.providers.local_llm_provider import LocalLLMProvider

    settings = _make_settings("ollama")
    provider = LocalLLMProvider(settings)

    assert hasattr(provider, "_health_lock")
    assert isinstance(provider._health_lock, asyncio.Lock)


@pytest.mark.asyncio
async def test_gemini_provider_health_cache_has_lock() -> None:
    """GeminiProvider имеет атрибут _health_lock типа asyncio.Lock."""
    from src.providers.gemini_provider import GeminiProvider

    settings = _make_settings("gemini")
    provider = GeminiProvider(settings)

    assert hasattr(provider, "_health_lock")
    assert isinstance(provider._health_lock, asyncio.Lock)


@pytest.mark.asyncio
async def test_openrouter_provider_health_cache_has_lock() -> None:
    """OpenRouterProvider имеет атрибут _health_lock типа asyncio.Lock."""
    from src.providers.openrouter_provider import OpenRouterProvider

    settings = _make_settings("openrouter")
    provider = OpenRouterProvider(settings)

    assert hasattr(provider, "_health_lock")
    assert isinstance(provider._health_lock, asyncio.Lock)


@pytest.mark.asyncio
async def test_provider_health_lock_prevents_concurrent_check() -> None:
    """Конкурентные вызовы check_health сериализуются через Lock."""
    from src.providers.gemini_provider import GeminiProvider

    settings = _make_settings("gemini")
    provider = GeminiProvider(settings)

    real_call_count = 0
    barrier_event = asyncio.Event()

    mock_response = _make_mock_response(200)

    def make_stream_ctx() -> _MockStreamCtx:
        nonlocal real_call_count
        real_call_count += 1
        return _MockStreamCtx(mock_response, barrier_event)

    provider._health_cache["time"] = 0

    with patch.object(
        provider,
        "_get_client",
        new_callable=AsyncMock,
    ) as mock_get_client:
        mock_client = MagicMock()
        mock_client.stream = MagicMock(side_effect=lambda *a, **kw: make_stream_ctx())
        mock_get_client.return_value = mock_client

        async def run_check() -> bool:
            return await provider.check_health()

        task1 = asyncio.create_task(run_check())
        task2 = asyncio.create_task(run_check())

        await asyncio.sleep(0.05)
        barrier_event.set()

        results = await asyncio.gather(task1, task2)

    assert results[0] is True
    assert results[1] is True
    assert real_call_count == 1


@pytest.mark.asyncio
async def test_provider_health_lock_ttl_expired_rechecks() -> None:
    """После истечения TTL lock позволяет повторную проверку health."""
    from src.providers.local_llm_provider import LocalLLMProvider

    settings = _make_settings("ollama")
    provider = LocalLLMProvider(settings)

    provider._health_cache["time"] = 0
    provider._health_cache["status"] = True

    mock_response = _make_mock_response(200)

    def make_stream_ctx() -> _MockStreamCtx:
        return _MockStreamCtx(mock_response)

    with patch.object(
        provider,
        "_get_client",
        new_callable=AsyncMock,
    ) as mock_get_client:
        mock_client = MagicMock()
        mock_client.stream = MagicMock(side_effect=lambda *a, **kw: make_stream_ctx())
        mock_get_client.return_value = mock_client

        result_first = await provider.check_health()

        assert result_first is True
        first_call_count = mock_get_client.call_count
        assert first_call_count == 1

        provider._health_cache["time"] = int(time.time()) - provider.health_cache_ttl - 1
        provider._health_cache["status"] = False

        result_second = await provider.check_health()

        assert result_second is True
        assert mock_get_client.call_count == 2


@pytest.mark.asyncio
async def test_local_llm_provider_health_exception_does_not_deadlock() -> None:
    """LocalLLMProvider: исключение в check_health не блокирует Lock."""
    from src.providers.local_llm_provider import LocalLLMProvider

    settings = _make_settings("ollama")
    provider = LocalLLMProvider(settings)

    provider._health_cache["time"] = 0

    with patch.object(
        provider,
        "_get_client",
        new_callable=AsyncMock,
    ) as mock_get_client:
        mock_get_client.return_value.stream = MagicMock(
            side_effect=httpx.RequestError("connection failed", request=MagicMock()),
        )

        result1 = await asyncio.wait_for(provider.check_health(), timeout=2.0)

    assert result1 is False

    mock_response = _make_mock_response(200)
    stream_ctx = _MockStreamCtx(mock_response)
    provider._health_cache["time"] = 0

    with patch.object(
        provider,
        "_get_client",
        new_callable=AsyncMock,
    ) as mock_get_client:
        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=stream_ctx)
        mock_get_client.return_value = mock_client

        result2 = await asyncio.wait_for(provider.check_health(), timeout=2.0)

    assert result2 is True


@pytest.mark.asyncio
async def test_gemini_provider_health_exception_does_not_deadlock() -> None:
    """GeminiProvider: исключение в check_health не блокирует Lock."""
    from src.providers.gemini_provider import GeminiProvider

    settings = _make_settings("gemini")
    provider = GeminiProvider(settings)

    provider._health_cache["time"] = 0

    with patch.object(
        provider,
        "_get_client",
        new_callable=AsyncMock,
    ) as mock_get_client:
        mock_get_client.return_value.stream = MagicMock(
            side_effect=httpx.RequestError("connection failed", request=MagicMock()),
        )

        result1 = await asyncio.wait_for(provider.check_health(), timeout=2.0)

    assert result1 is False

    mock_response = _make_mock_response(200)
    stream_ctx = _MockStreamCtx(mock_response)
    provider._health_cache["time"] = 0

    with patch.object(
        provider,
        "_get_client",
        new_callable=AsyncMock,
    ) as mock_get_client:
        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=stream_ctx)
        mock_get_client.return_value = mock_client

        result2 = await asyncio.wait_for(provider.check_health(), timeout=2.0)

    assert result2 is True
