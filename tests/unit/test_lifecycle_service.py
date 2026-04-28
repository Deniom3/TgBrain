"""Тесты ApplicationLifecycleService — обработка запуска Ingester."""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.application_lifecycle_service import ApplicationLifecycleService


class TestLifecycleInitIngester:
    """Тесты метода _init_ingester — обработка запуска Ingester."""

    @pytest.mark.asyncio
    async def test_init_ingester_success_sets_ingester_in_state(self) -> None:
        """Успешный start() с _running=True оставляет ingester в state."""
        # Arrange
        service = ApplicationLifecycleService(MagicMock())
        mock_ingester = AsyncMock()
        mock_ingester._running = True

        state: Dict[str, Any] = {
            "embeddings": MagicMock(),
            "rate_limiter": MagicMock(),
        }
        mock_auth_repo = MagicMock()
        mock_app_settings_repo = MagicMock()

        # Act
        with patch(
            "src.ingestion.TelegramIngester",
            return_value=mock_ingester,
        ):
            await service._init_ingester(
                state, service.settings, mock_auth_repo, mock_app_settings_repo
            )

        # Assert
        assert state["ingester"] is mock_ingester
        mock_ingester.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_init_ingester_exception_sets_ingester_none(self) -> None:
        """Исключение при start() устанавливает ingester=None в state."""
        # Arrange
        service = ApplicationLifecycleService(MagicMock())
        mock_ingester = AsyncMock()
        mock_ingester.start = AsyncMock(side_effect=RuntimeError("Connection failed"))
        mock_ingester._running = False

        state: Dict[str, Any] = {
            "embeddings": MagicMock(),
            "rate_limiter": MagicMock(),
        }
        mock_auth_repo = MagicMock()
        mock_app_settings_repo = MagicMock()

        # Act
        with patch(
            "src.ingestion.TelegramIngester",
            return_value=mock_ingester,
        ):
            await service._init_ingester(
                state, service.settings, mock_auth_repo, mock_app_settings_repo
            )

        # Assert
        assert state["ingester"] is None

    @pytest.mark.asyncio
    async def test_init_ingester_silent_return_sets_ingester_none(self) -> None:
        """Silent return из start() (_running=False) устанавливает ingester=None."""
        # Arrange
        service = ApplicationLifecycleService(MagicMock())
        mock_ingester = AsyncMock()
        mock_ingester.start = AsyncMock(return_value=None)
        mock_ingester._running = False

        state: Dict[str, Any] = {
            "embeddings": MagicMock(),
            "rate_limiter": MagicMock(),
        }
        mock_auth_repo = MagicMock()
        mock_app_settings_repo = MagicMock()

        # Act
        with patch(
            "src.ingestion.TelegramIngester",
            return_value=mock_ingester,
        ):
            await service._init_ingester(
                state, service.settings, mock_auth_repo, mock_app_settings_repo
            )

        # Assert
        assert state["ingester"] is None
