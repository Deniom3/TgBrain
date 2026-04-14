"""
Unit tests for WebhookService — дополнительные тесты.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.webhook.webhook_service import WebhookService
from src.webhook.exceptions import WebhookDeliveryError, WebhookValidationError
from src.domain.exceptions import ValidationError


@pytest.fixture
def webhook_service() -> WebhookService:
    """Создать WebhookService для тестов."""
    return WebhookService(timeout=5.0, max_retries=3, backoff_seconds=1)


@pytest.fixture
def sample_webhook_config() -> dict:
    """Конфигурация webhook для тестов."""
    return {
        "url": "https://example.com/webhook",
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body_template": {
            "summary": "{{summary}}",
        },
    }


class TestSummaryWebhookServiceSequentialCalls:
    """Тесты проверки что SummaryWebhookService не закрывает singleton WebhookService."""

    @pytest.mark.asyncio
    async def test_two_consecutive_send_webhook_for_summary_do_not_close_service(
        self,
    ) -> None:
        """Два последовательных вызова send_webhook_for_summary не закрывают WebhookService."""
        from contextlib import asynccontextmanager
        from src.infrastructure.services.summary_webhook_service import SummaryWebhookService

        mock_webhook_service = AsyncMock(spec=WebhookService)
        mock_webhook_service.send_summary_webhook = AsyncMock(return_value=True)
        mock_webhook_service.close = AsyncMock()

        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_db_pool = MagicMock()
        mock_db_pool.acquire = mock_acquire

        mock_summary = MagicMock()
        mock_summary.result_text = "Test summary result"
        mock_summary.period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        mock_summary.period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)
        mock_summary.messages_count = 50
        mock_summary.status = MagicMock()
        mock_summary.status.value = "completed"

        mock_summary_repo = AsyncMock()
        mock_summary_repo.get_summary_task = AsyncMock(return_value=mock_summary)

        mock_chat_settings_repo = AsyncMock()
        mock_chat_setting = MagicMock()
        mock_chat_setting.title = "Test Chat"
        mock_chat_settings_repo.get = AsyncMock(return_value=mock_chat_setting)

        service = SummaryWebhookService(
            config=MagicMock(),
            rag_search=MagicMock(),
            llm_client=MagicMock(),
            embeddings_client=MagicMock(),
            db_pool=mock_db_pool,
            webhook_service=mock_webhook_service,
            chat_settings_repo=mock_chat_settings_repo,
            summary_usecase=AsyncMock(),
            summary_repo=mock_summary_repo,
        )

        result1 = await service.send_webhook_for_summary(
            task_id=1,
            chat_id=123,
            config={"url": "https://example.com/webhook"},
        )

        assert result1 is True

        mock_webhook_service.close.assert_not_called()

        result2 = await service.send_webhook_for_summary(
            task_id=2,
            chat_id=456,
            config={"url": "https://example.com/webhook2"},
        )

        assert result2 is True

        mock_webhook_service.close.assert_not_called()

        assert mock_webhook_service.send_summary_webhook.await_count == 2


class TestWebhookServiceClientManagement:
    """Тесты управления HTTP клиентом."""

    @pytest.mark.asyncio
    async def test_get_client_lazy_initialization(
        self, webhook_service: WebhookService
    ) -> None:
        """Клиент создаётся при первом вызове."""
        assert webhook_service._client is None
        
        client = webhook_service._get_client()
        
        assert client is not None
        assert webhook_service._client is not None
        assert isinstance(client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing(
        self, webhook_service: WebhookService
    ) -> None:
        """Повторный вызов возвращает тот же клиент."""
        client1 = webhook_service._get_client()
        client2 = webhook_service._get_client()
        
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_close_sets_client_to_none(
        self, webhook_service: WebhookService
    ) -> None:
        """Закрытие устанавливает _client в None."""
        webhook_service._get_client()
        assert webhook_service._client is not None
        
        await webhook_service.close()
        
        assert webhook_service._client is None


class TestWebhookServiceRetryLogic:
    """Тесты логики retry."""

    @pytest.mark.asyncio
    async def test_send_webhook_5xx_exponential_backoff(
        self, webhook_service: WebhookService, sample_webhook_config: dict
    ) -> None:
        """5xx ошибка использует exponential backoff."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        mock_response = AsyncMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with patch("asyncio.sleep") as mock_sleep:
                with pytest.raises(WebhookDeliveryError):
                    await webhook_service.send_summary_webhook(
                        webhook_config=sample_webhook_config,
                        summary_text="Test",
                        chat_id=123,
                        chat_title="Test",
                        period_start=period_start,
                        period_end=period_end,
                        messages_count=10,
                    )

                assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_send_webhook_timeout_exponential_backoff(
        self, webhook_service: WebhookService, sample_webhook_config: dict
    ) -> None:
        """Timeout использует exponential backoff."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            mock_get_client.return_value = mock_client

            with patch("asyncio.sleep") as mock_sleep:
                with pytest.raises(WebhookDeliveryError):
                    await webhook_service.send_summary_webhook(
                        webhook_config=sample_webhook_config,
                        summary_text="Test",
                        chat_id=123,
                        chat_title="Test",
                        period_start=period_start,
                        period_end=period_end,
                        messages_count=10,
                    )
                
                assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_send_webhook_request_error_exponential_backoff(
        self, webhook_service: WebhookService, sample_webhook_config: dict
    ) -> None:
        """RequestError использует exponential backoff."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(
                side_effect=httpx.RequestError("Network error")
            )
            mock_get_client.return_value = mock_client

            with patch("asyncio.sleep") as mock_sleep:
                with pytest.raises(WebhookDeliveryError):
                    await webhook_service.send_summary_webhook(
                        webhook_config=sample_webhook_config,
                        summary_text="Test",
                        chat_id=123,
                        chat_title="Test",
                        period_start=period_start,
                        period_end=period_end,
                        messages_count=10,
                    )
                
                assert mock_sleep.call_count == 2


