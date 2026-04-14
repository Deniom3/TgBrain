"""
Dependency для проверки аутентификации.

Назначение:
- Проверка наличия активной сессии Telegram
- Защита endpoints от неавторизованного доступа
"""

import logging
from typing import Optional

import asyncpg
from fastapi import Depends, HTTPException, Request

from src.api.error_codes import AUTH_ERROR_CODES
from src.api.models import ErrorDetail, ErrorResponse
from src.settings.repositories.telegram_auth import TelegramAuthRepository

logger = logging.getLogger(__name__)


class AuthenticatedUser:
    """
    Представление авторизованного пользователя.
    
    В текущей реализации содержит только флаг авторизации,
    так как проект использует Telegram сессии без разделения на пользователей.
    """

    def __init__(self, is_authenticated: bool = True) -> None:
        self.is_authenticated = is_authenticated


async def _get_telegram_auth_repo(request: Request) -> TelegramAuthRepository:
    """Получить TelegramAuthRepository из app.state."""
    repo = getattr(request.app.state, "telegram_auth_repo", None)
    if repo is None:
        ec = AUTH_ERROR_CODES["AUTH-004"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    return repo


async def get_current_user(
    request: Request,
    telegram_auth_repo: TelegramAuthRepository = Depends(_get_telegram_auth_repo),
) -> AuthenticatedUser:
    """
    Dependency для проверки аутентификации пользователя.

    Проверяет наличие активной сессии Telegram в БД.

    Args:
        request: HTTP запрос.
        telegram_auth_repo: Репозиторий авторизации (из app.state).

    Returns:
        AuthenticatedUser если аутентификация успешна.

    Raises:
        HTTPException: Если сессия не активна (401 Unauthorized).
    """
    try:
        logger.debug("Проверка аутентификации для %s", request.url.path)
        is_active = await telegram_auth_repo.is_session_active()
        logger.debug("Результат проверки сессии: is_active=%s", is_active)

        if not is_active:
            logger.warning("Попытка доступа без активной сессии: %s", request.url.path)
            ec = AUTH_ERROR_CODES["AUTH-001"]
            raise HTTPException(
                status_code=ec.http_status,
                detail=ErrorResponse(
                    error=ErrorDetail(code=ec.code, message=ec.message)
                ).model_dump(),
                headers={"WWW-Authenticate": "QR-Auth"},
            )

        return AuthenticatedUser(is_authenticated=True)

    except HTTPException:
        raise
    except (asyncpg.PostgresError, ConnectionError) as e:
        logger.exception("Ошибка проверки аутентификации: %s", e)
        ec = AUTH_ERROR_CODES["AUTH-002"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("Неожиданная ошибка проверки аутентификации: %s", type(e).__name__)
        ec = AUTH_ERROR_CODES["AUTH-003"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )


async def get_current_user_optional(
    request: Request,
    telegram_auth_repo: TelegramAuthRepository = Depends(_get_telegram_auth_repo),
) -> Optional[AuthenticatedUser]:
    """
    Dependency для опциональной проверки аутентификации.
    
    Возвращает AuthenticatedUser если сессия активна, иначе None.
    Не вызывает HTTPException.
    
    Args:
        request: HTTP запрос.
        telegram_auth_repo: Репозиторий авторизации (из app.state).
        
    Returns:
        AuthenticatedUser или None.
    """
    try:
        is_active = await telegram_auth_repo.is_session_active()
        
        if is_active:
            return AuthenticatedUser(is_authenticated=True)
        
        return None
        
    except (asyncpg.PostgresError, ConnectionError, OSError):
        logger.warning("Optional auth database/connection error")
        return None
