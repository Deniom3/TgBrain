"""
Парсинг и валидация CORS_ORIGINS из переменной окружения.
"""

import logging

logger = logging.getLogger(__name__)

_DEFAULT_ORIGINS = ["http://localhost:3000"]


def parse_cors_origins(
    env_value: str | None,
    default: list[str] | None = None,
) -> list[str]:
    """Распарсить и провалидировать CORS origins из значения переменной окружения.

    Примеры:
        >>> parse_cors_origins(None)
        ['http://localhost:3000']
        >>> parse_cors_origins("")
        ['http://localhost:3000']
        >>> parse_cors_origins("http://example.com, https://app.example.com")
        ['http://example.com', 'https://app.example.com']
        >>> parse_cors_origins("*")  # логирует warning
        ['*']
        >>> parse_cors_origins("ftp://invalid.com")  # логирует warning, пропускает
        []
    """
    if default is None:
        default = _DEFAULT_ORIGINS

    if not env_value or not env_value.strip():
        return list(default)

    if env_value.strip() == "*":
        logger.warning(
            "CORS wildcard '*' detected — all origins are allowed. "
            "Not recommended for production."
        )
        return ["*"]

    _SCHEMES = ("http://", "https://")

    origins: list[str] = []
    for raw in env_value.split(","):
        origin = raw.strip()
        if not origin:
            continue
        if not origin.startswith(_SCHEMES):
            logger.warning(
                "Invalid CORS origin skipped (must start with http:// or https://): %s",
                origin,
            )
            continue
        host_part = origin.removeprefix("http://").removeprefix("https://")
        if not host_part or host_part.startswith("/"):
            logger.warning(
                "Invalid CORS origin skipped (missing host): %s",
                origin,
            )
            continue
        origins.append(origin)

    return origins
