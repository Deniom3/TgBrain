"""
Chat Bulk Operations API endpoints.

Массовые операции и переключение чатов.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.models import ErrorDetail, ErrorResponse

from ..settings import ChatSettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings/Chats/Operations"])


# ==================== Models ====================

class ChatToggleResponse(BaseModel):
    """Ответ на переключение мониторинга чата."""
    chat_id: int
    is_monitored: bool
    title: str | None
    message: str


class ChatBulkUpdateRequest(BaseModel):
    """Запрос на массовое обновление настроек чатов."""
    chat_ids: List[int] = Field(..., description="Список ID чатов")
    is_monitored: Optional[bool] = Field(default=None)
    summary_enabled: Optional[bool] = Field(default=None)
    custom_prompt: Optional[str] = Field(default=None)
    filter_bots: Optional[bool] = Field(default=None)
    filter_actions: Optional[bool] = Field(default=None)
    filter_min_length: Optional[int] = Field(default=None, ge=0)
    filter_ads: Optional[bool] = Field(default=None)


class ChatBulkUpdateResponse(BaseModel):
    """Ответ на массовое обновление настроек чатов."""
    updated_count: int
    chat_ids: List[int]
    message: str


# ==================== Endpoints ====================

@router.post("/chats/{chat_id}/toggle", response_model=ChatToggleResponse)
async def toggle_chat_monitoring(chat_id: int):
    """Переключить состояние мониторинга чата."""
    from ..app import get_app_state

    app_state = get_app_state()
    if not app_state or not app_state.db_pool:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="Database not available")
            ).model_dump(),
        )
    
    repo = ChatSettingsRepository(app_state.db_pool)
    setting = await repo.toggle_chat_monitoring(chat_id)

    if not setting:
        setting = await repo.upsert(
            chat_id=chat_id,
            title=f"Chat {chat_id}",
            is_monitored=True,
            summary_enabled=True,
        )
        if not setting:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-101", message="Failed to toggle chat monitoring")
                ).model_dump(),
            )
        message = f"Чат {chat_id} добавлен и включён"
    else:
        message = f"Мониторинг чата {'включён' if setting.is_monitored else 'отключён'}"

    logger.info(f"Мониторинг чата {chat_id} переключен: {setting.is_monitored}")

    try:
        app_state = get_app_state()
        if app_state and hasattr(app_state, 'ingester') and app_state.ingester:
            await app_state.ingester.reload_monitored_chats()
            logger.info("Ingester уведомлён об обновлении monitored чатов")
    except Exception as e:
        logger.warning(f"Не удалось уведомить Ingester: {e}")

    return ChatToggleResponse(
        chat_id=chat_id,
        is_monitored=setting.is_monitored,
        title=setting.title,
        message=message,
    )


@router.post("/chats/{chat_id}/enable", response_model=ChatToggleResponse)
async def enable_chat_monitoring(chat_id: int):
    """Включить мониторинг чата."""
    from ..app import get_app_state

    app_state = get_app_state()
    if not app_state or not app_state.db_pool:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="Database not available")
            ).model_dump(),
        )
    
    repo = ChatSettingsRepository(app_state.db_pool)
    setting = await repo.enable_chat(chat_id)

    if not setting:
        setting = await repo.upsert(
            chat_id=chat_id,
            title=f"Chat {chat_id}",
            is_monitored=True,
            summary_enabled=True,
        )
        if not setting:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-101", message="Failed to enable chat monitoring")
                ).model_dump(),
            )

    logger.info(f"Мониторинг чата {chat_id} включён")

    try:
        app_state = get_app_state()
        if app_state and hasattr(app_state, 'ingester') and app_state.ingester:
            await app_state.ingester.reload_monitored_chats()
            logger.info("Ingester уведомлён об обновлении monitored чатов")
    except Exception as e:
        logger.warning(f"Не удалось уведомить Ingester: {e}")

    return ChatToggleResponse(
        chat_id=chat_id,
        is_monitored=setting.is_monitored,
        title=setting.title,
        message=f"Чат {chat_id} включён для мониторинга",
    )


@router.post("/chats/{chat_id}/disable", response_model=ChatToggleResponse)
async def disable_chat_monitoring(chat_id: int):
    """Отключить мониторинг чата."""
    from ..app import get_app_state

    app_state = get_app_state()
    if not app_state or not app_state.db_pool:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="Database not available")
            ).model_dump(),
        )
    
    repo = ChatSettingsRepository(app_state.db_pool)
    setting = await repo.disable_chat(chat_id)

    if not setting:
        setting = await repo.upsert(
            chat_id=chat_id,
            title=f"Chat {chat_id}",
            is_monitored=False,
            summary_enabled=False,
        )
        if not setting:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-101", message="Failed to disable chat monitoring")
                ).model_dump(),
            )

    logger.info(f"Мониторинг чата {chat_id} отключён")

    try:
        app_state = get_app_state()
        if app_state and hasattr(app_state, 'ingester') and app_state.ingester:
            await app_state.ingester.reload_monitored_chats()
            logger.info("Ingester уведомлён об обновлении monitored чатов")
    except Exception as e:
        logger.warning(f"Не удалось уведомить Ingester: {e}")

    return ChatToggleResponse(
        chat_id=chat_id,
        is_monitored=setting.is_monitored,
        title=setting.title,
        message=f"Чат {chat_id} отключён от мониторинга",
    )


@router.post("/chats/bulk-update", response_model=ChatBulkUpdateResponse)
async def bulk_update_chat_settings(request: ChatBulkUpdateRequest):
    """Массовое обновление настроек чатов."""
    if not request.chat_ids:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-102", message="Список chat_ids не может быть пустым")
            ).model_dump(),
        )

    from ..app import get_app_state
    app_state = get_app_state()
    if not app_state or not app_state.db_pool:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="Database not available")
            ).model_dump(),
        )

    repo = ChatSettingsRepository(app_state.db_pool)
    updated_count = 0
    for chat_id in request.chat_ids:
        setting = await repo.update(
            chat_id=chat_id,
            is_monitored=request.is_monitored,
            summary_enabled=request.summary_enabled,
            custom_prompt=request.custom_prompt,
            filter_bots=request.filter_bots,
            filter_actions=request.filter_actions,
            filter_min_length=request.filter_min_length,
            filter_ads=request.filter_ads,
        )
        if setting:
            updated_count += 1

    logger.info(f"Массовое обновление: обновлено {updated_count} из {len(request.chat_ids)} чатов")

    try:
        from ..app import get_app_state
        app_state = get_app_state()
        if app_state and hasattr(app_state, 'ingester') and app_state.ingester:
            await app_state.ingester.reload_monitored_chats()
            logger.info("Ingester уведомлён об обновлении monitored чатов")
    except Exception as e:
        logger.warning(f"Не удалось уведомить Ingester: {e}")

    return ChatBulkUpdateResponse(
        updated_count=updated_count,
        chat_ids=request.chat_ids,
        message=f"Обновлено {updated_count} чатов",
    )
