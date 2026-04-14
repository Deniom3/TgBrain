"""
Rate limiting dependency для webhook endpoints.

Назначение:
- Ограничение частоты запросов к webhook endpoints
- Защита от злоупотреблений и DDoS
- Приоритизация webhook запросов
"""

import logging
from typing import Any

import asyncpg
from fastapi import Depends, HTTPException

from src.api.dependencies.auth import AuthenticatedUser, get_current_user
from src.api.error_codes import RATE_ERROR_CODES
from src.api.models import ErrorDetail, ErrorResponse
from src.api.protocols import RateLimiterProtocol
from src.rate_limiter.models import RateLimitExceeded, RequestPriority

logger = logging.getLogger(__name__)


class WebhookRateLimitConfig:
    """Конфигурация rate limiting для webhook endpoints."""

    MAX_WEBHOOK_REQUESTS_PER_MINUTE = 10
    MAX_WEBHOOK_REQUESTS_PER_HOUR = 100


def _ensure_rate_limiter_ready(state: Any) -> RateLimiterProtocol:
    """
    Проверить, что rate limiter инициализирован и запущен.

    Args:
        state: Объект состояния приложения.

    Returns:
        RateLimiterProtocol если всё в порядке.

    Raises:
        HTTPException: 503 если rate limiter недоступен.
    """
    if not state or not hasattr(state, "rate_limiter") or state.rate_limiter is None:
        logger.warning("Rate limiter не инициализирован, блокирую запрос")
        ec = RATE_ERROR_CODES["RATE-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    rate_limiter: RateLimiterProtocol = state.rate_limiter

    if not rate_limiter.is_running:
        logger.warning("Rate limiter не запущен, блокирую запрос")
        ec = RATE_ERROR_CODES["RATE-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    return rate_limiter


async def webhook_rate_limit(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    Dependency для rate limiting webhook endpoints.

    Проверяет лимит частоты запросов для webhook endpoints.

    Args:
        current_user: Авторизованный пользователь.

    Returns:
        AuthenticatedUser если лимит не превышен.

    Raises:
        HTTPException: Если лимит превышен (429 Too Many Requests).
    """
    try:
        from src.app import get_app_state

        state = get_app_state()
        rate_limiter = _ensure_rate_limiter_ready(state)

        await rate_limiter.check_rate_limit(
            key="webhook_send",
            priority=RequestPriority.HIGH,
        )

        return current_user

    except RateLimitExceeded as e:
        logger.warning(
            "Rate limit exceeded: key=%s, retry_after=%ds",
            e.key, e.retry_after_seconds,
        )
        ec = RATE_ERROR_CODES["RATE-002"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message),
                retry_after_seconds=e.retry_after_seconds,
            ).model_dump(),
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except (asyncpg.PostgresError, ConnectionError):
        logger.warning("Rate limiter database/connection error")
        ec = RATE_ERROR_CODES["RATE-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    except HTTPException:
        raise


async def webhook_config_rate_limit(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    Dependency для rate limiting webhook config endpoints.

    Менее строгий лимит для операций конфигурации.

    Args:
        current_user: Авторизованный пользователь.

    Returns:
        AuthenticatedUser если лимит не превышен.
    """
    try:
        from src.app import get_app_state

        state = get_app_state()
        rate_limiter = _ensure_rate_limiter_ready(state)

        await rate_limiter.check_rate_limit(
            key="webhook_config",
            priority=RequestPriority.NORMAL,
        )

        return current_user

    except RateLimitExceeded as e:
        logger.warning(
            "Rate limit exceeded: key=%s, retry_after=%ds",
            e.key, e.retry_after_seconds,
        )
        ec = RATE_ERROR_CODES["RATE-002"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message),
                retry_after_seconds=e.retry_after_seconds,
            ).model_dump(),
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except (asyncpg.PostgresError, ConnectionError):
        logger.warning("Rate limiter service unavailable")
        ec = RATE_ERROR_CODES["RATE-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    except HTTPException:
        raise


async def webhook_test_rate_limit(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    Dependency для rate limiting webhook test endpoints.

    Строгий лимит: 5 запросов в минуту для предотвращения злоупотреблений.

    Args:
        current_user: Авторизованный пользователь.

    Returns:
        AuthenticatedUser если лимит не превышен.
    """
    try:
        from src.app import get_app_state

        state = get_app_state()
        rate_limiter = _ensure_rate_limiter_ready(state)

        user_id = getattr(current_user, "user_id", "anonymous")
        await rate_limiter.check_rate_limit(
            key="webhook_test:%s" % user_id,
            priority=RequestPriority.LOW,
        )

        return current_user

    except RateLimitExceeded as e:
        logger.warning(
            "Rate limit exceeded: key=%s, retry_after=%ds",
            e.key, e.retry_after_seconds,
        )
        ec = RATE_ERROR_CODES["RATE-002"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message),
                retry_after_seconds=e.retry_after_seconds,
            ).model_dump(),
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except (asyncpg.PostgresError, ConnectionError):
        logger.warning("Rate limiter service unavailable")
        ec = RATE_ERROR_CODES["RATE-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    except HTTPException:
        raise


class SummaryRateLimitConfig:
    """Конфигурация rate limiting для summary generation endpoints."""

    MAX_SUMMARY_REQUESTS_PER_MINUTE = 5
    MAX_SUMMARY_REQUESTS_PER_HOUR = 50


async def summary_rate_limit(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    Dependency для rate limiting summary generation endpoints.

    Ограничивает частоту запросов на генерацию summary.

    NOTE (S1): Rate limit key привязан к типу операции ("summary_generate"),
    а не к user_id, так как текущая система аутентификации использует
    единую Telegram-сессию без разделения на пользователей.
    При переходе на multi-user auth заменить на f"summary:{current_user.user_id}".

    Args:
        current_user: Авторизованный пользователь.

    Returns:
        AuthenticatedUser если лимит не превышен.

    Raises:
        HTTPException: 429 Too Many Requests при превышении лимита.
    """
    try:
        from src.app import get_app_state

        state = get_app_state()
        rate_limiter = _ensure_rate_limiter_ready(state)

        await rate_limiter.check_rate_limit(
            key="summary_generate",
            priority=RequestPriority.NORMAL,
        )

        return current_user

    except RateLimitExceeded as e:
        logger.warning(
            "Rate limit exceeded: key=%s, retry_after=%ds",
            e.key, e.retry_after_seconds,
        )
        ec = RATE_ERROR_CODES["RATE-002"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message),
                retry_after_seconds=e.retry_after_seconds,
            ).model_dump(),
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except (asyncpg.PostgresError, ConnectionError):
        logger.warning("Rate limiter database/connection error")
        ec = RATE_ERROR_CODES["RATE-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    except HTTPException:
        raise


class ImportRateLimitConfig:
    """Конфигурация rate limiting для import endpoints."""

    MAX_IMPORT_REQUESTS_PER_MINUTE = 3
    MAX_IMPORT_REQUESTS_PER_HOUR = 20


async def import_rate_limit(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    Dependency для rate limiting import endpoints.

    Ограничивает частоту запросов на импорт сообщений.

    Args:
        current_user: Авторизованный пользователь.

    Returns:
        AuthenticatedUser если лимит не превышен.

    Raises:
        HTTPException: 429 Too Many Requests при превышении лимита.
    """
    try:
        from src.app import get_app_state

        state = get_app_state()
        rate_limiter = _ensure_rate_limiter_ready(state)

        await rate_limiter.check_rate_limit(
            key="import_messages",
            priority=RequestPriority.LOW,
        )

        return current_user

    except RateLimitExceeded as e:
        logger.warning(
            "Rate limit exceeded: key=%s, retry_after=%ds",
            e.key, e.retry_after_seconds,
        )
        ec = RATE_ERROR_CODES["RATE-002"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message),
                retry_after_seconds=e.retry_after_seconds,
            ).model_dump(),
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except (asyncpg.PostgresError, ConnectionError):
        logger.warning("Rate limiter database/connection error")
        ec = RATE_ERROR_CODES["RATE-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    except HTTPException:
        raise


__all__ = [
    "webhook_rate_limit",
    "webhook_config_rate_limit",
    "webhook_test_rate_limit",
    "summary_rate_limit",
    "import_rate_limit",
    "WebhookRateLimitConfig",
    "SummaryRateLimitConfig",
    "ImportRateLimitConfig",
]
