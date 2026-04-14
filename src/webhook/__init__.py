"""
Webhook Service — отправка summary по webhook URL с шаблонизацией.
"""

from .exceptions import (
    WebhookDeliveryError,
    WebhookError,
    WebhookTimeoutError,
    WebhookValidationError,
)
from .template_engine import TemplateEngine
from .webhook_service import WebhookService

__all__ = [
    "WebhookService",
    "TemplateEngine",
    "WebhookError",
    "WebhookDeliveryError",
    "WebhookValidationError",
    "WebhookTimeoutError",
]
