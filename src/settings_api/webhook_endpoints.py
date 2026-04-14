"""
Webhook Settings API endpoints.

Endpoints:
- PUT /api/v1/settings/chats/{chat_id}/webhook/config — установить конфигурацию webhook
- GET /api/v1/settings/chats/{chat_id}/webhook/config — получить конфигурацию webhook
- DELETE /api/v1/settings/chats/{chat_id}/webhook/config — отключить webhook
- POST /api/v1/settings/chats/{chat_id}/webhook/test — тестовая отправка webhook

Базовый префикс роутера: /api/v1/settings/chats (монтирование в src.settings_api.app).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .dependencies import (
    AuthenticatedUser,
    get_current_user,
    get_webhook_settings_service,
    webhook_config_rate_limit,
    webhook_test_rate_limit,
)
from ..domain.value_objects import WebhookUrl
from ..settings.repositories.chat_settings import ChatSettingsRepository
from ..application.services.webhook_settings_service import WebhookSettingsService
from ..application.exceptions import ChatNotFoundError, InvalidInputError
from ..api.error_codes import WHK_ERROR_CODES
from ..api.models import ErrorDetail, ErrorResponse
from ..webhook.exceptions import WebhookDeliveryError, WebhookTimeoutError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings/Chats/Webhook"], prefix="/chats")

def _mask_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    """Маскировка sensitive значений в headers (substring match)."""
    from src.settings.repositories.chat_settings import SENSITIVE_HEADER_MARKERS

    result: dict[str, str] = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if any(marker in key_lower for marker in SENSITIVE_HEADER_MARKERS):
            result[key] = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
        else:
            result[key] = value
    return result


class WebhookConfigRequest(BaseModel):
    """Запрос на установку конфигурации webhook."""

    url: str = Field(..., description="Webhook URL (должен начинаться с http:// или https://)")
    method: str = Field(default="POST", description="HTTP метод (POST, GET, PUT, PATCH, DELETE)")
    headers: dict[str, str] = Field(
        default_factory=lambda: {"Content-Type": "application/json"},
        description="HTTP заголовки",
        max_length=50,
    )
    body_template: dict[str, object] = Field(
        ..., description="Шаблон тела запроса", min_length=1
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Валидация URL через WebhookUrl Value Object для SSRF защиты."""
        try:
            webhook_url = WebhookUrl(v)
            return str(webhook_url)
        except ValueError as e:
            raise ValueError(f"Невалидный webhook URL: {e}") from e

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, v: dict[str, str]) -> dict[str, str]:
        """
        Валидация headers.

        Проверяет:
        - Максимальное количество headers (50)
        - Ключи не пустые
        - Значения не пустые

        Sensitive headers (auth, token, key, secret) разрешены,
        но их значения будут маскироваться в логах.
        """
        if len(v) > 50:
            raise ValueError("Слишком много headers (максимум 50)")

        for key, value in v.items():
            if not key or not key.strip():
                raise ValueError("Ключ header не может быть пустым")
            if not value or not str(value).strip():
                raise ValueError(f"Значение header для '{key}' не может быть пустым")

        return v

    @field_validator("body_template")
    @classmethod
    def validate_body_template(cls, v: dict[str, object]) -> dict[str, object]:
        """
        Валидация body_template на наличие обязательных переменных.

        Проверяет:
        - Наличие переменной {{summary}} в значениях (рекурсивно)
        - Пустые ключи запрещены

        Raises:
            ValueError: Если {{summary}} отсутствует.
        """
        def has_summary_variable(obj: object) -> bool:
            """Рекурсивная проверка наличия {{summary}} в структуре."""
            if isinstance(obj, str):
                return "{{summary}}" in obj or "{summary}" in obj
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if not key or not key.strip():
                        raise ValueError("Ключ body_template не может быть пустым")
                    if has_summary_variable(value):
                        return True
            if isinstance(obj, list):
                for item in obj:
                    if has_summary_variable(item):
                        return True
            return False

        if not has_summary_variable(v):
            raise ValueError(
                "body_template должен содержать переменную {{summary}} или {summary} "
                "для подстановки текста summary"
            )

        return v


class WebhookConfigResponse(BaseModel):
    """Ответ с конфигурацией webhook."""

    chat_id: int
    webhook_enabled: bool
    webhook_config: Optional[dict]
    message: str


