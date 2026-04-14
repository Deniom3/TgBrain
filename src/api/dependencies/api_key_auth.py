"""
Dependency для проверки API key.

Назначение:
- Проверка заголовка X-API-Key против Settings.API_KEY
- Защита эндпоинтов от неавторизованного доступа
- Local dev mode: если API_KEY не установлен — проверка пропускается
"""

import hmac
import logging

from fastapi import HTTPException, Request

from src.api.error_codes import AUTH_ERROR_CODES
from src.api.models import ErrorDetail, ErrorResponse
from src.config import get_settings

logger = logging.getLogger(__name__)


async def verify_api_key(request: Request) -> None:
    """
    Dependency для проверки API key.

    Читает Settings.API_KEY и сравнивает с заголовком X-API-Key.
    Если API_KEY не установлен — проверка пропускается (local dev mode).

    Args:
        request: HTTP запрос.

    Raises:
        HTTPException: 401 AUTH-101 — заголовок X-API-Key отсутствует.
        HTTPException: 401 AUTH-102 — API key не совпадает.
    """
    settings = get_settings()
    api_key = settings.api_key

    if not api_key:
        return

    header = request.headers.get("X-API-Key")

    if not header:
        logger.warning("Отсутствует заголовок X-API-Key для %s", request.url.path)
        ec = AUTH_ERROR_CODES["AUTH-101"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    if not hmac.compare_digest(header, api_key):
        mask = header[:4] + "***" if len(header) > 4 else "***"
        logger.warning("Неверный API key (маска: %s) для %s", mask, request.url.path)
        ec = AUTH_ERROR_CODES["AUTH-102"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
