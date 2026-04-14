"""
Тесты repository-сценариев webhook конфигурации.
"""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest

from src.settings.repositories.chat_settings import (
    ChatSettingsRepository,
)


class _FakeConnection:
    def __init__(self, row_for_fetchrow=None):
        self._row_for_fetchrow = row_for_fetchrow

    async def fetchrow(self, *args, **kwargs):
        return self._row_for_fetchrow


def _create_fake_pool(row_for_fetchrow):
    """Создать мокированный pool с fake connection."""
    pool = MagicMock()
    
    @asynccontextmanager
    async def fake_acquire():
        yield _FakeConnection(row_for_fetchrow=row_for_fetchrow)
    
    pool.acquire = fake_acquire
    return pool


class TestWebhookRepositoryRuntime:
    @pytest.mark.asyncio
    async def test_set_webhook_config_success_returns_chat_setting(self):
        row = {
            "id": 1,
            "chat_id": 123,
            "title": "chat",
            "webhook_config": {
                "url": "https://example.com/webhook",
                "method": "POST",
                "body_template": {"summary": "{{summary}}"},
            },
            "webhook_enabled": True,
        }

        pool = _create_fake_pool(row)
        repo = ChatSettingsRepository(pool)
        
        result = await repo.set_webhook_config(
            123,
            {
                "url": "https://example.com/webhook",
                "method": "POST",
                "body_template": {"summary": "{{summary}}"},
            },
        )

        assert result is not None
        assert result.chat_id == 123

    @pytest.mark.asyncio
    async def test_get_webhook_config_not_found_returns_none(self):
        pool = _create_fake_pool(None)
        repo = ChatSettingsRepository(pool)
        
        result = await repo.get_webhook_config(123)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_webhook_config_invalid_stored_returns_none(self):
        row = {
            "chat_id": 123,
            "webhook_config": {
                "url": "https://example.com/webhook",
                "method": "POST",
            },
            "webhook_enabled": True,
        }

        pool = _create_fake_pool(row)
        repo = ChatSettingsRepository(pool)
        
        result = await repo.get_webhook_config(123)

        assert result is None

    @pytest.mark.asyncio
    async def test_disable_webhook_not_found_returns_none(self):
        pool = _create_fake_pool(None)
        repo = ChatSettingsRepository(pool)
        
        result = await repo.disable_webhook(123)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_webhook_config_success_returns_sanitized_config(self):
        row = {
            "chat_id": 123,
            "webhook_config": {
                "url": "https://user:***REDACTED***@example.com/webhook?token=abc",
                "method": "POST",
                "headers": {"Authorization": "Bearer ***REDACTED***"},
                "body_template": {"summary": "{{summary}}"},
            },
            "webhook_enabled": True,
        }

        pool = _create_fake_pool(row)
        repo = ChatSettingsRepository(pool)
        
        result = await repo.get_webhook_config(123)

        assert result is not None
        assert "user:***REDACTED***@" not in str(result.get("url"))
        headers = result.get("headers")
        assert isinstance(headers, dict)
        assert headers.get("Authorization") == "***"

    @pytest.mark.asyncio
    async def test_get_webhook_config_raw_success_returns_unmasked_config(self):
        row = {
            "chat_id": 123,
            "webhook_config": {
                "url": "https://user:***REDACTED***@example.com/webhook?token=abc",
                "method": "POST",
                "headers": {"Authorization": "Bearer ***REDACTED***"},
                "body_template": {"summary": "{{summary}}"},
            },
            "webhook_enabled": True,
        }

        pool = _create_fake_pool(row)
        repo = ChatSettingsRepository(pool)

        result = await repo.get_webhook_config_raw(123)

        assert result is not None
        assert "user:***REDACTED***@" in str(result.get("url"))
        headers = result.get("headers")
        assert isinstance(headers, dict)
        assert headers.get("Authorization") == "Bearer ***REDACTED***"


class TestWebhookRepositoryStorageError:
    @pytest.mark.asyncio
    async def test_get_webhook_config_storage_error_returns_none(self):
        class _BrokenConnection:
            async def fetchrow(self, *args, **kwargs):
                raise ValueError("db error")

        broken_pool = MagicMock()
        
        @asynccontextmanager
        async def broken_acquire():
            yield _BrokenConnection()
        
        broken_pool.acquire = broken_acquire

        repo = ChatSettingsRepository(broken_pool)
        result = await repo.get_webhook_config(1)

        assert result is None
