"""
Тесты Settings поля api_key.

Проверяет:
- Поле api_key существует в Settings
- Тип поля Optional[str]
- Валидация минимальной длины (16 символов)
- Пустая строка → None
"""

import pytest

from src.config import get_settings
from src.config.settings import Settings


def test_settings_api_key_field_exists():
    """Settings имеет поле api_key типа Optional[str]."""
    settings = get_settings()
    assert hasattr(settings, "api_key")
    assert isinstance(settings.api_key, (str, type(None)))


def test_settings_api_key_empty_string_becomes_none(monkeypatch):
    """Пустая строка API_KEY='' преобразуется в None."""
    monkeypatch.setenv("API_KEY", "")
    settings = Settings()
    assert settings.api_key is None


def test_settings_api_key_too_short_raises_error(monkeypatch):
    """API_KEY короче 16 символов вызывает ValueError."""
    monkeypatch.setenv("API_KEY", "short")
    with pytest.raises(ValueError, match="минимум 16 символов"):
        Settings()


def test_settings_api_key_valid_length(monkeypatch):
    """API_KEY длиной 16+ символов принимается."""
    monkeypatch.setenv("API_KEY", "a" * 16)
    settings = Settings()
    assert settings.api_key == "a" * 16
