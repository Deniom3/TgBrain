"""Webhook exceptions."""


class WebhookError(Exception):
    """Базовое исключение webhook."""

    code: str
    message: str

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class WebhookDeliveryError(WebhookError):
    """Ошибка доставки webhook."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        # Статические коды ошибок вместо динамических
        if status_code is not None:
            if 400 <= status_code < 500:
                code = "WH-004"  # Client error
            elif 500 <= status_code < 600:
                code = "WH-005"  # Server error
            else:
                code = "WH-001"  # Unknown error
        else:
            code = "WH-001"
        super().__init__(code, message)


class WebhookValidationError(WebhookError):
    """Ошибка валидации webhook конфигурации."""

    def __init__(self, message: str) -> None:
        super().__init__("WH-002", message)


class WebhookTimeoutError(WebhookError):
    """Timeout при отправке webhook."""

    def __init__(self, message: str) -> None:
        super().__init__("WH-003", message)
