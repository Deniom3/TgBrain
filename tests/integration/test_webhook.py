"""
Integration tests for WebhookService.

Требует mock HTTP сервер (respx).
"""

import pytest
import respx
import httpx
import socket
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

from src.webhook.webhook_service import WebhookService
from src.webhook.exceptions import WebhookDeliveryError

pytestmark = pytest.mark.integration


@pytest.fixture
def webhook_service() -> WebhookService:
    """Create WebhookService for integration tests."""
    return WebhookService(timeout=5.0, max_retries=3, backoff_seconds=1)


@pytest.fixture
def sample_webhook_config() -> dict:
    """Sample webhook configuration."""
    return {
        "url": "https://api.example.com/webhook",
        "method": "POST",
        "headers": {"Content-Type": "application/json", "X-API-Key": "<TEST_API_KEY>"},
        "body_template": {
            "text": "{{summary}}",
            "chat_id": "{{chat_id}}",
            "chat_title": "{{chat_title}}",
        },
    }


@pytest.fixture
def mock_dns_resolution():
    """Mock DNS resolution to allow test hostnames.
    
    Returns public IP addresses for test domains to pass SSRF protection.
    """
    # Mock sync socket.getaddrinfo (used in WebhookUrl value object)
    def mock_getaddrinfo(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM, proto=0, flags=0):
        # Return public IP for test domains
        if host in ("api.example.com", "webhook.site", "example.com"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', port or 0))]
        elif host.startswith("api.telegram.org"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('149.154.167.99', port or 0))]
        # For unknown hosts, raise gaierror as real DNS would
        raise socket.gaierror("Mock DNS: unknown host")
    
    # Mock async loop.getaddrinfo (used in WebhookService._validate_ip_address)
    async def mock_async_getaddrinfo(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM, proto=0, flags=0):
        return mock_getaddrinfo(host, port, family, type, proto, flags)
    
    with patch('socket.getaddrinfo', side_effect=mock_getaddrinfo):
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(side_effect=mock_async_getaddrinfo)
            yield


@pytest.mark.integration
class TestWebhookServiceHTTPIntegration:
    """Интеграционные тесты с реальным HTTP клиентом."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_send_telegram_bot_api(self, webhook_service, mock_dns_resolution):
        """Отправка в Telegram Bot API."""
        telegram_config = {
            "url": "https://api.telegram.org/<TEST_BOT_TOKEN>/sendMessage",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body_template": {
                "chat_id": "{{chat_id}}",
                "text": "{{summary}}",
            },
        }

        respx.post("https://api.telegram.org/<TEST_BOT_TOKEN>/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {}})
        )

        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)

        result = await webhook_service.send_summary_webhook(
            webhook_config=telegram_config,
            summary_text="Test summary",
            chat_id=123,
            chat_title="Test Chat",
            period_start=period_start,
            period_end=period_end,
            messages_count=10,
        )

        assert result is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_send_custom_webhook(
        self, webhook_service, sample_webhook_config, mock_dns_resolution
    ):
        """Отправка в произвольный webhook."""
        respx.post("https://api.example.com/webhook").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)
        
        result = await webhook_service.send_summary_webhook(
            webhook_config=sample_webhook_config,
            summary_text="Test summary",
            chat_id=123,
            chat_title="Test Chat",
            period_start=period_start,
            period_end=period_end,
            messages_count=10,
        )
        
        assert result is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_retry_on_timeout(
        self, webhook_service, sample_webhook_config, mock_dns_resolution
    ):
        """Retry при timeout."""
        respx.post("https://api.example.com/webhook").mock(
            side_effect=[
                httpx.TimeoutException("Timeout"),
                httpx.TimeoutException("Timeout"),
                httpx.Response(200, json={"status": "ok"}),
            ]
        )
        
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)
        
        with patch("asyncio.sleep"):
            result = await webhook_service.send_summary_webhook(
                webhook_config=sample_webhook_config,
                summary_text="Test summary",
                chat_id=123,
                chat_title="Test Chat",
                period_start=period_start,
                period_end=period_end,
                messages_count=10,
            )
        
        assert result is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_retry_on_5xx(
        self, webhook_service, sample_webhook_config, mock_dns_resolution
    ):
        """Retry при 5xx."""
        respx.post("https://api.example.com/webhook").mock(
            side_effect=[
                httpx.Response(503, json={"error": "Service unavailable"}),
                httpx.Response(503, json={"error": "Service unavailable"}),
                httpx.Response(200, json={"status": "ok"}),
            ]
        )
        
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)
        
        with patch("asyncio.sleep"):
            result = await webhook_service.send_summary_webhook(
                webhook_config=sample_webhook_config,
                summary_text="Test summary",
                chat_id=123,
                chat_title="Test Chat",
                period_start=period_start,
                period_end=period_end,
                messages_count=10,
            )
        
        assert result is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_no_retry_on_4xx(
        self, webhook_service, sample_webhook_config, mock_dns_resolution
    ):
        """Без retry при 4xx."""
        respx.post("https://api.example.com/webhook").mock(
            return_value=httpx.Response(400, json={"error": "Bad request"})
        )
        
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)
        
        with pytest.raises(WebhookDeliveryError, match="Client error: 400"):
            await webhook_service.send_summary_webhook(
                webhook_config=sample_webhook_config,
                summary_text="Test summary",
                chat_id=123,
                chat_title="Test Chat",
                period_start=period_start,
                period_end=period_end,
                messages_count=10,
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_rate_limit_429(self, webhook_service, sample_webhook_config, mock_dns_resolution):
        """Обработка 429 Retry-After."""
        respx.post("https://api.example.com/webhook").mock(
            side_effect=[
                httpx.Response(
                    429,
                    headers={"Retry-After": "2"},
                    json={"error": "Too many requests"},
                ),
                httpx.Response(200, json={"status": "ok"}),
            ]
        )
        
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)
        
        with pytest.raises(WebhookDeliveryError, match="Client error: 429"):
            await webhook_service.send_summary_webhook(
                webhook_config=sample_webhook_config,
                summary_text="Test summary",
                chat_id=123,
                chat_title="Test Chat",
                period_start=period_start,
                period_end=period_end,
                messages_count=10,
            )


@pytest.mark.integration
class TestWebhookServiceTemplateIntegration:
    """Интеграционные тесты шаблонизации."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_template_all_variables(self, webhook_service, mock_dns_resolution):
        """Шаблонизация всех переменных."""
        webhook_config = {
            "url": "https://api.example.com/webhook/{{chat_id}}",
            "method": "POST",
            "headers": {
                "Content-Type": "application/json",
                "X-Chat-Title": "{{chat_title}}",
            },
            "body_template": {
                "summary": "{{summary}}",
                "chat_id": "{{chat_id}}",
                "chat_title": "{{chat_title}}",
                "period_start": "{{period_start}}",
                "period_end": "{{period_end}}",
                "messages_count": "{{messages_count}}",
            },
        }
        
        route = respx.post("https://api.example.com/webhook/123").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)
        
        result = await webhook_service.send_summary_webhook(
            webhook_config=webhook_config,
            summary_text="Test summary",
            chat_id=123,
            chat_title="Test Chat",
            period_start=period_start,
            period_end=period_end,
            messages_count=10,
        )
        
        assert result is True
        assert route.called
        
        request = route.calls.last.request
        assert request.headers["X-Chat-Title"] == "Test Chat"

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_template_nested_structure(self, webhook_service, mock_dns_resolution):
        """Шаблонизация вложенной структуры."""
        webhook_config = {
            "url": "https://api.example.com/webhook",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body_template": {
                "data": {
                    "summary": "{{summary}}",
                    "chat": {
                        "id": "{{chat_id}}",
                        "title": "{{chat_title}}",
                    },
                    "period": {
                        "start": "{{period_start}}",
                        "end": "{{period_end}}",
                    },
                },
                "metadata": {
                    "messages_count": "{{messages_count}}",
                },
            },
        }
        
        route = respx.post("https://api.example.com/webhook").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)
        
        result = await webhook_service.send_summary_webhook(
            webhook_config=webhook_config,
            summary_text="Test summary",
            chat_id=123,
            chat_title="Test Chat",
            period_start=period_start,
            period_end=period_end,
            messages_count=10,
        )
        
        assert result is True
        assert route.called


