"""
QR Auth API endpoints.

API для QR код авторизации Telegram.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional, Callable, Awaitable

if TYPE_CHECKING:
    from src.protocols import IApplicationState

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.api.models import ErrorDetail, ErrorResponse

from ..auth import QRAuthService, DEFAULT_SESSION_PATH
from ..settings.repositories.telegram_auth import TelegramAuthRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings/Telegram QR Auth"])

_active_services: dict[str, QRAuthService] = {}

_qr_auth_complete_callback: Optional[Callable[[str, Optional["IApplicationState"]], Awaitable[None]]] = None

_logout_complete_callback: Optional[Callable[[str, Optional["IApplicationState"]], Awaitable[None]]] = None


def set_qr_auth_complete_callback(
    callback: Callable[[str, Optional["IApplicationState"]], Awaitable[None]],
) -> None:
    """Установить callback для уведомления о завершении QR авторизации."""
    global _qr_auth_complete_callback
    _qr_auth_complete_callback = callback
    logger.info("QR Auth callback установлен")


def set_logout_complete_callback(
    callback: Callable[[str, Optional["IApplicationState"]], Awaitable[None]],
) -> None:
    """Установить callback для уведомления о завершении logout."""
    global _logout_complete_callback
    _logout_complete_callback = callback
    logger.info("Logout callback установлен")


async def _on_qr_auth_complete(
    session_name: str,
    state: Optional["IApplicationState"] = None,
) -> None:
    """Callback вызываемый после успешной QR авторизации."""
    try:
        if state is not None:
            repo = getattr(state, "telegram_auth_repo", None)
            if repo is not None:
                await repo.upsert(session_name=session_name)

        if _qr_auth_complete_callback:
            try:
                await _qr_auth_complete_callback(session_name, state)
            except Exception as exc:
                logger.error("Ошибка callback on_qr_auth_complete: %s", exc)

    except Exception as exc:
        logger.error("Ошибка сохранения session_name в БД: %s", exc)


class CreateQRResponse(BaseModel):
    """Ответ с данными QR кода."""
    session_id: str
    session_name: str
    qr_code_data: str
    expires_in: int


class QRStatusResponse(BaseModel):
    """Ответ со статусом QR авторизации."""
    exists: bool
    is_completed: bool = False
    is_expired: bool = False
    user_id: Optional[int] = None
    user_username: Optional[str] = None
    error: Optional[str] = None
    saved_to_db: bool = False
    reconnect_attempted: bool = False


class AuthStatusResponse(BaseModel):
    """Ответ со статусом авторизации Telegram."""
    is_authenticated: bool
    is_session_active: bool
    can_authorize: bool
    error: Optional[str] = None


@router.get("/telegram/auth-status", response_model=AuthStatusResponse)
async def get_auth_status(request: Request) -> AuthStatusResponse:
    """Проверить статус авторизации Telegram."""
    try:
        telegram_auth_repo: TelegramAuthRepository = request.app.state.telegram_auth_repo
        auth = await telegram_auth_repo.get()

        if not auth or not auth.session_name:
            return AuthStatusResponse(
                is_authenticated=False,
                is_session_active=False,
                can_authorize=True,
                error=None,
            )

        is_active = await telegram_auth_repo.is_session_active()

        return AuthStatusResponse(
            is_authenticated=True,
            is_session_active=is_active,
            can_authorize=not is_active,
            error=None,
        )

    except Exception as exc:
        logger.error("Ошибка проверки статуса авторизации: %s", exc, exc_info=True)
        return AuthStatusResponse(
            is_authenticated=False,
            is_session_active=False,
            can_authorize=True,
            error="Внутренняя ошибка сервера",
        )


@router.post("/telegram/logout")
async def logout(request: Request) -> dict[str, str]:
    """Выйти из текущей сессии Telegram."""
    try:
        telegram_auth_repo: TelegramAuthRepository = request.app.state.telegram_auth_repo
        auth = await telegram_auth_repo.get()
        session_name = auth.session_name.value if auth and auth.session_name else "tg_scraper_session"

        success = await telegram_auth_repo.clear_session()

        if success:
            logger.info("Logout выполнен успешно")

            if _logout_complete_callback:
                try:
                    state = request.app.state
                    asyncio.ensure_future(
                        _logout_complete_callback(session_name, state),
                    )
                    logger.info("Ingester уведомлён о logout, сессия: %s", session_name)
                except Exception as exc:
                    logger.error("Ошибка вызова logout callback: %s", exc)

            return {"success": "true", "message": "Сессия сброшена"}

        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Не удалось сбросить сессию")
            ).model_dump(),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Ошибка logout: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Внутренняя ошибка сервера")
            ).model_dump(),
        )


@router.post("/telegram/qr-code", response_model=CreateQRResponse)
async def create_qr_code(request: Request) -> CreateQRResponse:
    """Создать новую сессию QR авторизации."""
    state = request.app.state
    telegram_auth_repo: TelegramAuthRepository = state.telegram_auth_repo

    is_active = await telegram_auth_repo.is_session_active()

    if is_active:
        raise HTTPException(
            status_code=409,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-105", message="Уже есть активная сессия. Сначала выполните logout.")
            ).model_dump(),
        )

    auth = await telegram_auth_repo.get()

    if not auth or not auth.api_id or not auth.api_hash:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-102", message="Telegram credentials not configured")
            ).model_dump(),
        )

    import uuid
    session_name = f"qr_auth_{uuid.uuid4().hex}"

    service = QRAuthService(
        api_id=auth.api_id.value if auth.api_id else 0,
        api_hash=auth.api_hash.value if auth.api_hash else "",
        session_path=DEFAULT_SESSION_PATH,
        on_auth_complete=_on_qr_auth_complete,
        state=state,
        telegram_auth_repo=telegram_auth_repo,
    )

    try:
        qr_session = await service.create_session()

        _active_services[qr_session.session_id] = service

        logger.info("Создана QR сессия: %s, файл: %s", qr_session.session_id, session_name)

        return CreateQRResponse(
            session_id=qr_session.session_id,
            session_name=qr_session.session_name,
            qr_code_data=qr_session.qr_code_data,
            expires_in=300,
        )

    except Exception as exc:
        logger.error("Ошибка создания QR сессии: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Внутренняя ошибка сервера")
            ).model_dump(),
        )


@router.get("/telegram/qr-status/{session_id}", response_model=QRStatusResponse)
async def get_qr_status(session_id: str) -> QRStatusResponse:
    """Проверить статус QR авторизации."""
    if session_id not in _active_services:
        return QRStatusResponse(
            exists=False,
            error="Сессия не найдена",
        )

    service = _active_services[session_id]
    status = await service.check_session_status(session_id)

    return QRStatusResponse(**status)


@router.post("/telegram/qr-cancel/{session_id}")
async def cancel_qr_auth(session_id: str) -> dict[str, bool]:
    """Отменить сессию QR авторизации."""
    if session_id not in _active_services:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Сессия не найдена")
            ).model_dump(),
        )

    service = _active_services[session_id]
    success = await service.cancel_session(session_id)

    if success:
        del _active_services[session_id]

    return {"success": success}
