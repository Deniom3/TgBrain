"""
Тесты: LLMClient без мутации Settings.

Проверяют что LLMClient не изменяет config при создании провайдеров
и корректно обновляется через refresh_config().
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm_client import LLMClient
from src.providers import ProviderFactory


def _make_mock_settings(
    active_provider: str = "gemini",
    model_name: str = "gemini-2.0-flash",
    auto_fallback: bool = False,
    fallback_timeout: float = 5.0,
    fallback_provider: str = "ollama",
) -> MagicMock:
    """Создать мок Settings с заданными параметрами."""
    settings = MagicMock()
    settings.llm_active_provider = active_provider
    settings.llm_model_name = model_name
    settings.llm_auto_fallback = auto_fallback
    settings.llm_fallback_timeout = fallback_timeout
    settings.llm_fallback_provider = fallback_provider
    settings.get_provider_chain.return_value = [active_provider.lower()]
    settings.is_local_provider.return_value = False
    return settings


def _make_mock_provider() -> MagicMock:
    """Создать мок LLM провайдера."""
    provider = MagicMock()
    provider.check_health = AsyncMock(return_value=True)
    provider.get_models = AsyncMock(return_value=["model-1", "model-2"])
    provider.generate = AsyncMock(return_value="ok")
    provider.close = AsyncMock()
    return provider


class TestCreateProviderNoMutation:
    """Тесты: _create_provider не мутирует config."""

    def test_llm_client_create_provider_no_config_mutation(self) -> None:
        """_create_provider не изменяет config.llm_active_provider."""
        settings = _make_mock_settings(active_provider="gemini")
        client = LLMClient(settings)
        mock_provider = _make_mock_provider()

        with patch.object(
            ProviderFactory, "create", return_value=mock_provider
        ) as mock_create:
            provider = client._create_provider("ollama")

            assert provider is mock_provider
            assert settings.llm_active_provider == "gemini"
            mock_create.assert_called_once_with(settings, "ollama")

    def test_llm_client_create_provider_passes_name_to_factory(self) -> None:
        """_create_provider передаёт provider_name в ProviderFactory.create."""
        settings = _make_mock_settings(active_provider="gemini")
        client = LLMClient(settings)
        mock_provider = _make_mock_provider()

        with patch.object(
            ProviderFactory, "create", return_value=mock_provider
        ) as mock_create:
            client._create_provider("openrouter")

            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert call_args[0][0] is settings
            assert call_args[0][1] == "openrouter"


class TestCheckHealthNoMutation:
    """Тесты: check_health не мутирует config."""

    @pytest.mark.asyncio
    async def test_llm_client_check_health_no_config_mutation(self) -> None:
        """check_health не изменяет config.llm_active_provider."""
        settings = _make_mock_settings(active_provider="gemini")
        settings.get_provider_chain.return_value = ["gemini"]
        settings.is_local_provider.return_value = False
        client = LLMClient(settings)
        mock_provider = _make_mock_provider()

        with patch.object(
            ProviderFactory, "create", return_value=mock_provider
        ):
            result = await client.check_health()

            assert result is True
            assert settings.llm_active_provider == "gemini"


class TestGetModelsNoMutation:
    """Тесты: get_models не мутирует config."""

    @pytest.mark.asyncio
    async def test_llm_client_get_models_no_config_mutation(self) -> None:
        """get_models не изменяет config.llm_active_provider."""
        settings = _make_mock_settings(active_provider="gemini")
        settings.get_provider_chain.return_value = ["gemini"]
        settings.is_local_provider.return_value = False
        client = LLMClient(settings)
        mock_provider = _make_mock_provider()

        with patch.object(
            ProviderFactory, "create", return_value=mock_provider
        ):
            models = await client.get_models()

            assert models == ["model-1", "model-2"]
            assert settings.llm_active_provider == "gemini"


class TestConcurrentCreateProviderSafe:
    """Тесты: конкурентные вызовы _create_provider безопасны."""

    @pytest.mark.asyncio
    async def test_llm_client_concurrent_create_provider_safe(self) -> None:
        """Конкурентные _create_provider не вызывают race condition."""
        settings = _make_mock_settings(active_provider="gemini")
        client = LLMClient(settings)

        call_count = 0

        def mock_factory_create(config, name):
            nonlocal call_count
            call_count += 1
            provider = MagicMock()
            provider.check_health = AsyncMock(return_value=True)
            provider.generate = AsyncMock(return_value="ok")
            provider.close = AsyncMock()
            return provider

        with patch.object(ProviderFactory, "create", side_effect=mock_factory_create):
            tasks = [
                asyncio.create_task(
                    asyncio.to_thread(client._create_provider, "gemini")
                )
                for _ in range(10)
            ]
            results = await asyncio.gather(*tasks)

            assert len(results) == 10
            assert call_count == 10
            assert settings.llm_active_provider == "gemini"


class TestFallbackChainNoMutation:
    """Тесты: fallback-цепочка не мутирует config."""

    @pytest.mark.asyncio
    async def test_llm_client_fallback_chain_no_mutation(self) -> None:
        """Fallback-цепочка создаёт провайдеры без мутации config."""
        settings = _make_mock_settings(
            active_provider="gemini",
            auto_fallback=True,
            fallback_provider="ollama",
        )
        settings.get_provider_chain.return_value = ["gemini", "ollama"]
        settings.is_local_provider.return_value = False
        client = LLMClient(settings)
        mock_provider = _make_mock_provider()
        create_calls: list[tuple] = []

        def track_create(config, name):
            create_calls.append((config, name))
            return mock_provider

        with patch.object(ProviderFactory, "create", side_effect=track_create):
            result = await client.check_health()

            assert result is True
            assert settings.llm_active_provider == "gemini"
            assert len(create_calls) >= 1


class TestRefreshConfig:
    """Тесты: refresh_config корректно обновляет состояние."""

    def test_llm_client_refresh_config_updates_reference(self) -> None:
        """refresh_config обновляет self.config и пересоздаёт провайдер."""
        old_settings = _make_mock_settings(
            active_provider="gemini",
            model_name="gemini-2.0-flash",
            auto_fallback=False,
            fallback_timeout=5.0,
        )
        client = LLMClient(old_settings)
        mock_old_provider = _make_mock_provider()
        with patch.object(ProviderFactory, "create", return_value=mock_old_provider):
            client._create_provider("gemini")

        new_settings = _make_mock_settings(
            active_provider="openrouter",
            model_name="gpt-4o-mini",
            auto_fallback=True,
            fallback_timeout=10.0,
        )

        client.refresh_config(new_settings)

        assert client.config is new_settings
        assert client.provider_name == "openrouter"
        assert client.model == "gpt-4o-mini"
        assert client.auto_fallback is True
        assert client.fallback_timeout == 10.0
        assert client._provider is None
        assert client._current_provider_name is None

    def test_llm_client_refresh_config_preserves_provider_cache(self) -> None:
        """refresh_config очищает кэш доступных провайдеров."""
        settings = _make_mock_settings(active_provider="gemini")
        client = LLMClient(settings)
        mock_provider = _make_mock_provider()

        with patch.object(ProviderFactory, "create", return_value=mock_provider):
            client._create_provider("gemini")
            client._available_providers["gemini"] = True
            client._available_providers["ollama"] = False

        new_settings = _make_mock_settings(active_provider="openrouter")
        client.refresh_config(new_settings)

        assert len(client._available_providers) == 0
        assert client.config is new_settings
