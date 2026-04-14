"""
Edge cases и security тесты для verify_api_key dependency.

Проверяет:
- Пустой API_KEY — проверка пропущена
- Регистрозависимое сравнение
- API_KEY не попадает в логи (SEC-040)
- Oversized заголовок — проходит до compare_digest
- Нестроковое значение заголовка
- Пробелы в заголовке НЕ обрезаются
- Ingest endpoint не требует Telegram session auth
- Import endpoint требует Telegram session auth (исправление B3)
"""

import logging

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from src.api.dependencies.api_key_auth import verify_api_key


@pytest.mark.asyncio
async def test_verify_api_key_passes_with_empty_api_key(mock_settings_empty_key):
    """API_KEY="" — проверка пропущена."""
    request = MagicMock()
    request.headers = {}
    request.url.path = "/test"

    result = await verify_api_key(request)
    assert result is None


@pytest.mark.asyncio
async def test_verify_api_key_case_sensitive(mock_settings_with_key):
    """Регистрозависимое сравнение API key."""
    request = MagicMock()
    request.headers = {"X-API-Key": "TEST-KEY"}
    request.url.path = "/test"

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "AUTH-102"  # type: ignore[index]


@pytest.mark.asyncio
async def test_api_key_not_logged(mock_settings_with_key, caplog):
    """API_KEY не появляется в логах (SEC-040)."""
    caplog.set_level(logging.WARNING)

    request = MagicMock()
    request.headers = {"X-API-Key": "wrong-key"}
    request.url.path = "/test"

    with pytest.raises(HTTPException):
        await verify_api_key(request)

    assert "wrong-key" not in caplog.text
    assert "test-key" not in caplog.text
    assert "wron***" in caplog.text


@pytest.mark.asyncio
async def test_verify_api_key_oversized_header(mock_settings_with_key):
    """Заголовок > 1024 chars — проходит до compare_digest, возвращает 401."""
    request = MagicMock()
    request.headers = {"X-API-Key": "A" * 2000}
    request.url.path = "/test"

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(request)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_malformed_header_value(mock_settings_with_key):
    """Нестроковое значение заголовка — graceful handling."""
    request = MagicMock()
    request.headers = {"X-API-Key": None}
    request.url.path = "/test"

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(request)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_does_not_trim_whitespace(mock_settings_with_key):
    """Пробелы в заголовке НЕ обрезаются — ' test-key' != 'test-key'."""
    request = MagicMock()
    request.headers = {"X-API-Key": " test-key "}
    request.url.path = "/test"

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "AUTH-102"  # type: ignore[index]


def test_ingest_no_telegram_auth_required():
    """Ingest endpoint не использует Telegram session auth."""
    from src.api.endpoints import external_ingest
    assert not hasattr(external_ingest, "get_current_user")


def test_import_requires_telegram_auth():
    """Import endpoint использует Telegram session auth (исправление B3)."""
    from src.api.endpoints import import_endpoint
    assert hasattr(import_endpoint, "get_current_user")
