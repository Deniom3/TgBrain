"""Санитизация данных для логирования."""
import re


def sanitize_for_log(text: str, max_length: int = 100) -> str:
    """Санитизация текста для логирования.

    - Обрезает до max_length символов
    - Удаляет токены (32+ символа)
    - Удаляет потенциальные секреты

    Args:
        text: Текст для санитизации
        max_length: Максимальная длина текста

    Returns:
        Санитизированный текст
    """
    if not text:
        return ""

    truncated = text[:max_length] + "..." if len(text) > max_length else text
    sanitized = re.sub(r"[A-Za-z0-9_-]{32,}", "[TOKEN]", truncated)
    sanitized = re.sub(
        r"api[_-]?key[=:]\s*\S+", "[REDACTED]", sanitized, flags=re.IGNORECASE
    )

    return sanitized
