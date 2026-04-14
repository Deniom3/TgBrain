"""
Тесты для parse_cors_origins.

Тестируется парсинг, валидация и логирование.
"""

import pytest

from src.config.cors import parse_cors_origins


def test_parse_cors_origins_none_returns_default() -> None:
    """None значение возвращает список по умолчанию."""
    result = parse_cors_origins(None)
    assert result == ["http://localhost:3000"]


def test_parse_cors_origins_empty_string_returns_default() -> None:
    """Пустая строка возвращает список по умолчанию."""
    result = parse_cors_origins("")
    assert result == ["http://localhost:3000"]


def test_parse_cors_origins_parses_comma_separated() -> None:
    """Корректные origins парсятся по запятой с trim."""
    result = parse_cors_origins("http://example.com, https://app.example.com")
    assert result == ["http://example.com", "https://app.example.com"]


def test_parse_cors_origins_custom_default() -> None:
    """Кастомный default используется при None."""
    result = parse_cors_origins(None, default=["https://custom.dev"])
    assert result == ["https://custom.dev"]


def test_parse_cors_origins_wildcard_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Wildcard '*' разрешается с warning."""
    with caplog.at_level("WARNING"):
        result = parse_cors_origins("*")
    assert result == ["*"]
    assert "wildcard" in caplog.text.lower()


def test_parse_cors_origins_invalid_urls_logged_and_skipped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Некорректные URL логируются и пропускаются."""
    with caplog.at_level("WARNING"):
        result = parse_cors_origins("http://valid.com, ftp://invalid.com, https://also-valid.com")
    assert result == ["http://valid.com", "https://also-valid.com"]
    assert "invalid" in caplog.text.lower()


def test_parse_cors_origins_missing_host_logged_and_skipped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Origin без хоста (только схема) логируется и пропускается."""
    with caplog.at_level("WARNING"):
        result = parse_cors_origins("http://, http://valid.com, https://")
    assert result == ["http://valid.com"]
    assert "missing host" in caplog.text.lower()
