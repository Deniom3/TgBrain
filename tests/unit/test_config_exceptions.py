"""
Тесты для ConfigurationError.

Тестируется создание, форматирование и валидация кода.
"""

import pytest

from src.config.exceptions import ConfigurationError


def test_configuration_error_str_returns_formatted_message() -> None:
    """__str__ возвращает формат '[CODE] message'."""
    error = ConfigurationError("CONF-001", "Missing API key")
    assert str(error) == "[CONF-001] Missing API key"


def test_configuration_error_stores_attributes() -> None:
    """Атрибуты code, message, context сохраняются корректно."""
    context = {"key": "CORS_ORIGINS", "value": "*"}
    error = ConfigurationError("CONF-002", "Invalid value", context=context)
    assert error.code == "CONF-002"
    assert error.message == "Invalid value"
    assert error.context == context


def test_configuration_error_invalid_code_raises_value_error() -> None:
    """Код без префикса 'CONF-' вызывает ValueError."""
    with pytest.raises(ValueError, match="must start with 'CONF-'"):
        ConfigurationError("INVALID", "Bad code")


def test_configuration_error_is_runtime_error() -> None:
    """ConfigurationError наследует RuntimeError."""
    error = ConfigurationError("CONF-001", "Test")
    assert isinstance(error, RuntimeError)


def test_configuration_error_context_defaults_to_none() -> None:
    """Контекст по умолчанию равен None."""
    error = ConfigurationError("CONF-001", "No context")
    assert error.context is None
