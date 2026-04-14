"""
Typed exception для конфигурационных ошибок.
"""

from typing import Any


class ConfigurationError(RuntimeError):
    """Ошибка конфигурации с кодом и контекстом.

    Наследует RuntimeError для обратной совместимости с существующим кодом.
    """

    def __init__(
        self,
        code: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Создать ошибку конфигурации.

        Args:
            code: Стабильный код ошибки, формат "CONF-XXX".
            message: Человекочитаемое описание ошибки.
            context: Дополнительный контекст. Не должен содержать sensitive данные
                (API keys, tokens, passwords).

        Примеры:
            >>> ConfigurationError("CONF-001", "Missing API key")
            >>> ConfigurationError("CONF-002", "Invalid value", context={"key": "CORS_ORIGINS"})
        """
        if not code.startswith("CONF-"):
            raise ValueError(
                f"ConfigurationError code must start with 'CONF-', got: {code!r}"
            )
        self.code = code
        self.message = message
        self.context = context
        super().__init__(f"[{code}] {message}")

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"
