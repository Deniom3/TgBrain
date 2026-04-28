"""
Telegram Auth API endpoints.
"""

import logging
import re
from typing import Any, ClassVar, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from src.api.models import ErrorDetail, ErrorResponse
from src.infrastructure.exceptions import (
    SessionDecryptionError,
    SessionNotAuthorizedError,
    SessionNotConfiguredError,
)
from src.infrastructure.telegram_client_factory import TelegramClientFactory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings/Telegram"])


class TelegramAuthRequest(BaseModel):
    """Запрос на обновление настроек Telegram."""
    api_id: int | None = Field(default=None, ge=1)
    api_hash: str | None = Field(default=None, min_length=32)
    phone_number: str | None = Field(default=None)
    session_name: str = Field(default="tg_scraper_session")

    SESSION_NAME_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9_-]+$")

    @field_validator("session_name")
    @classmethod
    def validate_session_name(cls, value: str) -> str:
        if len(value) > 64:
            raise ValueError("session_name must be at most 64 characters")
        if not cls.SESSION_NAME_PATTERN.match(value):
            raise ValueError(
                "session_name must contain only letters, digits, hyphens, and underscores"
            )
        return value


class TelegramAuthResponse(BaseModel):
    """Ответ с настройками Telegram (без чувствительных данных)."""
    id: int
    api_id: int | None = None
    api_hash: str | None = None
    phone_number: str | None = None
    session_name: str
    updated_at: str | None
    is_configured: bool
    is_session_active: bool = False


def mask_sensitive_data(data: str | None, show_first: int = 0) -> str | None:
    """Замаскировать чувствительные данные."""
    if not data:
        return None
    if show_first > 0 and len(data) > show_first:
        return data[:show_first] + "***"
    return "***"


@router.get("/telegram", response_model=TelegramAuthResponse)
async def get_telegram_auth(request: Request):
    """
    Получить настройки авторизации Telegram.

    Возвращает текущие настройки подключения к Telegram API.
    Чувствительные данные скрываются после первой настройки.
    """
    # Получаем репозиторий из app.state
    telegram_auth_repo = request.app.state.telegram_auth_repo
    auth = await telegram_auth_repo.get()

    if not auth:
        return TelegramAuthResponse(
            id=1,
            api_id=None,
            api_hash=None,
            phone_number=None,
            session_name="tg_scraper_session",
            updated_at=None,
            is_configured=False,
            is_session_active=False,
        )

    # Проверяем активность сессии
    is_session_active = False
    try:
        is_session_active = await telegram_auth_repo.is_session_active()
    except Exception:
        is_session_active = False

    # Скрываем чувствительные данные если они уже были установлены
    show_sensitive = auth.api_id is None

    # Конвертируем session_name в строку если это Value Object
    session_name_str: str
    if auth.session_name is None:
        session_name_str = "tg_scraper_session"
    elif hasattr(auth.session_name, 'value'):
        session_name_str = str(auth.session_name.value)
    else:
        session_name_str = str(auth.session_name)

    return TelegramAuthResponse(
        id=auth.id,
        api_id=auth.api_id.value if show_sensitive and auth.api_id else None,
        api_hash=auth.api_hash.value if show_sensitive and auth.api_hash else None,
        phone_number=auth.phone_number.value if show_sensitive and auth.phone_number else None,
        session_name=session_name_str,
        updated_at=auth.updated_at.isoformat() if auth.updated_at else None,
        is_configured=bool(auth.api_id and auth.api_hash),
        is_session_active=is_session_active,
    )


@router.put("/telegram", response_model=TelegramAuthResponse)
async def update_telegram_auth(request: Request, payload: TelegramAuthRequest):
    """
    Обновить настройки авторизации Telegram.

    Изменения вступают в силу немедленно для новых подключений.
    """
    # Получаем репозиторий из app.state
    telegram_auth_repo = request.app.state.telegram_auth_repo
    auth = await telegram_auth_repo.upsert(
        api_id=payload.api_id,
        api_hash=payload.api_hash,
        phone_number=payload.phone_number,
        session_name=payload.session_name,
    )

    if not auth:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Ошибка сохранения настроек Telegram")
            ).model_dump(),
        )

    logger.info("Настройки Telegram обновлены: api_id=***")

    return TelegramAuthResponse(
        id=auth.id,
        api_id=auth.api_id.value if auth.api_id else None,
        api_hash=auth.api_hash.value if auth.api_hash else None,
        phone_number=auth.phone_number.value if auth.phone_number else None,
        session_name=auth.session_name.value if auth.session_name else "tg_scraper_session",
        updated_at=auth.updated_at.isoformat() if auth.updated_at else None,
        is_configured=bool(auth.api_id and auth.api_hash),
    )


@router.get("/telegram/check", response_model=Dict[str, Any])
async def check_telegram_health(request: Request):
    """
    Проверить работоспособность Telegram сессии.

    Возвращает статус подключения к Telegram API.
    """
    result = {
        "name": "telegram",
        "is_available": False,
        "is_authorized": False,
        "user": None,
        "error": None,
    }

    factory: TelegramClientFactory | None = request.app.state.telegram_client_factory
    if not factory:
        result["error"] = "Telegram client factory not available"
        return result

    try:
        client, session_path = await factory.create_client()
        try:
            await factory.connect_client(client)
            result["is_available"] = True
            result["is_authorized"] = True
            me = await client.get_me()
            result["user"] = {
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "is_premium": getattr(me, "is_premium", False),
            }
        finally:
            await client.disconnect()
            factory.cleanup(session_path)
    except SessionNotConfiguredError:
        result["error"] = "Сессия Telegram не настроена"
    except SessionNotAuthorizedError:
        result["error"] = "Сессия не авторизована"
    except SessionDecryptionError:
        result["error"] = "Ошибка расшифровки сессии"
    except Exception as e:
        logger.error("Check Telegram error: %s", type(e).__name__)
        result["error"] = "Internal server error"

    return result
