"""
Chat User Management API endpoints.

Эндпоинты для добавления/удаления пользователей и синхронизации с Telegram.
"""

import logging
import os
from typing import Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.error_codes import APP_ERROR_CODES
from src.api.models import ErrorDetail, ErrorResponse

from ..settings.repositories import ChatSettingsRepository
from ..settings.repositories.telegram_auth import TelegramAuthRepository
from ..auth import DEFAULT_SESSION_PATH
from ..common.application_state import AppStateStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings/Chats/Users"])


class AddUserRequest(BaseModel):
    """Запрос на добавление пользователя для мониторинга."""
    user_identifier: str = Field(..., description="ID пользователя или username")
    is_monitored: bool = Field(default=True)


class AddUserResponse(BaseModel):
    """Ответ на добавление пользователя."""
    chat_id: int
    title: str
    username: str | None
    is_monitored: bool
    is_bot: bool
    message: str


class RemoveUserRequest(BaseModel):
    """Запрос на отключение пользователя от мониторинга."""
    user_identifier: str = Field(..., description="ID пользователя или username")


class RemoveUserResponse(BaseModel):
    """Ответ на отключение пользователя."""
    chat_id: int
    title: str
    username: str | None
    is_monitored: bool
    message: str


@router.post("/chats/sync", response_model=Dict[str, int])
async def sync_chats_with_telegram(request: Request):
    """Принудительная синхронизация чатов с Telegram."""
    from ..ingestion.chat_sync_service import ChatSyncService
    from telethon import TelegramClient

    try:
        telegram_auth_repo: TelegramAuthRepository = request.app.state.telegram_auth_repo
        auth = await telegram_auth_repo.get()
        if not auth or not auth.session_name:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Сессия Telegram не настроена")
                ).model_dump(),
            )

        session_name_str = auth.session_name.value if hasattr(auth.session_name, 'value') else str(auth.session_name)
        session_file = os.path.join(DEFAULT_SESSION_PATH, session_name_str)

        client = TelegramClient(session_file, auth.api_id.value if auth.api_id else 0, auth.api_hash.value if auth.api_hash else "")
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Сессия не авторизована")
                ).model_dump(),
            )

        pool = request.app.state.db_pool
        sync_service = ChatSyncService(pool)
        stats = await sync_service.sync_chats_with_telegram(client, limit=100, preserve_existing=True)

        await client.disconnect()
        logger.info("Синхронизация чатов завершена: %s", stats)
        return stats

    except HTTPException:
        raise
    except Exception:
        logger.exception("Ошибка синхронизации чатов")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.post("/chats/user/add", response_model=AddUserResponse)
