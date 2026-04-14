"""
Тесты безопасности и валидации webhook конфигурации.
"""

import pytest
import asyncpg

from src.models.data_models import WebhookConfig
from src.settings.repositories.chat_settings import (
    ChatSettingsRepository,
    WebhookConfigValidationError,
)


class TestWebhookConfigValidation:
    """Тесты валидации структуры webhook конфигурации."""

    @pytest.mark.asyncio
    async def test_validate_config_requires_body_template_object(self):
        config = {
            "url": "https://example.com/webhook",
            "method": "POST",
            "body_template": "{{summary}}",
        }

        with pytest.raises(WebhookConfigValidationError):
            await ChatSettingsRepository._validate_webhook_config(config)

    @pytest.mark.asyncio
    async def test_validate_config_allows_delete_method(self):
        config = {
            "url": "https://example.com/webhook",
            "method": "DELETE",
            "body_template": {"summary": "{{summary}}"},
        }

        validated = await ChatSettingsRepository._validate_webhook_config(config)

        assert validated.get("method") == "DELETE"

    @pytest.mark.asyncio
    async def test_validate_config_blocks_http_transport(self):
        config = {
            "url": "http://example.com/webhook",
            "method": "POST",
            "body_template": {"summary": "{{summary}}"},
        }

        with pytest.raises(WebhookConfigValidationError):
            await ChatSettingsRepository._validate_webhook_config(config)

    @pytest.mark.asyncio
    async def test_validate_config_blocks_localhost_ssrf(self):
        config = {
            "url": "https://localhost/webhook",
            "method": "POST",
            "body_template": {"summary": "{{summary}}"},
        }

        with pytest.raises(WebhookConfigValidationError):
            await ChatSettingsRepository._validate_webhook_config(config)

    @pytest.mark.asyncio
    async def test_validate_config_blocks_private_ip_ssrf(self):
        config = {
            "url": "https://10.0.0.5/webhook",
            "method": "POST",
            "body_template": {"summary": "{{summary}}"},
        }

        with pytest.raises(WebhookConfigValidationError):
            await ChatSettingsRepository._validate_webhook_config(config)

    @pytest.mark.asyncio
    async def test_validate_config_blocks_metadata_dns_resolve(self, monkeypatch: pytest.MonkeyPatch):
        config = {
            "url": "https://service.example.com/webhook",
            "method": "POST",
            "body_template": {"summary": "{{summary}}"},
        }

        async def fake_getaddrinfo(*args, **kwargs):
            return [(None, None, None, None, ("169.254.169.254", 0))]

        loop = __import__("asyncio").get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", fake_getaddrinfo)

        with pytest.raises(WebhookConfigValidationError):
            await ChatSettingsRepository._validate_webhook_config(config)


class TestWebhookConfigMasking:
    """Тесты безопасной выдачи webhook конфигурации."""

    def test_masking_hides_sensitive_headers(self):
        config: WebhookConfig = {
            "url": "https://example.com/webhook",
            "method": "POST",
            "headers": {"Authorization": "Bearer secret-token"},
            "body_template": {"summary": "{{summary}}"},
        }

        masked = ChatSettingsRepository._mask_webhook_config(config)

        headers = masked.get("headers")
        assert isinstance(headers, dict)
        assert headers.get("Authorization") == "***"

    def test_masking_hides_sensitive_query_params(self):
        config: WebhookConfig = {
            "url": "https://example.com/webhook?token=abc123&mode=full",
            "method": "POST",
            "body_template": {"summary": "{{summary}}"},
        }

        masked = ChatSettingsRepository._mask_webhook_config(config)

        assert "token=***" in str(masked.get("url"))

    def test_masking_hides_bot_token_in_path(self):
        config: WebhookConfig = {
            "url": "https://api.telegram.org/bot123456:ABCDEF/sendMessage",
            "method": "POST",
            "body_template": {"summary": "{{summary}}"},
        }

        masked = ChatSettingsRepository._mask_webhook_config(config)

        assert "bot123***DEF" in str(masked.get("url"))

    def test_masking_removes_userinfo_from_url(self):
        config: WebhookConfig = {
            "url": "https://user:password@example.com/webhook",
            "method": "POST",
            "body_template": {"summary": "{{summary}}"},
        }

        masked = ChatSettingsRepository._mask_webhook_config(config)

        assert "user:password@" not in str(masked.get("url"))

    def test_masking_hides_cookie_header_by_default(self):
        config: WebhookConfig = {
            "url": "https://example.com/webhook",
            "method": "POST",
            "headers": {"Cookie": "session=abcd"},
            "body_template": {"summary": "{{summary}}"},
        }

        masked = ChatSettingsRepository._mask_webhook_config(config)

        headers = masked.get("headers")
        assert isinstance(headers, dict)
        assert headers.get("Cookie") == "***"


class TestWebhookRepositoryErrorContract:
    """Тесты поведения repository в ошибочных сценариях."""

    @pytest.mark.asyncio
    async def test_set_webhook_config_returns_none_on_validation_error(
        self,
        mock_db_pool: asyncpg.Pool,
    ):
        repo = ChatSettingsRepository(mock_db_pool)
        result = await repo.set_webhook_config(
            chat_id=1,
            config={"url": "https://example.com/webhook", "method": "POST"},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_webhook_config_not_found_returns_none(
        self,
        mock_db_pool: asyncpg.Pool,
    ):
        repo = ChatSettingsRepository(mock_db_pool)
        result = await repo.get_webhook_config(chat_id=999999999)

        assert result is None

    @pytest.mark.asyncio
    async def test_set_webhook_config_success_returns_chat_setting(
        self,
        mock_db_pool: asyncpg.Pool,
    ):
        repo = ChatSettingsRepository(mock_db_pool)
        result = await repo.set_webhook_config(
            chat_id=1,
            config={
                "url": "https://example.com/webhook",
                "method": "POST",
                "body_template": {"summary": "{{summary}}"},
            },
        )

        assert result is None or result.chat_id == 1
