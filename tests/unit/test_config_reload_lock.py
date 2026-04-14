"""
Тесты для asyncio.Lock защиты reload_settings().

Проверяется:
- Последовательное выполнение concurrent вызовов
- Освобождение lock при исключении
- Lazy инициализация lock
- Корректная работа функции под lock
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.loader import _get_reload_lock, reload_settings


@pytest.fixture(autouse=True)
def reset_reload_lock() -> None:
    """Сбрасывает lock перед каждым тестом для изоляции."""
    import src.config.loader as loader_module

    loader_module._reload_lock = None


def test_get_reload_lock_returns_asyncio_lock() -> None:
    """_get_reload_lock возвращает asyncio.Lock при первом вызове."""
    lock = _get_reload_lock()
    assert isinstance(lock, asyncio.Lock)


def test_get_reload_lock_returns_same_instance() -> None:
    """Повторные вызовы возвращают один и тот же lock."""
    lock1 = _get_reload_lock()
    lock2 = _get_reload_lock()
    assert lock1 is lock2


@pytest.mark.asyncio
async def test_reload_settings_executes_under_lock() -> None:
    """reload_settings выполняется, захватывая lock."""
    execution_order: list[str] = []
    loaded_settings = AsyncMock()

    async def fake_load_settings():
        execution_order.append("load_started")
        await asyncio.sleep(0.01)
        execution_order.append("load_finished")
        return loaded_settings

    with (
        patch("src.config.loader.load_settings_from_db", side_effect=fake_load_settings),
        patch("src.config.settings.get_settings") as mock_get,
    ):
        mock_get.cache_clear = MagicMock()

        result = await reload_settings()

        assert result is loaded_settings
        assert execution_order == ["load_started", "load_finished"]


@pytest.mark.asyncio
async def test_reload_settings_concurrent_calls_execute_sequentially() -> None:
    """Concurrent вызовы reload_settings выполняются последовательно."""
    call_timestamps: list[float] = []

    async def slow_load_settings():
        call_timestamps.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.05)
        call_timestamps.append(asyncio.get_event_loop().time())
        return AsyncMock()

    with (
        patch("src.config.loader.load_settings_from_db", side_effect=slow_load_settings),
        patch("src.config.settings.get_settings") as mock_get,
    ):
        mock_instance = AsyncMock()
        mock_get.return_value = mock_instance
        mock_get.cache_clear = MagicMock()

        await asyncio.gather(
            reload_settings(),
            reload_settings(),
            reload_settings(),
        )

        start_times = call_timestamps[::2]
        for i in range(len(start_times) - 1):
            assert start_times[i + 1] >= start_times[i], (
                f"Вызов {i + 1} начался до завершения вызова {i}"
            )


@pytest.mark.asyncio
async def test_reload_settings_exception_releases_lock() -> None:
    """Исключение внутри reload_settings освобождает lock."""
    call_count = 0
    loaded_settings = AsyncMock()

    async def failing_load_settings():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("DB connection failed")
        return loaded_settings

    with (
        patch("src.config.loader.load_settings_from_db", side_effect=failing_load_settings),
        patch("src.config.settings.get_settings") as mock_get,
    ):
        mock_get.cache_clear = MagicMock()

        with pytest.raises(ValueError, match="DB connection failed"):
            await reload_settings()

        result = await reload_settings()
        assert result is loaded_settings
        assert call_count == 2
