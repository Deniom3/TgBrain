"""
Shared fixtures для unit тестов API key аутентификации.
"""

import pytest

from src.config import get_settings
from unittest.mock import MagicMock


@pytest.fixture
def mock_settings_with_key(monkeypatch):
    """Mock settings с установленным api_key."""
    get_settings.cache_clear()
    mock_settings = MagicMock()
    mock_settings.api_key = "test-key"
    monkeypatch.setattr("src.api.dependencies.api_key_auth.get_settings", lambda: mock_settings)


@pytest.fixture
def mock_settings_without_key(monkeypatch):
    """Mock settings без api_key (None)."""
    get_settings.cache_clear()
    mock_settings = MagicMock()
    mock_settings.api_key = None
    monkeypatch.setattr("src.api.dependencies.api_key_auth.get_settings", lambda: mock_settings)


@pytest.fixture
def mock_settings_empty_key(monkeypatch):
    """Mock settings с пустым api_key."""
    get_settings.cache_clear()
    mock_settings = MagicMock()
    mock_settings.api_key = ""
    monkeypatch.setattr("src.api.dependencies.api_key_auth.get_settings", lambda: mock_settings)


@pytest.fixture
def mock_request_with_header():
    """Mock запрос с заголовком X-API-Key."""
    request = MagicMock()
    request.headers = {"X-API-Key": "test-key"}
    request.url.path = "/test"
    return request


@pytest.fixture
def mock_request_without_header():
    """Mock запрос без заголовка X-API-Key."""
    request = MagicMock()
    request.headers = {}
    request.url.path = "/test"
    return request