@router.put(
    "/{chat_id}/webhook/config",
    response_model=WebhookConfigResponse,
    summary="Установить конфигурацию webhook",
)
async def set_webhook_config(
    chat_id: int,
    request: WebhookConfigRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rate_limit: AuthenticatedUser = Depends(webhook_config_rate_limit),
    webhook_service: WebhookSettingsService = Depends(get_webhook_settings_service),
) -> WebhookConfigResponse:
    """
    Установить конфигурацию webhook для чата.

    Error codes:
    - WHK-001 — Chat not found
    - WHK-002 — Invalid webhook configuration
    """
    try:
        await webhook_service.set_webhook_config(
            chat_id=chat_id,
            url=request.url,
            method=request.method,
            headers=request.headers,
            body_template=request.body_template,
        )
    except ChatNotFoundError:
        ec = WHK_ERROR_CODES["WHK-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    except InvalidInputError:
        ec = WHK_ERROR_CODES["WHK-002"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    config: dict[str, object] = {
        "url": request.url,
        "method": request.method,
        "headers": _mask_sensitive_headers(request.headers),
        "body_template": request.body_template,
    }

    return WebhookConfigResponse(
        chat_id=chat_id,
        webhook_enabled=True,
        webhook_config=config,
        message="Webhook конфигурация установлена",
    )


@router.get(
    "/{chat_id}/webhook/config",
    response_model=WebhookConfigResponse,
    summary="Получить конфигурацию webhook",
)
async def get_webhook_config(
    chat_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rate_limit: AuthenticatedUser = Depends(webhook_config_rate_limit),
    webhook_service: WebhookSettingsService = Depends(get_webhook_settings_service),
) -> WebhookConfigResponse:
    """Получить конфигурацию webhook для чата."""
    try:
        webhook_enabled, config, message = await webhook_service.get_webhook_config(
            chat_id=chat_id,
        )
    except ChatNotFoundError:
        ec = WHK_ERROR_CODES["WHK-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    if config and isinstance(config.get("url"), str):
        config = dict(config)
        config["url"] = ChatSettingsRepository._sanitize_webhook_url(
            str(config["url"])
        )
    if config and isinstance(config.get("headers"), dict):
        config = dict(config)
        config["headers"] = _mask_sensitive_headers(config["headers"])

    return WebhookConfigResponse(
        chat_id=chat_id,
        webhook_enabled=webhook_enabled,
        webhook_config=config,
        message=message,
    )


@router.delete(
    "/{chat_id}/webhook/config",
    response_model=WebhookConfigResponse,
    summary="Отключить webhook",
)
async def disable_webhook(
    chat_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rate_limit: AuthenticatedUser = Depends(webhook_config_rate_limit),
    webhook_service: WebhookSettingsService = Depends(get_webhook_settings_service),
) -> WebhookConfigResponse:
    """
    Отключить webhook для чата.
    
    Error codes:
    - WHK-001 — Chat not found
    - WHK-002 — Invalid webhook configuration
    """
    try:
        await webhook_service.disable_webhook(chat_id=chat_id)
    except ChatNotFoundError:
        ec = WHK_ERROR_CODES["WHK-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    except InvalidInputError:
        ec = WHK_ERROR_CODES["WHK-002"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    return WebhookConfigResponse(
        chat_id=chat_id,
        webhook_enabled=False,
        webhook_config=None,
        message="Webhook отключён",
    )


@router.post(
    "/{chat_id}/webhook/test",
    response_model=dict,
    summary="Тестовая отправка webhook",
)
async def test_webhook(
    chat_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rate_limit: AuthenticatedUser = Depends(webhook_test_rate_limit),
    webhook_service: WebhookSettingsService = Depends(get_webhook_settings_service),
) -> dict:
    """
    Отправить тестовый webhook.
    
    Error codes:
    - WHK-001 — Chat not found
    - WHK-002 — Webhook не настроен
    - WHK-003 — Ошибка доставки webhook
    - WHK-004 — Таймаут webhook
    - WHK-006 — Webhook not configured
    """
    try:
        return await webhook_service.test_webhook(chat_id=chat_id)
    except ChatNotFoundError:
        ec = WHK_ERROR_CODES["WHK-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    except InvalidInputError:
        ec = WHK_ERROR_CODES["WHK-006"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    except WebhookDeliveryError:
        ec = WHK_ERROR_CODES["WHK-003"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    except WebhookTimeoutError:
        ec = WHK_ERROR_CODES["WHK-004"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
