"""
Модульные тесты verify_api_key dependency.

Проверяет core логику аутентификации по API key:
- Успешная проверка с валидным ключом
- Ошибка 401 при отсутствии заголовка
- Ошибка 401 при неверном ключе
- Пропуск проверки когда API_KEY не установлен
"""

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from src.api.dependencies.api_key_auth import verify_api_key


@pytest.mark.asyncio
async def test_verify_api_key_passes_with_valid_key(mock_settings_with_key, mock_request_with_header):
    """Проверка пройдена когда заголовок совпадает с API_KEY."""
    result = await verify_api_key(mock_request_with_header)  # type: ignore[func-returns-value]

    assert result is None


@pytest.mark.asyncio
async def test_verify_api_key_raises_401_missing_header(mock_settings_with_key, mock_request_without_header):
    """API_KEY установлен, заголовок отсутствует — 401 AUTH-101."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(mock_request_without_header)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "AUTH-101"  # type: ignore[index]


@pytest.mark.asyncio
async def test_verify_api_key_raises_401_invalid_key(mock_settings_with_key):
    """API_KEY установлен, заголовок не совпадает — 401 AUTH-102."""
    request = MagicMock()
    request.headers = {"X-API-Key": "wrong-key"}
    request.url.path = "/test"

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "AUTH-102"  # type: ignore[index]


@pytest.mark.asyncio
async def test_verify_api_key_passes_when_api_key_not_set(mock_settings_without_key, mock_request_without_header):
    """API_KEY не установлен — проверка пропущена."""
    result = await verify_api_key(mock_request_without_header)  # type: ignore[func-returns-value]

    assert result is None
