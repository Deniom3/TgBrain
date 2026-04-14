"""
Тесты для mask_api_key.

Чистая функция — без моков, без зависимостей.
"""

import pytest

from src.config.masking import mask_api_key


@pytest.mark.parametrize(
    ("api_key", "expected"),
    [
        pytest.param(None, None, id="none_input"),
        pytest.param("", None, id="empty_string"),
        pytest.param("short", "***", id="length_le_8"),
        pytest.param("12345678", "***", id="length_exactly_8"),
        pytest.param("sk-abc123def456xyz789", "sk-...z789", id="contains_dash_in_prefix"),
        pytest.param("abcdefghijklmnop", "abcd...mnop", id="no_dash_standard"),
    ],
)
def test_mask_api_key_various_inputs(api_key: str | None, expected: str | None) -> None:
    """Проверка всех сценариев маскирования API ключа."""
    result = mask_api_key(api_key)
    assert result == expected