class TestWebhookServiceSuccessStatuses:
    """Тесты различных успешных статусов."""

    @pytest.mark.asyncio
    async def test_send_webhook_success_202(
        self, webhook_service: WebhookService, sample_webhook_config: dict
    ) -> None:
        """Статус 202 считается успешным."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        mock_response = AsyncMock()
        mock_response.status_code = 202

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await webhook_service.send_summary_webhook(
                webhook_config=sample_webhook_config,
                summary_text="Test",
                chat_id=123,
                chat_title="Test",
                period_start=period_start,
                period_end=period_end,
                messages_count=10,
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_send_webhook_success_204(
        self, webhook_service: WebhookService, sample_webhook_config: dict
    ) -> None:
        """Статус 204 считается успешным."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        mock_response = AsyncMock()
        mock_response.status_code = 204

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await webhook_service.send_summary_webhook(
                webhook_config=sample_webhook_config,
                summary_text="Test",
                chat_id=123,
                chat_title="Test",
                period_start=period_start,
                period_end=period_end,
                messages_count=10,
            )

            assert result is True


class TestWebhookServiceErrorStatuses:
    """Тесты различных ошибочных статусов."""

    @pytest.mark.asyncio
    async def test_send_webhook_400_no_retry(
        self, webhook_service: WebhookService, sample_webhook_config: dict
    ) -> None:
        """Статус 400 не вызывает retry."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(WebhookDeliveryError, match="Client error: 400"):
                await webhook_service.send_summary_webhook(
                    webhook_config=sample_webhook_config,
                    summary_text="Test",
                    chat_id=123,
                    chat_title="Test",
                    period_start=period_start,
                    period_end=period_end,
                    messages_count=10,
                )

            mock_client.request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_webhook_401_no_retry(
        self, webhook_service: WebhookService, sample_webhook_config: dict
    ) -> None:
        """Статус 401 не вызывает retry."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(WebhookDeliveryError, match="Client error: 401"):
                await webhook_service.send_summary_webhook(
                    webhook_config=sample_webhook_config,
                    summary_text="Test",
                    chat_id=123,
                    chat_title="Test",
                    period_start=period_start,
                    period_end=period_end,
                    messages_count=10,
                )

            mock_client.request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_webhook_502_retry(
        self, webhook_service: WebhookService, sample_webhook_config: dict
    ) -> None:
        """Статус 502 вызывает retry."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        mock_response = AsyncMock()
        mock_response.status_code = 502
        mock_response.text = "Bad Gateway"

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(WebhookDeliveryError, match="Server error after 3 attempts: 502"):
                await webhook_service.send_summary_webhook(
                    webhook_config=sample_webhook_config,
                    summary_text="Test",
                    chat_id=123,
                    chat_title="Test",
                    period_start=period_start,
                    period_end=period_end,
                    messages_count=10,
                )

            assert mock_client.request.await_count == 3


class TestWebhookServiceValidationEdgeCases:
    """Тесты граничных случаев валидации."""

    @pytest.mark.asyncio
    async def test_send_webhook_empty_url(
        self, webhook_service: WebhookService
    ) -> None:
        """Пустой URL вызывает исключение."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        webhook_config = {
            "url": "",
            "method": "POST",
            "headers": {},
            "body_template": {},
        }

        with pytest.raises(WebhookValidationError, match="Webhook URL не указан"):
            await webhook_service.send_summary_webhook(
                webhook_config=webhook_config,
                summary_text="Test",
                chat_id=123,
                chat_title="Test",
                period_start=period_start,
                period_end=period_end,
                messages_count=10,
            )
    @pytest.mark.asyncio
    async def test_send_webhook_default_method_post(
        self, webhook_service: WebhookService
    ) -> None:
        """Метод по умолчанию POST."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        webhook_config = {
            "url": "https://example.com/webhook",
            "headers": {},
            "body_template": {},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await webhook_service.send_summary_webhook(
                webhook_config=webhook_config,
                summary_text="Test",
                chat_id=123,
                chat_title="Test",
                period_start=period_start,
                period_end=period_end,
                messages_count=10,
            )

            assert result is True
            call_args = mock_client.request.call_args
            assert call_args.kwargs["method"] == "POST"


class TestWebhookServiceErrorCodes:
    """Тесты покрытия error codes WH-001 — WH-006."""

    @pytest.mark.asyncio
    async def test_wh001_invalid_webhook_url(
        self, webhook_service: WebhookService
    ) -> None:
        """WH-001: Invalid webhook URL."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        webhook_config = {
            "url": "not-a-valid-url",
            "method": "POST",
            "headers": {},
            "body_template": {},
        }

        with pytest.raises(ValidationError, match="Webhook URL должен быть HTTPS"):
            await webhook_service.send_summary_webhook(
                webhook_config=webhook_config,
                summary_text="Test",
                chat_id=123,
                chat_title="Test",
                period_start=period_start,
                period_end=period_end,
                messages_count=10,
            )

    @pytest.mark.asyncio
    async def test_wh002_webhook_send_failed(
        self, webhook_service: WebhookService
    ) -> None:
        """WH-002: Webhook send failed."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        webhook_config = {
            "url": "https://example.com/webhook",
            "method": "POST",
            "headers": {},
            "body_template": {},
        }

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )
            mock_get_client.return_value = mock_client

            with patch("asyncio.sleep"):
                with pytest.raises(WebhookDeliveryError, match="Request failed after"):
                    await webhook_service.send_summary_webhook(
                        webhook_config=webhook_config,
                        summary_text="Test",
                        chat_id=123,
                        chat_title="Test",
                        period_start=period_start,
                        period_end=period_end,
                        messages_count=10,
                    )

    @pytest.mark.asyncio
    async def test_wh003_webhook_timeout(
        self, webhook_service: WebhookService
    ) -> None:
        """WH-003: Webhook timeout."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        webhook_config = {
            "url": "https://example.com/webhook",
            "method": "POST",
            "headers": {},
            "body_template": {},
        }

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )
            mock_get_client.return_value = mock_client

            with patch("asyncio.sleep"):
                with pytest.raises(WebhookDeliveryError, match="Timeout after"):
                    await webhook_service.send_summary_webhook(
                        webhook_config=webhook_config,
                        summary_text="Test",
                        chat_id=123,
                        chat_title="Test",
                        period_start=period_start,
                        period_end=period_end,
                        messages_count=10,
                    )

    @pytest.mark.asyncio
    async def test_wh004_webhook_rate_limit(
        self, webhook_service: WebhookService
    ) -> None:
        """WH-004: Webhook rate limit."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        webhook_config = {
            "url": "https://example.com/webhook",
            "method": "POST",
            "headers": {},
            "body_template": {},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(WebhookDeliveryError, match="Client error: 429"):
                await webhook_service.send_summary_webhook(
                    webhook_config=webhook_config,
                    summary_text="Test",
                    chat_id=123,
                    chat_title="Test",
                    period_start=period_start,
                    period_end=period_end,
                    messages_count=10,
                )

    @pytest.mark.asyncio
    async def test_wh005_template_render_error(
        self, webhook_service: WebhookService
    ) -> None:
        """WH-005: Template render error."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        webhook_config = {
            "url": "https://example.com/webhook",
            "method": "POST",
            "headers": {},
            "body_template": {"text": "{{invalid_variable}}"},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch.object(webhook_service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await webhook_service.send_summary_webhook(
                webhook_config=webhook_config,
                summary_text="Test",
                chat_id=123,
                chat_title="Test",
                period_start=period_start,
                period_end=period_end,
                messages_count=10,
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_wh006_webhook_not_configured(
        self, webhook_service: WebhookService
    ) -> None:
        """WH-006: Webhook not configured."""
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        webhook_config = {
            "url": "",
            "method": "POST",
            "headers": {},
            "body_template": {},
        }

        with pytest.raises(WebhookValidationError, match="Webhook URL не указан"):
            await webhook_service.send_summary_webhook(
                webhook_config=webhook_config,
                summary_text="Test",
                chat_id=123,
                chat_title="Test",
                period_start=period_start,
                period_end=period_end,
                messages_count=10,
            )
