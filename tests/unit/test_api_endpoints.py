"""
Unit tests for API endpoints — Schedule и Webhook.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.endpoints.summary_send_webhook import (
    send_summary_webhook,
    SummarySendWebhookRequest,
)
from src.infrastructure.services.summary_webhook_service import (
    SummaryWebhookService,
    SummaryWebhookResult,
)
from src.models.data_models import ChatSummary, SummaryStatus


@pytest.fixture
def mock_summary_webhook_service():
    """Mock SummaryWebhookService."""
    service = AsyncMock(spec_set=SummaryWebhookService)
    return service


@pytest.fixture
def mock_authenticated_user():
    """Mock AuthenticatedUser."""
    user = MagicMock()
    user.is_authenticated = True
    return user


@pytest.fixture
def sample_summary():
    """Sample ChatSummary."""
    return ChatSummary(
        id=1,
        chat_id=123,
        period_start=datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc),
        period_end=datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc),
        status=SummaryStatus.COMPLETED,
        result_text="Test summary text",
        messages_count=10,
        created_at=datetime.now(timezone.utc),
    )


class TestSendWebhookAPISuccess:
    """Тесты успешной отправки webhook через API."""

    @pytest.mark.asyncio
    async def test_cache_hit_immediate_send(
        self,
        mock_summary_webhook_service,
        mock_authenticated_user,
        sample_summary,
    ):
        """Кэш найден → webhook отправлен немедленно."""
        request = SummarySendWebhookRequest(
            period_minutes=1440,
            use_cache=True,
        )
        
        result = SummaryWebhookResult(
            summary=sample_summary,
            from_cache=True,
            webhook_sent=True,
            webhook_pending=False,
        )
        
        mock_summary_webhook_service.generate_and_send_webhook.return_value = result

        response = await send_summary_webhook(
            chat_id=123,
            request=request,
            _rate_limit=mock_authenticated_user,
            summary_webhook_service=mock_summary_webhook_service,
        )

        assert response.success is True
        assert response.from_cache is True
        assert response.webhook_sent is True
        assert response.webhook_pending is False
        assert response.summary_id == 1

    @pytest.mark.asyncio
    async def test_cache_miss_generate_task(
        self,
        mock_summary_webhook_service,
        mock_authenticated_user,
        sample_summary,
    ):
        """Кэш не найден → задача генерации создана."""
        request = SummarySendWebhookRequest(
            period_minutes=1440,
            use_cache=True,
        )
        
        pending_summary = ChatSummary(
            id=2,
            chat_id=123,
            period_start=datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc),
            period_end=datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc),
            status=SummaryStatus.PENDING,
            result_text="",
            messages_count=0,
            created_at=datetime.now(timezone.utc),
        )
        
        result = SummaryWebhookResult(
            summary=pending_summary,
            from_cache=False,
            webhook_sent=False,
            webhook_pending=True,
        )
        
        mock_summary_webhook_service.generate_and_send_webhook.return_value = result

        response = await send_summary_webhook(
            chat_id=123,
            request=request,
            _rate_limit=mock_authenticated_user,
            summary_webhook_service=mock_summary_webhook_service,
        )

        assert response.success is True
        assert response.from_cache is False
        assert response.webhook_sent is False
        assert response.webhook_pending is True
        assert response.task_id == 2


class TestSendWebhookAPIErrors:
    """Тесты ошибок API."""

    @pytest.mark.asyncio
    async def test_webhook_not_configured_400(
        self,
        mock_summary_webhook_service,
        mock_authenticated_user,
    ):
        """Webhook не настроен → success=False response."""
        from src.domain.exceptions import WebhookNotConfiguredError

        request = SummarySendWebhookRequest(
            period_minutes=1440,
            use_cache=True,
        )

        mock_summary_webhook_service.generate_and_send_webhook.side_effect = WebhookNotConfiguredError(chat_id=123)

        response = await send_summary_webhook(
            chat_id=123,
            request=request,
            _rate_limit=mock_authenticated_user,
            summary_webhook_service=mock_summary_webhook_service,
        )

        assert response.success is False
        assert response.from_cache is False
        assert response.webhook_sent is False
        assert "Webhook не настроен" in response.message

    @pytest.mark.asyncio
    async def test_chat_not_found_404(
        self,
        mock_summary_webhook_service,
        mock_authenticated_user,
    ):
        """Чат не найден → success=False response."""
        from src.domain.exceptions import WebhookNotFoundError

        request = SummarySendWebhookRequest(
            period_minutes=1440,
            use_cache=True,
        )

        mock_summary_webhook_service.generate_and_send_webhook.side_effect = WebhookNotFoundError(chat_id=999)

        response = await send_summary_webhook(
            chat_id=999,
            request=request,
            _rate_limit=mock_authenticated_user,
            summary_webhook_service=mock_summary_webhook_service,
        )

        assert response.success is False
        assert response.from_cache is False
        assert response.webhook_sent is False
        assert "не найден" in response.message


class TestSendWebhookAPICustomPrompt:
    """Тесты с custom_prompt."""

    @pytest.mark.asyncio
    async def test_custom_prompt_passed_to_service(
        self,
        mock_summary_webhook_service,
        mock_authenticated_user,
        sample_summary,
    ):
        """custom_prompt передаётся в сервис."""
        request = SummarySendWebhookRequest(
            period_minutes=1440,
            custom_prompt="Custom prompt text",
            use_cache=True,
        )
        
        result = SummaryWebhookResult(
            summary=sample_summary,
            from_cache=False,
            webhook_sent=False,
            webhook_pending=True,
        )
        
        mock_summary_webhook_service.generate_and_send_webhook.return_value = result
        
        await send_summary_webhook(
            chat_id=123,
            request=request,
            _rate_limit=mock_authenticated_user,
            summary_webhook_service=mock_summary_webhook_service,
        )
        
        call_args = mock_summary_webhook_service.generate_and_send_webhook.call_args
        assert call_args.kwargs["custom_prompt"] == "Custom prompt text"

    @pytest.mark.asyncio
    async def test_use_cache_false_force_generate(
        self,
        mock_summary_webhook_service,
        mock_authenticated_user,
        sample_summary,
    ):
        """use_cache=false → всегда генерация."""
        request = SummarySendWebhookRequest(
            period_minutes=1440,
            use_cache=False,
        )
        
        result = SummaryWebhookResult(
            summary=sample_summary,
            from_cache=False,
            webhook_sent=False,
            webhook_pending=True,
        )
        
        mock_summary_webhook_service.generate_and_send_webhook.return_value = result
        
        await send_summary_webhook(
            chat_id=123,
            request=request,
            _rate_limit=mock_authenticated_user,
            summary_webhook_service=mock_summary_webhook_service,
        )
        
        call_args = mock_summary_webhook_service.generate_and_send_webhook.call_args
        assert call_args.kwargs["use_cache"] is False


class TestSendWebhookAPIPeriodMinutes:
    """Тесты с различными period_minutes."""

    @pytest.mark.asyncio
    async def test_period_minutes_default_1440(
        self,
        mock_summary_webhook_service,
        mock_authenticated_user,
        sample_summary,
    ):
        """period_minutes по умолчанию 1440."""
        request = SummarySendWebhookRequest()
        
        result = SummaryWebhookResult(
            summary=sample_summary,
            from_cache=True,
            webhook_sent=True,
            webhook_pending=False,
        )
        
        mock_summary_webhook_service.generate_and_send_webhook.return_value = result
        
        await send_summary_webhook(
            chat_id=123,
            request=request,
            _rate_limit=mock_authenticated_user,
            summary_webhook_service=mock_summary_webhook_service,
        )
        
        call_args = mock_summary_webhook_service.generate_and_send_webhook.call_args
        assert call_args.kwargs["period_minutes"] == 1440

    @pytest.mark.asyncio
    async def test_period_minutes_custom_60(
        self,
        mock_summary_webhook_service,
        mock_authenticated_user,
        sample_summary,
    ):
        """period_minutes кастомное значение 60."""
        request = SummarySendWebhookRequest(period_minutes=60)
        
        result = SummaryWebhookResult(
            summary=sample_summary,
            from_cache=True,
            webhook_sent=True,
            webhook_pending=False,
        )
        
        mock_summary_webhook_service.generate_and_send_webhook.return_value = result
        
        await send_summary_webhook(
            chat_id=123,
            request=request,
            _rate_limit=mock_authenticated_user,
            summary_webhook_service=mock_summary_webhook_service,
        )
        
        call_args = mock_summary_webhook_service.generate_and_send_webhook.call_args
        assert call_args.kwargs["period_minutes"] == 60


class TestSendWebhookAPIResponseMessages:
    """Тесты сообщений в ответах."""

    @pytest.mark.asyncio
    async def test_response_message_cache_hit(
        self,
        mock_summary_webhook_service,
        mock_authenticated_user,
        sample_summary,
    ):
        """Сообщение при cache hit."""
        request = SummarySendWebhookRequest()
        
        result = SummaryWebhookResult(
            summary=sample_summary,
            from_cache=True,
            webhook_sent=True,
            webhook_pending=False,
        )
        
        mock_summary_webhook_service.generate_and_send_webhook.return_value = result

        response = await send_summary_webhook(
            chat_id=123,
            request=request,
            _rate_limit=mock_authenticated_user,
            summary_webhook_service=mock_summary_webhook_service,
        )

        assert "из кэша" in response.message

    @pytest.mark.asyncio
    async def test_response_message_pending(
        self,
        mock_summary_webhook_service,
        mock_authenticated_user,
        sample_summary,
    ):
        """Сообщение при pending."""
        request = SummarySendWebhookRequest()
        
        pending_summary = ChatSummary(
            id=2,
            chat_id=123,
            period_start=datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc),
            period_end=datetime(2026, 3, 29, 23, 59, 59, tzinfo=timezone.utc),
            status=SummaryStatus.PENDING,
            result_text="",
            messages_count=0,
            created_at=datetime.now(timezone.utc),
        )
        
        result = SummaryWebhookResult(
            summary=pending_summary,
            from_cache=False,
            webhook_sent=False,
            webhook_pending=True,
        )
        
        mock_summary_webhook_service.generate_and_send_webhook.return_value = result

        response = await send_summary_webhook(
            chat_id=123,
            request=request,
            _rate_limit=mock_authenticated_user,
            summary_webhook_service=mock_summary_webhook_service,
        )

        assert "генерируется" in response.message


class TestTimezoneAPI:
    """Тесты для PUT /api/v1/settings/app/timezone."""

    @pytest.fixture
    def timezone_app(self):
        """Создание тестового приложения для timezone тестов."""
        from fastapi import FastAPI
        from src.settings_api.app import router as app_settings_router

        app = FastAPI()
        app.include_router(app_settings_router)

        mock_app_settings_repo = AsyncMock()
        mock_app_settings_repo.upsert = AsyncMock(return_value=MagicMock())
        app.state.app_settings_repo = mock_app_settings_repo

        mock_telegram_auth_repo = AsyncMock()
        mock_telegram_auth_repo.is_session_active = AsyncMock(return_value=True)
        app.state.telegram_auth_repo = mock_telegram_auth_repo

        return app

    def test_set_timezone_success(self, timezone_app):
        """Успешная установка timezone."""
        from fastapi.testclient import TestClient

        import src.config as config_module

        with TestClient(timezone_app) as client:
            with patch("src.settings_api.app.reload_settings", new_callable=AsyncMock):
                original_settings = config_module.settings

                response = client.put(
                    "/app/timezone",
                    json={"timezone": "Europe/Moscow"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["timezone"] == "Europe/Moscow"
                assert data["message"] == "Timezone приложения обновлён"
                assert config_module.settings is not original_settings
                assert config_module.settings.timezone == "Europe/Moscow"

    def test_set_timezone_moscow(self, timezone_app):
        """Timezone Europe/Moscow."""
        from fastapi.testclient import TestClient

        with TestClient(timezone_app) as client:
            with patch("src.settings_api.app.reload_settings", new_callable=AsyncMock):
                with patch("src.config.get_settings", return_value=MagicMock()):
                    response = client.put(
                        "/app/timezone",
                        json={"timezone": "Europe/Moscow"},
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["timezone"] == "Europe/Moscow"

    def test_set_timezone_utc(self, timezone_app):
        """Timezone Etc/UTC."""
        from fastapi.testclient import TestClient

        with TestClient(timezone_app) as client:
            with patch("src.settings_api.app.reload_settings", new_callable=AsyncMock):
                with patch("src.config.get_settings", return_value=MagicMock()):
                    response = client.put(
                        "/app/timezone",
                        json={"timezone": "Etc/UTC"},
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["timezone"] == "Etc/UTC"

    def test_set_timezone_invalid_400(self, timezone_app):
        """Неверный timezone → 400."""
        from fastapi.testclient import TestClient

        with TestClient(timezone_app) as client:
            response = client.put(
                "/app/timezone",
                json={"timezone": "Invalid/Timezone"},
            )

            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"]["code"] == "APP-001"

    def test_set_timezone_db_updated(self, timezone_app):
        """БД обновлена."""
        from fastapi.testclient import TestClient

        with TestClient(timezone_app) as client:
            with patch("src.settings_api.app.reload_settings", new_callable=AsyncMock):
                with patch("src.config.get_settings", return_value=MagicMock()):
                    client.put(
                        "/app/timezone",
                        json={"timezone": "Europe/Moscow"},
                    )

            timezone_app.state.app_settings_repo.upsert.assert_awaited_once()

    def test_set_timezone_cache_updated(self, timezone_app):
        """Глобальный settings обновлён через model_copy с новым timezone."""
        from fastapi.testclient import TestClient

        import src.config as config_module

        with TestClient(timezone_app) as client:
            with patch("src.settings_api.app.reload_settings", new_callable=AsyncMock):
                original_settings = config_module.settings

                client.put(
                    "/app/timezone",
                    json={"timezone": "America/New_York"},
                )

                assert config_module.settings is not original_settings
                assert config_module.settings.timezone == "America/New_York"


class TestWebhookConfigAPI:
    """Тесты для endpoint'ов webhook конфигурации.
    
    Endpoints монтируются под /api/v1/settings, префикс роутера: /chats.
    Итоговые пути:
    - PUT /api/v1/settings/chats/{chat_id}/webhook/config
    - GET /api/v1/settings/chats/{chat_id}/webhook/config
    - DELETE /api/v1/settings/chats/{chat_id}/webhook/config
    - POST /api/v1/settings/chats/{chat_id}/webhook/test
    """

    @pytest.mark.asyncio
    async def test_set_config_success(self):
        """Успешная установка webhook_config."""
        from src.settings_api.webhook_endpoints import set_webhook_config, WebhookConfigRequest
        from src.application.services.webhook_settings_service import WebhookSettingsService
        from unittest.mock import AsyncMock
        
        mock_service = AsyncMock(spec_set=WebhookSettingsService)
        mock_service.set_webhook_config = AsyncMock()
        
        request = WebhookConfigRequest(
            url="https://example.com/webhook",
            method="POST",
            headers={"Content-Type": "application/json"},
            body_template={"summary": "{{summary}}"},
        )
        
        response = await set_webhook_config(
            chat_id=123,
            request=request,
            webhook_service=mock_service,
        )
        
        assert response.chat_id == 123
        assert response.webhook_enabled is True
        assert response.message == "Webhook конфигурация установлена"

    @pytest.mark.asyncio
    async def test_set_config_telegram(self):
        """Конфигурация для Telegram Bot API."""
        from src.settings_api.webhook_endpoints import set_webhook_config, WebhookConfigRequest
        from src.application.services.webhook_settings_service import WebhookSettingsService
        from unittest.mock import AsyncMock
        
        mock_service = AsyncMock(spec_set=WebhookSettingsService)
        mock_service.set_webhook_config = AsyncMock()
        
        request = WebhookConfigRequest(
            url="https://api.telegram.org/<TEST_BOT_TOKEN>/sendMessage",
            method="POST",
            headers={"Content-Type": "application/json"},
            body_template={"summary": "{{summary}}", "chat_name": "{{chat_name}}"},
        )
        
        response = await set_webhook_config(
            chat_id=123,
            request=request,
            webhook_service=mock_service,
        )
        
        assert response.webhook_enabled is True

    @pytest.mark.asyncio
    async def test_set_config_custom_webhook(self):
        """Конфигурация для произвольного webhook."""
        from src.settings_api.webhook_endpoints import set_webhook_config, WebhookConfigRequest
        from src.application.services.webhook_settings_service import WebhookSettingsService
        from unittest.mock import AsyncMock
        
        mock_service = AsyncMock(spec_set=WebhookSettingsService)
        mock_service.set_webhook_config = AsyncMock()
        
        request = WebhookConfigRequest(
            url="https://custom.webhook.com/api/notify",
            method="POST",
            headers={"Content-Type": "application/json"},
            body_template={"summary": "{{summary}}", "chat_name": "{{chat_name}}"},
        )
        
        response = await set_webhook_config(
            chat_id=123,
            request=request,
            webhook_service=mock_service,
        )
        
        assert response.webhook_enabled is True

    @pytest.mark.asyncio
    async def test_set_config_invalid_url_400(self):
        """Неверный URL → 400."""
        from src.settings_api.webhook_endpoints import WebhookConfigRequest
        from src.domain.exceptions import ValidationError
        
        with pytest.raises(ValidationError, match="Webhook URL должен быть HTTPS"):
            WebhookConfigRequest(
                url="invalid-url",
                method="POST",
                headers={},
                body_template={},
            )

    @pytest.mark.asyncio
    async def test_set_config_missing_body_400(self):
        """Отсутствует body_template → 400."""
        from src.settings_api.webhook_endpoints import WebhookConfigRequest
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            WebhookConfigRequest(
                url="https://example.com/webhook",
                method="POST",
                headers={},
                body_template={},
            )

    @pytest.mark.asyncio
    async def test_set_config_chat_not_found_404(self):
        """Чат не найден → domain exception."""
        from src.settings_api.webhook_endpoints import set_webhook_config, WebhookConfigRequest
        from src.application.services.webhook_settings_service import WebhookSettingsService
        from src.domain.exceptions import WebhookNotFoundError
        from unittest.mock import AsyncMock

        mock_service = AsyncMock(spec_set=WebhookSettingsService)
        mock_service.set_webhook_config = AsyncMock(side_effect=WebhookNotFoundError(chat_id=999))

        request = WebhookConfigRequest(
            url="https://example.com/webhook",
            method="POST",
            headers={},
            body_template={"summary": "{{summary}}"},
        )

        with pytest.raises(WebhookNotFoundError) as exc_info:
            await set_webhook_config(
                chat_id=999,
                request=request,
                webhook_service=mock_service,
            )

        assert exc_info.value.chat_id == 999

    @pytest.mark.asyncio
    async def test_set_config_db_updated(self):
        """JSON сохранён в БД."""
        from src.settings_api.webhook_endpoints import set_webhook_config, WebhookConfigRequest
        from src.application.services.webhook_settings_service import WebhookSettingsService
        from unittest.mock import AsyncMock
        
        mock_service = AsyncMock(spec_set=WebhookSettingsService)
        mock_service.set_webhook_config = AsyncMock()
        
        request = WebhookConfigRequest(
            url="https://example.com/webhook",
            method="POST",
            headers={"Content-Type": "application/json"},
            body_template={"summary": "{{summary}}"},
        )
        
        await set_webhook_config(
            chat_id=123,
            request=request,
            webhook_service=mock_service,
        )
        
        mock_service.set_webhook_config.assert_awaited_once()
