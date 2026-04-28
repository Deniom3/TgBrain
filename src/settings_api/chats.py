"""
Chat Settings API endpoints.

Базовые CRUD операции: get, list, update, delete.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.models import ErrorDetail, ErrorResponse

from ..settings import ChatSettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings/Chats"])


# ==================== Models ====================

class ChatSettingRequest(BaseModel):
    """Запрос на обновление настроек чата."""
    title: str | None = Field(default=None)
    is_monitored: bool = Field(default=True)
    summary_enabled: bool = Field(default=True)
    custom_prompt: str | None = Field(default=None)
    filter_bots: bool = Field(default=True)
    filter_actions: bool = Field(default=True)
    filter_min_length: int = Field(default=15, ge=0)
    filter_ads: bool = Field(default=True)


class ChatSettingResponse(BaseModel):
    """Ответ с настройками чата."""
    id: int | None
    chat_id: int
    title: str | None
    is_monitored: bool
    summary_enabled: bool
    custom_prompt: str | None
    filter_bots: bool
    filter_actions: bool
    filter_min_length: int
    filter_ads: bool
    created_at: str | None
    updated_at: str | None


class ChatListMeta(BaseModel):
    """Мета-информация о списке чатов."""
    total: int
    monitored: int
    not_monitored: int


class ChatListResponse(BaseModel):
    """Расширенный ответ со списком чатов."""
    chats: List[ChatSettingResponse]
    meta: ChatListMeta


class ChatFilterBulkRequest(BaseModel):
    """Запрос на массовое обновление фильтров."""
    filter_bots: bool = Field(default=True)
    filter_actions: bool = Field(default=True)
    filter_min_length: int = Field(default=15, ge=0)
    filter_ads: bool = Field(default=True)


class ChatFilterBulkResponse(BaseModel):
    """Ответ на массовое обновление фильтров."""
    status: str
    updated_count: int
    filters: dict


# ==================== Endpoints ====================

@router.get("/chats", response_model=List[ChatSettingResponse])
async def get_all_chat_settings():
    """Получить настройки всех чатов."""
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
    settings = await repo.get_all()

    return [
        ChatSettingResponse(
            id=s.id,
            chat_id=s.chat_id,
            title=s.title,
            is_monitored=s.is_monitored,
            summary_enabled=s.summary_enabled,
            custom_prompt=s.custom_prompt,
            filter_bots=s.filter_bots,
            filter_actions=s.filter_actions,
            filter_min_length=s.filter_min_length,
            filter_ads=s.filter_ads,
            created_at=s.created_at.isoformat() if s.created_at else None,
            updated_at=s.updated_at.isoformat() if s.updated_at else None,
        )
        for s in settings
    ]


@router.get("/chats/list", response_model=ChatListResponse)
async def get_all_chat_settings_with_meta():
    """Получить настройки всех чатов с мета-информацией."""
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
    settings = await repo.get_all()
    monitored_count = sum(1 for s in settings if s.is_monitored)

    return ChatListResponse(
        chats=[
            ChatSettingResponse(
                id=s.id,
                chat_id=s.chat_id,
                title=s.title,
                is_monitored=s.is_monitored,
                summary_enabled=s.summary_enabled,
                custom_prompt=s.custom_prompt,
                filter_bots=s.filter_bots,
                filter_actions=s.filter_actions,
                filter_min_length=s.filter_min_length,
                filter_ads=s.filter_ads,
                created_at=s.created_at.isoformat() if s.created_at else None,
                updated_at=s.updated_at.isoformat() if s.updated_at else None,
            )
            for s in settings
        ],
        meta=ChatListMeta(
            total=len(settings),
            monitored=monitored_count,
            not_monitored=len(settings) - monitored_count,
        )
    )


@router.get("/chats/monitored", response_model=List[ChatSettingResponse])
async def get_monitored_chat_settings():
    """Получить настройки только monitored чатов."""
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
    settings = await repo.get_monitored_chats()

    return [
        ChatSettingResponse(
            id=s.id,
            chat_id=s.chat_id,
            title=s.title,
            is_monitored=s.is_monitored,
            summary_enabled=s.summary_enabled,
            custom_prompt=s.custom_prompt,
            filter_bots=s.filter_bots,
            filter_actions=s.filter_actions,
            filter_min_length=s.filter_min_length,
            filter_ads=s.filter_ads,
            created_at=s.created_at.isoformat() if s.created_at else None,
            updated_at=s.updated_at.isoformat() if s.updated_at else None,
        )
        for s in settings
    ]


@router.get("/chats/{chat_id}", response_model=ChatSettingResponse)
async def get_chat_setting(chat_id: int):
    """Получить настройки конкретного чата."""
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
    setting = await repo.get(chat_id)

    if not setting:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Chat settings not found")
            ).model_dump(),
        )

    return ChatSettingResponse(
        id=setting.id,
        chat_id=setting.chat_id,
        title=setting.title,
        is_monitored=setting.is_monitored,
        summary_enabled=setting.summary_enabled,
        custom_prompt=setting.custom_prompt,
        filter_bots=setting.filter_bots,
        filter_actions=setting.filter_actions,
        filter_min_length=setting.filter_min_length,
        filter_ads=setting.filter_ads,
        created_at=setting.created_at.isoformat() if setting.created_at else None,
        updated_at=setting.updated_at.isoformat() if setting.updated_at else None,
    )


@router.put("/chats/{chat_id}", response_model=ChatSettingResponse)
async def update_chat_setting(request: Request, chat_id: int, request_data: ChatSettingRequest):
    """Обновить настройки чата."""
    app_state = request.app.state
    if not app_state.db_pool:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="Database not available")
            ).model_dump(),
        )
    
    repo = ChatSettingsRepository(app_state.db_pool)
    setting = await repo.update(
        chat_id=chat_id,
        is_monitored=request_data.is_monitored,
        summary_enabled=request_data.summary_enabled,
        custom_prompt=request_data.custom_prompt,
        filter_bots=request_data.filter_bots,
        filter_actions=request_data.filter_actions,
        filter_min_length=request_data.filter_min_length,
        filter_ads=request_data.filter_ads,
    )

    if not setting:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Failed to update chat settings")
            ).model_dump(),
        )

    # Обновляем кэш monitored чатов в Ingester
    app_state = request.app.state
    if hasattr(app_state, 'ingester') and app_state.ingester:
        await app_state.ingester.reload_monitored_chats()

    logger.info(f"Настройки чата {chat_id} обновлены")

    return ChatSettingResponse(
        id=setting.id,
        chat_id=setting.chat_id,
        title=setting.title,
        is_monitored=setting.is_monitored,
        summary_enabled=setting.summary_enabled,
        custom_prompt=setting.custom_prompt,
        filter_bots=setting.filter_bots,
        filter_actions=setting.filter_actions,
        filter_min_length=setting.filter_min_length,
        filter_ads=setting.filter_ads,
        created_at=setting.created_at.isoformat() if setting.created_at else None,
        updated_at=setting.updated_at.isoformat() if setting.updated_at else None,
    )


@router.put("/chats/bulk/filter", response_model=ChatFilterBulkResponse)
async def bulk_update_chat_filters(request: Request, filters: ChatFilterBulkRequest):
    """Массовое обновление фильтров для monitored чатов."""
    app_state = request.app.state
    if not app_state.db_pool:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="Database not available")
            ).model_dump(),
        )

    repo = ChatSettingsRepository(app_state.db_pool)
    monitored_chats = await repo.get_monitored_chat_ids()
    updated_count = 0

    for chat_id in monitored_chats:
        setting = await repo.update(
            chat_id=chat_id,
            filter_bots=filters.filter_bots,
            filter_actions=filters.filter_actions,
            filter_min_length=filters.filter_min_length,
            filter_ads=filters.filter_ads,
        )
        if setting:
            updated_count += 1

    if hasattr(app_state, "ingester") and app_state.ingester:
        await app_state.ingester.reload_monitored_chats()

    logger.info(
        "Bulk filter update: %d chats updated with bots=%s actions=%s min_length=%d ads=%s",
        updated_count,
        filters.filter_bots,
        filters.filter_actions,
        filters.filter_min_length,
        filters.filter_ads,
    )

    return ChatFilterBulkResponse(
        status="success",
        updated_count=updated_count,
        filters={
            "filter_bots": filters.filter_bots,
            "filter_actions": filters.filter_actions,
            "filter_min_length": filters.filter_min_length,
            "filter_ads": filters.filter_ads,
        },
    )


@router.delete("/chats/{chat_id}", response_model=dict)
async def delete_chat_setting(request: Request, chat_id: int):
    """Удалить настройки чата."""
    app_state = request.app.state
    if not app_state.db_pool:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="Database not available")
            ).model_dump(),
        )
    
    repo = ChatSettingsRepository(app_state.db_pool)
    success = await repo.delete(chat_id)

    if not success:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Failed to delete chat settings")
            ).model_dump(),
        )

    # Обновляем кэш monitored чатов в Ingester
    app_state = request.app.state
    if hasattr(app_state, 'ingester') and app_state.ingester:
        await app_state.ingester.reload_monitored_chats()

    logger.info(f"Настройки чата {chat_id} удалены")

    return {"status": "success", "chat_id": str(chat_id)}
