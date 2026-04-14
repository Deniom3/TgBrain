"""
Общий модуль зависимостей для settings_api endpoints.

Re-export из src/api/dependencies/ для устранения прямых импортов
и упрощения рефакторинга.
"""

from ..api.dependencies.auth import AuthenticatedUser, get_current_user
from ..api.dependencies.rate_limiter import (
    webhook_config_rate_limit,
    webhook_test_rate_limit,
)
from ..api.dependencies.services import get_webhook_settings_service

__all__ = [
    "AuthenticatedUser",
    "get_current_user",
    "get_webhook_settings_service",
    "webhook_config_rate_limit",
    "webhook_test_rate_limit",
]
