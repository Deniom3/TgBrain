"""
Dependency injection для API endpoints.

Импорты:
- get_current_user: Проверка аутентификации
- get_current_user_optional: Опциональная проверка
- verify_api_key: Проверка API key через заголовок X-API-Key
"""

from src.api.dependencies.api_key_auth import verify_api_key
from src.api.dependencies.auth import (
    AuthenticatedUser,
    get_current_user,
    get_current_user_optional,
)

__all__ = [
    "AuthenticatedUser",
    "get_current_user",
    "get_current_user_optional",
    "verify_api_key",
]
