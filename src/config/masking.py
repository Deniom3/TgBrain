"""
Утилита маскирования API ключей.

Чистая функция без I/O и внешних зависимостей.
"""


def mask_api_key(api_key: str | None) -> str | None:
    """Замаскировать API ключ, оставив только последние 4 символа.

    Примеры:
        >>> mask_api_key(None)
        >>> mask_api_key("")
        >>> mask_api_key("short")
        '***'
        >>> mask_api_key("sk-abc123def456")
        'sk-...f456'
        >>> mask_api_key("abcdefghijklmnop")
        'abcd...mnop'
    """
    if not api_key:
        return None
    if len(api_key) <= 8:
        return "***"
    if "-" in api_key[:10]:
        prefix = api_key.split("-")[0] + "-"
        suffix = api_key[-4:]
        return f"{prefix}...{suffix}"
    return f"{api_key[:4]}...{api_key[-4:]}"
