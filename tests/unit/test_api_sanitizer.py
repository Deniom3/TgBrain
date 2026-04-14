"""Тесты для sanitize_for_log."""

from src.api.utils.sanitizer import sanitize_for_log


class TestSanitizeForLog:
    """Тесты функции sanitize_for_log."""

    def test_empty_string(self) -> None:
        """Пустая строка возвращает пустую строку."""
        result = sanitize_for_log("")

        assert result == ""

    def test_none_value(self) -> None:
        """None возвращает пустую строку."""
        result = sanitize_for_log(None)  # type: ignore[arg-type]

        assert result == ""

    def test_short_text_no_truncation(self) -> None:
        """Короткий текст без изменений."""
        text = "Hello, world!"

        result = sanitize_for_log(text)

        assert result == "Hello, world!"

    def test_truncate_long_text(self) -> None:
        """Длинный текст обрезается до max_length с добавлением ..."""
        text = "A" * 200

        result = sanitize_for_log(text, max_length=50)

        assert "[TOKEN]..." == result

    def test_remove_long_tokens(self) -> None:
        """Токены 32+ символов заменяются на [TOKEN]."""
        text = "prefix_abcdefghijklmnopqrst_12345_suffix"

        result = sanitize_for_log(text)

        assert "[TOKEN]" in result

    def test_redact_api_key_equals(self) -> None:
        """Пары api_key=... редactятся."""
        text = "config: api_key=secret123 other=data"

        result = sanitize_for_log(text)

        assert "[REDACTED]" in result
        assert "secret123" not in result

    def test_redact_api_key_colon(self) -> None:
        """Пары api_key:... редactятся."""
        text = "config: api_key: secret_value rest"

        result = sanitize_for_log(text)

        assert "[REDACTED]" in result

    def test_redact_api_key_with_underscore(self) -> None:
        """Вариант api_key с подчёркиванием редactится."""
        text = "api_key=sensitive_token_here"

        result = sanitize_for_log(text)

        assert "[REDACTED]" in result

    def test_combined_truncation_and_redaction(self) -> None:
        """Комбинация обрезки, удаления токенов и редact."""
        text = "api_key=supersecretkey " + "A" * 100

        result = sanitize_for_log(text, max_length=50)

        assert "[REDACTED]" in result
        assert len(result) <= 55

    def test_custom_max_length(self) -> None:
        """Кастомная максимальная длина применяется."""
        text = "Short text here"

        result = sanitize_for_log(text, max_length=5)

        assert result == "Short..."

    def test_short_text_no_token_replacement(self) -> None:
        """Короткие строки без длинных токенов не изменяются."""
        text = "abc def ghi"

        result = sanitize_for_log(text)

        assert result == "abc def ghi"

    def test_token_at_boundary(self) -> None:
        """Токен ровно 32 символа заменяется."""
        text = "A" * 32

        result = sanitize_for_log(text)

        assert result == "[TOKEN]"

    def test_token_31_chars_not_replaced(self) -> None:
        """Токен 31 символ НЕ заменяется."""
        text = "A" * 31

        result = sanitize_for_log(text)

        assert result == "A" * 31