@pytest.mark.integration
class TestWebhookServiceErrorHandling:
    """Интеграционные тесты обработки ошибок."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_network_error_all_retries_fail(
        self, webhook_service, sample_webhook_config, mock_dns_resolution
    ):
        """Все retry неудачны → исключение."""
        respx.post("https://api.example.com/webhook").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)
        
        with patch("asyncio.sleep"):
            with pytest.raises(WebhookDeliveryError, match="Request failed after 3 attempts"):
                await webhook_service.send_summary_webhook(
                    webhook_config=sample_webhook_config,
                    summary_text="Test summary",
                    chat_id=123,
                    chat_title="Test Chat",
                    period_start=period_start,
                    period_end=period_end,
                    messages_count=10,
                )

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_timeout_all_retries_fail(
        self, webhook_service, sample_webhook_config, mock_dns_resolution
    ):
        """Все timeout retry неудачны → исключение."""
        respx.post("https://api.example.com/webhook").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)
        
        with patch("asyncio.sleep"):
            with pytest.raises(WebhookDeliveryError, match="Timeout after 3 attempts"):
                await webhook_service.send_summary_webhook(
                    webhook_config=sample_webhook_config,
                    summary_text="Test summary",
                    chat_id=123,
                    chat_title="Test Chat",
                    period_start=period_start,
                    period_end=period_end,
                    messages_count=10,
                )

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_5xx_all_retries_fail(
        self, webhook_service, sample_webhook_config, mock_dns_resolution
    ):
        """Все 5xx retry неудачны → исключение."""
        respx.post("https://api.example.com/webhook").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )
        
        period_start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc)
        
        with patch("asyncio.sleep"):
            with pytest.raises(WebhookDeliveryError, match="Server error after 3 attempts: 500"):
                await webhook_service.send_summary_webhook(
                    webhook_config=sample_webhook_config,
                    summary_text="Test summary",
                    chat_id=123,
                    chat_title="Test Chat",
                    period_start=period_start,
                    period_end=period_end,
                    messages_count=10,
                )
