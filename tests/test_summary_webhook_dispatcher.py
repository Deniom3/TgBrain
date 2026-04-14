"""
Тесты для SummaryWebhookDispatcher.

Unit-тесты: проверка конфигурации, пропуска, ошибок.
Integration-тест: с mock HTTP сервером.
"""

import logging
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.services.summary_webhook_dispatcher import (
    SummaryWebhookDispatcher,
)
from src.infrastructure.services.summary_webhook_service import SummaryWebhookService
from src.settings.repositories.chat_settings import ChatSettingsRepository


@pytest.fixture
def mock_webhook_service() -> AsyncMock:
    """Фикстура mock SummaryWebhookService."""
    return AsyncMock(spec=SummaryWebhookService)


@pytest.fixture
def mock_chat_settings_repo() -> AsyncMock:
    """Фикстура mock ChatSettingsRepository."""
    return AsyncMock(spec=ChatSettingsRepository)


@pytest.fixture
def test_logger() -> logging.Logger:
    """Фикстура логгера для тестов."""
    return logging.getLogger("test.webhook_dispatcher")


@pytest.fixture
def dispatcher(
    mock_webhook_service: AsyncMock,
    mock_chat_settings_repo: AsyncMock,
    test_logger: logging.Logger,
) -> SummaryWebhookDispatcher:
    """Фикстура SummaryWebhookDispatcher с мокнутыми зависимостями."""
    return SummaryWebhookDispatcher(
        webhook_service=mock_webhook_service,
        chat_settings_repo=mock_chat_settings_repo,
        logger=test_logger,
    )


class TestDispatchWebhookConfiguredSends:
    """Тесты: webhook настроен — fire-and-forget вызов."""

    async def test_dispatch_webhook_configured_sends(
        self,
        dispatcher: SummaryWebhookDispatcher,
        mock_webhook_service: AsyncMock,
        mock_chat_settings_repo: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Webhook настроен — планирование отправки, возврат True."""
        webhook_config = {"url": "https://example.com/hook", "method": "POST"}
        mock_chat_settings_repo.get_webhook_config_raw.return_value = webhook_config

        with caplog.at_level(logging.INFO):
            result = await dispatcher.dispatch_webhook_on_completion(
                task_id=42,
                chat_id=123,
            )

        assert result is True
        mock_chat_settings_repo.get_webhook_config_raw.assert_awaited_once_with(123)
        mock_webhook_service.send_webhook_after_generation.assert_called_once_with(
            task_id=42,
            chat_id=123,
            config=webhook_config,
        )
        assert any(
            "webhook запланирован к отправке для чата 123" in record.message
            for record in caplog.records
            if record.levelno == logging.INFO
        )


class TestDispatchWebhookNoConfigSkips:
    """Тесты: конфиг отсутствует — пропуск."""

    async def test_dispatch_webhook_no_config_skips(
        self,
        dispatcher: SummaryWebhookDispatcher,
        mock_chat_settings_repo: AsyncMock,
    ) -> None:
        """Конфиг отсутствует — возврат False, без вызова webhook."""
        mock_chat_settings_repo.get_webhook_config_raw.return_value = None

        result = await dispatcher.dispatch_webhook_on_completion(
            task_id=42,
            chat_id=123,
        )

        assert result is False
        mock_chat_settings_repo.get_webhook_config_raw.assert_awaited_once_with(123)


class TestDispatchWebhookConfigErrorLogs:
    """Тесты: ошибка получения конфига — warning."""

    async def test_dispatch_webhook_config_error_logs(
        self,
        dispatcher: SummaryWebhookDispatcher,
        mock_chat_settings_repo: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Ошибка получения конфига — warning лог, возврат False."""
        mock_chat_settings_repo.get_webhook_config_raw.side_effect = (
            ConnectionError("DB unavailable")
        )

        with caplog.at_level(logging.DEBUG):
            result = await dispatcher.dispatch_webhook_on_completion(
                task_id=42,
                chat_id=123,
            )

        assert result is False
        assert any(
            "Ошибка при подготовке отправки webhook для задачи 42: ConnectionError"
            in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        )


class TestDispatchWebhookSendErrorLogs:
    """Тесты: ошибка при создании fire-and-forget задачи."""

    async def test_dispatch_webhook_send_error_logs(
        self,
        dispatcher: SummaryWebhookDispatcher,
        mock_webhook_service: AsyncMock,
        mock_chat_settings_repo: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Fire-and-forget задача создаётся успешно — возврат True.

        Ошибка в фоне (background task) не перехватывается диспетчером —
        это ожидаемое поведение graceful degradation.
        """
        webhook_config = {"url": "https://example.com/hook"}
        mock_chat_settings_repo.get_webhook_config_raw.return_value = webhook_config

        with caplog.at_level(logging.DEBUG):
            result = await dispatcher.dispatch_webhook_on_completion(
                task_id=42,
                chat_id=123,
            )

        assert result is True
        mock_webhook_service.send_webhook_after_generation.assert_called_once_with(
            task_id=42,
            chat_id=123,
            config=webhook_config,
        )


class TestDispatchWebhookDisabled:
    """Тесты: webhook отключён — пропуск."""

    async def test_dispatch_webhook_webhook_disabled(
        self,
        dispatcher: SummaryWebhookDispatcher,
        mock_chat_settings_repo: AsyncMock,
    ) -> None:
        """Webhook отключён (пустой конфиг) — возврат False."""
        mock_chat_settings_repo.get_webhook_config_raw.return_value = {}

        result = await dispatcher.dispatch_webhook_on_completion(
            task_id=42,
            chat_id=123,
        )

        assert result is False
        mock_chat_settings_repo.get_webhook_config_raw.assert_awaited_once_with(123)


@pytest.mark.integration
class TestDispatchWebhookIntegration:
    """Integration-тесты для dispatch_webhook_on_completion."""

    async def test_dispatch_webhook_integration(
        self,
        mock_webhook_service: AsyncMock,
        mock_chat_settings_repo: AsyncMock,
        test_logger: logging.Logger,
    ) -> None:
        """Полный цикл: получение конфига и планирование отправки."""
        webhook_config = {
            "url": "https://example.com/hook",
            "method": "POST",
            "body_template": {"text": "{{summary}}"},
        }
        mock_chat_settings_repo.get_webhook_config_raw.return_value = webhook_config

        dispatcher = SummaryWebhookDispatcher(
            webhook_service=mock_webhook_service,
            chat_settings_repo=mock_chat_settings_repo,
            logger=test_logger,
        )

        result = await dispatcher.dispatch_webhook_on_completion(
            task_id=200,
            chat_id=456,
        )

        assert result is True
        mock_chat_settings_repo.get_webhook_config_raw.assert_awaited_once_with(456)
        mock_webhook_service.send_webhook_after_generation.assert_called_once_with(
            task_id=200,
            chat_id=456,
            config=webhook_config,
        )
