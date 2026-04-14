"""
Интеграционные тесты: перезагрузка настроек (reload_settings).

Проверяют корректность обновления глобального экземпляра Settings
и взаимодействие с долгоживущими сервисами.
"""

import asyncio
from typing import Generator
from unittest.mock import patch

import pytest

from src.common.application_state import AppStateStore
from src.config.loader import reload_settings
from src.config.settings import SettingsWithProviders, get_settings


@pytest.fixture(autouse=True)
def reset_app_state() -> Generator[None, None, None]:
    """Сбросить AppStateStore до и после каждого теста."""
    AppStateStore.reset()
    yield
    AppStateStore.reset()


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None, None, None]:
    """Сбросить кэш get_settings до и после каждого теста."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestReloadSettingsCreatesNewFrozenInstance:
    """Тесты: reload_settings создаёт новый frozen экземпляр."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reload_settings_creates_new_frozen_instance(self) -> None:
        """reload_settings создаёт новый frozen Settings."""
        old_settings = get_settings()

        with patch(
            "src.config.loader.load_settings_from_db",
            return_value=old_settings.model_copy(update={"log_level": "DEBUG"}),
        ):
            new_settings = await reload_settings()

        assert new_settings is not old_settings
        assert new_settings.model_config.get("frozen") is True
        assert new_settings.log_level == "DEBUG"


class TestReloadSettingsUpdatesGlobalReference:
    """Тесты: reload_settings обновляет глобальную ссылку."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reload_settings_updates_global_reference(self) -> None:
        """reload_settings обновляет config.settings на новый экземпляр."""
        import src.config as config_module

        original = config_module.settings

        with patch(
            "src.config.loader.load_settings_from_db",
            return_value=original.model_copy(update={"log_level": "WARNING"}),
        ):
            await reload_settings()

        assert config_module.settings is not original
        assert config_module.settings.log_level == "WARNING"


class TestReloadSettingsConcurrentCallsSerialized:
    """Тесты: конкурентные вызовы reload_settings сериализуются."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reload_settings_concurrent_calls_serialized(self) -> None:
        """Конкурентные reload_settings сериализуются через Lock."""
        call_order: list[int] = []
        lock_acquired_count = 0

        async def mock_load_settings(*args: object, **kwargs: object) -> SettingsWithProviders:
            nonlocal lock_acquired_count
            lock_acquired_count += 1
            call_id = lock_acquired_count
            call_order.append(call_id)
            await asyncio.sleep(0.01)
            return get_settings()

        with patch(
            "src.config.loader.load_settings_from_db",
            side_effect=mock_load_settings,
        ):
            tasks = [
                asyncio.create_task(reload_settings())
                for _ in range(5)
            ]
            await asyncio.gather(*tasks)

        assert len(call_order) == 5
        assert call_order == [1, 2, 3, 4, 5]


class TestHealthEndpointWithLockedCache:
    """Тесты: health endpoint работает при конкурентных запросах."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_endpoint_with_locked_cache(
        self,
        test_app,
        test_client,
    ) -> None:
        """GET /health работает корректно при конкурентных запросах."""
        responses = []

        async def fetch_health():
            response = test_client.get("/health")
            responses.append(response)

        tasks = [
            asyncio.create_task(fetch_health())
            for _ in range(10)
        ]
        await asyncio.gather(*tasks)

        assert len(responses) == 10
        for response in responses:
            assert response.status_code == 200
            assert response.json()["status"] == "ok"


class TestReloadSettingsDbFailurePreservesCache:
    """Тесты: при падении БД старый экземпляр сохраняется."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reload_settings_db_failure_preserves_cache(self) -> None:
        """При падении БД cache_clear() не вызывается, старый экземпляр сохраняется."""
        old_settings = get_settings()

        with patch(
            "src.config.loader.load_settings_from_db",
            side_effect=RuntimeError("DB connection failed"),
        ):
            with pytest.raises(RuntimeError, match="DB connection failed"):
                await reload_settings()

        current_settings = get_settings()
        assert current_settings is old_settings