async def add_user_for_monitoring(request_data: AddUserRequest, request: Request):
    """Добавить пользователя для мониторинга по ID или username."""
    from ..ingestion.chat_sync_service import ChatSyncService
    from telethon import TelegramClient

    try:
        telegram_auth_repo: TelegramAuthRepository = request.app.state.telegram_auth_repo
        auth = await telegram_auth_repo.get()
        if not auth or not auth.session_name:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Сессия Telegram не настроена")
                ).model_dump(),
            )

        session_name_str = auth.session_name.value if hasattr(auth.session_name, 'value') else str(auth.session_name)
        session_file = os.path.join(DEFAULT_SESSION_PATH, session_name_str)

        client = TelegramClient(session_file, auth.api_id.value if auth.api_id else 0, auth.api_hash.value if auth.api_hash else "")
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Сессия не авторизована")
                ).model_dump(),
            )

        user_identifier = request_data.user_identifier.strip()

        pool = request.app.state.db_pool
        sync_service = ChatSyncService(pool)

        try:
            user_id = int(user_identifier)
            user_info = await sync_service.get_chat_info(client, user_id)
        except ValueError:
            user_info = await sync_service.get_user_info_by_username(client, user_identifier)

        if not user_info:
            await client.disconnect()
            ec = APP_ERROR_CODES["APP-103"]
            raise HTTPException(
                status_code=ec.http_status,
                detail=ErrorResponse(
                    error=ErrorDetail(code=ec.code, message="User not found")
                ).model_dump(),
            )

        if user_info.get("is_bot", False):
            await client.disconnect()
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Нельзя добавить бота для мониторинга")
                ).model_dump(),
            )

        chat_id = user_info["chat_id"]

        app_state = AppStateStore.get_app().state if AppStateStore.is_initialized() else None
        if not app_state or not app_state.db_pool:
            await client.disconnect()
            raise HTTPException(
                status_code=503,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-106", message="Database not available")
                ).model_dump(),
            )

        repo = ChatSettingsRepository(app_state.db_pool)
        setting = await repo.upsert(
            chat_id=chat_id,
            title=user_info["title"],
            is_monitored=request_data.is_monitored,
            summary_enabled=True,
            custom_prompt=None,
        )

        if not setting:
            await client.disconnect()
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-101", message=f"Ошибка сохранения настроек для пользователя {chat_id}")
                ).model_dump(),
            )

        await client.disconnect()

        try:
            if app_state and hasattr(app_state, 'ingester') and app_state.ingester:
                await app_state.ingester.reload_monitored_chats()
                logger.info("Ingester уведомлён об обновлении monitored чатов")
        except Exception as e:
            logger.warning("Не удалось уведомить Ingester: %s", e)

        action = "включён" if request_data.is_monitored else "добавлен (отключён)"
        message = f"Пользователь {user_info['title']} {action} для мониторинга"

        logger.info("Пользователь %s (%s) добавлен: %s", chat_id, user_info.get('username', 'N/A'), action)

        return AddUserResponse(
            chat_id=chat_id,
            title=user_info["title"],
            username=user_info.get("username"),
            is_monitored=request_data.is_monitored,
            is_bot=False,
            message=message,
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Ошибка добавления пользователя")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.post("/chats/user/remove", response_model=RemoveUserResponse)
async def remove_user_from_monitoring(request_data: RemoveUserRequest, request: Request):
    """Отключить пользователя от мониторинга по ID или username."""
    from ..ingestion.chat_sync_service import ChatSyncService
    from telethon import TelegramClient

    try:
        telegram_auth_repo: TelegramAuthRepository = request.app.state.telegram_auth_repo
        auth = await telegram_auth_repo.get()
        if not auth or not auth.session_name:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Сессия Telegram не настроена")
                ).model_dump(),
            )

        session_name_str = auth.session_name.value if hasattr(auth.session_name, 'value') else str(auth.session_name)
        session_file = os.path.join(DEFAULT_SESSION_PATH, session_name_str)

        client = TelegramClient(session_file, auth.api_id.value if auth.api_id else 0, auth.api_hash.value if auth.api_hash else "")
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Сессия не авторизована")
                ).model_dump(),
            )

        user_identifier = request_data.user_identifier.strip()

        pool = request.app.state.db_pool
        sync_service = ChatSyncService(pool)

        try:
            user_id = int(user_identifier)
            user_info = await sync_service.get_chat_info(client, user_id)
        except ValueError:
            user_info = await sync_service.get_user_info_by_username(client, user_identifier)

        if not user_info:
            await client.disconnect()
            ec = APP_ERROR_CODES["APP-103"]
            raise HTTPException(
                status_code=ec.http_status,
                detail=ErrorResponse(
                    error=ErrorDetail(code=ec.code, message="User not found")
                ).model_dump(),
            )

        chat_id = user_info["chat_id"]

        app_state = AppStateStore.get_app().state if AppStateStore.is_initialized() else None
        if not app_state or not app_state.db_pool:
            await client.disconnect()
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
                title=user_info["title"],
                is_monitored=False,
                summary_enabled=False,
                custom_prompt=None,
            )

        if not setting:
            await client.disconnect()
            ec = APP_ERROR_CODES["APP-101"]
            raise HTTPException(
                status_code=ec.http_status,
                detail=ErrorResponse(
                    error=ErrorDetail(code=ec.code, message="Failed to disable user monitoring")
                ).model_dump(),
            )

        await client.disconnect()

        try:
            if app_state and hasattr(app_state, 'ingester') and app_state.ingester:
                await app_state.ingester.reload_monitored_chats()
                logger.info("Ingester уведомлён об обновлении monitored чатов")
        except Exception as e:
            logger.warning("Не удалось уведомить Ingester: %s", e)

        logger.info("Пользователь %s (%s) отключён от мониторинга", chat_id, user_info.get('username', 'N/A'))

        return RemoveUserResponse(
            chat_id=chat_id,
            title=user_info["title"],
            username=user_info.get("username"),
            is_monitored=False,
            message=f"Пользователь {user_info['title']} отключён от мониторинга",
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Ошибка отключения пользователя")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )
