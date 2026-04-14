"""
App Settings API endpoints.

Endpoints:
- GET /api/v1/settings/app — все настройки
- GET /api/v1/settings/app/{setting_key} — конкретная настройка
- PUT /api/v1/settings/app/{setting_key} — обновить настройку
- PUT /api/v1/settings/app/timezone — установить timezone приложения
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.api.error_codes import APP_ERROR_CODES
from src.api.models import ErrorDetail, ErrorResponse

from .dependencies import AuthenticatedUser, get_current_user
from ..config import reload_settings
from ..models.data_models import AppSetting
from ..common.application_state import AppStateStore
from ..domain.value_objects import AppSettingValue

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings/App"])

# Ключи, которые МОЖНО изменять через API
MODIFIABLE_SETTING_KEYS = {
    "app.timezone",
    "pending.ttl_minutes",
    "pending.cleanup_interval_minutes",
    "summary.ttl_minutes",
    "summary.cleanup_interval_minutes",
    "summary.cleanup.pending_timeout_minutes",
    "summary.cleanup.processing_timeout_minutes",
    "summary.cleanup.failed_retention_minutes",
    "summary.cleanup.completed_retention_minutes",
    "summary.cleanup.auto_enabled",
    "app.default_llm_provider",
    "app.default_embedding_provider",
}


def get_app() -> FastAPI:
    """
    Получить FastAPI приложение из AppStateStore.
    
    Returns:
        FastAPI приложение.
        
    Raises:
        RuntimeError: Если AppStateStore не инициализирован.
    """
    return AppStateStore.get_app()


class AppSettingRequest(BaseModel):
    """Запрос на обновление настройки приложения."""

    value: str | None = Field(default=None)


class AppSettingResponse(BaseModel):
    """Ответ с настройкой приложения."""

    id: Optional[int]
    key: str
    value: Optional[str]
    value_type: str
    description: Optional[str]
    is_sensitive: bool
    updated_at: Optional[str]


class TimezoneRequest(BaseModel):
    """Запрос на установку timezone приложения."""

    timezone: str = Field(..., description="Например: Europe/Moscow")


class TimezoneResponse(BaseModel):
    """Ответ с timezone приложения."""

    timezone: str
    message: str


def _filter_sensitive_settings(settings: list[AppSetting]) -> list[AppSettingResponse]:
    """
    Filter sensitive settings from response.
    
    Args:
        settings: List of AppSetting entities.
        
    Returns:
        List of AppSettingResponse with sensitive values masked.
    """
    result: list[AppSettingResponse] = []
    for s in settings:
        value = None if s.is_sensitive else s.value
        result.append(
            AppSettingResponse(
                id=s.id,
                key=s.key,
                value=value,
                value_type=s.value_type,
                description=s.description,
                is_sensitive=s.is_sensitive,
                updated_at=s.updated_at.isoformat() if s.updated_at else None,
            )
        )
    return result


def _filter_sensitive_setting(setting: AppSetting) -> AppSettingResponse:
    """
    Filter sensitive setting from response.
    
    Args:
        setting: AppSetting entity.
        
    Returns:
        AppSettingResponse with sensitive value masked.
    """
    value = None if setting.is_sensitive else setting.value
    return AppSettingResponse(
        id=setting.id,
        key=setting.key,
        value=value,
        value_type=setting.value_type,
        description=setting.description,
        is_sensitive=setting.is_sensitive,
        updated_at=setting.updated_at.isoformat() if setting.updated_at else None,
    )


@router.get("/app", response_model=list[AppSettingResponse])
async def get_all_app_settings(
    request: Request,
    _user: AuthenticatedUser = Depends(get_current_user),
) -> list[AppSettingResponse]:
    """
    Получить все общие настройки приложения.

    Чувствительные настройки (is_sensitive=True) возвращаются без значения.
    """
    app_settings_repo = request.app.state.app_settings_repo
    settings = await app_settings_repo.get_all()
    return _filter_sensitive_settings(settings)


@router.put(
    "/app/timezone",
    response_model=TimezoneResponse,
    summary="Установить timezone приложения",
)
async def set_timezone(
    timezone_request: TimezoneRequest,
    http_request: Request,
    _user: AuthenticatedUser = Depends(get_current_user),
) -> TimezoneResponse:
    """
    Установить timezone приложения.

    Используется для конвертации локального времени в UTC при установке расписания.

    Error codes:
    - APP-001 — Invalid timezone
    - APP-003 — Ошибка сохранения настройки timezone
    """
    logger.debug("set_timezone вызван с timezone=%s", timezone_request.timezone)
    
    try:
        ZoneInfo(timezone_request.timezone)
    except ZoneInfoNotFoundError as e:
        logger.warning("Невалидный timezone: %s, ошибка: %s", timezone_request.timezone, e)
        ec = APP_ERROR_CODES["APP-001"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    try:
        app_settings_repo = http_request.app.state.app_settings_repo
        saved_setting = await app_settings_repo.upsert(
            key="app.timezone",
            value=timezone_request.timezone,
            value_type="string",
            description="Timezone приложения для конвертации локального времени в UTC",
        )

        if not saved_setting:
            logger.error("Не удалось сохранить настройку timezone в БД: upsert вернул None")
            ec = APP_ERROR_CODES["APP-003"]
            raise HTTPException(
                status_code=ec.http_status,
                detail=ErrorResponse(
                    error=ErrorDetail(code=ec.code, message=ec.message)
                ).model_dump(),
            )

        logger.info("Timezone изменён: %s", timezone_request.timezone)
        logger.debug("Перед reload_settings(), saved_setting=%s", saved_setting)

        try:
            logger.debug("Вызов reload_settings()...")
            await reload_settings()
            logger.debug("reload_settings() завершён успешно")
        except Exception as reload_err:
            logger.error(
                "Ошибка reload_settings(): %s - %s",
                type(reload_err).__name__,
                reload_err,
                exc_info=True,
            )
            raise

        # Обновляем timezone в AppStateStore через глобальный settings
        from src.config import get_settings
        settings = get_settings()
        new_settings = settings.model_copy(update={"timezone": timezone_request.timezone})
        import src.config as config_module
        config_module.settings = new_settings

        logger.debug("Settings updated: timezone changed to %s", timezone_request.timezone)

        return TimezoneResponse(
            timezone=timezone_request.timezone,
            message="Timezone приложения обновлён",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Ошибка сохранения timezone: %s - %s",
            type(e).__name__,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-003", message="Ошибка сохранения настройки timezone")
            ).model_dump(),
        )


@router.get("/app/{setting_key}", response_model=AppSettingResponse)
async def get_app_setting(
    request: Request,
    setting_key: str,
    _user: AuthenticatedUser = Depends(get_current_user),
) -> AppSettingResponse:
    """
    Получить конкретную настройку приложения.

    Чувствительные настройки возвращаются без значения.
    """
    app_settings_repo = request.app.state.app_settings_repo
    setting = await app_settings_repo.get(key=setting_key)

    if not setting:
        ec = APP_ERROR_CODES["APP-002"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    return _filter_sensitive_setting(setting)


@router.put("/app/{setting_key}", response_model=AppSettingResponse)
async def update_app_setting(
    request: Request,
    setting_key: str,
    payload: AppSettingRequest,
    _user: AuthenticatedUser = Depends(get_current_user),
) -> AppSettingResponse:
    """Обновить настройку приложения."""
    if setting_key not in MODIFIABLE_SETTING_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="APP-004",
                    message="This setting cannot be modified via API",
                )
            ).model_dump(),
        )

    app_settings_repo = request.app.state.app_settings_repo
    value = AppSettingValue(payload.value).value if payload.value is not None else None
    setting = await app_settings_repo.update(key=setting_key, value=value)

    if not setting:
        ec = APP_ERROR_CODES["APP-003"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    logger.info("Настройка %s обновлена", setting_key)
    await reload_settings()

    return _filter_sensitive_setting(setting)
