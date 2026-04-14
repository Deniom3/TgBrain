"""
Тесты потокобезопасного кэша health endpoint.

Эти тесты документируют ожидаемое поведение health cache с asyncio.Lock:
- Конкурентные запросы сериализуются
- TTL корректно инвалидирует кэш
- Исключения не блокируют Lock и не портят кэш

AAA: Arrange / Act / Assert
Одна проверка на тест.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.endpoints import health as health_module


@pytest.fixture(autouse=True)
def _reset_health_cache() -> None:
    """Сбросить health cache перед каждым тестом."""
    health_module._health_cache["llm_status"] = None
    health_module._health_cache["llm_time"] = 0
    health_module._health_cache["emb_status"] = None
    health_module._health_cache["emb_time"] = 0
    health_module._health_cache["ttl"] = 60


@pytest.fixture
def mock_app() -> MagicMock:
    """Создать мок FastAPI app с embeddings и llm."""
    app = MagicMock()
    app.state.embeddings = AsyncMock()
    app.state.embeddings.check_health = AsyncMock(return_value=True)
    app.state.llm = AsyncMock()
    app.state.llm.check_health = AsyncMock(return_value=True)
    app.state.ingester = None
    return app


@pytest.fixture
def mock_request(mock_app: MagicMock) -> MagicMock:
    """Создать мок request с app."""
    request = MagicMock()
    request.app = mock_app
    return request


@pytest.mark.asyncio
async def test_health_cache_lock_prevents_concurrent_update(
    mock_app: MagicMock,
) -> None:
    """Два конкурентных запроса: только один вызывает реальный check_health."""
    from src.api.endpoints.health import health_check

    call_count = 0

    async def slow_check(*args: Any, **kwargs: Any) -> bool:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return True

    mock_app.state.embeddings.check_health = AsyncMock(side_effect=slow_check)
    mock_app.state.llm.check_health = AsyncMock(return_value=True)

    health_module._health_cache["emb_time"] = 0
    health_module._health_cache["emb_status"] = None

    request = MagicMock()
    request.app = mock_app

    with patch.object(health_module, "check_db_health", AsyncMock(return_value=True)):
        task1 = asyncio.create_task(health_check(request))
        task2 = asyncio.create_task(health_check(request))

        await asyncio.gather(task1, task2)

    assert call_count == 1


@pytest.mark.asyncio
async def test_health_cache_lock_ttl_expired_triggers_recheck(
    mock_app: MagicMock,
    mock_request: MagicMock,
) -> None:
    """После истечения TTL следующий запрос вызывает recheck."""
    from src.api.endpoints.health import health_check

    health_module._health_cache["emb_time"] = int(time.time()) - 120
    health_module._health_cache["emb_status"] = True
    health_module._health_cache["llm_time"] = int(time.time()) - 120
    health_module._health_cache["llm_status"] = True

    await health_check(mock_request)

    assert mock_app.state.embeddings.check_health.call_count >= 1
    assert mock_app.state.llm.check_health.call_count >= 1


@pytest.mark.asyncio
async def test_health_cache_lock_ttl_not_expired_uses_cache(
    mock_app: MagicMock,
    mock_request: MagicMock,
) -> None:
    """В пределах TTL кэш возвращается без проверки."""
    from src.api.endpoints.health import health_check

    health_module._health_cache["emb_time"] = int(time.time())
    health_module._health_cache["emb_status"] = True
    health_module._health_cache["llm_time"] = int(time.time())
    health_module._health_cache["llm_status"] = True

    response = await health_check(mock_request)

    assert response.components["ollama_embeddings"] == "ok"
    assert response.components["llm"] == "ok"
    assert mock_app.state.embeddings.check_health.call_count == 0
    assert mock_app.state.llm.check_health.call_count == 0


@pytest.mark.asyncio
async def test_health_cache_lock_exception_handled(
    mock_app: MagicMock,
) -> None:
    """Exception при check_health не блокирует Lock."""
    from src.api.endpoints.health import health_check

    mock_app.state.embeddings.check_health = AsyncMock(side_effect=RuntimeError("DB error"))
    mock_app.state.llm.check_health = AsyncMock(side_effect=RuntimeError("LLM error"))

    health_module._health_cache["emb_time"] = 0
    health_module._health_cache["llm_time"] = 0

    request = MagicMock()
    request.app = mock_app

    with patch.object(health_module, "check_db_health", AsyncMock(return_value=True)):
        response1 = await health_check(request)

    assert response1 is not None

    mock_app.state.embeddings.check_health.reset_mock()
    mock_app.state.llm.check_health.reset_mock()

    health_module._health_cache["emb_time"] = 0
    health_module._health_cache["llm_time"] = 0

    with patch.object(health_module, "check_db_health", AsyncMock(return_value=True)):
        response2 = await health_check(request)

    assert response2 is not None


@pytest.mark.asyncio
async def test_health_cache_lock_exception_does_not_corrupt_cache(
    mock_app: MagicMock,
) -> None:
    """Exception при check_health не обновляет кэш некорректными данными."""
    from src.api.endpoints.health import health_check

    mock_app.state.embeddings.check_health = AsyncMock(side_effect=RuntimeError("embeddings down"))
    mock_app.state.llm.check_health = AsyncMock(side_effect=RuntimeError("llm down"))

    health_module._health_cache["emb_time"] = 0
    health_module._health_cache["llm_time"] = 0

    request = MagicMock()
    request.app = mock_app

    with patch.object(health_module, "check_db_health", AsyncMock(return_value=True)):
        response = await health_check(request)

    assert response.components["ollama_embeddings"] == "error"
    assert response.components["llm"] == "error"
    assert response.status in ("error", "degraded")


@pytest.mark.asyncio
async def test_health_cache_llm_status_cached(
    mock_app: MagicMock,
    mock_request: MagicMock,
) -> None:
    """LLM статус кэшируется аналогично embedding."""
    from src.api.endpoints.health import health_check

    health_module._health_cache["llm_time"] = int(time.time())
    health_module._health_cache["llm_status"] = True
    health_module._health_cache["emb_time"] = int(time.time())
    health_module._health_cache["emb_status"] = True

    await health_check(mock_request)

    assert mock_app.state.llm.check_health.call_count == 0


@pytest.mark.asyncio
async def test_health_cache_concurrent_different_keys(
    mock_app: MagicMock,
) -> None:
    """Concurrent запросы к health endpoint не блокируют друг друга (нет deadlock).

    Спецификация: «Concurrent запросы к разным ключам (llm/emb) не блокируют
    друг друга». Замеряем время выполнения параллельных вызовов — если они
    завершаются в пределах timeout, взаимной блокировки нет.
    """
    from src.api.endpoints.health import health_check

    mock_app.state.embeddings.check_health = AsyncMock(return_value=True)
    mock_app.state.llm.check_health = AsyncMock(return_value=True)

    health_module._health_cache["emb_time"] = 0
    health_module._health_cache["emb_status"] = None
    health_module._health_cache["llm_time"] = 0
    health_module._health_cache["llm_status"] = None

    request = MagicMock()
    request.app = mock_app

    with patch.object(health_module, "check_db_health", AsyncMock(return_value=True)):
        task1 = asyncio.create_task(health_check(request))
        task2 = asyncio.create_task(health_check(request))

        start = time.monotonic()
        responses = await asyncio.wait_for(
            asyncio.gather(task1, task2),
            timeout=2.0,
        )
        elapsed = time.monotonic() - start

    assert len(responses) == 2
    assert elapsed < 1.0
    assert all(r.status in ("ok", "degraded", "error") for r in responses)


def test_health_cache_module_level_has_lock() -> None:
    """Module-level _health_cache имеет associated asyncio.Lock.

    ПРЕДУПРЕЖДЕНИЕ: Этот тест ожидаемо падает до Фазы 3,
    когда будут добавлены атрибуты _emb_lock и _llm_lock в health_module.
    """
    assert hasattr(health_module, "_emb_lock")
    assert hasattr(health_module, "_llm_lock")
    assert isinstance(health_module._emb_lock, asyncio.Lock)
    assert isinstance(health_module._llm_lock, asyncio.Lock)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_health_cache_startup_first_request_always_checks(
    mock_app: MagicMock,
    mock_request: MagicMock,
) -> None:
    """Первый запрос при старте (time=0) всегда вызывает реальный check."""
    from src.api.endpoints.health import health_check

    health_module._health_cache["emb_time"] = 0
    health_module._health_cache["emb_status"] = None
    health_module._health_cache["llm_time"] = 0
    health_module._health_cache["llm_status"] = None

    await health_check(mock_request)

    assert mock_app.state.embeddings.check_health.call_count == 1
    assert mock_app.state.llm.check_health.call_count == 1
